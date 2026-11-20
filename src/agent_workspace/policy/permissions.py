from __future__ import annotations

import hashlib
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ApprovalDecision
from agent_workspace.core.autonomy_escalation import AutonomyEscalationPolicy
from agent_workspace.core.models import ApprovalScope, Autonomy, ToolSpec
from agent_workspace.policy.argument_rules import ToolArgumentPolicy
from agent_workspace.tools.paths import (
    PathOutsideWorkspaceError,
    StrPath,
    UnsafePathError,
    WorkspacePathError,
    WorkspacePaths,
    is_sensitive_workspace_path,
)

ApprovalResult = ApprovalDecision

_LOGGER = logging.getLogger(__name__)
_LOCATION_KEYS = ("source", "destination", "repository", "cwd", "path")
# Files of .agent that instruct the agent or act on their own, with the file used of each kind
# (the first found). They get the consent MCP servers and custom tools get: a cloned folder or an
# earlier turn may have written them.
_WORKSPACE_FILES = (
    ("optimizations", ("optimizations.json", "optimizations.toml")),
    ("prompt_assembly", ("prompt-assembly.json",)),
    ("schedule", ("schedule.toml",)),
    ("openapi", ("openapi.json",)),
)
WORKSPACE_FILE_KINDS = frozenset(kind for kind, _names in _WORKSPACE_FILES)
_MAX_WORKSPACE_FILE_BYTES = 1024 * 1024
# Native actions with a fixed effect, not general command execution. add_calendar_event (the
# Android app) writes one event to the user's calendar after a one-time approval.
# Process tools whose command the model does not write: run_checks runs the commands the user
# set up for the folder.
_FIXED_COMMAND_PROCESS_TOOLS = frozenset({"speak_text", "add_calendar_event", "run_checks"})
# What outlasts the turn and comes back as context later: refused in a distrusted session.
_LASTING_TOOLS = frozenset({"knowledge_add", "memory_write"})


type ApprovalValue = ApprovalResult | bool
type ApprovalCallback = Callable[
    [ToolSpec, dict[str, Any]], ApprovalValue | Awaitable[ApprovalValue]
]


@dataclass(frozen=True, slots=True)
class YoloRules:
    """What YOLO mode allows on a platform. The defaults fit one with run_sandbox for commands."""

    # No run_sandbox on this platform, so YOLO's commands run as host processes.
    host_process: bool = False
    # Effects asked about as in workspace mode. Any other unknown effect is refused.
    ask_effects: frozenset[str] = frozenset()


DEFAULT_YOLO_RULES = YoloRules()


@dataclass(frozen=True, slots=True)
class WorkspaceExtensionRequest:
    kind: str  # "mcp", "custom_tool" or one of WORKSPACE_FILE_KINDS
    identifier: str
    command: tuple[str, ...]
    cwd: str
    config_source: str
    config_digest: str
    executable_sha256: str = ""
    # The configuration lets YOLO mode run this extension's tools without asking (`yolo = true`):
    # the approval says so, and its digest covers it.
    yolo: bool = False


class ExtensionApprovalRequiredError(PermissionError):
    pass


type ExtensionApprovalCallback = Callable[[WorkspaceExtensionRequest], bool | Awaitable[bool]]


def compute_extension_digest(
    command: Sequence[str],
    cwd: str,
    config_source: str,
    executable_sha256: str = "",
    *,
    command_files: dict[str, str] | None = None,
    yolo: bool = False,
) -> str:
    """What an approval is bound to, as structured data: a joined string could read two
    different (command, cwd) pairs, with colons in Windows paths, as the same."""
    payload: dict[str, Any] = {
        "command": list(command),
        "cwd": cwd,
        "config": config_source,
        "executable_sha256": executable_sha256,
        "command_files": dict(sorted((command_files or {}).items())),
    }
    if yolo:
        # Turning `yolo = true` on is asked about again; without it the digest is as before, so
        # existing approvals stay valid.
        payload["yolo"] = True
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


