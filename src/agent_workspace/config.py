from __future__ import annotations

import hashlib
import ipaddress
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse


class ProviderProtocol(StrEnum):
    OPENAI_COMPATIBLE = "openai-compatible"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


_DEFAULT_BASE_URLS = {
    ProviderProtocol.OPENAI_COMPATIBLE: "https://api.openai.com/v1",
    ProviderProtocol.ANTHROPIC: "https://api.anthropic.com/v1",
    ProviderProtocol.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
    ProviderProtocol.OLLAMA: "http://127.0.0.1:11434",
}


def provider_origin(base_url: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(base_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("provider base URL must be an absolute HTTP(S) URL") from None

    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError("provider base URL must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("provider base URL may not include userinfo")
    if "?" in base_url:
        raise ValueError("provider base URL may not include a query")
    if "#" in base_url:
        raise ValueError("provider base URL may not include a fragment")
    if parsed.scheme == "http" and hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("unencrypted provider endpoints are only allowed on loopback")

    default_port = 80 if parsed.scheme == "http" else 443
    return parsed.scheme, hostname, port if port is not None else default_port


def is_loopback_endpoint(base_url: str, *, allow_localhost_name: bool = True) -> bool:
    _, hostname, _ = provider_origin(base_url)
    if allow_localhost_name and hostname.rstrip(".").lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    id: str
    base_url: str
    model: str
    api_key: str | None = None
    protocol: ProviderProtocol = ProviderProtocol.OPENAI_COMPATIBLE

    def validate(self) -> None:
        provider_origin(self.base_url)
        if not self.id.strip():
            raise ValueError("provider id may not be empty")
        if not self.model.strip():
            raise ValueError("model may not be empty")

    @classmethod
    def from_environment(
        cls,
        *,
        provider_id: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        protocol: str | ProviderProtocol | None = None,
    ) -> ProviderConfig:
        environment_protocol = ProviderProtocol(
            os.getenv("AGENT_WORKSPACE_PROTOCOL") or ProviderProtocol.OPENAI_COMPATIBLE
        )
        resolved_protocol = ProviderProtocol(protocol or environment_protocol)
        environment_base_url = os.getenv("AGENT_WORKSPACE_BASE_URL")
        default_base_url = _DEFAULT_BASE_URLS[resolved_protocol]
        resolved_base_url = base_url or environment_base_url or default_base_url
        api_key = os.getenv("AGENT_WORKSPACE_API_KEY")
        if api_key:
            key_base_url = environment_base_url or _DEFAULT_BASE_URLS[environment_protocol]
            try:
                key_origin = provider_origin(key_base_url)
                resolved_origin = provider_origin(resolved_base_url)
            except ValueError:
                api_key = None
            else:
                if key_origin != resolved_origin:
                    api_key = None

        config = cls(
            id=provider_id or os.getenv("AGENT_WORKSPACE_PROVIDER") or "openai-compatible",
            base_url=resolved_base_url,
            model=model or os.getenv("AGENT_WORKSPACE_MODEL") or "",
            api_key=api_key,
            protocol=resolved_protocol,
        )
        config.validate()
        return config


def default_data_dir() -> Path:
    configured = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AgentWorkspace"
    return Path.home() / ".agent-workspace"


def default_database_path() -> Path:
    return default_data_dir() / "data" / "agent.db"


def default_workspace_catalog_path() -> Path:
    """Return the durable list of recently used workspace directories."""
    return default_data_dir() / "workspaces.json"


def workspace_database_path(workspace: str | Path) -> Path:
    """Return a stable per-workspace database path.

    Workspaces keep separate event stores so long-running sessions in one
    workspace never block sessions in another on the global writer lock.
    """
    root = Path(workspace).expanduser().resolve()
    digest = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:16]
    return default_data_dir() / "workspaces" / f"{digest}.db"


def default_writer_lock_path() -> Path:
    return default_data_dir() / "data" / "writer.lock"


def database_writer_lock_path(database: str | Path) -> Path:
    """Return a writer lock path scoped to a specific database file."""
    db_path = Path(database).expanduser().resolve()
    digest = hashlib.sha256(str(db_path).casefold().encode("utf-8")).hexdigest()[:16]
    lock_dir = default_data_dir() / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"{digest}.lock"


def default_backup_dir() -> Path:
    return default_data_dir() / "backups"
