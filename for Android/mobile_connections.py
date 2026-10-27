"""Authenticated remote Serve hosts. Tokens remain in the platform credential store.

A desktop running Agent Workspace (Settings → Phone connection) is paired in one of three ways:
its pairing link (the QR code it shows, agentworkspace://pair?...), its address and one-time
pairing code, or an address and a token created on the desktop. In HTTPS mode the desktop has a
self-signed certificate; the phone pins it by the SHA-256 fingerprint in the pairing link and
afterwards trusts that certificate alone (docs/DEVICE_LINK_API.md in the monorepo).

A desktop of device link 2 (docs/DEVICE_LINK_V2.md here) also tells its other addresses (LAN and
Tailscale) and a stable desktop_id: a request that cannot connect tries the other addresses, and
the one that answers is used from then on.
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
_DESKTOP_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_MAX_ADDRESSES = 8
_RESPONSE_BYTES = 4 * 1024 * 1024
# What a desktop's runtime document may tell; kept with the host so pages can show the right controls.
_RUNTIME_KEYS = ("device_link", "features", "scopes", "model", "workspace", "wake", "name", "defaults")
# A request that never reached the desktop: safe to send again to another of its addresses.
_UNSENT = (httpx.ConnectError, httpx.ConnectTimeout)


# Answers from a paired computer that mean something to the person holding the phone.
_STATUS_REASONS = {
    401: "the computer no longer accepts this phone; remove it here and pair again",
    429: "the computer is turning this phone away for a moment after too many attempts; try again in a minute",
}


class RemoteHTTPError(ValueError):
    def __init__(self, status_code: int, code: str | None = None):
        self.status_code = status_code
        self.code = code
        super().__init__(_STATUS_REASONS.get(status_code)
                         or f"remote host returned HTTP {status_code}" + (f" ({code})" if code else ""))


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


def _pinning_failed(error: BaseException) -> bool:
    return unavailable_reason(error) != "remote host is unavailable"


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


def pairing_link(value: object) -> dict[str, Any]:
    """The parts of a desktop's pairing link (its QR code), found in pasted text too:
    agentworkspace://pair?v=1&name=<desktop>&url=<address>&code=<XXXX-XXXX>[&fp=sha256:<hex>]
    [&id=<desktop_id>][&alt=<another address>]..."""
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("this is not a pairing link")
    found = _LINK.search(value)
    if found is None:
        raise ValueError("this is not a pairing link")
    parsed = urlsplit(found.group(0))
    values = parse_qs(parsed.query, keep_blank_values=True)
    query = {key: items[0] for key, items in values.items()}
    if query.get("v") != "1":
        raise ValueError("this pairing link is from a newer version of the desktop app; update this app")
    name = " ".join(str(query.get("name") or "").split())[:100] or "Agent Workspace"
    target = pairing_target(query.get("url"), query.get("code"), query.get("fp"))
    desktop_id = query.get("id")
    return {
        "name": name,
        **target,
        "desktop_id": desktop_id if isinstance(desktop_id, str) and _DESKTOP_ID.fullmatch(desktop_id) else None,
        # Other addresses of the same desktop; a malformed or public one is left out.
        "alternates": checked_addresses(
            [{"url": item} for item in values.get("alt", [])], str(target["url"])
        ),
    }


def address_usable(url: str) -> bool:
    """Whether this phone would connect to the address: HTTP only on a private LAN or this phone."""
    try:
        endpoint_url(url, allow_lan=True)
    except ValueError:
        return False
    return _linkable(url)


def checked_addresses(items: object, primary: str) -> list[dict[str, str]]:
    """A desktop's other addresses: linkable, with the scheme of the paired one (a pinned certificate
    is for HTTPS), the primary left out and duplicates dropped. HTTP on Tailscale is kept to show
    that it needs HTTPS, but never used."""
    if not isinstance(items, list):
        return []
    scheme = urlsplit(primary).scheme
    found: list[dict[str, str]] = []
    seen = {primary}
    for item in items[:32]:
        url = item.get("url") if isinstance(item, dict) else None
        if not isinstance(url, str) or len(url) > 2048:
            continue
        try:
            normal = endpoint_url(url, allow_lan=True)
        except ValueError:
            parsed = urlsplit(url)
            # http://100.x.y.z (Tailscale without HTTPS): shown, not used.
            if parsed.scheme != "http" or not parsed.hostname or not _linkable(url):
                continue
            normal = urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))
        if urlsplit(normal).scheme != scheme or not _linkable(normal) or normal in seen:
            continue
        seen.add(normal)
        kind = item.get("kind") if isinstance(item, dict) else None
        address = _address(urlsplit(normal).hostname)
        if kind not in {"lan", "tailscale"}:
            kind = "tailscale" if address is not None and address in ipaddress.ip_network("100.64.0.0/10") else "lan"
        found.append({"url": normal, "kind": kind})
        if len(found) >= _MAX_ADDRESSES:
            break
    return found


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


_TLS_CONTEXTS: dict[str, ssl.SSLContext] = {}


def _tls_context(certificate_pem: str | None) -> ssl.SSLContext:
    """The TLS settings for a request, built once: loading a CA bundle for every request (a poll every
    20 seconds per computer) costs more than the request itself."""
    key = certificate_pem or ""
    context = _TLS_CONTEXTS.get(key)
    if context is None:
        context = pinned_context(certificate_pem) if certificate_pem else httpx.create_ssl_context()
        if len(_TLS_CONTEXTS) > 32:
            _TLS_CONTEXTS.clear()
        _TLS_CONTEXTS[key] = context
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
            # Added after the first release; older databases lack them. fingerprint/certificate: the
            # pinned certificate of a desktop paired over HTTPS. desktop_id, addresses (JSON) and
            # runtime (JSON, its last /mobile/runtime): a device link 2 desktop.
            for column, kind in (
                ("fingerprint", "TEXT"),
                ("certificate", "TEXT"),
                ("desktop_id", "TEXT"),
                ("addresses", "TEXT"),
                ("runtime", "TEXT"),
                ("runtime_at", "REAL"),
                ("last_ok_at", "REAL"),
            ):
                if column not in columns:
                    db.execute(f"ALTER TABLE mobile_hosts ADD COLUMN {column} {kind}")

    def _credentials(self):
        if self.credentials is None:
            from agent_workspace.credentials import default_credential_store

            self.credentials = default_credential_store()
        return self.credentials

    @staticmethod
    def _key(host_id: str):
        return f"agent-mobile-host:{host_id}"

    @staticmethod
    def _json(value: Any, fallback: Any) -> Any:
        try:
            loaded = json.loads(value) if value else fallback
        except ValueError:
            return fallback
        return loaded if isinstance(loaded, type(fallback)) else fallback

    @classmethod
    def _public(cls, row: sqlite3.Row) -> dict[str, Any]:
        document = dict(row)
        document.pop("certificate", None)
        runtime = cls._json(document.pop("runtime", None), {})
        addresses = cls._json(document.get("addresses"), [])
        document["addresses"] = [
            {**item, "usable": address_usable(item["url"])}
            for item in addresses
            if isinstance(item, dict) and isinstance(item.get("url"), str)
        ]
        features = runtime.get("features")
        scopes = runtime.get("scopes")
        document["device_link"] = runtime.get("device_link") if isinstance(runtime.get("device_link"), int) else None
        document["features"] = [item for item in features if isinstance(item, str)] if isinstance(features, list) else []
        document["scopes"] = [item for item in scopes if isinstance(item, str)] if isinstance(scopes, list) else []
        model = runtime.get("model")
        document["model"] = (
            {"name": str(model.get("name") or "")[:200], "location": "computer" if model.get("location") == "computer" else "cloud"}
            if isinstance(model, dict)
            else None
        )
        workspace = runtime.get("workspace")
        document["workspace"] = str(workspace.get("name") or "")[:200] if isinstance(workspace, dict) else None
        wake = runtime.get("wake")
        document["wake"] = bool(isinstance(wake, list) and wake)
        defaults = runtime.get("defaults")
        autonomy = defaults.get("autonomy") if isinstance(defaults, dict) else None
        # The settings a new conversation on the computer gets (a warning before "New conversation").
        document["new_conversation_autonomy"] = autonomy if autonomy in {"ask", "workspace", "yolo", "full_access"} else None
        return document

    def runtime(self, host_id: str) -> dict[str, Any]:
        """The host's last /mobile/runtime document as kept (wake targets included)."""
        return self._json(self._row(host_id)["runtime"], {})

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
        # Connecting is quick on a LAN or Tailscale; a computer that is away fails fast, so the next of
        # its addresses is tried within a page request's time.
        limits = httpx.Timeout(timeout, connect=min(float(timeout), 6.0))
        return httpx.AsyncClient(
            transport=self.transport, timeout=limits, follow_redirects=False, trust_env=False,
            verify=_tls_context(certificate),
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
        max_bytes: int = _RESPONSE_BYTES,
    ):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with (
            self._client(timeout, certificate) as client,
            client.stream(method, url + path, headers=headers, json=payload) as response,
        ):
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise ValueError(f"remote response exceeds {max_bytes // (1024 * 1024)} MiB")
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

    @staticmethod
    def _runtime_subset(runtime: dict[str, Any]) -> dict[str, Any]:
        return {key: runtime[key] for key in _RUNTIME_KEYS if key in runtime}

    async def _store(
        self,
        name: str,
        url: str,
        token: str,
        *,
        fingerprint: str | None,
        certificate: str | None,
        desktop_id: str | None = None,
        addresses: list[dict[str, str]] | None = None,
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
        except RemoteHTTPError as error:
            if error.status_code == 401:
                raise ValueError("the computer did not accept this token") from None
            raise
        api = "mobile" if code == 200 and runtime.get("idempotent_submissions") is True else "serve"
        kept = self._runtime_subset(runtime) if api == "mobile" else {}
        reported_id = runtime.get("desktop_id") if api == "mobile" else None
        if isinstance(reported_id, str) and _DESKTOP_ID.fullmatch(reported_id):
            desktop_id = reported_id
        known = list(addresses or [])
        if api == "mobile":
            known += runtime.get("addresses") if isinstance(runtime.get("addresses"), list) else []
        kept_addresses = checked_addresses(known, url)
        existing = next((host for host in self.list() if host["url"] == url), None)
        if existing is None and desktop_id:
            # The same desktop paired again at another address: keep one entry for it.
            existing = next((host for host in self.list() if host.get("desktop_id") == desktop_id), None)
        host_id = existing["host_id"] if existing else str(uuid4())
        self._credentials().set(self._key(host_id), token)
        now = time.time()
        with connection_database(self.path) as db:
            if existing is not None:
                db.execute(
                    "UPDATE mobile_hosts SET url=?, name=?, api=?, fingerprint=?, certificate=?, desktop_id=?, "
                    "addresses=?, runtime=?, runtime_at=?, last_ok_at=? WHERE host_id=?",
                    (url, name.strip(), api, fingerprint, certificate, desktop_id, json.dumps(kept_addresses),
                     json.dumps(kept), now, now, host_id),
                )
            else:
                db.execute(
                    "INSERT INTO mobile_hosts (host_id, url, name, api, paired_at, fingerprint, certificate, "
                    "desktop_id, addresses, runtime, runtime_at, last_ok_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (host_id, url, name.strip(), api, now, fingerprint, certificate, desktop_id,
                     json.dumps(kept_addresses), json.dumps(kept), now, now),
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
        fingerprint = target["fingerprint"]
        unreachable = "could not reach the computer; check that both are on the same network or Tailscale"
        # The link's other addresses of the computer (another network adapter, Tailscale): tried in
        # turn when the first cannot be reached. A certificate that does not match stops it.
        candidates = [str(target["url"]), *(item["url"] for item in target.get("alternates") or []
                                             if address_usable(item["url"]))]
        for index, url in enumerate(candidates):
            last = index == len(candidates) - 1
            try:
                certificate = await self._pinned(url, fingerprint)
                _, paired = await self._request(
                    url, None, "POST", "/pair", {"code": target["code"], "name": device_name}, certificate=certificate
                )
                break
            except RemoteHTTPError as error:
                if error.code == "pairing_code_invalid":
                    raise ValueError("the pairing code is wrong; check it, or show a new one on the computer") from None
                if error.code == "pairing_unavailable":
                    raise ValueError("the computer is not waiting for a phone; show the pairing QR code on it again") from None
                if error.code == "too_many_attempts":
                    raise ValueError("too many attempts; wait a minute and show a new pairing code on the computer") from None
                raise
            except httpx.HTTPError:
                if last:
                    raise ValueError(unreachable) from None
            except ValueError as error:
                if last or str(error) != unreachable:
                    raise
        token = paired.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("the computer did not return a token")
        name = str(paired.get("name") or target.get("name") or "Agent Workspace")[:100]
        reported = paired.get("addresses") if isinstance(paired.get("addresses"), list) else []
        desktop_id = paired.get("desktop_id") if isinstance(paired.get("desktop_id"), str) else target.get("desktop_id")
        host = await self._store(
            name,
            url,
            token,
            fingerprint=fingerprint,
            certificate=certificate,
            desktop_id=desktop_id if isinstance(desktop_id, str) and _DESKTOP_ID.fullmatch(desktop_id) else None,
            addresses=[{"url": str(target["url"])}, *(target.get("alternates") or []), *reported],
        )
        return {**host, "scopes": [scope for scope in paired.get("scopes") or [] if isinstance(scope, str)]}

    def remove(self, host_id: str) -> bool:
        self.get(host_id)
        self._credentials().delete(self._key(host_id))
        with connection_database(self.path) as db:
            return db.execute("DELETE FROM mobile_hosts WHERE host_id=?", (host_id,)).rowcount == 1

    async def unpair_remote(self, host_id: str) -> bool:
        """Ask the desktop to forget this phone (device link 2); False when it could not be told."""
        if "device" not in self.get(host_id)["features"]:
            return False
        try:
            await self.request(host_id, "POST", "/mobile/device/unpair", {}, timeout=8)
        except (httpx.HTTPError, ValueError):
            return False
        return True

    def _candidates(self, host: sqlite3.Row) -> list[str]:
        """The addresses to try, the one that answered last first, then LAN before Tailscale."""
        others = [
            item
            for item in self._json(host["addresses"], [])
            if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"] != host["url"]
        ]
        others.sort(key=lambda item: item.get("kind") == "tailscale")
        return [host["url"], *(item["url"] for item in others if address_usable(item["url"]))]

    def _answered(self, host_id: str, url: str) -> None:
        with connection_database(self.path) as db:
            current = db.execute("SELECT url, addresses FROM mobile_hosts WHERE host_id=?", (host_id,)).fetchone()
            if current is None:
                return
            if current["url"] == url:
                db.execute("UPDATE mobile_hosts SET last_ok_at=? WHERE host_id=?", (time.time(), host_id))
                return
            # Another address answered: it becomes the one tried first; the old one stays a fallback.
            addresses = [item for item in self._json(current["addresses"], []) if isinstance(item, dict)]
            addresses = [item for item in addresses if item.get("url") != url]
            addresses.insert(0, {"url": current["url"]})
            try:
                db.execute(
                    "UPDATE mobile_hosts SET url=?, addresses=?, last_ok_at=? WHERE host_id=?",
                    (url, json.dumps(checked_addresses(addresses, url)), time.time(), host_id),
                )
            except sqlite3.IntegrityError:
                db.execute("UPDATE mobile_hosts SET last_ok_at=? WHERE host_id=?", (time.time(), host_id))

    def use_address(self, host_id: str, url: object) -> dict[str, Any]:
        """Move a host to an address the user confirmed (a desktop found at a new LAN address)."""
        host = self._row(host_id)
        address = endpoint_url(url, allow_lan=True)
        if not _linkable(address) or urlsplit(address).scheme != urlsplit(host["url"]).scheme:
            raise ValueError("pairing works with a computer on this network or on Tailscale")
        self._answered(host_id, address)
        return self.get(host_id)

    async def request(
        self, host_id: str, method: str, path: str, payload=None, *, timeout=15, max_bytes: int = _RESPONSE_BYTES
    ):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("invalid remote route")
        host = self._row(host_id)
        token = self._credentials().get(self._key(host_id))
        if not token:
            raise ValueError("host credential is unavailable; pair the host again")
        failure: BaseException | None = None
        for url in self._candidates(host):
            try:
                answer = await self._request(
                    url, token, method, path, payload, timeout=timeout, certificate=host["certificate"],
                    max_bytes=max_bytes,
                )
            except _UNSENT as error:
                # Never reached the desktop at this address: the next one gets the same request.
                failure = failure if isinstance(failure, httpx.ConnectError) and _pinning_failed(failure) else error
                continue
            self._answered(host_id, url)
            return answer
        assert failure is not None
        raise failure

    async def refresh_runtime(self, host_id: str) -> dict[str, Any]:
        """The desktop's current runtime document (features, scopes, addresses), kept with the host."""
        _, runtime = await self.request(host_id, "GET", "/mobile/runtime")
        host = self._row(host_id)
        reported = runtime.get("addresses") if isinstance(runtime.get("addresses"), list) else []
        kept = self._json(host["addresses"], [])
        desktop_id = runtime.get("desktop_id")
        with connection_database(self.path) as db:
            db.execute(
                "UPDATE mobile_hosts SET runtime=?, runtime_at=?, addresses=?, desktop_id=COALESCE(?, desktop_id) "
                "WHERE host_id=?",
                (
                    json.dumps(self._runtime_subset(runtime)),
                    time.time(),
                    json.dumps(checked_addresses([*reported, *kept], host["url"])),
                    desktop_id if isinstance(desktop_id, str) and _DESKTOP_ID.fullmatch(desktop_id) else None,
                    host_id,
                ),
            )
        return self.get(host_id)

    async def upload(
        self, host_id: str, path: str, source: Path, *, sha256: str, timeout: float = 600
    ) -> dict[str, Any]:
        """PUT a file's bytes (streamed) to the desktop; the route carries name, size and checksum."""
        host = self._row(host_id)
        token = self._credentials().get(self._key(host_id))
        if not token:
            raise ValueError("host credential is unavailable; pair the host again")
        size = source.stat().st_size

        async def chunks():
            with source.open("rb") as stream:
                for block in iter(lambda: stream.read(256 * 1024), b""):
                    yield block

        failure: BaseException | None = None
        for url in self._candidates(host):
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(size),
                "X-Content-SHA256": sha256,
            }
            try:
                async with self._client(timeout, host["certificate"]) as client:
                    response = await client.put(url + path, headers=headers, content=chunks())
            except _UNSENT as error:
                failure = error
                continue
            self._answered(host_id, url)
            if response.status_code < 200 or response.status_code >= 300:
                raise RemoteHTTPError(response.status_code, _remote_error(response.content[:4096]))
            try:
                data = response.json()
            except ValueError:
                raise ValueError("remote host returned invalid JSON") from None
            if not isinstance(data, dict):
                raise ValueError("remote host returned an invalid document")
            return data
        assert failure is not None
        raise failure

    async def download(
        self, host_id: str, path: str, target: Path, *, max_bytes: int, timeout: float = 600
    ) -> dict[str, Any]:
        """GET a file into ``target`` (written beside it first, then moved), checking its size and the
        X-Content-SHA256 the desktop sends. Returns {"size", "sha256"}."""
        host = self._row(host_id)
        token = self._credentials().get(self._key(host_id))
        if not token:
            raise ValueError("host credential is unavailable; pair the host again")
        partial = target.with_name(f".{target.name}.part")
        failure: BaseException | None = None
        for url in self._candidates(host):
            try:
                async with (
                    self._client(timeout, host["certificate"]) as client,
                    client.stream("GET", url + path, headers={"Authorization": f"Bearer {token}"}) as response,
                ):
                    if response.status_code < 200 or response.status_code >= 300:
                        await response.aread()
                        raise RemoteHTTPError(response.status_code, _remote_error(response.content[:4096]))
                    digest, size = hashlib.sha256(), 0
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        with partial.open("wb") as stream:
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > max_bytes:
                                    raise ValueError(f"the file is larger than {max_bytes // (1024 * 1024)} MiB")
                                digest.update(chunk)
                                stream.write(chunk)
                        expected = (response.headers.get("X-Content-SHA256") or "").strip().lower()
                        if expected and not hmac.compare_digest(expected, digest.hexdigest()):
                            raise ValueError("the file arrived damaged; try again")
                        partial.replace(target)
                    finally:
                        partial.unlink(missing_ok=True)
            except _UNSENT as error:
                failure = error
                continue
            self._answered(host_id, url)
            return {"size": size, "sha256": digest.hexdigest()}
        assert failure is not None
        raise failure

    async def sessions(self, host_id: str):
        _, document = await self.request(host_id, "GET", "/sessions")
        return document

    async def events(self, host_id: str, session_id: str):
        _, document = await self.request(
            host_id, "GET", f"/sessions/{quote(session_id, safe='')}/events"
        )
        return document