_MAX_COMMAND_FILE_BYTES = 32 * 1024 * 1024


def _workspace_command_files(command: Sequence[str], workspace_path: Path) -> dict[str, str]:
    """The content of each file of the workspace a command names (["node", "tools/server.js"]):
    an approval binds to it, so a script the agent rewrote after the approval, which a
    checkpointed write allows without asking, is asked about again before it runs."""
    try:
        paths = WorkspacePaths(workspace_path)
    except WorkspacePathError:
        return {}
    found: dict[str, str] = {}
    for argument in command[:64]:
        if not isinstance(argument, str) or not argument or "\x00" in argument:
            continue
        try:
            candidate = paths.resolve(argument)
            if not candidate.is_file():
                continue
            size = candidate.stat().st_size
            relative = paths.relative(candidate)
            if size > _MAX_COMMAND_FILE_BYTES:
                found[relative] = f"size:{size}"
                continue
            found[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        except (WorkspacePathError, OSError):
            continue
    return found


def build_custom_tool_extension_request(
    cdef: Any,
    workspace_path: Path,
) -> WorkspaceExtensionRequest:
    command = (cdef.executable, *cdef.argv_template)
    config_source = cdef.path
    yolo = getattr(cdef, "yolo", False) is True
    digest = compute_extension_digest(
        command,
        str(workspace_path),
        config_source,
        executable_sha256=cdef.executable_sha256,
        command_files=_workspace_command_files(command, workspace_path),
        yolo=yolo,
    )
    return WorkspaceExtensionRequest(
        kind="custom_tool",
        identifier=cdef.name,
        command=command,
        cwd=str(workspace_path),
        config_source=config_source,
        config_digest=digest,
        executable_sha256=cdef.executable_sha256,
        yolo=yolo,
    )


def build_mcp_extension_request(
    server: Any,
    workspace_path: Path,
) -> WorkspaceExtensionRequest:
    command = tuple(server.command)
    config_source = str(workspace_path / ".agent" / "mcp.toml")
    yolo = getattr(server, "yolo", False) is True
    digest = compute_extension_digest(
        command,
        str(workspace_path),
        config_source,
        command_files=_workspace_command_files(command, workspace_path),
        yolo=yolo,
    )
    return WorkspaceExtensionRequest(
        kind="mcp",
        identifier=server.id,
        command=command,
        cwd=str(workspace_path),
        config_source=config_source,
        config_digest=digest,
        yolo=yolo,
    )


def _openapi_server(content: bytes) -> tuple[str, ...]:
    """Where an OpenAPI file's tools send requests, for the person asked to allow them."""
    try:
        url = json.loads(content)["servers"][0]["url"]
    except (ValueError, KeyError, IndexError, TypeError):
        return ()
    return (url,) if isinstance(url, str) else ()


def workspace_file_requests(
    workspace_path: Path, *, kinds: Collection[str] = WORKSPACE_FILE_KINDS
) -> list[WorkspaceExtensionRequest]:
    """A request for each such file of the folder, bound to its content."""
    requests: list[WorkspaceExtensionRequest] = []
    for kind, names in _WORKSPACE_FILES:
        path = next(
            (
                candidate
                for name in names
                if (candidate := workspace_path / ".agent" / name).is_file()
            ),
            None,
        )
        if kind not in kinds or path is None:
            continue
        if path.stat().st_size > _MAX_WORKSPACE_FILE_BYTES:
            _LOGGER.warning("ignoring %s: larger than %d bytes", path, _MAX_WORKSPACE_FILE_BYTES)
            continue
        content = path.read_bytes()
        command = _openapi_server(content) if kind == "openapi" else ()
        content_sha256 = hashlib.sha256(content).hexdigest()
        requests.append(
            WorkspaceExtensionRequest(
                kind=kind,
                identifier=f".agent/{path.name}",
                command=command,
                cwd=str(workspace_path),
                config_source=str(path),
                config_digest=compute_extension_digest(
                    command, str(workspace_path), str(path), executable_sha256=content_sha256
                ),
                executable_sha256=content_sha256,
            )
        )
    return requests


def workspace_file_decision(
    request: WorkspaceExtensionRequest,
    allow_workspace_extensions: bool,
    extension_approval_callback: ExtensionApprovalCallback | None,
) -> bool | Awaitable[bool]:
    if allow_workspace_extensions:
        return True
    if extension_approval_callback is None:
        raise ExtensionApprovalRequiredError(
            f"workspace file {request.identifier} requires authorization before it is used"
        )
    return extension_approval_callback(request)


class WorkspacePolicy:
    def __init__(
        self,
        workspace: WorkspacePaths | StrPath,
        autonomy: Autonomy = Autonomy.WORKSPACE,
        approval_callback: ApprovalCallback | None = None,
        *,
        argument_policy: ToolArgumentPolicy | None = None,
        autonomy_policy: AutonomyEscalationPolicy | None = None,
        grant_store_path: StrPath | None = None,
        session_grant_ttl_seconds: int = 3600,
        clock: Callable[[], float] = time.time,
        yolo_rules: YoloRules = DEFAULT_YOLO_RULES,
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.autonomy = autonomy
        self.yolo_rules = yolo_rules
        self.approval_callback = approval_callback
        self.argument_policy = argument_policy
        self.autonomy_policy = autonomy_policy
        self._session_grants: set[tuple[str, str]] = set()
        if (
            type(session_grant_ttl_seconds) is not int
            or not 1 <= session_grant_ttl_seconds <= 30 * 24 * 3600
        ):
            raise ValueError("session grant TTL must be from 1 second to 30 days")
        self._session_grant_ttl_seconds = session_grant_ttl_seconds
        self._grant_store_path = Path(grant_store_path) if grant_store_path is not None else None
        self._clock = clock
        self._session_grant_expiry: dict[tuple[str, str], float] = {}
        self._distrusted_sessions: set[str] = set()
        self._instructed_sessions: set[str] = set()
        self._load_session_grants()

    def remember_outside_instructions(self, session_id: str) -> None:
        """The session read outside content that talks to the agent. From then on, in later turns
        too, writing the workspace's instruction files or skills asks the user each time, whatever
        the autonomy: written now, the content would instruct every later conversation."""
        self._instructed_sessions.add(session_id)

    def writes_instructions(
        self, tool: ToolSpec, arguments: dict[str, Any], session_id: str | None
    ) -> bool:
        """Whether this call writes an instruction file or skill in a session that read outside
        content talking to the agent (remember_outside_instructions)."""
        if session_id not in self._instructed_sessions:
            return False
        if self._effect_kind(tool.side_effect) not in {"write", "move"}:
            return False
        # Here, not at the top: core.instructions imports the tools package, which imports this.
        from agent_workspace.core.instructions import INSTRUCTION_FILENAMES

        instruction_paths = {name.casefold() for name in INSTRUCTION_FILENAMES}
        for raw_path in self._raw_paths(tool, arguments):
            try:
                relative = self.paths.relative(raw_path).casefold()
            except WorkspacePathError:
                continue
            if relative in instruction_paths or relative.startswith(".agent/skills/"):
                return True
        return False

    def distrust_session(self, session_id: str) -> None:
        """Outside content talked to the agent: the session's grants go, and until its next turn
        every step asks, whatever the autonomy, and nothing lasting is written."""
        self._distrusted_sessions.add(session_id)
        self.revoke_session_grant(session_id)

    def trust_session_again(self, session_id: str) -> None:
        self._distrusted_sessions.discard(session_id)

    def session_distrusted(self, session_id: str | None) -> bool:
        return session_id in self._distrusted_sessions

    def grants_sandbox_for_session(self, arguments: dict[str, Any]) -> bool:
        """Whether this sandbox run can be allowed for the session, for the approval dialog."""
        return self.autonomy is Autonomy.WORKSPACE and not arguments.get("_sandbox_sensitive_count")

    async def authorize(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
        *,
        session_id: str | None = None,
        untrusted_context: bool = False,
    ) -> ApprovalResult:
        self._prune_session_grants()
        if self.argument_policy is not None:
            allowed, reason = self.argument_policy.evaluate(tool.name, arguments)
            if not allowed:
                return ApprovalResult(False, reason or "tool arguments denied by policy")
        effective_autonomy = self.autonomy
        if self.autonomy_policy is not None:
            granted_tools = (
                {
                    name
                    for granted_session, name in self._session_grants
                    if granted_session == session_id
                }
                if session_id is not None
                else frozenset()
            )
            effective_autonomy = self.autonomy_policy.effective_autonomy(
                self.autonomy,
                tool.name,
                frozenset(granted_tools),
            )
        effect = self._effect_kind(tool.side_effect)
        distrusted = session_id in self._distrusted_sessions
        if distrusted:
            if effect == "memory_write" or tool.name in _LASTING_TOOLS:
                return ApprovalResult(
                    False,
                    "outside content in this turn talked to the agent; nothing lasting is written",
                )
            effective_autonomy = Autonomy.ASK
        if effect == "session_state":
            effect = "read_state" if arguments.get("action") == "list" else "write_state"
            # The tool found, while preparing the call, that it removes or replaces something the
            # user kept (the phone's memory, app notes and skills): asked as a memory change.
            if arguments.get("_confirm_change"):
                effect = "memory_write"
        elif tool.name == "browser":
            action = arguments.get("action")
            if action in {"screenshot", "print_pdf"} and "path" in arguments:
                effect = "write"
            elif action in {"click", "type", "fill", "evaluate"}:
                effect = "network"
        if effect in {"none", ""}:
            return ApprovalResult(True, "tool has no side effects")
        if effect == "read_state":
            return ApprovalResult(True, "session state read is allowed")

        file_effect = effect in {
            "read",
            "write",
            "delete",
            "move",
            "mkdir",
            "git_read",
            "git_write",
        }
        location: bool | None = None
        if file_effect or effect in {"process", "sandboxed_process"}:
            location_result = self._paths_are_inside(tool, arguments)
            if isinstance(location_result, ApprovalResult):
                return location_result
            location = location_result
        raw_paths = self._raw_paths(tool, arguments)
        sensitive_path = (
            file_effect
            and any(
                is_sensitive_workspace_path(raw_path) or self._resolved_path_is_sensitive(raw_path)
                for raw_path in raw_paths
            )
        ) or (
            effect == "sandboxed_process"
            and isinstance(arguments.get("_sandbox_sensitive_count"), int)
            and arguments.get("_sandbox_sensitive_count", 0) > 0
        )
        if tool.name == "search_files" and arguments.get("include_sensitive") is True:
            sensitive_path = True
        sensitive_read = effect == "read" and sensitive_path

        if self.writes_instructions(tool, arguments, session_id):
            return await self._request_approval(
                tool,
                arguments,
                "this conversation read outside content that talks to the agent, and this file "
                "instructs every later conversation of the workspace: approve each write",
                grant_key=None,
            )

        if effective_autonomy is Autonomy.FULL_ACCESS:
            # Full access removes approval prompts for the explicitly selected
            # session, including sensitive files, host processes, network
            # tools, and writes.  _paths_are_inside still ran above, so
            # malformed paths, symlinks/reparse points, hard links, and other
            # hard validation failures remain fail-closed.  The boolean
            # containment result itself is intentionally not an authorization
            # gate in this mode; the tool implementation owns its own input
            # validation and the execution is recorded in the audit stream.
            return ApprovalResult(
                True,
                "Full access mode allows this operation without approval; audit recorded",
            )

        if effective_autonomy is Autonomy.YOLO and effect in self.yolo_rules.ask_effects:
            effective_autonomy = Autonomy.WORKSPACE

        if effective_autonomy is Autonomy.YOLO:
            # A workspace extension's tool (an MCP server's or a custom tool) runs in YOLO mode only
            # when its configuration says `yolo = true`, on every platform; it then goes on as any
            # other YOLO action, with the same record.
            if tool.yolo_opt_in is False and self.yolo_rules.host_process:
                return ApprovalResult(
                    False,
                    "YOLO mode does not run a workspace extension's tools (an MCP server's or a "
                    "custom tool) without asking, so this tool is not available now; it works in "
                    "workspace mode, where each call is approved",
                )
            if (
                effect == "process"
                and tool.name not in _FIXED_COMMAND_PROCESS_TOOLS
                and not self.yolo_rules.host_process
                and tool.yolo_opt_in is not True
            ):
                # Not "use run_sandbox": an MCP server's or custom tool cannot be redone there.
                return ApprovalResult(
                    False,
                    "YOLO mode starts no programs on this computer except through run_sandbox, "
                    "so this tool is not available now; it works in workspace mode, where each "
                    "call is approved",
                )
            allowed_effects = {
                "delete",
                "git_read",
                "git_write",
                "memory_write",
                "mkdir",
                "move",
                "network",
                "process",
                "read",
                "write",
                "write_state",
                "sandboxed_process",
            }
            if effect not in allowed_effects:
                return ApprovalResult(False, f"YOLO mode does not recognize side effect: {effect}")
            if (file_effect or effect in {"process", "sandboxed_process"}) and location is not True:
                return ApprovalResult(False, "operation is outside the workspace boundary")
            if sensitive_path:
                return await self._request_approval(
                    tool,
                    arguments,
                    "direct access to sensitive workspace data requires explicit approval",
                    grant_key=None,
                )
            return ApprovalResult(True, "YOLO mode autonomously allows this operation")

        if effect == "sandboxed_process":
            if location is not True:
                return ApprovalResult(False, "sandbox operation is outside the workspace boundary")
            if sensitive_path:
                return await self._request_approval(
                    tool,
                    arguments,
                    "sandbox access to sensitive workspace data requires one-time approval",
                    grant_key=None,
                )
            if effective_autonomy is Autonomy.WORKSPACE:
                # Only the workspace is a copy: the command runs on this computer, and its files
                # and the network are within reach. Asked once for a session, since a turn of
                # coding runs many.
                sandbox_grant = (
                    (session_id, tool.name) if session_id and not untrusted_context else None
                )
                if sandbox_grant is not None and sandbox_grant in self._session_grants:
                    return ApprovalResult(
                        True, "sandbox runs are approved for this session", ApprovalScope.SESSION
                    )
                return await self._request_approval(
                    tool,
                    arguments,
                    "a sandbox command runs on this computer and requires approval",
                    grant_key=sandbox_grant,
                )
            return await self._request_approval(
                tool,
                arguments,
                "ASK mode requires one-time approval for sandbox execution",
                grant_key=None,
            )

        if effect == "memory_write":
            return await self._request_approval(
                tool,
                arguments,
                "long-term workspace memory changes require explicit one-time approval",
                grant_key=None,
            )

        grant_key = (
            (session_id, tool.name)
            if session_id
            and not distrusted
            and not sensitive_path
            and (not file_effect or location is True)
            else None
        )
        if effect in {
            "delete",
            "git_read",
            "git_write",
            "mkdir",
            "move",
            "network",
            "process",
        }:
            return await self._request_approval(
                tool,
                arguments,
                f"{effect.replace('_', ' ')} requires explicit one-time approval",
                grant_key=None,
            )
        if untrusted_context and effect in {"write", "delete"}:
            return await self._request_approval(
                tool,
                arguments,
                "workspace data is untrusted; confirm the requested side effect",
                grant_key=None,
            )
        if grant_key is not None and grant_key in self._session_grants:
            return ApprovalResult(True, "tool is approved for this session", ApprovalScope.SESSION)

        if effective_autonomy is Autonomy.ASK:
            if effect == "read" and location is True and not sensitive_read:
                return ApprovalResult(True, "workspace read is allowed")
            reason = (
                "sensitive workspace reads require explicit approval"
                if sensitive_read
                else "ASK mode requires approval"
            )
            return await self._request_approval(tool, arguments, reason, grant_key=grant_key)

        if effective_autonomy is Autonomy.WORKSPACE:
            if effect == "write_state":
                return ApprovalResult(True, "current session state update is allowed")
            if effect == "read" and location is True and not sensitive_read:
                return ApprovalResult(True, "workspace read is allowed")
            if (
                effect == "write"
                and location is True
                and not sensitive_path
                and tool.durable_preimage_checkpoint
            ):
                return ApprovalResult(True, "workspace write has a durable rollback checkpoint")
            return await self._request_approval(
                tool,
                arguments,
                (
                    "workspace writes require approval until a durable rollback checkpoint exists"
                    if effect == "write" and location is True
                    else "sensitive workspace reads require explicit approval"
                    if sensitive_read
                    else f"{effect or 'unknown'} requires approval in workspace mode"
                ),
                grant_key=grant_key,
            )

        return ApprovalResult(False, f"unsupported autonomy mode: {effective_autonomy}")

    def _paths_are_inside(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
    ) -> bool | ApprovalResult:
        raw_paths = self._raw_paths(tool, arguments)
        if not raw_paths:
            if self._declared_location_keys(tool):
                return ApprovalResult(False, "file tools require a non-empty path")
            # Tools without any path-like parameter (e.g. speak_text, browser)
            # have no workspace-location constraint.
            return True
        for raw_path in raw_paths:
            try:
                self.paths.resolve(raw_path)
            except PathOutsideWorkspaceError:
                return False
            except (UnsafePathError, WorkspacePathError) as exc:
                return ApprovalResult(False, str(exc))
        return True

    @staticmethod
    def _declared_location_keys(tool: ToolSpec) -> frozenset[str]:
        if tool.name == "organize_files":
            return frozenset({"path"})  # a batch without paths is refused, never unbounded
        input_schema = tool.input_schema
        properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
        if not isinstance(properties, dict):
            return frozenset()
        return frozenset(key for key in _LOCATION_KEYS if key in properties)

    @staticmethod
    def _raw_paths(tool: ToolSpec, arguments: dict[str, Any]) -> tuple[str, ...]:
        if tool.name == "organize_files":
            # Every source and destination of the batch is checked, as for move_path.
            operations = arguments.get("operations")
            return tuple(
                value
                for operation in (operations if isinstance(operations, list) else ())
                if isinstance(operation, dict)
                for value in (operation.get("path"), operation.get("to"))
                if isinstance(value, str) and value
            )
        input_schema = tool.input_schema
        properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
        declared = properties if isinstance(properties, dict) else {}
        keys = (
            ("source", "destination")
            if tool.name == "move_path"
            # git_blame names a file besides the repository: checked for sensitive data too.
            else ("repository", "path")
            if tool.name.startswith("git_")
            else ("cwd",)
            if tool.name
            in {
                "run_process",
                "run_sandbox",
                "run_terminal",
                "start_background_job",
                "stop_background_job",
            }
            # Any other tool that runs in a folder (run_wsl): without cwd it runs in the
            # workspace, as the default says, rather than being refused for a missing path.
            or ("cwd" in declared and "path" not in declared)
            else ("cwd",)
            if isinstance(arguments.get("cwd"), str)
            else ("path",)
        )
        values: list[str] = []
        for key in keys:
            default = "." if key in {"cwd", "repository"} else None
            value = arguments.get(key, default)
            if isinstance(value, str) and value:
                values.append(value)
        # Lists of workspace files (git_diff, code_diagnostics): each one is checked too.
        listed = arguments.get("paths")
        if (tool.name.startswith("git_") or tool.name == "code_diagnostics") and isinstance(
            listed, list
        ):
            values.extend(value for value in listed if isinstance(value, str) and value)
        return tuple(values)

    def _resolved_path_is_sensitive(self, raw_path: str) -> bool:
        try:
            return is_sensitive_workspace_path(self.paths.relative(self.paths.resolve(raw_path)))
        except WorkspacePathError:
            return True

    async def _request_approval(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
        reason: str,
        *,
        grant_key: tuple[str, str] | None,
    ) -> ApprovalResult:
        if self.approval_callback is None:
            return ApprovalResult(False, reason)
        decision = self.approval_callback(tool, arguments)
        if inspect.isawaitable(decision):
            decision = await decision
        if isinstance(decision, bool):
            return ApprovalResult(
                decision,
                "approved by callback" if decision else reason,
                ApprovalScope.ONCE if decision else None,
            )
        if not isinstance(decision, ApprovalResult):
            return ApprovalResult(False, "approval callback returned an invalid result")
        if decision.allowed and decision.scope is None:
            decision = ApprovalResult(True, decision.reason, ApprovalScope.ONCE)
        if decision.allowed and decision.scope is ApprovalScope.SESSION and grant_key is not None:
            self._session_grants.add(grant_key)
            self._session_grant_expiry[grant_key] = self._clock() + self._session_grant_ttl_seconds
            self._save_session_grants()
        if decision.allowed and decision.scope is ApprovalScope.SESSION and grant_key is None:
            decision = ApprovalResult(True, decision.reason, ApprovalScope.ONCE)
        return decision

    def list_session_grants(self) -> tuple[dict[str, object], ...]:
        self._prune_session_grants()
        return tuple(
            {
                "session_id": session_id,
                "tool": tool_name,
                "expires_at": self._session_grant_expiry.get((session_id, tool_name)),
            }
            for session_id, tool_name in sorted(self._session_grants)
        )

    def revoke_session_grant(self, session_id: str, tool_name: str | None = None) -> int:
        targets = {
            key
            for key in self._session_grants
            if key[0] == session_id and (tool_name is None or key[1] == tool_name)
        }
        for key in targets:
            self._session_grants.discard(key)
            self._session_grant_expiry.pop(key, None)
        if targets:
            self._save_session_grants()
        return len(targets)

    def _prune_session_grants(self) -> None:
        now = self._clock()
        expired = {
            key
            for key in self._session_grants
            if self._session_grant_expiry.get(key, now + 1) <= now
        }
        if not expired:
            return
        for key in expired:
            self._session_grants.discard(key)
            self._session_grant_expiry.pop(key, None)
        self._save_session_grants()

    def _load_session_grants(self) -> None:
        if self._grant_store_path is None:
            return
        try:
            raw = json.loads(self._grant_store_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            return
        grants = raw.get("grants") if isinstance(raw, dict) else None
        if not isinstance(grants, list):
            return
        for item in grants:
            if not isinstance(item, dict):
                continue
            session_id = item.get("session_id")
            tool_name = item.get("tool")
            expires_at = item.get("expires_at")
            if (
                isinstance(session_id, str)
                and session_id
                and isinstance(tool_name, str)
                and tool_name
                and isinstance(expires_at, (int, float))
                and not isinstance(expires_at, bool)
            ):
                key = (session_id, tool_name)
                self._session_grants.add(key)
                self._session_grant_expiry[key] = float(expires_at)
        self._prune_session_grants()

    def _save_session_grants(self) -> None:
        if self._grant_store_path is None:
            return
        try:
            self._grant_store_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "grants": list(self.list_session_grants()),
            }
            temporary = self._grant_store_path.with_suffix(self._grant_store_path.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            temporary.replace(self._grant_store_path)
        except OSError:
            return

    @staticmethod
    def _effect_kind(side_effect: str) -> str:
        normalized = side_effect.strip().lower().replace("-", "_")
        return normalized.rsplit(":", maxsplit=1)[-1].removeprefix("filesystem_")
