"""Phones paired with this desktop: a small authenticated endpoint inside the desktop sidecar.

The Android app's device connections speak this protocol. A phone lists this desktop's sessions,
reads a session's messages, and hands tasks over with an idempotent request id; the tasks run in
the desktop's own runtime, so they show in its window and its approvals are given there.

Each phone gets its own token. Only the token's SHA-256 is stored, and a phone can be revoked on
its own. The endpoint answers only peers on private networks (LAN, Tailscale, link-local) and
Host headers that name this machine, and it can serve HTTPS with a self-signed certificate whose
fingerprint a phone pins when it pairs.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import sqlite3
import ssl
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import closing, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, unquote, urlencode, urlsplit
from uuid import uuid4

SCOPES = ("read", "tasks")
DEFAULT_PORT = 8765
_MAX_BODY_BYTES = 512 * 1024
_MAX_DEVICES = 32
_MAX_NAME_CHARS = 100
_MAX_REQUEST_ID_CHARS = 128
_PAIRING_SECONDS = 300
_PAIRING_ATTEMPTS = 5
_AUTH_FAILURE_LIMIT = 10
_AUTH_WINDOW_SECONDS = 60.0
_HANDSHAKE_TIMEOUT_SECONDS = 10.0
_ADDRESS_CACHE_SECONDS = 30.0
# Without look-alike letters and digits (0/O, 1/I/L), so a code read aloud is typed right.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
_ALLOWED_PEERS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


class DeviceLinkError(Exception):
    """A request the endpoint refuses: a stable code and its HTTP status."""

    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def _now() -> str:
    return datetime.now(UTC).isoformat()


def peer_allowed(address: str) -> bool:
    """Only peers on this machine, a private LAN, Tailscale or a link-local network."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip.version == network.version and ip in network for network in _ALLOWED_PEERS)


@dataclass(frozen=True, slots=True)
class LocalAddress:
    address: str
    kind: str  # "lan" or "tailscale"


def local_addresses() -> list[LocalAddress]:
    """This machine's IPv4 addresses a phone can reach: private LAN and Tailscale ones."""
    found: set[str] = set()
    with suppress(OSError):
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(str(info[4][0]))
    # The address of the default route; connecting a UDP socket sends nothing.
    with suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("10.255.255.255", 1))
        found.add(str(probe.getsockname()[0]))
    result: list[LocalAddress] = []
    for address in sorted(found):
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if ip in _TAILSCALE:
            result.append(LocalAddress(address, "tailscale"))
        elif ip.is_private and not ip.is_loopback and not ip.is_link_local:
            result.append(LocalAddress(address, "lan"))
    return sorted(result, key=lambda item: (item.kind != "lan", item.address))


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _clean_name(value: object) -> str:
    if not isinstance(value, str):
        raise DeviceLinkError("invalid_name")
    name = " ".join(value.split())
    if not name or len(name) > _MAX_NAME_CHARS or any(ord(c) < 32 for c in name):
        raise DeviceLinkError("invalid_name")
    return name


def clean_scopes(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, list | tuple)
        or not value
        or not all(isinstance(item, str) for item in value)
    ):
        raise DeviceLinkError("invalid_scopes")
    scopes = tuple(scope for scope in SCOPES if scope in value)
    if len(scopes) != len(set(value)):
        raise DeviceLinkError("invalid_scopes")
    if "read" not in scopes:
        # Pairing itself lists the desktop's sessions.
        raise DeviceLinkError("invalid_scopes")
    return scopes


@dataclass(frozen=True, slots=True)
class PairedDevice:
    device_id: str
    name: str
    scopes: tuple[str, ...]
    created_at: str
    last_seen_at: str | None = None
    last_address: str | None = None

    def document(self) -> dict[str, object]:
        return {
            "deviceId": self.device_id,
            "name": self.name,
            "scopes": list(self.scopes),
            "createdAt": self.created_at,
            "lastSeenAt": self.last_seen_at,
            "lastAddress": self.last_address,
        }


