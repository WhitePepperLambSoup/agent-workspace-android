"""Authenticated remote Serve hosts. Tokens remain in the platform credential store.

A desktop running Agent Workspace (Settings → Phone connection) is paired in one of three ways:
its pairing link (the QR code it shows, agentworkspace://pair?...), its address and one-time
pairing code, or an address and a token created on the desktop. In HTTPS mode the desktop has a
self-signed certificate; the phone pins it by the SHA-256 fingerprint in the pairing link and
afterwards trusts that certificate alone (docs/DEVICE_LINK_API.md in the monorepo).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import re
import socket
import sqlite3
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit
from uuid import uuid4

import httpx

_PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)
# Where a desktop can be paired from a link or a code: its LAN, Tailscale (100.64/10 and
# fd7a:115c:a1e0::/48 inside fc00::/7) or this phone (adb reverse).
_LINKABLE_NETWORKS = (*_PRIVATE_NETWORKS, ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("169.254.0.0/16"))
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_LINK = re.compile(r"agentworkspace://pair\?[^\s<>\"']+", re.IGNORECASE)
_CODE_CHARACTERS = re.compile(r"[A-Z0-9]{8}")


class RemoteHTTPError(ValueError):
    def __init__(self, status_code: int, code: str | None = None):
        self.status_code = status_code
        self.code = code
        super().__init__(f"remote host returned HTTP {status_code}" + (f" ({code})" if code else ""))


def unavailable_reason(error: BaseException) -> str:
    """Why a paired device could not be reached, for the person looking at the phone."""
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, ssl.SSLCertVerificationError):
            # Pinned hosts trust only the certificate from pairing (pinned_context).
            return (
                "the computer's certificate is not the one from pairing; if the computer made a "
                "new certificate, remove it here and pair again"
            )
        cause = cause.__cause__ or cause.__context__
    return "remote host is unavailable"


def connection_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def endpoint_url(value: object, *, allow_lan: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError("invalid endpoint URL")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("endpoint requires HTTP or HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint cannot contain credentials, query or fragment")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("invalid endpoint port") from None
    if port is not None and port < 1:
        raise ValueError("invalid endpoint port")
    if parsed.scheme == "http":
        address = _address(parsed.hostname)
        private = address is not None and any(address in network for network in _PRIVATE_NETWORKS)
        loopback = parsed.hostname == "localhost" or bool(address and address.is_loopback)
        if not loopback and not (allow_lan and private):
            raise ValueError("HTTP requires an explicitly enabled private LAN IP; use HTTPS")
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


def _address(host: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address((host or "").split("%", 1)[0])
    except ValueError:
        return None


def _linkable(url: str) -> bool:
    """A desktop on this network, Tailscale or this phone: never the internet."""
    host = urlsplit(url).hostname
    address = _address(host)
    if address is None:
        return host == "localhost"
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback or address.is_link_local or any(address in network for network in _LINKABLE_NETWORKS)


def fingerprint_value(value: object) -> str | None:
    """A certificate fingerprint as the desktop shows it (sha256:<hex>, hex, or hex with colons)."""
    if value in (None, ""):
        return None
    text = str(value).strip().lower().removeprefix("sha256:").replace(":", "").replace(" ", "")
    if not _FINGERPRINT.fullmatch(text):
        raise ValueError("the certificate fingerprint must be 64 hexadecimal characters")
    return text


def pairing_code(value: object) -> str:
    """The desktop's one-time code (XXXX-XXXX), as typed: case, spaces and the dash do not matter."""
    text = "".join(str(value or "").upper().split()).replace("-", "")
    if not _CODE_CHARACTERS.fullmatch(text):
        raise ValueError("the pairing code has 8 letters and digits, such as ABCD-EFGH")
    return f"{text[:4]}-{text[4:]}"


