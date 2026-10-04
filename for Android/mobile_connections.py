"""Authenticated remote Serve hosts. Tokens remain in the platform credential store."""

from __future__ import annotations

import ipaddress
import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4

import httpx


class RemoteHTTPError(ValueError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"remote host returned HTTP {status_code}")


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
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        networks = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
        private = address is not None and any(address in ipaddress.ip_network(n) for n in networks)
        loopback = parsed.hostname == "localhost" or bool(address and address.is_loopback)
        if not loopback and not (allow_lan and private):
            raise ValueError("HTTP requires an explicitly enabled private LAN IP; use HTTPS")
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


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

    def _credentials(self):
        if self.credentials is None:
            from agent_workspace.credentials import default_credential_store

            self.credentials = default_credential_store()
        return self.credentials

    @staticmethod
    def _key(host_id: str):
        return f"agent-mobile-host:{host_id}"

    def list(self) -> list[dict[str, Any]]:
        with connection_database(self.path) as db:
            return [
                dict(row) for row in db.execute("SELECT * FROM mobile_hosts ORDER BY name, host_id")
            ]

    def get(self, host_id: str) -> dict[str, Any]:
        with connection_database(self.path) as db:
            row = db.execute("SELECT * FROM mobile_hosts WHERE host_id=?", (host_id,)).fetchone()
        if row is None:
            raise KeyError("unknown paired host")
        return dict(row)

    async def _request(
        self,
        url: str,
        token: str,
        method: str,
        path: str,
        payload=None,
        *,
        timeout=15,
        allow_not_found=False,
    ):
        async with (
            httpx.AsyncClient(
                transport=self.transport, timeout=timeout, follow_redirects=False, trust_env=False
            ) as client,
            client.stream(
                method, url + path, headers={"Authorization": f"Bearer {token}"}, json=payload
            ) as response,
        ):
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError("remote response exceeds 4 MiB")
            if response.status_code == 404 and allow_not_found:
                return response.status_code, {}
            if response.status_code < 200 or response.status_code >= 300:
                raise RemoteHTTPError(response.status_code)
            try:
                data = json.loads(body)
            except (ValueError, UnicodeError):
                raise ValueError("remote host returned invalid JSON") from None
            if not isinstance(data, dict):
                raise ValueError("remote host returned an invalid document")
            return response.status_code, data

    async def pair(self, payload: dict[str, Any]) -> dict[str, Any]:
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
        try:
            _, sessions = await self._request(url, token, "GET", "/sessions")
            if not isinstance(sessions.get("sessions"), list):
                raise ValueError("host does not expose the Agent Serve API")
            code, runtime = await self._request(
                url, token, "GET", "/mobile/runtime", allow_not_found=True
            )
        except httpx.HTTPError:
            raise ValueError("could not authenticate or connect to the remote host") from None
        api = "mobile" if code == 200 and runtime.get("idempotent_submissions") is True else "serve"
        existing = next((host for host in self.list() if host["url"] == url), None)
        host_id = existing["host_id"] if existing else str(uuid4())
        self._credentials().set(self._key(host_id), token)
        with connection_database(self.path) as db:
            db.execute(
                "INSERT INTO mobile_hosts VALUES (?,?,?,?,?) ON CONFLICT(url) "
                "DO UPDATE SET name=excluded.name, api=excluded.api",
                (host_id, url, name.strip(), api, time.time()),
            )
        return self.get(host_id)

    def remove(self, host_id: str) -> bool:
        self.get(host_id)
        self._credentials().delete(self._key(host_id))
        with connection_database(self.path) as db:
            return db.execute("DELETE FROM mobile_hosts WHERE host_id=?", (host_id,)).rowcount == 1

    async def request(self, host_id: str, method: str, path: str, payload=None, *, timeout=15):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("invalid remote route")
        host = self.get(host_id)
        token = self._credentials().get(self._key(host_id))
        if not token:
            raise ValueError("host credential is unavailable; pair the host again")
        return await self._request(host["url"], token, method, path, payload, timeout=timeout)

    async def sessions(self, host_id: str):
        _, document = await self.request(host_id, "GET", "/sessions")
        return document

    async def events(self, host_id: str, session_id: str):
        _, document = await self.request(
            host_id, "GET", f"/sessions/{quote(session_id, safe='')}/events"
        )
        return document