@dataclass(slots=True)
class _PairingCode:
    code: str
    scopes: tuple[str, ...]
    expires_at: float
    attempts: int = 0


class DeviceRegistry:
    """Paired phones in ``devices.json``; tokens are kept only as their SHA-256."""

    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self._clock = clock
        self._lock = threading.Lock()
        self._pairing: _PairingCode | None = None
        self._failed_redeems: list[float] = []

    def _read(self) -> list[dict[str, Any]]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            return []
        devices = document.get("devices") if isinstance(document, dict) else None
        if not isinstance(devices, list):
            return []
        return [item for item in devices if isinstance(item, dict)]

    def _write(self, devices: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        staging = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            staging.write_text(
                json.dumps({"version": 1, "devices": devices}, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(staging, self.path)
        finally:
            staging.unlink(missing_ok=True)

    @staticmethod
    def _device(record: dict[str, Any]) -> PairedDevice | None:
        try:
            scopes = tuple(scope for scope in SCOPES if scope in record.get("scopes", []))
            return PairedDevice(
                device_id=str(record["id"]),
                name=str(record["name"]),
                scopes=scopes,
                created_at=str(record["created_at"]),
                last_seen_at=record.get("last_seen_at"),
                last_address=record.get("last_address"),
            )
        except (KeyError, TypeError):
            return None

    def list(self) -> list[PairedDevice]:
        with self._lock:
            records = self._read()
        return [device for record in records if (device := self._device(record)) is not None]

    def create(self, name: object, scopes: object) -> tuple[PairedDevice, str]:
        clean = _clean_name(name)
        allowed = clean_scopes(scopes)
        token = secrets.token_urlsafe(32)
        record = {
            "id": str(uuid4()),
            "name": clean,
            "token_sha256": _token_digest(token),
            "scopes": list(allowed),
            "created_at": _now(),
            "last_seen_at": None,
            "last_address": None,
        }
        with self._lock:
            records = self._read()
            if len(records) >= _MAX_DEVICES:
                raise DeviceLinkError("too_many_devices", 409)
            records.append(record)
            self._write(records)
        device = self._device(record)
        assert device is not None
        return device, token

    def authenticate(self, token: str) -> PairedDevice | None:
        if not token or len(token) > 512:
            return None
        digest = _token_digest(token)
        with self._lock:
            records = self._read()
        match: dict[str, Any] | None = None
        for record in records:
            stored = record.get("token_sha256")
            # Compare every record, so the time taken does not tell which one matched.
            if isinstance(stored, str) and hmac.compare_digest(stored, digest):
                match = record
        return self._device(match) if match is not None else None

    def touch(self, device_id: str, address: str) -> None:
        with self._lock:
            records = self._read()
            for record in records:
                if record.get("id") == device_id:
                    record["last_seen_at"] = _now()
                    record["last_address"] = address
                    with suppress(OSError):
                        self._write(records)
                    return

    def revoke(self, device_id: object) -> bool:
        if not isinstance(device_id, str) or not device_id:
            raise DeviceLinkError("invalid_device")
        with self._lock:
            records = self._read()
            kept = [record for record in records if record.get("id") != device_id]
            if len(kept) == len(records):
                return False
            self._write(kept)
            return True

    def start_pairing(self, scopes: object) -> tuple[str, float]:
        """A one-time code for the next phone; it replaces any earlier code."""
        allowed = clean_scopes(scopes)
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        expires_at = self._clock() + _PAIRING_SECONDS
        with self._lock:
            self._pairing = _PairingCode(code, allowed, expires_at)
        return f"{code[:4]}-{code[4:]}", expires_at

    def cancel_pairing(self) -> None:
        with self._lock:
            self._pairing = None

    def redeem(self, code: object, name: object) -> tuple[PairedDevice, str]:
        clean = _clean_name(name)
        typed = "".join(str(code).upper().split()).replace("-", "") if isinstance(code, str) else ""
        now = self._clock()
        with self._lock:
            self._failed_redeems = [at for at in self._failed_redeems if now - at < 600]
            pairing = self._pairing
            if pairing is None or pairing.expires_at <= now:
                self._pairing = None
                raise DeviceLinkError("pairing_unavailable", 403)
            if not typed or not hmac.compare_digest(typed, pairing.code):
                pairing.attempts += 1
                self._failed_redeems.append(now)
                if pairing.attempts >= _PAIRING_ATTEMPTS or len(self._failed_redeems) >= 10:
                    # Too many guesses: the code is spent and a new one must be shown.
                    self._pairing = None
                raise DeviceLinkError("pairing_code_invalid", 403)
            self._pairing = None
            scopes = pairing.scopes
        return self.create(clean, list(scopes))


@dataclass(frozen=True, slots=True)
class DeviceTask:
    task_id: str
    device_id: str
    request_id: str
    session_id: str
    prompt: str
    state: str
    created_at: str
    updated_at: str
    error: str | None = None
    message_event_id: str | None = None
    correlation_id: str | None = None


_TERMINAL_TASK_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


class DeviceTasks:
    """Tasks phones handed over, keyed by the phone's request id so a resend is not run twice."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS device_tasks (
                    task_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    state TEXT NOT NULL,
                    error TEXT,
                    message_event_id TEXT,
                    correlation_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (device_id, request_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _task(row: sqlite3.Row) -> DeviceTask:
        return DeviceTask(
            task_id=row["task_id"],
            device_id=row["device_id"],
            request_id=row["request_id"],
            session_id=row["session_id"],
            prompt=row["prompt"],
            state=row["state"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error=row["error"],
            message_event_id=row["message_event_id"],
            correlation_id=row["correlation_id"],
        )

    def create(
        self, device_id: str, request_id: str, session_id: str, prompt: str
    ) -> tuple[DeviceTask, bool]:
        """The task for this request id: a new one (True) or the one sent before (False)."""
        digest = hashlib.sha256(json.dumps([session_id, prompt]).encode("utf-8")).hexdigest()
        now = _now()
        with closing(self._connect()) as connection, connection:
            existing = connection.execute(
                "SELECT * FROM device_tasks WHERE device_id = ? AND request_id = ?",
                (device_id, request_id),
            ).fetchone()
            if existing is not None:
                if existing["digest"] != digest:
                    raise DeviceLinkError("request_id_conflict", 409)
                return self._task(existing), False
            task_id = str(uuid4())
            connection.execute(
                "INSERT INTO device_tasks (task_id, device_id, request_id, digest, session_id, "
                "prompt, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'dispatching', ?, ?)",
                (task_id, device_id, request_id, digest, session_id, prompt, now, now),
            )
            row = connection.execute(
                "SELECT * FROM device_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task(row), True

    def get(self, task_id: str) -> DeviceTask | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM device_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task(row) if row is not None else None

    def update(self, task_id: str, **fields: str | None) -> None:
        allowed = {"state", "error", "message_event_id", "correlation_id"}
        if not fields or set(fields) - allowed:
            raise ValueError("unknown device task fields")
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                f"UPDATE device_tasks SET {assignments}, updated_at = ? WHERE task_id = ?",
                (*fields.values(), _now(), task_id),
            )

    def discard(self, task_id: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM device_tasks WHERE task_id = ?", (task_id,))

    def open_tasks(self) -> list[DeviceTask]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM device_tasks WHERE state NOT IN (?, ?, ?, ?) ORDER BY created_at",
                tuple(sorted(_TERMINAL_TASK_STATES)),
            ).fetchall()
        return [self._task(row) for row in rows]

    def claimed_messages(self, session_id: str) -> set[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT message_event_id FROM device_tasks "
                "WHERE session_id = ? AND message_event_id IS NOT NULL",
                (session_id,),
            ).fetchall()
        return {str(row["message_event_id"]) for row in rows}


@dataclass(frozen=True, slots=True)
class TlsIdentity:
    certificate: Path
    key: Path
    fingerprint: str  # SHA-256 of the DER certificate, lower-case hex


def ensure_certificate(directory: Path, *, name: str) -> TlsIdentity:
    """This desktop's self-signed certificate, made once and kept for pinning."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    certificate_path = directory / "certificate.pem"
    key_path = directory / "key.pem"
    if not (certificate_path.is_file() and key_path.is_file()):
        directory.mkdir(parents=True, exist_ok=True)
        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, f"Agent Workspace {name}"[:64])]
        )
        now = datetime.now(UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(key, hashes.SHA256())
        )
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    loaded = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    fingerprint = loaded.fingerprint(hashes.SHA256()).hex()
    return TlsIdentity(certificate_path, key_path, fingerprint)