def pairing_link(value: object) -> dict[str, str | None]:
    """The parts of a desktop's pairing link (its QR code), found in pasted text too:
    agentworkspace://pair?v=1&name=<desktop>&url=<address>&code=<XXXX-XXXX>[&fp=sha256:<hex>]."""
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("this is not a pairing link")
    found = _LINK.search(value)
    if found is None:
        raise ValueError("this is not a pairing link")
    parsed = urlsplit(found.group(0))
    query = {key: values[0] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
    if query.get("v") != "1":
        raise ValueError("this pairing link is from a newer version of the desktop app; update this app")
    name = " ".join(str(query.get("name") or "").split())[:100] or "Agent Workspace"
    return {"name": name, **pairing_target(query.get("url"), query.get("code"), query.get("fp"))}


def pairing_target(url: object, code: object, fingerprint: object = None) -> dict[str, str | None]:
    """A checked address, code and certificate fingerprint to pair with."""
    address = endpoint_url(url, allow_lan=True)
    if not _linkable(address):
        raise ValueError("pairing works with a computer on this network or on Tailscale")
    pinned = fingerprint_value(fingerprint)
    scheme = urlsplit(address).scheme
    if scheme == "https" and pinned is None:
        raise ValueError("an HTTPS address needs the certificate fingerprint the computer shows")
    if scheme == "http" and pinned is not None:
        raise ValueError("a certificate fingerprint goes with an HTTPS address")
    return {"url": address, "code": pairing_code(code), "fingerprint": pinned}


def pinned_context(certificate_pem: str) -> ssl.SSLContext:
    """TLS that trusts this one certificate and nothing else; its name does not matter."""
    context = ssl.create_default_context(cadata=certificate_pem)
    context.check_hostname = False
    return context


def fetch_certificate(url: str, fingerprint: str, *, timeout: float = 10.0) -> str:
    """The desktop's certificate (PEM), after checking it has the fingerprint from the pairing link."""
    parsed = urlsplit(url)
    host, port = parsed.hostname or "", parsed.port or 443
    probe = ssl.create_default_context()
    probe.check_hostname = False
    probe.verify_mode = ssl.CERT_NONE  # the fingerprint is checked below, before anything is sent
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw, probe.wrap_socket(raw) as tls:
            certificate = tls.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError):
        raise ValueError("could not reach the computer; check that both are on the same network or Tailscale") from None
    if not certificate or not hmac.compare_digest(hashlib.sha256(certificate).hexdigest(), fingerprint):
        raise ValueError("the computer's certificate does not match its pairing link; do not pair with it")
    return ssl.DER_cert_to_PEM_cert(certificate)


def _remote_error(document: bytes) -> str | None:
    try:
        error = json.loads(document).get("error")
    except (ValueError, AttributeError):
        return None
    return error if isinstance(error, str) and len(error) <= 80 else None


