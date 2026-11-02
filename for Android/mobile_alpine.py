"""Alpine packages for the optional toolchain, checked the way apk checks them.

The catalog names packages, not versions: an Alpine stable branch keeps only the latest build of
each package, so a pinned version stops downloading within weeks (python3 3.12.15 did in two). The
installer reads the branch's current APKINDEX, checks its RSA signature with the keys of the pinned
minirootfs, resolves what the named packages need beyond what the rootfs already has, and accepts a
package only when its control segment matches the index checksum and its data segment matches the
datahash in that control segment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import re
import tarfile
import zlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

_MAX_INDEX_BYTES = 32 * 1024 * 1024
# DER DigestInfo prefixes of PKCS #1 v1.5 signatures (RFC 8017, section 9.2).
_DIGEST_INFO = {
    "sha1": bytes.fromhex("3021300906052b0e03021a05000414"),
    "sha256": bytes.fromhex("3031300d060960864801650304020105000420"),
}
_RSA_ENCRYPTION = bytes.fromhex("2a864886f70d010101")


class AlpineError(ValueError):
    pass


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    repository: str
    size: int
    checksum: str
    license: str = ""
    url: str = ""
    depends: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    priority: int = 0


@dataclass
class Index:
    packages: dict[str, Package] = field(default_factory=dict)
    providers: dict[str, list[Package]] = field(default_factory=dict)

    def add(self, package: Package) -> None:
        # The first repository listed wins, as in apk (main before community).
        if package.name in self.packages:
            return
        self.packages[package.name] = package
        for name in (package.name, *(_atom_name(item) for item in package.provides)):
            self.providers.setdefault(name, []).append(package)


def _der(data: bytes, offset: int) -> tuple[int, bytes, int]:
    """One DER element at offset: its tag, contents and the offset after it."""
    if offset + 2 > len(data):
        raise AlpineError("The signing key is truncated")
    tag, length = data[offset], data[offset + 1]
    offset += 2
    if length & 0x80:
        count = length & 0x7F
        if not 1 <= count <= 4 or offset + count > len(data):
            raise AlpineError("The signing key has an invalid length")
        length = int.from_bytes(data[offset : offset + count], "big")
        offset += count
    if offset + length > len(data):
        raise AlpineError("The signing key is truncated")
    return tag, data[offset : offset + length], offset + length


def rsa_public_key(pem: bytes) -> tuple[int, int]:
    """The modulus and exponent of a PEM SubjectPublicKeyInfo RSA key (Alpine's *.rsa.pub)."""
    text = pem.decode("ascii", "strict")
    match = re.search(r"-----BEGIN PUBLIC KEY-----(.*?)-----END PUBLIC KEY-----", text, re.S)
    if not match:
        raise AlpineError("The signing key is not a PEM public key")
    der = base64.b64decode("".join(match.group(1).split()), validate=True)
    tag, info, _ = _der(der, 0)
    if tag != 0x30:
        raise AlpineError("The signing key is not a public key")
    tag, algorithm, offset = _der(info, 0)
    _, oid, _ = _der(algorithm, 0)
    if tag != 0x30 or oid != _RSA_ENCRYPTION:
        raise AlpineError("The signing key is not an RSA key")
    tag, bits, _ = _der(info, offset)
    if tag != 0x03 or not bits or bits[0] != 0:
        raise AlpineError("The signing key is malformed")
    tag, numbers, _ = _der(bits[1:], 0)
    tag_n, modulus, offset = _der(numbers, 0)
    tag_e, exponent, _ = _der(numbers, offset)
    if tag != 0x30 or tag_n != 0x02 or tag_e != 0x02:
        raise AlpineError("The signing key is malformed")
    n, e = int.from_bytes(modulus, "big"), int.from_bytes(exponent, "big")
    if n.bit_length() < 2048 or e < 3 or e % 2 == 0:
        raise AlpineError("The signing key is too weak")
    return n, e


def rsa_verify(key: tuple[int, int], signature: bytes, digest: bytes, algorithm: str) -> bool:
    """PKCS #1 v1.5 signature verification (only public operations; nothing secret here)."""
    n, e = key
    size = (n.bit_length() + 7) // 8
    if len(signature) != size or int.from_bytes(signature, "big") >= n:
        return False
    prefix = _DIGEST_INFO[algorithm] + digest
    if size < len(prefix) + 11:
        return False
    expected = b"\x00\x01" + b"\xff" * (size - len(prefix) - 3) + b"\x00" + prefix
    actual = pow(int.from_bytes(signature, "big"), e, n).to_bytes(size, "big")
    return hmac.compare_digest(actual, expected)


def segment_bounds(path: Path, limit: int = 4) -> list[tuple[int, int]]:
    """Byte ranges of the gzip members an APK or APKINDEX is made of, read without holding it."""
    bounds: list[tuple[int, int]] = []
    with path.open("rb") as stream:
        start, pending = 0, b""
        while True:
            if not pending:
                pending = stream.read(1 << 16)
                if not pending:
                    return bounds
            if len(bounds) == limit:
                raise AlpineError("The package has more parts than an Alpine package")
            inflater = zlib.decompressobj(31)
            position = start
            while not inflater.eof:
                if not pending:
                    pending = stream.read(1 << 16)
                    if not pending:
                        raise AlpineError("The package is cut short")
                offered = len(pending)
                try:
                    inflater.decompress(pending, 1 << 20)
                except zlib.error as error:
                    raise AlpineError("The package is not a gzip stream") from error
                pending = inflater.unused_data if inflater.eof else inflater.unconsumed_tail
                position += offered - len(pending)
            bounds.append((start, position))
            start = position


def _read_range(path: Path, start: int, end: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(start)
        return stream.read(end - start)


def _hash_range(path: Path, start: int, end: int, algorithm: str) -> bytes:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = end - start
        while remaining:
            chunk = stream.read(min(remaining, 1 << 20))
            if not chunk:
                raise AlpineError("The package is cut short")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.digest()


def _tar_members(segment: bytes, limit: int) -> dict[str, bytes]:
    try:
        raw = zlib.decompressobj(31).decompress(segment, limit + 1)
    except zlib.error as error:
        raise AlpineError("A package part is not a gzip stream") from error
    if len(raw) > limit:
        raise AlpineError("A package part is larger than expected")
    members = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:", ignore_zeros=True) as archive:
        for member in archive:
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is not None:
                    members[member.name] = stream.read()
    return members


def rootfs_trust(archive_path: Path) -> tuple[dict[str, bytes], str]:
    """The signing keys (etc/apk/keys) and package database of a minirootfs tarball."""
    keys: dict[str, bytes] = {}
    database = ""
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if not member.isfile() or member.size > 4 * 1024 * 1024:
                continue
            if name.startswith("etc/apk/keys/") and name.count("/") == 3:
                stream = archive.extractfile(member)
                if stream is not None:
                    keys[name.rsplit("/", 1)[-1]] = stream.read()
            elif name == "lib/apk/db/installed":
                stream = archive.extractfile(member)
                if stream is not None:
                    database = stream.read().decode("utf-8", "replace")
    if not keys or not database:
        raise AlpineError("The rootfs holds no Alpine signing keys or package database")
    return keys, database


def verify_index(path: Path, keys: dict[str, bytes]) -> str:
    """The APKINDEX text of a signed APKINDEX.tar.gz, or AlpineError."""
    if path.stat().st_size > _MAX_INDEX_BYTES:
        raise AlpineError("The package index is larger than expected")
    bounds = segment_bounds(path)
    if len(bounds) != 2:
        raise AlpineError("The package index is not signed")
    signatures = _tar_members(_read_range(path, *bounds[0]), 64 * 1024)
    signed = _read_range(path, *bounds[1])
    for name, signature in signatures.items():
        for marker, algorithm in ((".SIGN.RSA256.", "sha256"), (".SIGN.RSA.", "sha1")):
            if not name.startswith(marker):
                continue
            key = keys.get(name[len(marker) :])
            if key is None:
                continue
            digest = hashlib.new(algorithm, signed).digest()
            if rsa_verify(rsa_public_key(key), signature, digest, algorithm):
                text = _tar_members(signed, _MAX_INDEX_BYTES * 8).get("APKINDEX")
                if text is None:
                    raise AlpineError("The signed package index holds no APKINDEX")
                return text.decode("utf-8")
            raise AlpineError("The package index signature does not match its key")
    raise AlpineError("The package index is not signed with a key of this rootfs")


def _atom_name(atom: str) -> str:
    return re.split(r"[<>=~]", atom.removeprefix("!"), maxsplit=1)[0]


def _records(text: str) -> Iterable[dict[str, str]]:
    for block in text.split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if len(line) > 2 and line[1] == ":":
                fields[line[0]] = line[2:]
        if "P" in fields and "V" in fields:
            yield fields


def parse_index(text: str, repository: str, index: Index | None = None) -> Index:
    index = index if index is not None else Index()
    for fields in _records(text):
        index.add(
            Package(
                name=fields["P"],
                version=fields["V"],
                repository=repository,
                size=int(fields.get("S", "0")),
                checksum=fields.get("C", ""),
                license=fields.get("L", ""),
                url=fields.get("U", ""),
                depends=tuple(fields.get("D", "").split()),
                provides=tuple(fields.get("p", "").split()),
                priority=int(fields.get("k", "0") or 0),
            )
        )
    return index


def installed_provides(database: str) -> set[str]:
    """What the packages recorded in a rootfs's lib/apk/db/installed provide (names included)."""
    provided = set()
    for fields in _records(database):
        provided.add(fields["P"])
        provided.update(_atom_name(item) for item in fields.get("p", "").split())
    return provided


def resolve(index: Index, wanted: Iterable[str], present: set[str]) -> list[Package]:
    """The named packages, and what they depend on that `present` does not provide.

    A named package is taken from the index even when the rootfs has it: that is how the rootfs's
    own musl, busybox and OpenSSL get the branch's security updates.
    """
    chosen: dict[str, Package] = {}
    named = list(wanted)
    queue = list(named)
    satisfied = set(present) - {_atom_name(atom) for atom in named}
    while queue:
        atom = queue.pop(0)
        if atom.startswith("!"):
            continue
        name = _atom_name(atom)
        if name in satisfied:
            continue
        candidates = index.providers.get(name, [])
        exact = index.packages.get(name)
        package = exact or max(candidates, key=lambda item: (item.priority, item.name), default=None)
        if package is None:
            raise AlpineError(f"Alpine has no package that provides {name}")
        satisfied.add(name)
        if package.name in chosen:
            continue
        chosen[package.name] = package
        satisfied.add(package.name)
        satisfied.update(_atom_name(item) for item in package.provides)
        queue.extend(package.depends)
    return list(chosen.values())


def verify_package(path: Path, package: Package) -> None:
    """AlpineError unless the downloaded file is exactly the indexed package."""
    if path.stat().st_size != package.size:
        raise AlpineError(f"{package.name} does not have its indexed size")
    bounds = segment_bounds(path)
    if len(bounds) != 3:
        raise AlpineError(f"{package.name} is not a signed Alpine package")
    if not package.checksum.startswith("Q1"):
        raise AlpineError(f"The index gives {package.name} no SHA-1 checksum")
    control_digest = _hash_range(path, *bounds[1], "sha1")
    if not hmac.compare_digest(base64.b64encode(control_digest).decode(), package.checksum[2:]):
        raise AlpineError(f"{package.name} does not match its index checksum")
    info = _tar_members(_read_range(path, *bounds[1]), 4 * 1024 * 1024).get(".PKGINFO", b"")
    fields = dict(
        line.split(" = ", 1) for line in info.decode("utf-8", "replace").splitlines() if " = " in line
    )
    if fields.get("pkgname") != package.name or fields.get("pkgver") != package.version:
        raise AlpineError(f"{package.name} names another package inside")
    datahash = fields.get("datahash", "")
    if not re.fullmatch(r"[0-9a-f]{64}", datahash):
        raise AlpineError(f"{package.name} has no data hash")
    if not hmac.compare_digest(_hash_range(path, bounds[2][0], bounds[2][1], "sha256").hex(), datahash):
        raise AlpineError(f"{package.name} does not match its data hash")


def package_url(mirror: str, branch: str, architecture: str, package: Package) -> str:
    return f"{mirror.rstrip('/')}/{branch}/{package.repository}/{architecture}/{package.name}-{package.version}.apk"


def index_url(mirror: str, branch: str, repository: str, architecture: str) -> str:
    return f"{mirror.rstrip('/')}/{branch}/{repository}/{architecture}/APKINDEX.tar.gz"