class DeviceLinkBackend(Protocol):
    """What the endpoint asks of the desktop runtime."""

    def device_sessions(self) -> list[dict[str, object]]: ...

    def device_session_events(self, session_id: str) -> list[dict[str, object]] | None: ...

    def device_submit(
        self, device: PairedDevice, request_id: str, session_id: str, prompt: str
    ) -> dict[str, object]: ...

    def device_task(self, device: PairedDevice, task_id: str) -> dict[str, object] | None: ...


@dataclass(slots=True)
class _Throttle:
    failures: dict[str, list[float]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def blocked(self, peer: str, now: float) -> bool:
        with self.lock:
            recent = [at for at in self.failures.get(peer, []) if now - at < _AUTH_WINDOW_SECONDS]
            self.failures[peer] = recent
            return len(recent) >= _AUTH_FAILURE_LIMIT

    def fail(self, peer: str, now: float) -> None:
        with self.lock:
            self.failures.setdefault(peer, []).append(now)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self, address: tuple[str, int], link: DeviceLinkServer, tls: ssl.SSLContext | None
    ) -> None:
        self.link = link
        self.tls = tls
        super().__init__(address, _Handler)

    def verify_request(self, request: Any, client_address: Any) -> bool:
        return peer_allowed(str(client_address[0]))

    def finish_request(self, request: Any, client_address: Any) -> None:
        connection = request
        if self.tls is not None:
            request.settimeout(_HANDSHAKE_TIMEOUT_SECONDS)
            try:
                connection = self.tls.wrap_socket(request, server_side=True)
            except (ssl.SSLError, OSError):
                return
        try:
            _Handler(connection, client_address, self)
        finally:
            if connection is not request:
                with suppress(OSError):
                    connection.close()


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    timeout = 30
    server_version = "AgentWorkspaceDeviceLink/1"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        return

    @property
    def link(self) -> DeviceLinkServer:
        return self.server.link

    def _reply(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, error: DeviceLinkError) -> None:
        self._reply(error.status, {"error": error.code})

    def _peer(self) -> str:
        return str(self.client_address[0])

    def _check_host(self) -> None:
        host = self.headers.get("Host", "").strip().lower()
        if host.startswith("["):
            host = host[1 : host.find("]")] if "]" in host else host
        else:
            host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        if host not in self.link.host_names():
            raise DeviceLinkError("invalid_host", 400)

    def _device(self, scope: str) -> PairedDevice:
        now = self.link.clock()
        peer = self._peer()
        if self.link.throttle.blocked(peer, now):
            raise DeviceLinkError("too_many_attempts", 429)
        header = self.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        device = self.link.registry.authenticate(token)
        if device is None:
            self.link.throttle.fail(peer, now)
            raise DeviceLinkError("unauthorized", 401)
        if scope not in device.scopes:
            raise DeviceLinkError("scope_denied", 403)
        self.link.registry.touch(device.device_id, peer)
        return device

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            raise DeviceLinkError("invalid_length") from None
        if length < 0:
            raise DeviceLinkError("invalid_length")
        if length > _MAX_BODY_BYTES:
            raise DeviceLinkError("payload_too_large", 413)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except (ValueError, UnicodeDecodeError):
            raise DeviceLinkError("invalid_json") from None
        if not isinstance(payload, dict):
            raise DeviceLinkError("invalid_json")
        return payload

    def _parts(self) -> list[str]:
        return [unquote(part) for part in urlsplit(self.path).path.split("/") if part]

    def do_GET(self) -> None:
        try:
            self._check_host()
            parts = self._parts()
            backend = self.link.backend
            if parts == ["health"]:
                self._device("read")
                self._reply(200, {"ok": True, "name": self.link.name})
            elif parts == ["mobile", "runtime"]:
                device = self._device("read")
                self._reply(
                    200,
                    {
                        "idempotent_submissions": True,
                        "device_link": 1,
                        "app": "agent-workspace-desktop",
                        "name": self.link.name,
                        "scopes": list(device.scopes),
                    },
                )
            elif parts == ["sessions"]:
                self._device("read")
                self._reply(200, {"sessions": backend.device_sessions()})
            elif len(parts) == 3 and parts[0] == "sessions" and parts[2] == "events":
                self._device("read")
                events = backend.device_session_events(parts[1])
                if events is None:
                    raise DeviceLinkError("unknown_session", 404)
                self._reply(200, {"events": events})
            elif len(parts) == 3 and parts[:2] == ["mobile", "tasks"]:
                device = self._device("read")
                task = backend.device_task(device, parts[2])
                if task is None:
                    raise DeviceLinkError("unknown_task", 404)
                self._reply(200, {"task": task})
            else:
                raise DeviceLinkError("not_found", 404)
        except DeviceLinkError as error:
            self._error(error)
        except Exception:
            self._reply(500, {"error": "internal_error"})

    def do_POST(self) -> None:
        try:
            self._check_host()
            parts = self._parts()
            if parts == ["pair"]:
                now = self.link.clock()
                peer = self._peer()
                if self.link.throttle.blocked(peer, now):
                    raise DeviceLinkError("too_many_attempts", 429)
                payload = self._body()
                try:
                    device, token = self.link.registry.redeem(
                        payload.get("code"), payload.get("name")
                    )
                except DeviceLinkError:
                    self.link.throttle.fail(peer, now)
                    raise
                self.link.registry.touch(device.device_id, peer)
                self.link.paired(device)
                self._reply(
                    201,
                    {
                        "device_id": device.device_id,
                        "token": token,
                        "scopes": list(device.scopes),
                        "name": self.link.name,
                    },
                )
            elif parts == ["mobile", "tasks"]:
                device = self._device("tasks")
                payload = self._body()
                request_id = payload.get("request_id")
                session_id = payload.get("session_id")
                prompt = payload.get("prompt")
                if (
                    not isinstance(request_id, str)
                    or not request_id
                    or len(request_id) > _MAX_REQUEST_ID_CHARS
                ):
                    raise DeviceLinkError("invalid_request_id")
                if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
                    raise DeviceLinkError("invalid_session")
                if not isinstance(prompt, str) or not prompt.strip():
                    raise DeviceLinkError("invalid_prompt")
                if payload.get("phone_control") is True or payload.get("on_device") is True:
                    raise DeviceLinkError("unsupported_task", 422)
                task = self.link.backend.device_submit(device, request_id, session_id, prompt)
                self._reply(201, {"task": task})
            else:
                raise DeviceLinkError("not_found", 404)
        except DeviceLinkError as error:
            self._error(error)
        except Exception:
            self._reply(500, {"error": "internal_error"})