class MobileConnections:
    def __init__(self, path: Path, *, credentials: Any = None, transport: Any = None):
        self.path = path
        self.credentials = credentials
        self.transport = transport
        with connection_database(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS mobile_hosts "
                "(host_id TEXT PRIMARY KEY, url TEXT UNIQUE NOT NULL, name TEXT NOT NULL, "
                "api TEXT NOT NULL, paired_at REAL NOT NULL)"
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(mobile_hosts)")}
            # The pinned certificate of a desktop paired over HTTPS; older databases lack it.
            if "fingerprint" not in columns:
                db.execute("ALTER TABLE mobile_hosts ADD COLUMN fingerprint TEXT")
            if "certificate" not in columns:
                db.execute("ALTER TABLE mobile_hosts ADD COLUMN certificate TEXT")

    def _credentials(self):
        if self.credentials is None:
            from agent_workspace.credentials import default_credential_store

            self.credentials = default_credential_store()
        return self.credentials

    @staticmethod
    def _key(host_id: str):
        return f"agent-mobile-host:{host_id}"

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        document = dict(row)
        document.pop("certificate", None)
        return document

    def list(self) -> list[dict[str, Any]]:
        with connection_database(self.path) as db:
            return [
                self._public(row) for row in db.execute("SELECT * FROM mobile_hosts ORDER BY name, host_id")
            ]

    def _row(self, host_id: str) -> sqlite3.Row:
        with connection_database(self.path) as db:
            row = db.execute("SELECT * FROM mobile_hosts WHERE host_id=?", (host_id,)).fetchone()
        if row is None:
            raise KeyError("unknown paired host")
        return row

    def get(self, host_id: str) -> dict[str, Any]:
        return self._public(self._row(host_id))

    def _client(self, timeout: float, certificate: str | None) -> httpx.AsyncClient:
        verify: Any = pinned_context(certificate) if certificate else True
        return httpx.AsyncClient(
            transport=self.transport, timeout=timeout, follow_redirects=False, trust_env=False, verify=verify
        )

    async def _request(
        self,
        url: str,
        token: str | None,
        method: str,
        path: str,
        payload=None,
        *,
        timeout=15,
        allow_not_found=False,
        certificate: str | None = None,
    ):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with (
            self._client(timeout, certificate) as client,
            client.stream(method, url + path, headers=headers, json=payload) as response,
        ):
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError("remote response exceeds 4 MiB")
            if response.status_code == 404 and allow_not_found:
                return response.status_code, {}
            if response.status_code < 200 or response.status_code >= 300:
                raise RemoteHTTPError(response.status_code, _remote_error(bytes(body)))
            try:
                data = json.loads(body)
            except (ValueError, UnicodeError):
                raise ValueError("remote host returned invalid JSON") from None
            if not isinstance(data, dict):
                raise ValueError("remote host returned an invalid document")
            return response.status_code, data

    async def _pinned(self, url: str, fingerprint: str | None) -> str | None:
        """The pinned certificate for an HTTPS address with a fingerprint, else None."""
        if fingerprint is None or urlsplit(url).scheme != "https":
            return None
        return await asyncio.to_thread(fetch_certificate, url, fingerprint)

    async def _store(
        self, name: str, url: str, token: str, *, fingerprint: str | None, certificate: str | None
    ) -> dict[str, Any]:
        """Check the token works, then keep the host (the token goes to the credential store)."""
        try:
            _, sessions = await self._request(url, token, "GET", "/sessions", certificate=certificate)
            if not isinstance(sessions.get("sessions"), list):
                raise ValueError("host does not expose the Agent Serve API")
            code, runtime = await self._request(
                url, token, "GET", "/mobile/runtime", allow_not_found=True, certificate=certificate
            )
        except httpx.HTTPError:
            raise ValueError("could not authenticate or connect to the remote host") from None
        api = "mobile" if code == 200 and runtime.get("idempotent_submissions") is True else "serve"
        existing = next((host for host in self.list() if host["url"] == url), None)
        host_id = existing["host_id"] if existing else str(uuid4())
        self._credentials().set(self._key(host_id), token)
        with connection_database(self.path) as db:
            db.execute(
                "INSERT INTO mobile_hosts (host_id, url, name, api, paired_at, fingerprint, certificate) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET name=excluded.name, api=excluded.api, "
                "fingerprint=excluded.fingerprint, certificate=excluded.certificate",
                (host_id, url, name.strip(), api, time.time(), fingerprint, certificate),
            )
        return self.get(host_id)

    async def pair(self, payload: dict[str, Any]) -> dict[str, Any]:
        """An address and a token created on the host (any Serve API; HTTPS can be pinned)."""
        name, token = payload.get("name"), payload.get("token")
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("host name is required (max 100 characters)")
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 8192
            or any(ord(c) < 33 for c in token)
        ):
            raise ValueError("a valid host bearer token is required")
        url = endpoint_url(payload.get("url"), allow_lan=payload.get("allow_lan") is True)
        fingerprint = fingerprint_value(payload.get("fingerprint"))
        if fingerprint is not None and urlsplit(url).scheme != "https":
            raise ValueError("a certificate fingerprint goes with an HTTPS address")
        certificate = await self._pinned(url, fingerprint)
        return await self._store(name, url, token, fingerprint=fingerprint, certificate=certificate)

    async def pair_with_code(self, payload: dict[str, Any]) -> dict[str, Any]:
        """A desktop's pairing link, or its address and one-time code: the desktop gives this
        phone its own token (POST /pair) and the phone keeps it like a manually entered one."""
        if payload.get("link"):
            target = pairing_link(payload.get("link"))
        else:
            target = pairing_target(payload.get("url"), payload.get("code"), payload.get("fingerprint"))
        device_name = " ".join(str(payload.get("device_name") or "").split())[:60] or "Android"
        url, fingerprint = str(target["url"]), target["fingerprint"]
        certificate = await self._pinned(url, fingerprint)
        try:
            _, paired = await self._request(
                url, None, "POST", "/pair", {"code": target["code"], "name": device_name}, certificate=certificate
            )
        except RemoteHTTPError as error:
            if error.code == "pairing_code_invalid":
                raise ValueError("the pairing code is wrong; check it, or show a new one on the computer") from None
            if error.code == "pairing_unavailable":
                raise ValueError("the computer is not waiting for a phone; show the pairing QR code on it again") from None
            if error.code == "too_many_attempts":
                raise ValueError("too many attempts; wait a minute and show a new pairing code on the computer") from None
            raise
        except httpx.HTTPError:
            raise ValueError("could not reach the computer; check that both are on the same network or Tailscale") from None
        token = paired.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("the computer did not return a token")
        name = str(paired.get("name") or target.get("name") or "Agent Workspace")[:100]
        host = await self._store(name, url, token, fingerprint=fingerprint, certificate=certificate)
        return {**host, "scopes": [scope for scope in paired.get("scopes") or [] if isinstance(scope, str)]}

    def remove(self, host_id: str) -> bool:
        self.get(host_id)
        self._credentials().delete(self._key(host_id))
        with connection_database(self.path) as db:
            return db.execute("DELETE FROM mobile_hosts WHERE host_id=?", (host_id,)).rowcount == 1

    async def request(self, host_id: str, method: str, path: str, payload=None, *, timeout=15):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("invalid remote route")
        host = self._row(host_id)
        token = self._credentials().get(self._key(host_id))
        if not token:
            raise ValueError("host credential is unavailable; pair the host again")
        return await self._request(
            host["url"], token, method, path, payload, timeout=timeout, certificate=host["certificate"]
        )

    async def sessions(self, host_id: str):
        _, document = await self.request(host_id, "GET", "/sessions")
        return document

    async def events(self, host_id: str, session_id: str):
        _, document = await self.request(
            host_id, "GET", f"/sessions/{quote(session_id, safe='')}/events"
        )
        return document
