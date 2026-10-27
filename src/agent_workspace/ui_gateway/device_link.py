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
import queue
import secrets
import socket
import sqlite3
import ssl
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import closing, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
from uuid import uuid4

from agent_workspace.ui_gateway.device_store import DeviceStore
from agent_workspace.ui_gateway.firewall import FirewallWatch
from agent_workspace.ui_gateway.mdns import MdnsAnnouncer, txt_record
from agent_workspace.ui_gateway.net_adapters import reachable_addresses

SCOPES = ("read", "tasks", "approvals", "broad_autonomy", "files", "knowledge")
# Device link 2 (docs/DEVICE_LINK_API.md): what this desktop implements, for the phone to show.
PROTOCOL_VERSION = 2
FEATURES = (
    "tasks",
    "inbox",
    "approvals",
    "autonomy_ack",
    "private_ack",
    "phone_jobs",
    "turns",
    "stop",
    "task_activity",
    "addresses",
    "files",
    "transfers",
    "messages",
    "conversations",
    "wake",
    "inbox_read",
    "knowledge",
    "device",
)
DEFAULT_PORT = 8765
_MAX_BODY_BYTES = 512 * 1024
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_KNOWLEDGE_BYTES = 32 * 1024 * 1024
MAX_CONVERSATION_BYTES = 1024 * 1024
_MAX_ALT_ADDRESSES = 3
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
    """A request the endpoint refuses: a stable code, its HTTP status, and any fields the
    answer carries besides the code (a conversation's current ``autonomy``)."""

    def __init__(self, code: str, status: int = 400, **extra: object) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


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
    """This machine's IPv4 addresses a phone can reach (net_adapters): real network cards and
    Tailscale, LAN first with the default route's address leading."""
    return [LocalAddress(address, kind) for address, kind in reachable_addresses()]


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
    # The phone takes jobs this desktop's AI hands it (it reports this itself).
    accepts_jobs: bool = False
    # Turns finishing on this desktop are listed in the phone's inbox (set on the desktop).
    notify_turns: bool = True

    def document(self) -> dict[str, object]:
        return {
            "deviceId": self.device_id,
            "name": self.name,
            "scopes": list(self.scopes),
            "createdAt": self.created_at,
            "lastSeenAt": self.last_seen_at,
            "lastAddress": self.last_address,
            "acceptsJobs": self.accepts_jobs,
            "notifyTurns": self.notify_turns,
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
                accepts_jobs=record.get("accepts_jobs") is True,
                notify_turns=record.get("notify_turns") is not False,
            )
        except (KeyError, TypeError):
            return None

    def get(self, device_id: str) -> PairedDevice | None:
        return next((device for device in self.list() if device.device_id == device_id), None)

    def update(
        self,
        device_id: object,
        *,
        scopes: object = None,
        accepts_jobs: bool | None = None,
        notify_turns: bool | None = None,
    ) -> PairedDevice:
        """Change a paired phone's scopes or settings; its token stays the same."""
        if not isinstance(device_id, str) or not device_id:
            raise DeviceLinkError("invalid_device")
        allowed = clean_scopes(scopes) if scopes is not None else None
        with self._lock:
            records = self._read()
            record = next((item for item in records if item.get("id") == device_id), None)
            if record is None:
                raise DeviceLinkError("unknown_device", 404)
            if allowed is not None:
                record["scopes"] = list(allowed)
            if accepts_jobs is not None:
                record["accepts_jobs"] = accepts_jobs
            if notify_turns is not None:
                record["notify_turns"] = notify_turns
            self._write(records)
        device = self._device(record)
        assert device is not None
        return device

    def revoke_all(self) -> list[str]:
        with self._lock:
            removed = [str(record.get("id")) for record in self._read()]
            self._write([])
        return removed

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
    # Device link 2: the conversation's autonomy the task ran with, where its model runs, and
    # what the window marks the turn with (broad_autonomy, private, subtask).
    autonomy: str | None = None
    model_location: str | None = None
    labels: tuple[str, ...] = ()


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
            columns = {row[1] for row in connection.execute("PRAGMA table_info(device_tasks)")}
            for column in ("autonomy", "model_location", "labels"):
                if column not in columns:  # tasks kept by device link 1
                    connection.execute(f"ALTER TABLE device_tasks ADD COLUMN {column} TEXT")

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
            autonomy=row["autonomy"],
            model_location=row["model_location"],
            labels=tuple(label for label in (row["labels"] or "").split(",") if label),
        )

    def create(
        self,
        device_id: str,
        request_id: str,
        session_id: str,
        prompt: str,
        *,
        autonomy: str | None = None,
        model_location: str | None = None,
        labels: Iterable[str] = (),
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
                "prompt, state, created_at, updated_at, autonomy, model_location, labels) "
                "VALUES (?, ?, ?, ?, ?, ?, 'dispatching', ?, ?, ?, ?, ?)",
                (
                    task_id, device_id, request_id, digest, session_id, prompt, now, now,
                    autonomy, model_location, ",".join(labels),
                ),
            )  # fmt: skip
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

    def find(self, device_id: str, request_id: str) -> DeviceTask | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM device_tasks WHERE device_id = ? AND request_id = ?",
                (device_id, request_id),
            ).fetchone()
        return self._task(row) if row is not None else None

    def for_session(self, session_id: str) -> list[DeviceTask]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM device_tasks WHERE session_id = ? ORDER BY created_at",
                (session_id,),
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
        self,
        device: PairedDevice,
        request_id: str,
        session_id: str,
        prompt: str,
        options: TaskOptions | None = None,
    ) -> dict[str, object]: ...

    def device_task(self, device: PairedDevice, task_id: str) -> dict[str, object] | None: ...

    def device_inbox(self, device: PairedDevice) -> dict[str, object]: ...

    def device_resolve_approval(
        self, device: PairedDevice, request_id: str, approve: bool
    ) -> dict[str, object]: ...

    # Device link 2.
    def device_runtime(self) -> dict[str, object]: ...

    def device_stop(self, device: PairedDevice, session_id: str) -> dict[str, object]: ...

    def device_inbox_read(self, device: PairedDevice, run_ids: list[str]) -> None: ...

    def device_job_report(
        self, device: PairedDevice, job_id: str, payload: dict[str, Any]
    ) -> dict[str, object]: ...

    def device_receive_file(
        self, device: PairedDevice, transfer_id: str, upload: Upload
    ) -> dict[str, object]: ...

    def device_files(self, device: PairedDevice, path: str) -> dict[str, object]: ...

    def device_file(self, device: PairedDevice, path: str) -> tuple[Path, str]: ...

    def device_transfer(
        self, device: PairedDevice, transfer_id: str
    ) -> tuple[Path | None, Any]: ...

    def device_transfer_done(self, device: PairedDevice, transfer_id: str) -> None: ...

    def device_message(self, device: PairedDevice, payload: dict[str, Any]) -> None: ...

    def device_conversation(
        self, device: PairedDevice, payload: dict[str, Any]
    ) -> dict[str, object]: ...

    def device_knowledge(self, device: PairedDevice) -> dict[str, object]: ...

    def device_knowledge_document(
        self, device: PairedDevice, document_id: str
    ) -> dict[str, object]: ...

    def device_knowledge_add(
        self, device: PairedDevice, payload: dict[str, Any]
    ) -> tuple[int, dict[str, object]]: ...

    def device_info(self, device: PairedDevice) -> dict[str, object]: ...

    def device_settings(
        self, device: PairedDevice, payload: dict[str, Any]
    ) -> dict[str, object]: ...

    def device_unpair(self, device: PairedDevice) -> None: ...