class DeviceLinkServer:
    """The listening endpoint. ``start`` binds, ``stop`` closes; both are idempotent."""

    def __init__(
        self,
        registry: DeviceRegistry,
        backend: DeviceLinkBackend,
        *,
        name: str,
        port: int,
        bind_host: str = "0.0.0.0",
        tls: TlsIdentity | None = None,
        on_paired: Callable[[PairedDevice], None] | None = None,
        clock: Callable[[], float] = time.time,
        addresses: Callable[[], Iterable[LocalAddress]] = local_addresses,
    ) -> None:
        self.registry = registry
        self.backend = backend
        self.name = name
        self.port = port
        self.bind_host = bind_host
        self.tls = tls
        self.clock = clock
        self.throttle = _Throttle()
        self._on_paired = on_paired
        self._addresses = addresses
        self._address_cache: tuple[float, frozenset[str]] | None = None
        self._server: _Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def bound_port(self) -> int | None:
        return int(self._server.server_address[1]) if self._server is not None else None

    def host_names(self) -> frozenset[str]:
        now = time.monotonic()
        cached = self._address_cache
        if cached is None or now - cached[0] > _ADDRESS_CACHE_SECONDS:
            names = {"localhost", "127.0.0.1", "::1"}
            hostname = socket.gethostname().lower()
            names.update({hostname, f"{hostname}.local"})
            names.update(item.address for item in self._addresses())
            if self.bind_host not in {"0.0.0.0", "::"}:
                names.add(self.bind_host.lower())
            cached = (now, frozenset(names))
            self._address_cache = cached
        return cached[1]

    def paired(self, device: PairedDevice) -> None:
        if self._on_paired is not None:
            with suppress(Exception):
                self._on_paired(device)

    def start(self) -> None:
        if self._server is not None:
            return
        context: ssl.SSLContext | None = None
        if self.tls is not None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.tls.certificate, self.tls.key)
        try:
            server = _Server((self.bind_host, self.port), self, context)
        except OSError as error:
            raise DeviceLinkError("port_unavailable", 409) from error
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.25},
            name="device-link",
            daemon=True,
        )
        self._server = server
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)


