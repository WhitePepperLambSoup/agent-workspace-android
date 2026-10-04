"""Durable, fail-closed consent for workspace MCP and custom extensions."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import tomllib
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.policy import (
    WorkspaceExtensionRequest,
    build_custom_tool_extension_request,
    build_mcp_extension_request,
)
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.custom import load_custom_tool_definitions
from agent_workspace.tools.mcp_host import load_mcp_servers

_MAX_ITEMS = 256
_MAX_STRING = 4096
_SECRET_ARG = re.compile(r"(?i)(token|secret|password|passwd|api[-_]?key|credential|auth)")


def _safe(value: object, limit: int = _MAX_STRING) -> str:
    text = str(value)
    return text[:limit]


def _canonical_config(source: Path) -> object:
    if not source.is_file() or source.stat().st_size > 512 * 1024:
        raise ValueError("extension configuration is missing or exceeds its size limit")
    try:
        raw = tomllib.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        try:
            return source.read_bytes()[: 512 * 1024]
        except OSError:
            return "missing"
    return raw


def canonical_extension_digest(
    request: WorkspaceExtensionRequest, workspace: str | os.PathLike[str]
) -> str:
    root = Path(workspace).resolve(strict=True)
    source = Path(request.config_source).expanduser().resolve()
    if request.kind not in {"mcp", "custom_tool"} or not request.identifier:
        raise ValueError("unsupported extension identity")
    try:
        source.relative_to(root / ".agent")
    except ValueError as exc:
        raise ValueError(
            "extension configuration must be inside the workspace .agent directory"
        ) from exc
    payload = {
        "kind": request.kind,
        "identifier": request.identifier,
        "command": list(request.command),
        "cwd": str(Path(request.cwd).resolve()),
        "workspace": str(root),
        "config_source": str(source),
        "config": _canonical_config(source),
        "executable_sha256": request.executable_sha256,
        "command_files": [],
    }
    for index, argument in enumerate(request.command[:64]):
        candidate = Path(argument).expanduser()
        if index == 0 and not candidate.is_absolute():
            discovered = shutil.which(argument)
            candidate = Path(discovered) if discovered else candidate
        elif not candidate.is_absolute():
            candidate = root / candidate
        try:
            if candidate.is_file():
                if candidate.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("extension command file exceeds its identity limit")
                payload["command_files"].append(
                    {
                        "argument": index,
                        "path": str(candidate.resolve()),
                        "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    }
                )
        except OSError:
            continue
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _public_command(command: tuple[str, ...] | list[str]) -> list[str]:
    from agent_workspace.policy.redaction import default_redactor

    if not command:
        return []
    result = []
    redact_next = False
    redactor = default_redactor()
    for value in command[:16]:
        text = str(value)
        if redact_next:
            result.append("<redacted>")
            redact_next = False
            continue
        if text.startswith("-") and _SECRET_ARG.search(text):
            key, separator, _ = text.partition("=")
            result.append(key + "=<redacted>" if separator else key)
            redact_next = not separator
            continue
        result.append(redactor.redact(text[:512]))
    return result


class _ConsentGuardTool:
    def __init__(
        self, tool: Any, store: MobileExtensionConsentStore, request_id: str, digest: str
    ) -> None:
        self._tool = tool
        self._store = store
        self._request_id = request_id
        self._digest = digest
        self.spec = tool.spec
        self.hard_cancellable = getattr(tool, "hard_cancellable", False)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tool, name)

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._store.require_authorized(self._request_id, self._digest)
        prepare = getattr(self._tool, "prepare_for_approval", None)
        return prepare(arguments) if prepare is not None else arguments

    async def execute(self, arguments: dict[str, Any]) -> str:
        self._store.require_authorized(self._request_id, self._digest)
        return await self._tool.execute(arguments)

    async def execute_with_context(self, arguments: dict[str, Any], context: Any) -> str:
        self._store.require_authorized(self._request_id, self._digest)
        execute = getattr(self._tool, "execute_with_context", None)
        return (
            await execute(arguments, context)
            if execute is not None
            else await self._tool.execute(arguments)
        )


class MobileExtensionConsentStore:
    """Persist approvals outside the workspace; absent or corrupt state denies."""

    def __init__(self, path: str | os.PathLike[str], workspace: str | os.PathLike[str]) -> None:
        self.path = Path(path).expanduser().resolve()
        self.workspace = Path(workspace).expanduser().resolve(strict=True)
        try:
            self.path.relative_to(self.workspace)
        except ValueError:
            pass
        else:
            raise ValueError("extension consent store must be outside the workspace")
        self._storage_error: str | None = None
        self._records: list[dict[str, Any]] = []
        self._active: set[str] = set()
        self._registry: Any = None
        self._configuration_errors: list[str] = []
        self._runtime_errors: dict[str, str] = {}
        self._startup_approved: set[str] = set()
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("oversized consent store")
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(raw, dict)
                or raw.get("version") != 1
                or not isinstance(raw.get("extensions"), list)
            ):
                raise ValueError("invalid consent store")
            records = raw["extensions"]
            if len(records) > _MAX_ITEMS or any(
                not isinstance(item, dict)
                or item.get("kind") not in {"mcp", "custom_tool"}
                or item.get("status") not in {"pending", "approved", "denied", "revoked"}
                or not isinstance(item.get("digest"), str)
                or re.fullmatch(r"[0-9a-f]{64}", item["digest"]) is None
                or not all(
                    isinstance(item.get(key), str) and len(item[key]) <= _MAX_STRING
                    for key in ("request_id", "identifier", "cwd", "config_source")
                )
                for item in records
            ):
                raise ValueError("invalid consent records")
            self._records = [dict(item) for item in records]
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._storage_error = "consent state could not be read safely"
            self._records = []

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "extensions": self._records}
        fd, temporary = tempfile.mkstemp(prefix=".extensions-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            with contextlib.suppress(OSError):
                self.path.chmod(0o600)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(temporary)

    def _request_record(self, request: WorkspaceExtensionRequest) -> dict[str, Any]:
        digest = canonical_extension_digest(request, self.workspace)
        return {
            "request_id": str(uuid4()),
            "kind": request.kind,
            "identifier": _safe(request.identifier, 128),
            "digest": digest,
            "status": "pending",
            "command": _public_command(request.command),
            "cwd": _safe(str(Path(request.cwd).resolve()), 1024),
            "config_source": _safe(request.config_source, 1024),
            "executable_sha256": _safe(request.executable_sha256, 128),
        }

    def _current_digest(self, record: dict[str, Any]) -> str | None:
        try:
            if str(record.get("kind")) == "mcp":
                for server in load_mcp_servers(self.workspace):
                    if server.id == record.get("identifier"):
                        return canonical_extension_digest(
                            build_mcp_extension_request(server, self.workspace), self.workspace
                        )
            else:
                for definition in load_custom_tool_definitions(self.workspace):
                    if definition.name == record.get("identifier"):
                        return canonical_extension_digest(
                            build_custom_tool_extension_request(definition, self.workspace),
                            self.workspace,
                        )
            return None
        except Exception:
            return None

    def authorize(self, request: WorkspaceExtensionRequest) -> bool:
        with self._lock:
            if self._storage_error:
                return False
            try:
                digest = canonical_extension_digest(request, self.workspace)
            except (OSError, ValueError):
                return False
            current = next(
                (
                    item
                    for item in self._records
                    if item.get("kind") == request.kind
                    and item.get("identifier") == request.identifier
                ),
                None,
            )
            if current is None:
                if len(self._records) >= _MAX_ITEMS:
                    return False
                self._records.append(self._request_record(request))
                self._write()
                return False
            if current.get("digest") != digest:
                request_id = current["request_id"]
                current.update(self._request_record(request))
                current["request_id"] = request_id
                self._write()
                self.disable_tools(self._registry)
                return False
            return current.get("status") == "approved"

    def authorize_runtime(self, request: WorkspaceExtensionRequest) -> bool:
        approved = self.authorize(request)
        if not approved:
            return False
        self._startup_approved.add(request.identifier)
        return True

    def decide(self, request_id: str, allowed: bool, expected_digest: str) -> dict[str, Any]:
        if type(allowed) is not bool:
            raise ValueError("allowed must be an explicit boolean decision")
        current = next(
            (item for item in self._records if item.get("request_id") == request_id), None
        )
        if current is None or current.get("digest") != expected_digest:
            raise ValueError("extension consent is stale; review the current configuration")
        if self._current_digest(current) != expected_digest:
            raise ValueError("extension configuration changed; review it again")
        current["status"] = "approved" if allowed else "denied"
        self._write()
        if not allowed:
            self.disable_tools(self._registry)
        return dict(current)

    def revoke(self, request_id: str, expected_digest: str) -> dict[str, Any]:
        current = next(
            (item for item in self._records if item.get("request_id") == request_id), None
        )
        if current is None or current.get("digest") != expected_digest:
            raise ValueError("extension consent is stale; refresh the extension list")
        current["status"] = "revoked"
        self._write()
        self.disable_tools(self._registry)
        return dict(current)

    def require_authorized(self, request_id: str, digest: str) -> None:
        with self._lock:
            current = next(
                (item for item in self._records if item.get("request_id") == request_id), None
            )
            if (
                self._storage_error
                or current is None
                or current.get("status") != "approved"
                or current.get("digest") != digest
            ):
                raise ToolError("workspace extension consent was revoked or is not authorized")
            if self._current_digest(current) != digest:
                current["status"] = "pending"
                self._write()
                raise ToolError(
                    "workspace extension configuration changed; new consent is required"
                )

    def bind_runtime(self, runtime: Any) -> None:
        """Guard approved custom tools and MCP proxies, including held references."""
        registry = getattr(
            getattr(getattr(runtime, "service", None), "runner", None), "_tools", None
        )
        self._registry = registry
        tools = getattr(registry, "_tools", {})
        for record in self._records:
            if record.get("status") != "approved":
                continue
            for name, tool in tuple(tools.items()):
                matches = (record["kind"] == "custom_tool" and name == record["identifier"]) or (
                    record["kind"] == "mcp"
                    and getattr(tool, "_server_id", None) == record["identifier"]
                )
                if matches:
                    tools[name] = _ConsentGuardTool(
                        tool, self, record["request_id"], record["digest"]
                    )
                    self._active.add(record["request_id"])

    def disable_tools(self, registry: Any) -> None:
        if registry is None:
            return
        tools = getattr(registry, "_tools", {})
        for name, tool in tuple(tools.items()):
            if not isinstance(tool, _ConsentGuardTool):
                continue
            current = next(
                (
                    record
                    for record in self._records
                    if record.get("request_id") == tool._request_id
                ),
                None,
            )
            if (
                current is None
                or current.get("status") != "approved"
                or current.get("digest") != tool._digest
            ):
                tools.pop(name, None)

    def refresh(self) -> None:
        """Discover new declarations and invalidate approvals whose configuration changed."""
        self._configuration_errors = []
        requests = []
        try:
            requests.extend(
                build_mcp_extension_request(server, self.workspace)
                for server in load_mcp_servers(self.workspace)
            )
        except Exception:
            self._configuration_errors.append(
                "MCP declarations could not be loaded; check .agent/mcp.toml"
            )
        try:
            requests.extend(
                build_custom_tool_extension_request(definition, self.workspace)
                for definition in load_custom_tool_definitions(self.workspace)
            )
        except Exception:
            self._configuration_errors.append(
                "Custom tools could not be loaded; check configuration and executable paths"
            )
            for path in sorted((self.workspace / ".agent" / "tools").glob("*.toml"))[:_MAX_ITEMS]:
                try:
                    raw = _canonical_config(path)
                    if not isinstance(raw, dict):
                        continue
                    command = raw.get("command")
                    name = raw.get("name")
                    if (
                        not isinstance(name, str)
                        or not isinstance(command, list)
                        or not command
                        or len(command) > 256
                        or not all(isinstance(item, str) and item for item in command)
                    ):
                        continue
                    requests.append(
                        WorkspaceExtensionRequest(
                            kind="custom_tool",
                            identifier=name,
                            command=tuple(command),
                            cwd=str(self.workspace),
                            config_source=str(path),
                            config_digest="",
                            executable_sha256=str(raw.get("executable_sha256", "")),
                        )
                    )
                    self._runtime_errors[name] = (
                        "The custom tool executable or configuration is unavailable in this runtime"
                    )
                except (OSError, ValueError):
                    continue
        for request in requests:
            self.authorize(request)

    def snapshot(self) -> dict[str, Any]:
        self.refresh()
        result = []
        for record in self._records:
            item = {
                key: record.get(key)
                for key in (
                    "request_id",
                    "kind",
                    "identifier",
                    "digest",
                    "status",
                    "command",
                    "cwd",
                    "config_source",
                )
            }
            was_active = record.get("request_id") in self._active
            item["active"] = was_active and record.get("status") == "approved"
            item["restart_required"] = (record.get("status") == "approved" and not was_active) or (
                was_active and not item["active"]
            )
            item["reason"] = (
                "Restart the engine to activate this extension"
                if record.get("status") == "approved" and not was_active
                else (
                    "Explicit approval is required" if record.get("status") == "pending" else None
                )
            )
            item["reason"] = (
                self._runtime_errors.get(str(record.get("identifier"))) or item["reason"]
            )
            result.append(item)
        return {
            "extensions": result,
            "restart_required": any(item["restart_required"] for item in result),
            "storage_error": self._storage_error,
            "configuration_errors": self._configuration_errors,
        }


async def build_mobile_runtime_async(
    workspace: Any,
    database: Any,
    provider_config: Any,
    *,
    extension_consents: MobileExtensionConsentStore,
    **options: Any,
) -> Any:
    """Keep the mobile API usable when declarations cannot load or a server fails startup."""
    from agent_workspace.application import runtime as core_runtime

    previous_mcp = core_runtime.load_mcp_servers
    previous_custom = core_runtime.load_custom_tool_definitions

    def mcp_servers(root: Any) -> Any:
        try:
            return load_mcp_servers(root)
        except Exception:
            extension_consents._configuration_errors.append(
                "MCP configuration is invalid and was suppressed at startup"
            )
            return ()

    def custom_tools(root: Any) -> Any:
        try:
            return load_custom_tool_definitions(root)
        except Exception:
            extension_consents._configuration_errors.append(
                "Custom tool configuration is invalid and was suppressed at startup"
            )
            return ()

    options.pop("extension_approval_callback", None)
    options.pop("allow_workspace_extensions", None)
    core_runtime.load_mcp_servers = mcp_servers
    core_runtime.load_custom_tool_definitions = custom_tools
    extension_consents.refresh()
    try:
        try:
            return await core_runtime.build_runtime_async(
                workspace,
                database,
                provider_config,
                extension_approval_callback=extension_consents.authorize_runtime,
                allow_workspace_extensions=False,
                **options,
            )
        except ToolError:
            if not extension_consents._startup_approved:
                raise
            for identifier in extension_consents._startup_approved:
                extension_consents._runtime_errors[identifier] = (
                    "Extension startup failed; verify its executable and MCP handshake, "
                    "then restart"
                )
            return await core_runtime.build_runtime_async(
                workspace,
                database,
                provider_config,
                extension_approval_callback=lambda request: False,
                allow_workspace_extensions=False,
                **options,
            )
    finally:
        core_runtime.load_mcp_servers = previous_mcp
        core_runtime.load_custom_tool_definitions = previous_custom


__all__ = [
    "MobileExtensionConsentStore",
    "build_mobile_runtime_async",
    "canonical_extension_digest",
]