@dataclass(frozen=True, slots=True)
class TaskOptions:
    """What a phone confirmed about a task (device link 2): the conversation's broad autonomy,
    and private content it agreed to send."""

    accept_autonomy: str | None = None
    on_device: bool = False
    private_accepted: bool = False
    # The phone's own AI handed this part of its task over (ask_computer), not its user.
    from_agent: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> TaskOptions:
        accept = payload.get("accept_autonomy")
        if accept is not None and accept not in {"yolo", "full_access"}:
            raise DeviceLinkError("invalid_autonomy")
        if payload.get("phone_control") is True:
            # Operating a phone is the phone's own work; this desktop asks a phone through jobs.
            raise DeviceLinkError("unsupported_task", 422)
        on_device = payload.get("on_device") is True
        private = payload.get("private_accepted") is True
        if on_device and not private:
            raise DeviceLinkError("unsupported_task", 422)
        return cls(
            accept_autonomy=accept,
            on_device=on_device,
            private_accepted=private,
            from_agent=payload.get("from_agent") is True,
        )


@dataclass(frozen=True, slots=True)
class Upload:
    """A file a phone sent, already checked and staged on disk."""

    name: str
    path: Path
    size: int
    sha256: str
    knowledge: str | None = None


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
    server_version = "AgentWorkspaceDeviceLink/2"
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
        self._reply(error.status, {**error.extra, "error": error.code})

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

    def _length(self, limit: int) -> int:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            raise DeviceLinkError("invalid_length") from None
        if length < 0:
            raise DeviceLinkError("invalid_length")
        if length > limit:
            raise DeviceLinkError("payload_too_large", 413)
        return length

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlsplit(self.path).query, keep_blank_values=True)

    def _reply_bytes(self, data: bytes, headers: dict[str, str]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _reply_file(self, path: Path, sha256: str) -> None:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise DeviceLinkError("payload_too_large", 413)
        with path.open("rb") as stream:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("X-Content-SHA256", sha256)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while chunk := stream.read(1024 * 1024):
                self.wfile.write(chunk)

    def _body(self, limit: int = _MAX_BODY_BYTES) -> dict[str, Any]:
        length = self._length(limit)
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
                self._reply(200, self.link.runtime_document(device))
            elif parts == ["mobile", "device"]:
                device = self._device("read")
                self._reply(200, backend.device_info(device))
            elif parts == ["mobile", "files"]:
                device = self._device("files")
                path = (self._query().get("path") or [""])[0]
                self._reply(200, backend.device_files(device, path))
            elif parts == ["mobile", "files", "content"]:
                device = self._device("files")
                path = (self._query().get("path") or [""])[0]
                source, digest = backend.device_file(device, path)
                self._reply_file(source, digest)
            elif len(parts) == 4 and parts[:2] == ["mobile", "transfers"] and parts[3] == "content":
                device = self._device("read")
                file, document = backend.device_transfer(device, parts[2])
                if file is not None:
                    self._reply_file(file, str(document))
                else:
                    self._reply(200, document)
            elif parts == ["mobile", "knowledge"]:
                device = self._device("knowledge")
                self._reply(200, backend.device_knowledge(device))
            elif len(parts) == 4 and parts[:3] == ["mobile", "knowledge", "documents"]:
                device = self._device("knowledge")
                self._reply(200, backend.device_knowledge_document(device, parts[3]))
            elif parts == ["mobile", "inbox"]:
                device = self._device("read")
                self._reply(200, backend.device_inbox(device))
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
                        "desktop_id": self.link.desktop_id,
                        "addresses": self.link.addresses(),
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
                options = TaskOptions.from_payload(payload)
                task = self.link.backend.device_submit(
                    device, request_id, session_id, prompt, options
                )
                self._reply(201, {"task": task})
            elif len(parts) == 4 and parts[:2] == ["mobile", "sessions"] and parts[3] == "stop":
                device = self._device("tasks")
                self._body()
                self._reply(200, self.link.backend.device_stop(device, parts[2]))
            elif parts == ["mobile", "inbox", "read"]:
                device = self._device("read")
                run_ids = self._body().get("run_ids")
                if not isinstance(run_ids, list) or not all(
                    isinstance(item, str) and 0 < len(item) <= 128 for item in run_ids
                ):
                    raise DeviceLinkError("invalid_run_ids")
                self.link.backend.device_inbox_read(device, run_ids[:200])
                self._reply(200, {"ok": True})
            elif len(parts) == 3 and parts[:2] == ["mobile", "phone-jobs"]:
                device = self._device("read")
                job = self.link.backend.device_job_report(device, parts[2], self._body())
                self._reply(200, {"job": job})
            elif len(parts) == 4 and parts[:2] == ["mobile", "transfers"] and parts[3] == "done":
                device = self._device("read")
                self._body()
                self.link.backend.device_transfer_done(device, parts[2])
                self._reply(200, {"ok": True})
            elif parts == ["mobile", "messages"]:
                device = self._device("files")
                self.link.backend.device_message(device, self._body())
                self._reply(201, {"ok": True})
            elif parts == ["mobile", "conversations"]:
                device = self._device("tasks")
                payload = self._body(MAX_CONVERSATION_BYTES)
                self._reply(201, self.link.backend.device_conversation(device, payload))
            elif parts == ["mobile", "knowledge", "documents"]:
                device = self._device("knowledge")
                payload = self._body(MAX_KNOWLEDGE_BYTES)
                status, answer = self.link.backend.device_knowledge_add(device, payload)
                self._reply(status, answer)
            elif parts == ["mobile", "device"]:
                device = self._device("read")
                self._reply(200, self.link.backend.device_settings(device, self._body()))
            elif parts == ["mobile", "device", "unpair"]:
                device = self._device("read")
                self._body()
                self.link.backend.device_unpair(device)
                self._reply(200, {"ok": True})
            elif len(parts) == 3 and parts[:2] == ["mobile", "approvals"]:
                device = self._device("approvals")
                decision = self._body().get("decision")
                if decision not in {"approve", "reject"}:
                    raise DeviceLinkError("invalid_decision")
                answer = self.link.backend.device_resolve_approval(
                    device, parts[2], decision == "approve"
                )
                self._reply(200, {"approval": answer})
            else:
                raise DeviceLinkError("not_found", 404)
        except DeviceLinkError as error:
            self._error(error)
        except Exception:
            self._reply(500, {"error": "internal_error"})

    def do_PUT(self) -> None:
        staged: Path | None = None
        try:
            self._check_host()
            parts = self._parts()
            if not (len(parts) == 3 and parts[:2] == ["mobile", "files"]):
                raise DeviceLinkError("not_found", 404)
            device = self._device("files")
            transfer_id = parts[2]
            if not transfer_id or len(transfer_id) > _MAX_REQUEST_ID_CHARS:
                raise DeviceLinkError("invalid_transfer")
            query = self._query()
            name = (query.get("name") or [""])[0]
            size_text = (query.get("size") or [""])[0]
            expected = (query.get("sha256") or [""])[0].lower()
            knowledge = query["knowledge"][0] if query.get("knowledge") else None
            if not size_text.isdigit() or len(expected) != 64:
                raise DeviceLinkError("invalid_upload")
            length = self._length(MAX_FILE_BYTES)
            if length != int(size_text):
                self.rfile.read(length)
                raise DeviceLinkError("checksum_mismatch")
            # Read the whole body before answering, even for a resend, so the stream stays aligned.
            descriptor, temporary = tempfile.mkstemp(prefix=".upload-", dir=self.link.staging())
            staged = Path(temporary)
            digest = hashlib.sha256()
            remaining = length
            with os.fdopen(descriptor, "wb") as stream:
                while remaining:
                    chunk = self.rfile.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise DeviceLinkError("invalid_length")
                    digest.update(chunk)
                    stream.write(chunk)
                    remaining -= len(chunk)
            if digest.hexdigest() != expected:
                raise DeviceLinkError("checksum_mismatch")
            upload = Upload(
                name=name, path=staged, size=length, sha256=expected, knowledge=knowledge
            )
            self._reply(201, self.link.backend.device_receive_file(device, transfer_id, upload))
        except DeviceLinkError as error:
            self.close_connection = True  # an unread upload body must not become the next request
            self._error(error)
        except Exception:
            self.close_connection = True
            self._reply(500, {"error": "internal_error"})
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)


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
        desktop_id: str = "",
        runtime_extra: Callable[[], dict[str, object]] | None = None,
        staging: Path | None = None,
    ) -> None:
        self.registry = registry
        self.backend = backend
        self.name = name
        self.port = port
        self.bind_host = bind_host
        self.tls = tls
        self.clock = clock
        self.throttle = _Throttle()
        self.desktop_id = desktop_id
        self._on_paired = on_paired
        self._addresses = addresses
        self._runtime_extra = runtime_extra
        self._staging = staging
        self._address_cache: tuple[float, frozenset[str]] | None = None
        self._server: _Server | None = None
        self._thread: threading.Thread | None = None

    def addresses(self) -> list[dict[str, str]]:
        """Every address this endpoint answers at, LAN first, with its scheme and port."""
        scheme = "https" if self.tls is not None else "http"
        port = self.bound_port or self.port
        found = list(self._addresses())
        if self.bind_host not in {"0.0.0.0", "::"}:
            found = [LocalAddress(self.bind_host, "lan")]
        return [{"url": f"{scheme}://{item.address}:{port}", "kind": item.kind} for item in found]

    def runtime_document(self, device: PairedDevice) -> dict[str, object]:
        document: dict[str, object] = {
            "idempotent_submissions": True,
            "device_link": PROTOCOL_VERSION,
            "app": "agent-workspace-desktop",
            "name": self.name,
            "desktop_id": self.desktop_id,
            "scopes": list(device.scopes),
            "features": list(FEATURES),
            "addresses": self.addresses(),
        }
        backend_runtime = getattr(self.backend, "device_runtime", None)
        if callable(backend_runtime):
            document.update(backend_runtime())
        if self._runtime_extra is not None:
            document.update(self._runtime_extra())
        return document

    def staging(self) -> Path:
        directory = self._staging or Path(tempfile.gettempdir()) / "agent-workspace-uploads"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

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