def pairing_uri(*, name: str, url: str, code: str, fingerprint: str | None) -> str:
    """What the pairing QR code holds, for phones that can scan it."""
    query = {"v": "1", "name": name, "url": url, "code": code}
    if fingerprint:
        query["fp"] = f"sha256:{fingerprint}"
    return "agentworkspace://pair?" + urlencode(query, quote_via=quote)


class DeviceLink:
    """Settings, paired phones, handed-over tasks and the endpoint of this desktop.

    Settings live in ``settings.json`` next to the registry; the endpoint is off until the user
    turns it on, and it starts again with the desktop when it was on.
    """

    def __init__(
        self,
        directory: Path,
        backend: DeviceLinkBackend,
        *,
        name: str | None = None,
        bind_host: str | None = None,
        clock: Callable[[], float] = time.time,
        addresses: Callable[[], Iterable[LocalAddress]] = local_addresses,
    ) -> None:
        self.directory = directory
        self.backend = backend
        self.name = name or socket.gethostname() or "Agent Workspace"
        self.bind_host = bind_host or os.getenv("AGENT_WORKSPACE_DEVICE_LINK_BIND") or "0.0.0.0"
        self.clock = clock
        self.registry = DeviceRegistry(directory / "devices.json", clock=clock)
        self._addresses = addresses
        self._tasks: DeviceTasks | None = None
        self._server: DeviceLinkServer | None = None
        self._identity: TlsIdentity | None = None
        self._error: str | None = None
        self._pairing: tuple[str, float] | None = None
        self._lock = threading.RLock()

    @property
    def tasks(self) -> DeviceTasks:
        with self._lock:
            if self._tasks is None:
                self._tasks = DeviceTasks(self.directory / "tasks.db")
            return self._tasks

    def settings(self) -> dict[str, Any]:
        try:
            document = json.loads((self.directory / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            document = {}
        if not isinstance(document, dict):
            document = {}
        port = document.get("port")
        return {
            "enabled": document.get("enabled") is True,
            "port": port if type(port) is int and 1024 <= port <= 65535 else DEFAULT_PORT,
            "secure": document.get("secure") is True,
        }

    def _save_settings(self, settings: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "settings.json"
        staging = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            staging.write_text(json.dumps(settings), encoding="utf-8")
            os.replace(staging, path)
        finally:
            staging.unlink(missing_ok=True)

    def configure(
        self,
        *,
        enabled: bool | None = None,
        port: int | None = None,
        secure: bool | None = None,
    ) -> dict[str, object]:
        with self._lock:
            settings = self.settings()
            if enabled is not None:
                settings["enabled"] = enabled
            if port is not None:
                if type(port) is not int or not 1024 <= port <= 65535:
                    raise DeviceLinkError("invalid_port")
                settings["port"] = port
            if secure is not None:
                settings["secure"] = secure
            self._save_settings(settings)
            self._restart(settings)
            return self.status()

    def start_if_enabled(self) -> None:
        with self._lock:
            settings = self.settings()
            if settings["enabled"] and self._server is None:
                self._restart(settings)

    def _restart(self, settings: dict[str, Any]) -> None:
        self._stop_server()
        self._error = None
        if not settings["enabled"]:
            self._pairing = None
            self.registry.cancel_pairing()
            return
        tls = None
        if settings["secure"]:
            try:
                tls = self._identity = ensure_certificate(self.directory, name=self.name)
            except (OSError, ValueError):
                self._error = "certificate_unavailable"
                return
        server = DeviceLinkServer(
            self.registry,
            self.backend,
            name=self.name,
            port=settings["port"],
            bind_host=self.bind_host,
            tls=tls,
            on_paired=lambda _device: self._paired(),
            clock=self.clock,
            addresses=self._addresses,
        )
        try:
            server.start()
        except DeviceLinkError as error:
            self._error = error.code
            return
        self._server = server

    def _paired(self) -> None:
        with self._lock:
            self._pairing = None

    def _stop_server(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.stop()

    def stop(self) -> None:
        with self._lock:
            self._stop_server()

    def _urls(self, settings: dict[str, Any]) -> list[dict[str, str]]:
        scheme = "https" if settings["secure"] else "http"
        port = self._server.bound_port if self._server is not None else settings["port"]
        addresses = list(self._addresses())
        if self.bind_host not in {"0.0.0.0", "::"}:
            addresses = [LocalAddress(self.bind_host, "lan")]
        return [
            {"address": item.address, "kind": item.kind, "url": f"{scheme}://{item.address}:{port}"}
            for item in addresses
        ]

    def status(self) -> dict[str, object]:
        with self._lock:
            settings = self.settings()
            urls = self._urls(settings)
            pairing = self._pairing
            if pairing is not None and pairing[1] <= self.clock():
                pairing = self._pairing = None
            fingerprint = None
            if settings["secure"]:
                identity = self._identity
                if identity is None:
                    with suppress(OSError, ValueError):
                        identity = self._identity = ensure_certificate(
                            self.directory, name=self.name
                        )
                fingerprint = identity.fingerprint if identity is not None else None
            document: dict[str, object] = {
                **settings,
                "running": self._server is not None,
                "error": self._error,
                "name": self.name,
                "fingerprint": fingerprint,
                "addresses": urls,
                "devices": [device.document() for device in self.registry.list()],
                "pairing": None,
            }
            if pairing is not None and urls and self._server is not None:
                code, expires_at = pairing
                document["pairing"] = {
                    "code": code,
                    "expiresAt": datetime.fromtimestamp(expires_at, UTC).isoformat(),
                    "url": urls[0]["url"],
                    "uri": pairing_uri(
                        name=self.name, url=urls[0]["url"], code=code, fingerprint=fingerprint
                    ),
                }
            return document

    def start_pairing(self, scopes: object) -> dict[str, object]:
        with self._lock:
            if self._server is None:
                raise DeviceLinkError("device_link_off", 409)
            self._pairing = self.registry.start_pairing(scopes)
            return self.status()

    def create_token(self, name: object, scopes: object) -> tuple[PairedDevice, str]:
        with self._lock:
            if self._server is None:
                raise DeviceLinkError("device_link_off", 409)
            return self.registry.create(name, scopes)

    def revoke(self, device_id: object) -> dict[str, object]:
        with self._lock:
            if not self.registry.revoke(device_id):
                raise DeviceLinkError("unknown_device", 404)
            return self.status()


__all__ = [
    "DEFAULT_PORT",
    "SCOPES",
    "DeviceLink",
    "DeviceLinkBackend",
    "DeviceLinkError",
    "DeviceLinkServer",
    "DeviceRegistry",
    "DeviceTask",
    "DeviceTasks",
    "LocalAddress",
    "PairedDevice",
    "TlsIdentity",
    "clean_scopes",
    "ensure_certificate",
    "local_addresses",
    "pairing_uri",
    "peer_allowed",
]