def pairing_uri(
    *,
    name: str,
    url: str,
    code: str,
    fingerprint: str | None,
    desktop_id: str | None = None,
    alternates: Iterable[str] = (),
) -> str:
    """What the pairing QR code holds, for phones that can scan it. ``id`` and ``alt`` (device
    link 2) let a phone find this desktop again at another address; older phones ignore them."""
    query: list[tuple[str, str]] = [("v", "1"), ("name", name), ("url", url), ("code", code)]
    if fingerprint:
        query.append(("fp", f"sha256:{fingerprint}"))
    if desktop_id:
        query.append(("id", desktop_id))
    query.extend(("alt", item) for item in list(alternates)[:_MAX_ALT_ADDRESSES])
    return "agentworkspace://pair?" + urlencode(query, quote_via=quote)


def short_fingerprint(fingerprint: str | None) -> str | None:
    """The first 16 hex digits in groups of four, for comparing with what a phone shows."""
    if not fingerprint:
        return None
    head = fingerprint[:16].lower()
    return " ".join(head[index : index + 4] for index in range(0, 16, 4))


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
        mdns: MdnsAnnouncer | None = None,
        firewall: FirewallWatch | None = None,
    ) -> None:
        self.directory = directory
        self.backend = backend
        if mdns is None and os.getenv("AGENT_WORKSPACE_DEVICE_LINK_MDNS", "1") != "0":
            mdns = MdnsAnnouncer()
        self._mdns = mdns
        if (
            firewall is None
            and os.name == "nt"
            and os.getenv("AGENT_WORKSPACE_DEVICE_LINK_FIREWALL", "1") != "0"
        ):
            firewall = FirewallWatch()
        self._firewall = firewall
        self.name = (
            name
            or os.getenv("AGENT_WORKSPACE_DEVICE_LINK_NAME")
            or socket.gethostname()
            or "Agent Workspace"
        )
        self.bind_host = bind_host or os.getenv("AGENT_WORKSPACE_DEVICE_LINK_BIND") or "0.0.0.0"
        self.clock = clock
        self.registry = DeviceRegistry(directory / "devices.json", clock=clock)
        self._addresses = addresses
        self._tasks: DeviceTasks | None = None
        self._store: DeviceStore | None = None
        self._wake_cache: tuple[float, list[dict[str, str]]] | None = None
        self._server: DeviceLinkServer | None = None
        self._identity: TlsIdentity | None = None
        self._error: str | None = None
        self._pairing: tuple[str, float] | None = None
        self._lock = threading.RLock()
        # What the local network should be told, newest last; one thread tells it.
        self._mdns_wanted: queue.SimpleQueue[dict[str, Any] | None] = queue.SimpleQueue()
        self._mdns_thread: threading.Thread | None = None

    @property
    def tasks(self) -> DeviceTasks:
        with self._lock:
            if self._tasks is None:
                self._tasks = DeviceTasks(self.directory / "tasks.db")
            return self._tasks

    @property
    def store(self) -> DeviceStore:
        with self._lock:
            if self._store is None:
                self._store = DeviceStore(self.directory)
            return self._store

    def settings(self) -> dict[str, Any]:
        try:
            document = json.loads((self.directory / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            document = {}
        if not isinstance(document, dict):
            document = {}
        port = document.get("port")
        desktop_id = document.get("desktop_id")
        settings = {
            "enabled": document.get("enabled") is True,
            "port": port if type(port) is int and 1024 <= port <= 65535 else DEFAULT_PORT,
            # HTTPS unless the user chose otherwise: the pairing QR code carries the certificate's
            # fingerprint, so it costs the user nothing, and phones need it over Tailscale.
            "secure": document.get("secure") is not False,
            # Made the first time and kept, so a phone can find this desktop at a new address.
            "desktop_id": desktop_id if isinstance(desktop_id, str) and desktop_id else None,
            "wake": document.get("wake") is True,
            "clipboard": document.get("clipboard") is not False,
        }
        if settings["desktop_id"] is None:
            settings["desktop_id"] = uuid4().hex
            with suppress(OSError):
                self._save_settings(settings)
        return settings

    @property
    def desktop_id(self) -> str:
        return str(self.settings()["desktop_id"])

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
        wake: bool | None = None,
        clipboard: bool | None = None,
    ) -> dict[str, object]:
        with self._lock:
            settings = self.settings()
            restart = enabled is not None or port is not None or secure is not None
            if enabled is not None:
                settings["enabled"] = enabled
            if port is not None:
                if type(port) is not int or not 1024 <= port <= 65535:
                    raise DeviceLinkError("invalid_port")
                settings["port"] = port
            if secure is not None:
                settings["secure"] = secure
            if wake is not None:
                settings["wake"] = wake
                self._wake_cache = None
            if clipboard is not None:
                settings["clipboard"] = clipboard
            self._save_settings(settings)
            if restart:
                self._restart(settings)
            return self.status()

    def reset(self) -> dict[str, object]:
        """A new desktop id; every paired phone is removed and has to pair again."""
        with self._lock:
            settings = self.settings()
            settings["desktop_id"] = uuid4().hex
            self._save_settings(settings)
            for device_id in self.registry.revoke_all():
                with suppress(OSError, sqlite3.Error):
                    self.store.forget_device(device_id)
            self._pairing = None
            self.registry.cancel_pairing()
            if settings["enabled"]:
                self._restart(settings)
            return self.status()

    def update_device(
        self, device_id: object, *, scopes: object = None, notify_turns: bool | None = None
    ) -> dict[str, object]:
        with self._lock:
            self.registry.update(device_id, scopes=scopes, notify_turns=notify_turns)
            return self.status()

    def _runtime_extra(self) -> dict[str, object]:
        """Wake-on-LAN targets, only while the user allows waking this computer, and the
        ``mdns`` feature while this desktop is announced on the local network."""
        extra: dict[str, object] = {}
        if self._mdns is not None and self._mdns.active:
            extra["features"] = [*FEATURES, "mdns"]
        if not self.settings()["wake"]:
            return extra
        now = self.clock()
        cached = self._wake_cache
        if cached is None or now - cached[0] > 600:
            cached = self._wake_cache = (now, wake_targets())
        if cached[1]:
            extra["wake"] = cached[1]
        return extra

    def _announce(self) -> None:
        """Tell the local network about the endpoint while it runs, with ``pair=1`` while a
        pairing code is shown (lock held). The system call runs on its own thread."""
        if self._mdns is None:
            return
        wanted: dict[str, Any] | None = None
        server = self._server
        if server is not None and not _loopback(self.bind_host):
            settings = self.settings()
            if self.bind_host not in {"0.0.0.0", "::"}:
                address: str | None = self.bind_host
            else:
                address = next(
                    (item.address for item in self._addresses() if item.kind == "lan"), None
                )
            identity = self._identity if settings["secure"] else None
            wanted = {
                "name": self.name,
                "port": server.bound_port or settings["port"],
                "address": address,
                "txt": txt_record(
                    desktop_id=str(settings["desktop_id"]),
                    tls=bool(settings["secure"]),
                    fingerprint=identity.fingerprint if identity is not None else None,
                    pairing=self._pairing is not None,
                ),
            }
        self._mdns_wanted.put(wanted)
        if self._mdns_thread is None or not self._mdns_thread.is_alive():
            self._mdns_thread = threading.Thread(
                target=self._tell_network, name="device-link-mdns", daemon=True
            )
            self._mdns_thread.start()

    def _tell_network(self) -> None:
        mdns = self._mdns
        assert mdns is not None
        while True:
            wanted = self._mdns_wanted.get()
            with suppress(queue.Empty):
                while True:  # only the newest state matters
                    wanted = self._mdns_wanted.get_nowait()
            with suppress(Exception):
                if wanted is None:
                    mdns.stop()
                else:
                    mdns.announce(**wanted)

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
            on_paired=lambda device: self._paired(device),
            clock=self.clock,
            addresses=self._addresses,
            desktop_id=str(settings["desktop_id"]),
            runtime_extra=self._runtime_extra,
            staging=self.directory / "incoming",
        )
        try:
            server.start()
        except DeviceLinkError as error:
            self._error = error.code
            return
        self._server = server
        self._announce()
        if self._firewall is not None and not _loopback(self.bind_host):
            self._firewall.recheck()

    def _firewall_state(self) -> str | None:
        """Whether Windows Firewall lets phones in: "open", "blocked", "checking", "fixing",
        "declined" or "unknown"; None when it does not apply (not Windows, loopback only)."""
        if self._firewall is None or self._server is None or _loopback(self.bind_host):
            return None
        return self._firewall.state()

    def allow_through_firewall(self) -> dict[str, object]:
        """Ask Windows (its administrator confirmation) to let phones reach this endpoint."""
        with self._lock:
            if self._firewall is None or self._server is None:
                raise DeviceLinkError("device_link_off", 409)
            self._firewall.allow()
            return self.status()

    def _paired(self, device: PairedDevice) -> None:
        with self._lock:
            self._pairing = None
            self._announce()
        with suppress(OSError, sqlite3.Error):
            self.store.log(device.device_id, "paired", device.name)

    def _stop_server(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.stop()
            self._announce()

    def stop(self) -> None:
        with self._lock:
            self._stop_server()
        if self._mdns is not None:
            self._mdns_wanted.put(None)
            with suppress(Exception):
                self._mdns.stop()  # before the process exits

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
                self._announce()
            fingerprint = None
            if settings["secure"]:
                identity = self._identity
                if identity is None:
                    with suppress(OSError, ValueError):
                        identity = self._identity = ensure_certificate(
                            self.directory, name=self.name
                        )
                fingerprint = identity.fingerprint if identity is not None else None
            devices: list[dict[str, object]] = []
            names: dict[str, str] = {}
            for device in self.registry.list():
                activity: list[dict[str, str]] = []
                with suppress(OSError, sqlite3.Error):
                    activity = self.store.activity(device.device_id)[:10]
                devices.append({**device.document(), "activity": activity})
                names[device.device_id] = device.name
            # Texts and links phones sent, newest first ("手机发来的").
            messages: list[dict[str, object]] = []
            if (self.directory / "link.db").is_file():
                with suppress(OSError, sqlite3.Error):
                    messages = [
                        {
                            "id": item["id"],
                            "kind": item["kind"],
                            "text": item["text"],
                            "createdAt": item["created_at"],
                            "device": names.get(str(item["device_id"]), ""),
                        }
                        for item in self.store.messages()
                    ]
            document: dict[str, object] = {
                "enabled": settings["enabled"],
                "port": settings["port"],
                "secure": settings["secure"],
                "wake": settings["wake"],
                "clipboard": settings["clipboard"],
                "desktopId": settings["desktop_id"],
                "running": self._server is not None,
                "error": self._error,
                "name": self.name,
                "fingerprint": fingerprint,
                "fingerprintShort": short_fingerprint(fingerprint),
                "addresses": urls,
                "devices": devices,
                "messages": messages,
                "announced": self._mdns is not None and self._mdns.active,
                "firewall": self._firewall_state(),
                "pairing": None,
            }
            if pairing is not None and urls and self._server is not None:
                code, expires_at = pairing
                document["pairing"] = {
                    "code": code,
                    "expiresAt": datetime.fromtimestamp(expires_at, UTC).isoformat(),
                    "url": urls[0]["url"],
                    "uri": pairing_uri(
                        name=self.name,
                        url=urls[0]["url"],
                        code=code,
                        fingerprint=fingerprint,
                        desktop_id=str(settings["desktop_id"]),
                        alternates=[item["url"] for item in urls[1:]],
                    ),
                }
            return document

    def start_pairing(self, scopes: object) -> dict[str, object]:
        with self._lock:
            if self._server is None:
                raise DeviceLinkError("device_link_off", 409)
            self._pairing = self.registry.start_pairing(scopes)
            self._announce()
            return self.status()

    def create_token(self, name: object, scopes: object) -> tuple[PairedDevice, str]:
        with self._lock:
            if self._server is None:
                raise DeviceLinkError("device_link_off", 409)
            device, token = self.registry.create(name, scopes)
        self._paired(device)
        return device, token

    def revoke(self, device_id: object) -> dict[str, object]:
        with self._lock:
            if not self.registry.revoke(device_id):
                raise DeviceLinkError("unknown_device", 404)
            with suppress(OSError, sqlite3.Error):
                self.store.forget_device(str(device_id))
            return self.status()


def wake_targets() -> list[dict[str, str]]:
    """The MAC and broadcast address of each connected LAN adapter, for Wake-on-LAN."""
    if os.name != "nt":
        return []
    script = (
        "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | ForEach-Object { $a = $_; "
        "Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction "
        "SilentlyContinue | ForEach-Object { [pscustomobject]@{ mac = $a.MacAddress; "
        "ip = $_.IPAddress; prefix = $_.PrefixLength } } } | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        raw = json.loads(completed.stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    rows = raw if isinstance(raw, list) else [raw]
    targets: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            network = ipaddress.IPv4Network(f"{row['ip']}/{int(row['prefix'])}", strict=False)
            address = ipaddress.IPv4Address(str(row["ip"]))
        except (KeyError, ValueError, TypeError):
            continue
        mac = str(row.get("mac") or "").replace("-", ":").lower()
        if len(mac) != 17 or not address.is_private or address in _TAILSCALE:
            continue
        if address.is_link_local or address.is_loopback:
            continue
        target = {"mac": mac, "broadcast": str(network.broadcast_address)}
        if target not in targets:
            targets.append(target)
    return targets


__all__ = [
    "DEFAULT_PORT",
    "FEATURES",
    "MAX_CONVERSATION_BYTES",
    "MAX_FILE_BYTES",
    "MAX_KNOWLEDGE_BYTES",
    "PROTOCOL_VERSION",
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
    "TaskOptions",
    "TlsIdentity",
    "Upload",
    "clean_scopes",
    "ensure_certificate",
    "local_addresses",
    "pairing_uri",
    "peer_allowed",
    "short_fingerprint",
    "wake_targets",
]
