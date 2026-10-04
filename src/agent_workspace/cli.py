from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import multiprocessing
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from agent_workspace.application.runtime import ApplicationRuntime, build_runtime
from agent_workspace.config import (
    ProviderConfig,
    ProviderProtocol,
    default_backup_dir,
    default_data_dir,
    default_database_path,
    default_writer_lock_path,
)
from agent_workspace.core.agents import find_agent, load_agents
from agent_workspace.core.approval_batch import ApprovalBatchDecision, ApprovalBatchReviewer
from agent_workspace.core.audit_retention import AuditRetentionPolicy, apply_audit_retention
from agent_workspace.core.budgets import BudgetExceededError
from agent_workspace.core.build_cache import (
    build_artifact_get,
    build_artifact_prune,
    build_artifact_put,
    build_artifact_stats,
)
from agent_workspace.core.context_probe import context_window_probe
from agent_workspace.core.credential_health import credential_health_dashboard
from agent_workspace.core.database_integrity import database_integrity_check
from agent_workspace.core.disk_usage import workspace_disk_usage
from agent_workspace.core.event_replay_patch import event_replay_patch_document
from agent_workspace.core.events import Event
from agent_workspace.core.instructions import discover_workspace_instructions
from agent_workspace.core.models import (
    ApprovalScope,
    Autonomy,
    ChatMessage,
    DeltaKind,
    ImagePart,
    ImagePartError,
    Mode,
    ProviderEgressRequest,
    ProviderRequest,
    Role,
    TodoStatus,
    ToolSpec,
    validate_image_parts,
)
from agent_workspace.core.multi_session_search import merge_batch_search_results
from agent_workspace.core.process_limits import process_resource_report
from agent_workspace.core.prompt_batches import (
    load_prompt_batch,
    save_prompt_batch,
    summarize_prompt_batch_file,
)
from agent_workspace.core.prompt_injection import classify_prompt_injection
from agent_workspace.core.repo_map import build_repo_map_context
from agent_workspace.core.schedule_preview import schedule_next_runs
from agent_workspace.core.session import Session
from agent_workspace.core.skills import load_skills, render_skills_context
from agent_workspace.core.transcript_merge import merge_session_transcripts
from agent_workspace.core.workspace_env import WorkspaceEnvironment
from agent_workspace.credentials import credential_target
from agent_workspace.policy import (
    ApprovalRequiredError,
    ApprovalResult,
    ProviderEgressDeniedError,
)
from agent_workspace.policy.approval_display import approval_display_arguments
from agent_workspace.providers import ProviderError, create_provider
from agent_workspace.settings import (
    ProviderProfile,
    ProviderSettingsStore,
    default_provider_settings_store,
)
from agent_workspace.storage import (
    AlreadyRunningError,
    BackupValidationError,
    ProcessWriteLock,
    SearchIndexUnavailableError,
    SQLiteEventStore,
    create_verified_backup,
    export_session,
    import_session_archive,
    restore_verified_backup,
    validate_database,
    verify_backup,
    verify_session_archive,
)
from agent_workspace.tools.image import _detect_media_type

_CLI_SHUTDOWN_HARD_TIMEOUT_SECONDS = 30.0


def _start_shutdown_watchdog(
    completed: threading.Event,
    *,
    timeout: float = _CLI_SHUTDOWN_HARD_TIMEOUT_SECONDS,
    force_exit: Callable[[int], object] = os._exit,
) -> threading.Thread:
    """Give the CLI a process-level hard stop without weakening runtime fences."""

    def supervise() -> None:
        if not completed.wait(timeout):
            force_exit(1)

    watchdog = threading.Thread(
        target=supervise,
        name="agent-workspace-shutdown-watchdog",
        daemon=True,
    )
    watchdog.start()
    return watchdog


_WRITE_LOCK_EXIT = 4
_APPROVAL_REQUIRED_EXIT = 3


class ConsoleRenderer:
    def __init__(self, *, json_output: bool) -> None:
        self.json_output = json_output

    async def handle(self, event: Event) -> None:
        if self.json_output:
            print(
                json.dumps(
                    {
                        "id": event.id,
                        "session_id": event.session_id,
                        "sequence": event.sequence,
                        "schema_version": event.schema_version,
                        "type": event.type,
                        "data": event.data,
                        "causation_id": event.causation_id,
                        "correlation_id": event.correlation_id,
                        "created_at": event.created_at,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
            return
        if event.type == "model.output.delta" and event.data.get("kind") == "text":
            text = event.data.get("text")
            if isinstance(text, str):
                print(text, end="", flush=True)
        elif event.type == "tool.proposed":
            print(f"\n[tool] {event.data.get('name')}", file=sys.stderr, flush=True)
        elif event.type == "tool.rejected":
            print(f"[denied] {event.data.get('reason')}", file=sys.stderr, flush=True)
        elif event.type == "tool.failed":
            print(f"[tool failed] {event.data.get('error')}", file=sys.stderr, flush=True)


async def _console_approval(tool: ToolSpec, arguments: dict[str, Any]) -> ApprovalResult:
    if not sys.stdin.isatty():
        raise ApprovalRequiredError(f"approval required for tool: {tool.name}")
    print(f"\nApproval required: {tool.name}", file=sys.stderr)
    print(
        json.dumps(approval_display_arguments(tool, arguments), ensure_ascii=False, indent=2),
        file=sys.stderr,
    )
    try:
        answer = await asyncio.to_thread(input, "Allow once? [y/N] ")
    except EOFError as exc:
        raise ApprovalRequiredError(f"approval required for tool: {tool.name}") from exc
    allowed = answer.strip().lower() in {"y", "yes"}
    return ApprovalResult(
        allowed,
        "user decision",
        ApprovalScope.ONCE if allowed else None,
    )


async def _console_egress_approval(request: ProviderEgressRequest) -> ApprovalResult:
    if not sys.stdin.isatty():
        raise ApprovalRequiredError(
            f"Provider egress approval required for endpoint: {request.endpoint}"
        )
    print(f"\nProvider egress approval required: {request.endpoint}", file=sys.stderr)
    print(f"Data categories: {', '.join(request.data_categories)}", file=sys.stderr)
    try:
        answer = await asyncio.to_thread(input, "Allow for this session? [y/N] ")
    except EOFError as exc:
        raise ApprovalRequiredError(
            f"Provider egress approval required for endpoint: {request.endpoint}; "
            "run in an interactive terminal or use --autonomy yolo/full_access"
        ) from exc
    allowed = answer.strip().lower() in {"y", "yes"}
    return ApprovalResult(
        allowed,
        "user decision",
        ApprovalScope.SESSION if allowed else None,
    )


def _provider_config(args: argparse.Namespace) -> ProviderConfig:
    profile_id = cast(str | None, getattr(args, "profile", None))
    provider_id = cast(str | None, getattr(args, "provider", None))
    protocol = cast(str | ProviderProtocol | None, getattr(args, "protocol", None))
    base_url = cast(str | None, getattr(args, "base_url", None))
    model = cast(str | None, getattr(args, "model", None))
    if profile_id is not None:
        conflicting = {
            "--provider": provider_id,
            "--protocol": protocol,
            "--base-url": base_url,
            "--model": model,
        }
        used = [name for name, value in conflicting.items() if value is not None]
        if used:
            raise ValueError(f"--profile may not be combined with {', '.join(used)}")
        try:
            return _provider_settings_store().resolve_config(profile_id)
        except KeyError as exc:
            raise ValueError(str(exc)) from None
    return ProviderConfig.from_environment(
        provider_id=provider_id,
        base_url=base_url,
        model=model,
        protocol=protocol,
    )


def _provider_settings_store() -> ProviderSettingsStore:
    return default_provider_settings_store()


async def _open_runtime(
    args: argparse.Namespace,
    renderer: ConsoleRenderer,
    *,
    workspace: str,
    autonomy: Autonomy,
) -> tuple[ApplicationRuntime, ProviderConfig]:
    config = _provider_config(args)
    runtime = build_runtime(
        workspace,
        args.database,
        config,
        autonomy=autonomy,
        approval_callback=_console_approval,
        egress_approval_callback=_console_egress_approval,
        event_listener=renderer.handle,
        parallel_tool_calls=bool(getattr(args, "parallel_tool_calls", False)),
        profile_turns=bool(getattr(args, "profile_turns", False)),
        sqlite_synchronous=os.getenv("AGENT_WORKSPACE_SQLITE_SYNCHRONOUS", "FULL"),
    )
    return runtime, config


def _resolve_session_configuration(
    args: argparse.Namespace,
) -> tuple[str, Mode, Autonomy, Session | None]:
    workspace_arg = cast(str | None, args.workspace)
    mode_arg = cast(str | None, args.mode)
    autonomy_arg = cast(str | None, args.autonomy)
    session_id = cast(str | None, args.session)

    if session_id is None:
        return (
            workspace_arg or ".",
            Mode(mode_arg or Mode.CODING.value),
            Autonomy(autonomy_arg or Autonomy.WORKSPACE.value),
            None,
        )

    database = Path(cast(str, args.database))
    if not database.is_file():
        raise ValueError(f"unknown session: {session_id}")
    session = SQLiteEventStore.get_session_read_only(database, session_id)
    if session is None:
        raise ValueError(f"unknown session: {session_id}")

    if (
        workspace_arg is not None
        and Path(workspace_arg).resolve() != Path(session.workspace).resolve()
    ):
        raise ValueError(f"--workspace does not match session workspace: {session.workspace}")
    if autonomy_arg is not None and Autonomy(autonomy_arg) is not session.autonomy:
        raise ValueError(f"--autonomy does not match session autonomy: {session.autonomy.value}")

    return (
        session.workspace,
        Mode(mode_arg) if mode_arg is not None else session.mode,
        session.autonomy,
        session,
    )


def _turn_configuration(
    args: argparse.Namespace,
    workspace: str,
    mode: Mode,
) -> tuple[str, frozenset[str] | None, Mode]:
    root = Path(workspace).resolve()
    sections: list[str] = []
    allowed_tools: frozenset[str] | None = None
    agent_id = cast(str | None, getattr(args, "agent", None))
    if agent_id:
        agent = find_agent(root, agent_id)
        if agent is None:
            raise ValueError(f"unknown agent: {agent_id}")
        sections.append(agent.system_prompt)
        allowed_tools = agent.tool_allowlist
        if agent.mode is not None and cast(str | None, getattr(args, "mode", None)) is None:
            mode = Mode(agent.mode)
    if not getattr(args, "no_instructions", False):
        instructions = discover_workspace_instructions(root)
        if instructions:
            sections.append(instructions)
        skills_context = render_skills_context(load_skills(root))
        if skills_context:
            sections.append(skills_context)
    if getattr(args, "repo_map", False):
        repo_map = build_repo_map_context(
            root,
            limit=cast(int, getattr(args, "repo_map_limit", 120)),
        )
        if repo_map:
            sections.append(repo_map)
    return "\n\n".join(sections)[: 64 * 1024], allowed_tools, mode


def _load_cli_images(args: argparse.Namespace) -> tuple[ImagePart, ...]:
    raw_paths = cast(list[str] | None, getattr(args, "image", None))
    if not raw_paths:
        return ()
    parts: list[ImagePart] = []
    for raw_path in raw_paths:
        path = Path(raw_path)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"cannot read image: {path}") from exc
        media_type = _detect_media_type(data)
        if media_type is None:
            raise ValueError(f"unsupported image format: {path}")
        parts.append(ImagePart(media_type, data))
    images = tuple(parts)
    try:
        validate_image_parts(images)
    except ImagePartError as exc:
        raise ValueError(str(exc)) from None
    return images


async def _run_verification(workspace: str, command: str) -> tuple[int, str]:
    """Run a user-supplied verification command with the audited process contract."""
    from agent_workspace.tools.command import _run_command_sync
    from agent_workspace.tools.process_worker import run_in_process

    document = json.loads(
        await run_in_process(
            _run_command_sync,
            workspace,
            "powershell",
            None,
            [],
            command,
            ".",
            110,
            None,
            None,
            allow_children=True,
        )
    )
    exit_code = document.get("exit_code")
    stdout = document.get("stdout")
    stderr = document.get("stderr")
    stdout_text = stdout.get("text", "") if isinstance(stdout, dict) else ""
    stderr_text = stderr.get("text", "") if isinstance(stderr, dict) else ""
    output = f"{stdout_text}\n{stderr_text}".strip()[:12_000]
    return (exit_code if isinstance(exit_code, int) else 1), output


async def _run_once(args: argparse.Namespace) -> int:
    workspace, mode, autonomy, session = _resolve_session_configuration(args)
    system_suffix, allowed_tools, mode = _turn_configuration(args, workspace, mode)
    images = _load_cli_images(args)
    renderer = ConsoleRenderer(json_output=args.json)
    runtime, config = await _open_runtime(
        args,
        renderer,
        workspace=workspace,
        autonomy=autonomy,
    )
    primary_error: BaseException | None = None
    try:
        if session is None:
            session = runtime.service.create_session(
                workspace,
                mode=mode,
                autonomy=autonomy,
                title=args.prompt.strip()[:80] or "New session",
            )
        elif session.mode is not mode:
            await runtime.service.change_mode(session, mode)
        run_options: dict[str, Any] = {}
        if getattr(args, "no_instructions", False):
            run_options["include_instructions"] = False
            run_options["include_skills"] = False
        if system_suffix:
            run_options["system_suffix"] = system_suffix
        if allowed_tools is not None:
            run_options["allowed_tools"] = allowed_tools
        if images:
            run_options["images"] = images
        if getattr(args, "summarize_history", False):
            run_options["summarize_history"] = True
        await runtime.service.run(session, args.prompt, config.model, **run_options)
        verify_command = cast(str | None, getattr(args, "verify", None))
        fix_limit = cast(int, getattr(args, "fix_loop", 0))
        if verify_command and fix_limit > 0:
            for _iteration in range(fix_limit):
                exit_code, output = await _run_verification(workspace, verify_command)
                if exit_code == 0:
                    break
                await runtime.service.continue_run(
                    session,
                    config.model,
                    system_suffix=system_suffix,
                    allowed_tools=allowed_tools,
                    continuation_prompt=(
                        f"The verification command failed with exit code {exit_code}:\n"
                        f"{output}\nFix the workspace and the model will re-run verification."
                    ),
                )
        if not args.json:
            print()
        return 0
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        await _close_runtime(runtime, primary_error)


async def _chat(args: argparse.Namespace) -> int:
    if not sys.stdin.isatty():
        print("interactive chat requires a TTY", file=sys.stderr)
        return 2
    workspace, mode, autonomy, session = _resolve_session_configuration(args)
    system_suffix, allowed_tools, mode = _turn_configuration(args, workspace, mode)
    images = _load_cli_images(args)
    renderer = ConsoleRenderer(json_output=args.json)
    runtime, config = await _open_runtime(
        args,
        renderer,
        workspace=workspace,
        autonomy=autonomy,
    )
    primary_error: BaseException | None = None
    try:
        if session is None:
            session = runtime.service.create_session(
                workspace,
                mode=mode,
                autonomy=autonomy,
                title="Interactive session",
            )
        elif session.mode is not mode:
            await runtime.service.change_mode(session, mode)
        print(f"Session {session.id}. Enter /exit to quit.", file=sys.stderr)
        pending_images = images
        while True:
            try:
                prompt = await asyncio.to_thread(input, "> ")
            except EOFError:
                break
            if prompt.strip() in {"/exit", "/quit"}:
                break
            if not prompt.strip():
                continue
            run_options: dict[str, Any] = {}
            if getattr(args, "no_instructions", False):
                run_options["include_instructions"] = False
                run_options["include_skills"] = False
            if system_suffix:
                run_options["system_suffix"] = system_suffix
            if allowed_tools is not None:
                run_options["allowed_tools"] = allowed_tools
            if pending_images:
                run_options["images"] = pending_images
                pending_images = ()
            await runtime.service.run(session, prompt, config.model, **run_options)
            if not args.json:
                print()
        return 0
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        await _close_runtime(runtime, primary_error)


async def _close_runtime(
    runtime: ApplicationRuntime,
    primary_error: BaseException | None,
) -> None:
    shutdown_completed = threading.Event()
    _start_shutdown_watchdog(shutdown_completed)
    try:
        try:
            await runtime.aclose()
        except BaseException as exc:
            if primary_error is None:
                raise
            print(f"runtime close also failed: {exc}", file=sys.stderr)
    finally:
        shutdown_completed.set()
    backup_error = getattr(runtime, "backup_error", None)
    if isinstance(backup_error, str):
        print(f"runtime backup failed: {backup_error}", file=sys.stderr)


def _run_sessions(args: argparse.Namespace) -> int:
    database = Path(args.database).expanduser().resolve()
    if args.session_action == "verify":
        if args.session_value is None:
            raise ValueError("archive path is required for session verification")
        if args.output is not None or args.workspace is not None or args.limit != 50:
            raise ValueError("sessions verify accepts only an archive path and --json")
        validation = verify_session_archive(args.session_value)
        payload = asdict(validation)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.session_action == "import":
        if args.session_value is None:
            raise ValueError("archive path is required for session import")
        if args.workspace is None:
            raise ValueError("--workspace is required for session import")
        if args.output is not None or args.limit != 50:
            raise ValueError("--output and --limit are not valid for session import")
        database.parent.mkdir(parents=True, exist_ok=True)
        with ProcessWriteLock(default_writer_lock_path()), SQLiteEventStore(database) as store:
            imported = import_session_archive(store, args.session_value, args.workspace)
        payload = {
            "id": imported.id,
            "title": imported.title,
            "workspace": imported.workspace,
            "mode": imported.mode.value,
            "autonomy": imported.autonomy.value,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(imported.id)
        return 0
    if args.session_action == "cost":
        if args.session_value is None:
            raise ValueError("session id is required for cost reporting")
        if args.output is not None or args.limit != 50:
            raise ValueError("--output and --limit are not valid for cost reporting")
        return _sessions_cost(args)
    if args.session_action == "comment":
        if args.session_value is None or not args.comment:
            raise ValueError("session id and --comment are required for commenting")
        from agent_workspace.core.comments import add_comment

        with ProcessWriteLock(default_writer_lock_path()), SQLiteEventStore(database) as store:
            comment_id = add_comment(store, args.session_value, args.comment, "cli")
        print(comment_id)
        return 0
    if args.session_action == "comments":
        if args.session_value is None:
            raise ValueError("session id is required for listing comments")
        from agent_workspace.core.comments import list_comments

        with SQLiteEventStore(database) as store:
            comments = list_comments(store, args.session_value)
        if args.json:
            print(json.dumps(comments, ensure_ascii=False, sort_keys=True))
        else:
            for comment in comments:
                print(f"{comment['created_at']}\t{comment['author']}\t{comment['text']}")
        return 0
    if args.session_action == "fork":
        if args.session_value is None or args.workspace is None:
            raise ValueError("session id and --workspace are required for forking")
        import tempfile as _tempfile

        with _tempfile.TemporaryDirectory(prefix="agent-workspace-fork-") as temporary:
            archive = export_session(database, args.session_value, Path(temporary) / "fork.zip")
            with ProcessWriteLock(default_writer_lock_path()), SQLiteEventStore(database) as store:
                forked = import_session_archive(store, archive, args.workspace)
        if getattr(args, "snapshot", False):
            from agent_workspace.storage import snapshot_workspace_tree

            source_session = SQLiteEventStore.get_session_read_only(database, args.session_value)
            if source_session is None:
                raise KeyError(f"unknown session: {args.session_value}")
            snapshot_workspace_tree(source_session.workspace, args.workspace)
        print(forked.id)
        return 0
    if args.session_action == "checkpoints":
        if args.session_value is None:
            raise ValueError("session id is required for checkpoint reporting")
        from agent_workspace.storage import session_checkpoint_report

        report = session_checkpoint_report(database, args.session_value)
        if args.json:
            print(json.dumps(report, sort_keys=True))
        else:
            for item in report:
                print(f"{item['attempt_id']}\t{item['path']}")
        return 0
    if args.session_action == "export":
        if args.session_value is None:
            raise ValueError("session id is required for export")
        if args.output is None:
            raise ValueError("--output is required for export")
        if args.limit != 50:
            raise ValueError("--limit is only valid for session listing")
        if args.workspace is not None:
            raise ValueError("--workspace is not valid for session export")
        exported = export_session(database, args.session_value, args.output)
        if args.json:
            print(
                json.dumps(
                    {"path": str(exported), "session_id": args.session_value},
                    sort_keys=True,
                )
            )
        else:
            print(exported)
        return 0
    if args.session_action == "search":
        if args.session_value is None:
            raise ValueError("query is required for session search")
        if args.output is not None:
            raise ValueError("--output is only valid for session export")
        results = SQLiteEventStore.search_sessions_read_only(
            database,
            args.session_value,
            limit=args.limit,
            workspace=args.workspace,
        )
        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "id": result.session.id,
                            "title": result.session.title,
                            "workspace": result.session.workspace,
                            "mode": result.session.mode.value,
                            "autonomy": result.session.autonomy.value,
                            "updated_at": result.session.updated_at,
                            "document_kind": result.document_kind,
                            "snippet": result.snippet,
                            "rank": result.rank,
                        }
                        for result in results
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            for result in results:
                snippet = " ".join(result.snippet.split())
                print(
                    f"{result.session.id}\t{result.session.title}\t"
                    f"{result.document_kind}\t{snippet}\t{result.session.workspace}"
                )
        return 0
    if args.session_value is not None:
        raise ValueError("session id is only valid for export")
    if args.output is not None:
        raise ValueError("--output requires sessions export")
    if database.exists():
        sessions = SQLiteEventStore.list_sessions_read_only(
            database,
            limit=args.limit,
            workspace=args.workspace,
        )
    else:
        sessions = []
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": session.id,
                        "title": session.title,
                        "workspace": session.workspace,
                        "mode": session.mode.value,
                        "autonomy": session.autonomy.value,
                        "updated_at": session.updated_at,
                    }
                    for session in sessions
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        for session in sessions:
            print(f"{session.id}\t{session.mode.value}\t{session.title}\t{session.workspace}")
    return 0


def _todo_list(args: argparse.Namespace) -> int:
    database = Path(args.database).expanduser().resolve()
    if not database.is_file():
        raise KeyError(f"unknown session: {args.session}")
    session = SQLiteEventStore.get_session_read_only(database, args.session)
    if session is None:
        raise KeyError(f"unknown session: {args.session}")
    todos = SQLiteEventStore.list_todos_read_only(database, args.session)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": todo.id,
                        "content": todo.content,
                        "status": todo.status.value,
                        "position": todo.position,
                    }
                    for todo in todos
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        for todo in todos:
            marker = "x" if todo.status is TodoStatus.COMPLETED else " "
            print(f"[{marker}] {todo.id}\t{todo.status.value}\t{todo.content}")
    return 0


def _todo_mutation(args: argparse.Namespace) -> int:
    database = Path(args.database).expanduser().resolve()
    if not database.is_file():
        raise KeyError(f"unknown session: {args.session}")
    if args.todo_command == "add":
        if not args.content.strip():
            raise ValueError("Todo content may not be empty")
        if len(args.content) > 10_000:
            raise ValueError("Todo content exceeds 10000 characters")
    lock = ProcessWriteLock(default_writer_lock_path())
    with lock, SQLiteEventStore(database) as store:
        session = store.get_session(args.session)
        if session is None:
            raise KeyError(f"unknown session: {args.session}")
        todos = store.list_todos(args.session)
        if args.todo_command == "add":
            todo_id = str(uuid4())
            event = Event(
                session_id=args.session,
                type="todo.upserted",
                data={
                    "todo_id": todo_id,
                    "content": args.content,
                    "status": TodoStatus.PENDING.value,
                    "position": len(todos),
                },
            )
        else:
            todo = next((item for item in todos if item.id == args.id), None)
            if todo is None:
                raise KeyError(f"unknown todo: {args.id}")
            if args.todo_command == "complete":
                event = Event(
                    session_id=args.session,
                    type="todo.upserted",
                    data={
                        "todo_id": todo.id,
                        "content": todo.content,
                        "status": TodoStatus.COMPLETED.value,
                        "position": todo.position,
                    },
                )
            elif args.todo_command == "delete":
                event = Event(
                    session_id=args.session,
                    type="todo.deleted",
                    data={"todo_id": todo.id},
                )
            else:
                raise AssertionError(f"unsupported todo command: {args.todo_command}")
        store.append(event)
    print(f"todo {args.todo_command}: {event.data['todo_id']}")
    return 0


def _run_backups(args: argparse.Namespace) -> int:
    if args.backups_command == "create":
        print(
            create_verified_backup(
                args.database,
                args.directory,
                keep=args.keep,
                max_age_days=args.max_age_days,
                max_total_bytes=args.max_total_bytes,
                incremental=bool(getattr(args, "incremental", False)),
            )
        )
        return 0
    if args.backups_command == "verify":
        print(json.dumps(asdict(verify_backup(args.backup)), sort_keys=True))
        return 0
    if args.backups_command == "restore":
        with ProcessWriteLock(default_writer_lock_path()):
            print(restore_verified_backup(args.backup, args.destination))
        return 0
    raise AssertionError(f"unsupported backups command: {args.backups_command}")


def _doctor(args: argparse.Namespace) -> int:
    errors: list[str] = []
    workspace = Path(args.workspace)
    if not workspace.is_dir():
        errors.append(f"workspace is not a directory: {workspace}")
    try:
        config = _provider_config(args)
    except ValueError as exc:
        errors.append(str(exc))
        config = None
    print(f"Python: {sys.version.split()[0]}")
    print(f"Python executable: {Path(sys.executable).resolve()}")
    print(f"Workspace: {workspace.resolve() if workspace.exists() else workspace}")
    database = Path(args.database)
    print(f"Database: {database}")
    if database.exists():
        try:
            validation = validate_database(database)
        except BackupValidationError as exc:
            errors.append(f"database validation failed: {exc}")
        else:
            print(f"Database integrity: ok (schema {validation.schema_version})")
    else:
        print("Database integrity: not initialized")
    git = shutil.which("git")
    print(f"Git: {Path(git).resolve() if git else 'not available'}")
    if git is None:
        errors.append("Git executable is not available")
    if os.name == "nt":
        print(
            f"PowerShell: {shutil.which('pwsh') or shutil.which('powershell') or 'not available'}"
        )
        print(f"CMD: {shutil.which('cmd') or 'not available'}")
    if config:
        print(f"Provider: {config.id} ({config.base_url})")
        print(f"Protocol: {config.protocol.value}")
        print(f"Model: {config.model}")
        print(f"API key: {'configured' if config.api_key else 'not configured'}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


def _add_runtime_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", help="Workspace directory")
    parser.add_argument("--database", default=str(default_database_path()), help="SQLite path")
    parser.add_argument("--provider", help="Provider id (or AGENT_WORKSPACE_PROVIDER)")
    parser.add_argument("--profile", help="Saved Provider profile id")
    parser.add_argument("--protocol", choices=[protocol.value for protocol in ProviderProtocol])
    parser.add_argument("--base-url", help="API base URL (or AGENT_WORKSPACE_BASE_URL)")
    parser.add_argument("--model", help="Model id (or AGENT_WORKSPACE_MODEL)")
    parser.add_argument("--mode", choices=[mode.value for mode in Mode])
    parser.add_argument(
        "--autonomy",
        choices=[mode.value for mode in Autonomy],
    )
    parser.add_argument(
        "--agent",
        help="Workspace agent definition id from .agent/agents/*.toml",
    )
    parser.add_argument(
        "--no-instructions",
        action="store_true",
        help="Skip automatic AGENTS.md/CLAUDE.md/.cursorrules and skill discovery",
    )
    parser.add_argument(
        "--repo-map",
        action="store_true",
        help="Inject a bounded workspace code map into the system context",
    )
    parser.add_argument("--repo-map-limit", type=int, default=120)
    parser.add_argument(
        "--summarize-history",
        action="store_true",
        help="Summarize omitted history during context compaction instead of dropping it",
    )
    parser.add_argument(
        "--verify",
        metavar="COMMAND",
        help="PowerShell verification command for the auto-fix loop",
    )
    parser.add_argument(
        "--fix-loop",
        type=int,
        default=0,
        metavar="N",
        help="Rerun the agent up to N times until --verify succeeds",
    )
    parser.add_argument(
        "--image",
        action="append",
        metavar="PATH",
        help="Attach an image file to the user message (repeatable)",
    )
    parser.add_argument(
        "--parallel-tool-calls",
        action="store_true",
        help="Execute independent tool calls from one model response concurrently",
    )
    parser.add_argument(
        "--profile-turns",
        action="store_true",
        help="Record per-turn timing events",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON events")


def _provider_list(args: argparse.Namespace) -> int:
    store = _provider_settings_store()
    settings = store.load()
    rows = [
        {
            "id": profile.id,
            "name": profile.name,
            "protocol": profile.protocol.value,
            "base_url": profile.base_url,
            "model": profile.model,
            "default": profile.id == settings.default_provider_id,
            "has_credential": store.has_credential(profile.id),
        }
        for profile in settings.profiles.values()
    ]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
    else:
        for row in rows:
            marker = "*" if row["default"] else " "
            credential = "key" if row["has_credential"] else "no-key"
            print(
                f"{marker} {row['id']}\t{row['protocol']}\t{row['model'] or '<model unset>'}"
                f"\t{credential}\t{row['base_url']}"
            )
    return 0


def _provider_set(args: argparse.Namespace) -> int:
    store = _provider_settings_store()
    secret: str | None = None
    if args.api_key_env:
        secret = os.getenv(args.api_key_env)
        if not secret:
            raise ValueError(f"environment variable is empty or missing: {args.api_key_env}")
    target = credential_target(args.id, args.base_url)
    profile = ProviderProfile(
        id=args.id,
        name=args.name or args.id,
        protocol=ProviderProtocol(args.protocol),
        base_url=args.base_url,
        model=args.model,
        credential_target=target,
    )
    store.upsert(profile, secret=secret, make_default=args.default)
    print(f"saved provider profile: {profile.id}")
    return 0


def _provider_delete(args: argparse.Namespace) -> int:
    _provider_settings_store().delete(args.id)
    print(f"deleted provider profile: {args.id}")
    return 0


def _provider_default(args: argparse.Namespace) -> int:
    _provider_settings_store().set_default(args.id)
    print(f"default provider profile: {args.id}")
    return 0


async def _provider_test(args: argparse.Namespace) -> int:
    config = _provider_settings_store().resolve_config(args.id)
    provider = create_provider(config)
    text: list[str] = []
    finish_reason: str | None = None
    finish_seen = False
    try:
        request = ProviderRequest(
            model=config.model,
            messages=(ChatMessage(role=Role.USER, content="Reply with OK."),),
        )
        async for delta in provider.stream(request):
            if finish_seen:
                raise ProviderError(
                    "provider emitted data after its finish marker",
                    status_code=None,
                )
            if delta.kind is DeltaKind.FINISH:
                if delta.finish_reason is None or not delta.finish_reason.strip():
                    raise ProviderError(
                        "provider emitted an invalid finish marker",
                        status_code=None,
                    )
                finish_reason = delta.finish_reason
                finish_seen = True
            elif delta.kind is DeltaKind.TEXT and delta.text:
                text.append(delta.text)
    finally:
        await provider.aclose()
    normalized_reason = (
        finish_reason.strip().casefold().replace("-", "_") if finish_reason is not None else ""
    )
    if not finish_seen or normalized_reason not in {"end_turn", "stop", "stop_sequence"}:
        raise ProviderError(
            "provider test did not complete normally",
            status_code=None,
        )
    if not "".join(text).strip():
        raise ProviderError("provider test returned no text", status_code=None)
    print(f"provider profile works: {config.id} ({''.join(text).strip()[:80]})")
    return 0


def _agents_list(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or ".").resolve()
    agents = load_agents(workspace)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "description": agent.description,
                        "mode": agent.mode,
                        "allowed_tools": list(agent.allowed_tools),
                    }
                    for agent in agents
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        for agent in agents:
            mode = agent.mode or "default"
            print(f"{agent.id}\t{mode}\t{agent.name}\t{agent.description}")
    return 0


def _skills_list(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or ".").resolve()
    skills = load_skills(workspace)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": skill.id,
                        "name": skill.name,
                        "description": skill.description,
                    }
                    for skill in skills
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        for skill in skills:
            print(f"{skill.id}\t{skill.name}\t{skill.description}")
    return 0


def _optimizations_path(workspace: str | Path) -> Path:
    return Path(workspace).resolve() / ".agent" / "optimizations.json"


def _optimizations_registry(args: argparse.Namespace) -> Any:
    from agent_workspace.optimizations import (
        ModelOptimizationRegistry,
        load_optimization_registry,
    )

    path = _optimizations_path(args.workspace or ".")
    if path.is_file():
        return load_optimization_registry(path)
    return ModelOptimizationRegistry()


def _optimizations_list(args: argparse.Namespace) -> int:
    registry = _optimizations_registry(args)
    rows = [
        {
            "id": profile.id,
            "name": profile.name,
            "version": profile.version,
            "type": profile.type,
            "enabled": profile.enabled,
            "models": list(profile.models),
            "requires": list(profile.requires),
            "conflicts": list(profile.conflicts),
            "description": profile.description,
        }
        for profile in registry.profiles.values()
    ]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
    else:
        for row in rows:
            state = "enabled" if row["enabled"] else "disabled"
            models = ",".join(row["models"])
            print(f"{row['id']} v{row['version']}\t{row['type']}\t{state}\t{models}")
    return 0


def _optimizations_install(args: argparse.Namespace) -> int:
    from agent_workspace.optimizations import (
        load_optimization_registry,
        update_optimization_registry,
    )

    incoming = load_optimization_registry(args.source)
    current = _optimizations_registry(args)
    merged = update_optimization_registry(current, incoming)
    merged.save(_optimizations_path(args.workspace or "."))
    print(
        "installed model optimization profiles: "
        + ", ".join(sorted(profile.id for profile in incoming.profiles.values()))
    )
    return 0


def _optimizations_template(args: argparse.Namespace) -> int:
    from agent_workspace.optimizations import default_model_optimization_registry

    registry = default_model_optimization_registry()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry.save(path)
    print(path)
    return 0


def _optimizations_set_enabled(args: argparse.Namespace, *, enabled: bool) -> int:
    registry = _optimizations_registry(args)
    try:
        profile = registry.profiles[args.id]
    except KeyError:
        raise KeyError(f"unknown model optimization profile: {args.id}") from None
    from dataclasses import replace

    registry.register(replace(profile, enabled=enabled))
    registry.save(_optimizations_path(args.workspace or "."))
    state = "enabled" if enabled else "disabled"
    print(f"{state} model optimization profile: {profile.id}")
    return 0


def _optimizations_verify(args: argparse.Namespace) -> int:
    registry = _optimizations_registry(args)
    enabled = registry.resolve(args.model)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": profile.id,
                        "version": profile.version,
                        "type": profile.type,
                    }
                    for profile in enabled
                ],
                sort_keys=True,
            )
        )
    else:
        for profile in enabled:
            print(f"{profile.id}\tv{profile.version}\t{profile.type}")
        if not enabled:
            print("no enabled model optimization profiles match", file=sys.stderr)
    return 0 if enabled else 1


def _prompts_render(args: argparse.Namespace) -> int:
    from agent_workspace.core.prompt_templates import PromptTemplateRegistry

    if args.prompt_command == "validate":
        registry = PromptTemplateRegistry()
        registry.load(args.template_file)
        print(
            json.dumps(
                {
                    "template_file": str(args.template_file),
                    "templates": len(registry._templates),
                },
                sort_keys=True,
            )
        )
        return 0
    registry = PromptTemplateRegistry()
    registry.load(args.template_file)
    variables: dict[str, str] = {}
    for assignment in args.var or ():
        key, separator, value = assignment.partition("=")
        if not separator:
            raise ValueError(f"template variable must use NAME=VALUE: {assignment}")
        variables[key] = value
    print(registry.render(args.id, variables))
    return 0


def _openapi_validate_run(args: argparse.Namespace) -> int:
    from agent_workspace.tools.openapi import load_openapi_file

    operations = load_openapi_file(args.file)
    if args.json:
        print(
            json.dumps(
                {
                    "file": str(args.file),
                    "operations": len(operations),
                    "tools": [operation.tool_name for operation in operations],
                },
                sort_keys=True,
            )
        )
    else:
        for operation in operations:
            print(operation.tool_name)
    return 0


def _nodes_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.remote_nodes import RemoteNodeRegistry

    config_path = args.config or Path(".agent") / "nodes.toml"
    registry = RemoteNodeRegistry.load(config_path)
    rows = [
        {
            "id": node.id,
            "host": node.host,
            "user": node.user,
            "port": node.port,
            "ssh_command": node.ssh_command,
        }
        for node in registry.nodes()
    ]
    if args.json:
        print(json.dumps(rows, sort_keys=True))
    else:
        for row in rows:
            print(f"{row['id']}\t{row['host']}\t{row['port']}")
    return 0


def _shell_completion_run(args: argparse.Namespace) -> int:
    commands = " ".join(
        sorted(
            {
                "run",
                "chat",
                "agents",
                "skills",
                "optimizations",
                "prompts",
                "workspaces",
                "model-registry",
                "events",
                "archive",
                "file-history",
                "queue",
                "plans",
                "pipelines",
                "evals",
                "bench",
                "serve",
                "sessions",
                "todos",
                "backups",
                "doctor",
                "credentials",
                "providers",
                "openapi",
                "nodes",
                "subagents",
            }
        )
    )
    if args.shell == "bash":
        print(
            "_agent_workspace_complete(){"
            "COMPREPLY=( $(compgen -W '" + commands + '\' -- "${COMP_WORDS[COMP_CWORD]}") );}\n'
            "complete -F _agent_workspace_complete agent-workspace"
        )
        return 0
    if args.shell == "zsh":
        print("#compdef agent-workspace\n_arguments '1:command:(" + commands + ")'")
        return 0
    raise ValueError("completion shell must be bash or zsh")


def _subagents_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.models import Autonomy, Mode
    from agent_workspace.core.subagents import SubagentRequest, run_subagent

    workspace = Path(args.workspace).resolve()
    database = Path(args.database)
    database.parent.mkdir(parents=True, exist_ok=True)
    config = _provider_config(args)

    async def execute() -> int:
        runtime = build_runtime(
            workspace,
            database,
            config,
            autonomy=Autonomy(args.autonomy),
        )
        try:
            result = await run_subagent(
                runtime.service,
                workspace,
                SubagentRequest(
                    prompt=args.prompt,
                    model=config.model,
                    allowed_tools=frozenset(args.allowed_tool or ()),
                    title=args.title or "CLI subagent",
                    mode=Mode(args.mode),
                    autonomy=Autonomy(args.autonomy),
                ),
            )
            print(
                json.dumps(
                    {"session_id": result.session_id, "text": result.text},
                    sort_keys=True,
                )
            )
        finally:
            await runtime.aclose()
        return 0

    return asyncio.run(execute())


def _workspaces_catalog_path() -> Path:
    return default_data_dir() / "workspaces.json"


def _workspaces_catalog() -> Any:
    from agent_workspace.core.workspace_catalog import WorkspaceCatalog

    return WorkspaceCatalog(_workspaces_catalog_path())


def _workspaces_run(args: argparse.Namespace) -> int:
    catalog = _workspaces_catalog()
    if args.workspace_command == "list":
        rows = [
            {"path": entry.path, "name": entry.name, "last_used": entry.last_used}
            for entry in catalog.entries()
        ]
        if args.json:
            print(json.dumps(rows, sort_keys=True))
        else:
            for row in rows:
                print(f"{row['name']}\t{row['path']}")
        return 0
    if args.workspace_command == "add":
        entry = catalog.add(args.path, args.name)
        print(entry.path)
        return 0
    if args.workspace_command == "remove":
        catalog.remove(args.path)
        return 0
    if args.workspace_command == "touch":
        catalog.touch(args.path)
        return 0
    raise AssertionError(f"unsupported workspace command: {args.workspace_command}")


def _model_registry_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.model_registry import LatestModelRegistry, builtin_latest_models

    registry = (
        LatestModelRegistry.load(args.file)
        if getattr(args, "file", None) is not None
        else builtin_latest_models()
    )
    if args.registry_command == "list":
        rows = [
            {
                "id": snapshot.id,
                "family": snapshot.family,
                "status": snapshot.status,
                "released_on": snapshot.released_on,
                "aliases": list(snapshot.aliases),
            }
            for snapshot in registry.snapshots()
        ]
        if args.json:
            print(json.dumps(rows, sort_keys=True))
        else:
            for row in rows:
                print(f"{row['id']}\t{row['family']}\t{row['status']}\t{row['released_on']}")
        return 0
    if args.registry_command == "resolve":
        resolved = registry.resolve(args.model)
        if resolved is None:
            raise KeyError(f"model is not registered: {args.model}")
        print(
            json.dumps(
                {
                    "requested": resolved.requested,
                    "snapshot": resolved.snapshot.id,
                    "alias_of": resolved.alias_of,
                    "legacy": resolved.legacy,
                },
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(f"unsupported registry command: {args.registry_command}")


def _events_run(args: argparse.Namespace) -> int:
    from agent_workspace.storage import export_events_ndjson

    database = Path(args.database)
    if not database.is_file():
        raise KeyError("database does not exist")
    with SQLiteEventStore(database) as store:
        count = export_events_ndjson(store, args.output, args.session)
    if args.json:
        print(json.dumps({"events_written": count}, sort_keys=True))
    else:
        print(count)
    return 0


def _archive_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.archive_signing import (
        sign_file,
        verify_file,
        write_signature,
    )

    key = os.getenv(args.key_env or "", "").encode("utf-8")
    if not key:
        raise ValueError("signing key environment variable is empty or missing")
    if args.archive_command == "sign":
        signature = sign_file(args.file, key)
        path = write_signature(args.output, signature)
        print(path)
        return 0
    if args.archive_command == "verify":
        signature = json.loads(args.signature.read_text(encoding="utf-8"))
        valid = verify_file(args.file, key, signature)
        print(json.dumps({"valid": valid}, sort_keys=True))
        return 0 if valid else 1
    raise AssertionError(f"unsupported archive command: {args.archive_command}")


def _file_history_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.file_history import FileHistoryManager

    database = Path(args.database)
    if not database.is_file():
        raise KeyError("database does not exist")
    with SQLiteEventStore(database) as store:
        versions = FileHistoryManager(store).versions(args.session, args.path)
    rows = [version.to_document() for version in versions]
    if args.json:
        print(json.dumps(rows, sort_keys=True))
    else:
        for row in rows:
            print(f"{row['sequence']}\t{row['recorded_at']}\t{row['sha256']}\t{row['path']}")
    return 0


def _queue_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.durable_run_queue import DurableRunQueue

    database = Path(args.database)
    if args.queue_command == "enqueue" and not database.exists():
        database.parent.mkdir(parents=True, exist_ok=True)

    async def execute() -> int:
        with SQLiteEventStore(database) as store:
            queue = DurableRunQueue(store)
            if args.queue_command == "enqueue":
                task = await queue.enqueue(
                    args.workspace,
                    args.prompt,
                    args.model,
                )
                print(task.id)
                return 0
            if args.queue_command == "list":
                tasks = queue.list(status=args.status)
                if args.json:
                    print(json.dumps([task.to_document() for task in tasks], sort_keys=True))
                else:
                    for task in tasks:
                        print(f"{task.id}\t{task.status.value}\t{task.prompt}")
                return 0
            if args.queue_command == "claim":
                task = await queue.claim(args.task_id)
                print(task.claim_token)
                return 0
            if args.queue_command == "complete":
                await queue.complete(args.task_id, args.claim_token)
                return 0
            if args.queue_command == "fail":
                await queue.fail(args.task_id, args.claim_token, args.error)
                return 0
            if args.queue_command == "cancel":
                await queue.cancel(args.task_id)
                return 0
            raise AssertionError(f"unsupported queue command: {args.queue_command}")

    return asyncio.run(execute())


def _db_run(args: argparse.Namespace) -> int:
    if args.db_command == "integrity":
        print(json.dumps(database_integrity_check(args.database), sort_keys=True))
        return 0
    if args.db_command == "disk-usage":
        print(
            json.dumps(
                workspace_disk_usage(args.workspace, top_n=args.top_n).to_document(),
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(f"unsupported db command: {args.db_command}")


def _artifacts_run(args: argparse.Namespace) -> int:
    if args.artifact_command == "put":
        entry = build_artifact_put(args.cache, args.source)
        print(entry.digest)
        return 0
    if args.artifact_command == "get":
        fetched = build_artifact_get(args.cache, args.digest, verify=True)
        if fetched is None:
            raise KeyError(f"artifact is missing or failed verification: {args.digest}")
        print(fetched.path)
        return 0
    if args.artifact_command == "stats":
        print(json.dumps(build_artifact_stats(args.cache), sort_keys=True))
        return 0
    if args.artifact_command == "prune":
        pruned = build_artifact_prune(
            args.cache,
            max_bytes=args.max_bytes,
            dry_run=args.dry_run,
        )
        print("\n".join(pruned))
        return 0
    raise AssertionError(f"unsupported artifact command: {args.artifact_command}")


def _audit_retention_run(args: argparse.Namespace) -> int:
    policy = AuditRetentionPolicy(
        max_age_days=args.max_age_days,
        max_files=args.max_files,
        max_total_bytes=args.max_total_bytes,
    )
    report = apply_audit_retention(
        args.directory,
        policy,
        dry_run=args.dry_run,
    )
    print(json.dumps(report.to_document(), sort_keys=True))
    return 0


def _process_limits_run(_args: argparse.Namespace) -> int:
    print(json.dumps(process_resource_report().to_document(), sort_keys=True))
    return 0


def _env_run(args: argparse.Namespace) -> int:
    environment = WorkspaceEnvironment(args.workspace)
    if args.env_command == "list":
        variables = environment.list()
        if args.json:
            print(
                json.dumps(
                    [
                        variable.to_document(redact_secrets=not args.show_secrets)
                        for variable in variables
                    ],
                    sort_keys=True,
                )
            )
        else:
            for variable in variables:
                value = variable.value if not variable.secret or args.show_secrets else "<redacted>"
                print(f"{variable.name}={value}")
        return 0
    if args.env_command == "get":
        found = environment.get(args.name)
        if found is None:
            raise KeyError(f"workspace environment variable is not set: {args.name}")
        if args.json:
            print(
                json.dumps(
                    found.to_document(redact_secrets=not args.show_secrets),
                    sort_keys=True,
                )
            )
        else:
            value = found.value if not found.secret or args.show_secrets else "<redacted>"
            print(value)
        return 0
    if args.env_command == "set":
        variable = environment.set(args.name, args.value, secret=args.secret)
        print(
            json.dumps(
                variable.to_document(redact_secrets=True),
                sort_keys=True,
            )
        )
        return 0
    if args.env_command == "unset":
        print(json.dumps({"name": args.name, "removed": environment.unset(args.name)}))
        return 0
    raise AssertionError(f"unsupported env command: {args.env_command}")


def _schedule_run(args: argparse.Namespace) -> int:
    preview = schedule_next_runs(args.expression, count=args.count)
    print(json.dumps(preview.to_document(), sort_keys=True))
    return 0


def _replay_patch_run(args: argparse.Namespace) -> int:
    database = Path(args.database)
    events: list[Event] = []
    if args.session is not None:
        session_ids = [args.session]
    else:
        session_ids = [
            session.id
            for session in SQLiteEventStore.list_sessions_read_only(database, limit=10_000)
        ]
    for session_id in session_ids:
        events.extend(SQLiteEventStore.list_events_read_only(database, session_id))
    print(json.dumps(event_replay_patch_document(events), sort_keys=True))
    return 0


def _transcript_merge_run(args: argparse.Namespace) -> int:
    if len(args.session) < 1:
        raise ValueError("transcript-merge requires at least one --session")
    database = Path(args.database)
    sources = {
        session_id: SQLiteEventStore.list_events_read_only(database, session_id)
        for session_id in args.session
    }
    result = merge_session_transcripts(sources)
    print(json.dumps(result.to_document(), sort_keys=True))
    return 0


def _search_batch_run(args: argparse.Namespace) -> int:
    if not args.query:
        raise ValueError("search-batch requires at least one --query")
    database = Path(args.database)
    queries = [str(query) for query in args.query]
    query_results = {
        query: SQLiteEventStore.search_sessions_hybrid(
            database,
            query,
            limit=args.limit,
        )
        for query in queries
    }
    result = merge_batch_search_results(query_results)
    print(json.dumps(result.to_document(), sort_keys=True))
    return 0


def _context_probe_run(args: argparse.Namespace) -> int:
    prompt = args.file.read_text(encoding="utf-8") if args.file is not None else args.prompt
    probe = context_window_probe(
        args.model,
        args.context_limit,
        system_prompt=args.system_prompt,
        history=(prompt,),
        reserved_output_tokens=args.reserve_output,
    )
    print(json.dumps(probe.to_document(), sort_keys=True))
    return 0


def _prompt_batch_run(args: argparse.Namespace) -> int:
    if args.prompt_batch_command == "validate":
        summary = summarize_prompt_batch_file(args.file)
        print(json.dumps(summary.to_document(), sort_keys=True))
        return 0
    if args.prompt_batch_command == "convert":
        entries = load_prompt_batch(args.input)
        destination = save_prompt_batch(args.output, entries, format=args.format)
        print(json.dumps({"output": str(destination), "entries": len(entries)}))
        return 0
    raise AssertionError(f"unsupported prompt batch command: {args.prompt_batch_command}")


def _approval_batch_run(args: argparse.Namespace) -> int:
    reviewer = ApprovalBatchReviewer(
        args.file,
        default_ttl_seconds=float(getattr(args, "ttl_seconds", 300.0)),
    )
    if args.approval_batch_command == "submit":
        try:
            arguments = json.loads(args.arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(f"approval arguments are not valid JSON: {exc}") from exc
        if not isinstance(arguments, dict):
            raise ValueError("approval arguments must be a JSON object")
        request = reviewer.submit(
            args.tool,
            arguments,
            session_id=args.session,
            priority=args.priority,
            ttl_seconds=args.ttl_seconds,
        )
        print(request.id)
        return 0
    if args.approval_batch_command == "list":
        print(
            json.dumps(
                [request.to_document() for request in reviewer.pending()],
                sort_keys=True,
            )
        )
        return 0
    if args.approval_batch_command == "review":
        decisions: list[ApprovalBatchDecision] = []
        for request_id in args.allow:
            decisions.append(ApprovalBatchDecision(request_id, True, args.reason))
        for request_id in args.deny:
            decisions.append(ApprovalBatchDecision(request_id, False, args.reason))
        report = reviewer.review(decisions, dry_run=args.dry_run)
        print(json.dumps(report.to_document(), sort_keys=True))
        return 0
    raise AssertionError(f"unsupported approval batch command: {args.approval_batch_command}")


def _inspect_prompt_run(args: argparse.Namespace) -> int:
    prompt = Path(args.file).read_text(encoding="utf-8") if args.file is not None else args.prompt
    assessment = classify_prompt_injection(
        prompt,
        allowlisted_instructions=tuple(args.allowlisted_instruction or ()),
    )
    print(json.dumps(assessment.to_document(), sort_keys=True))
    return 0


def _credentials_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.credential_rotation import CredentialRotationManager
    from agent_workspace.credentials import default_credential_store

    metadata = default_data_dir() / "credential-metadata.json"
    manager = CredentialRotationManager(default_credential_store(), metadata)
    if args.credential_command == "status":
        status = manager.status(args.provider)
        if status is None:
            raise KeyError(f"credential metadata not found for provider: {args.provider}")
        print(
            json.dumps(
                {
                    "provider_id": status.provider_id,
                    "age_days": status.age_days,
                    "last_used_at": status.last_used_at,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.credential_command == "rotate":
        secret = os.getenv(args.secret_env, "")
        if not secret:
            raise ValueError("credential rotation secret environment variable is empty")
        manager.rotate(args.provider, secret)
        return 0
    if args.credential_command == "recommendations":
        print(
            json.dumps(
                manager.recommendations(
                    warn_days=args.warn_days,
                    rotate_days=args.rotate_days,
                ),
                sort_keys=True,
            )
        )
        return 0
    if args.credential_command == "health":
        print(
            json.dumps(
                credential_health_dashboard(
                    manager.list_statuses(),
                    warn_days=args.warn_days,
                    rotate_days=args.rotate_days,
                ).to_document(),
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(f"unsupported credential command: {args.credential_command}")


def _plans_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.plans import GoalStatus, PlanManager, StepStatus

    database = Path(args.database)
    if args.plan_command == "create" and not database.exists():
        database.parent.mkdir(parents=True, exist_ok=True)

    async def execute() -> int:
        with SQLiteEventStore(database) as store:
            manager = PlanManager(store)
            if args.plan_command == "create":
                await manager.create_goal(args.session, args.goal_id, args.title)
                return 0
            if args.plan_command == "list":
                goals = manager.list_goals(args.session)
                if args.json:
                    print(json.dumps([goal.to_document() for goal in goals], sort_keys=True))
                else:
                    for goal in goals:
                        print(f"{goal.id}\t{goal.status.value}\t{goal.title}")
                return 0
            if args.plan_command == "step":
                await manager.upsert_step(
                    args.session,
                    args.step_id,
                    args.goal_id,
                    args.title,
                    status=StepStatus(args.status),
                    position=args.position,
                    parent_step_id=args.parent_step_id,
                )
                return 0
            if args.plan_command == "steps":
                steps = manager.list_steps(args.session, args.goal_id)
                if args.json:
                    print(json.dumps([step.to_document() for step in steps], sort_keys=True))
                else:
                    for step in steps:
                        print(f"{step.id}\t{step.status.value}\t{step.position}\t{step.title}")
                return 0
            if args.plan_command == "update":
                await manager.update_goal(args.session, args.goal_id, GoalStatus(args.status))
                return 0
            raise AssertionError(f"unsupported plan command: {args.plan_command}")

    return asyncio.run(execute())


def _pipelines_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.pipeline import (
        PipelineDefinition,
        PipelineManager,
        PipelineStep,
    )

    database = Path(args.database)
    if args.pipeline_command == "create" and not database.exists():
        database.parent.mkdir(parents=True, exist_ok=True)

    async def execute() -> int:
        with SQLiteEventStore(database) as store:
            manager = PipelineManager(store)
            if args.pipeline_command == "create":
                document = json.loads(Path(args.definition).read_text(encoding="utf-8"))
                if not isinstance(document, dict) or not isinstance(document.get("steps"), list):
                    raise ValueError("pipeline definition must declare id, name, and steps")
                steps = tuple(
                    PipelineStep(
                        id=str(item["id"]),
                        name=str(item["name"]),
                        depends_on=tuple(
                            str(dependency) for dependency in item.get("depends_on", ())
                        ),
                        max_retries=int(item.get("max_retries", 0)),
                    )
                    for item in document["steps"]
                )
                await manager.create(
                    PipelineDefinition(
                        id=str(document["id"]),
                        name=str(document["name"]),
                        steps=steps,
                    )
                )
                return 0
            if args.pipeline_command == "list":
                states = manager.list()
                rows = [
                    {
                        "pipeline_id": state.definition.id,
                        "name": state.definition.name,
                        "status": state.status.value,
                        "ready_steps": list(state.ready_steps()),
                    }
                    for state in states
                ]
                if args.json:
                    print(json.dumps(rows, sort_keys=True))
                else:
                    for row in rows:
                        print(f"{row['pipeline_id']}\t{row['status']}\t{row['name']}")
                return 0
            if args.pipeline_command == "start":
                await manager.start(args.pipeline_id)
                return 0
            if args.pipeline_command == "start-step":
                await manager.start_step(args.pipeline_id, args.step_id)
                return 0
            if args.pipeline_command == "complete-step":
                await manager.complete_step(args.pipeline_id, args.step_id)
                return 0
            if args.pipeline_command == "fail-step":
                await manager.fail_step(args.pipeline_id, args.step_id, args.error)
                return 0
            raise AssertionError(f"unsupported pipeline command: {args.pipeline_command}")

    return asyncio.run(execute())


def _evals_run(args: argparse.Namespace) -> int:
    import tempfile

    from agent_workspace.core.evals import (
        EvalOutcome,
        ScriptedEvalProvider,
        load_scenarios,
        render_outcomes,
        run_scenario,
    )

    workspace = Path(args.workspace or ".").resolve()
    scenarios = load_scenarios(args.directory)
    outcomes: list[EvalOutcome] = []

    async def execute() -> None:
        for scenario in scenarios:
            scripts = [list(turn.deltas) for turn in scenario.turns]
            provider = ScriptedEvalProvider(scripts)
            with tempfile.TemporaryDirectory(prefix="agent-workspace-evals-") as temporary:
                store = SQLiteEventStore(Path(temporary) / "agent.db")
                try:
                    outcomes.append(await run_scenario(scenario, provider, store, workspace))
                finally:
                    store.close()

    asyncio.run(execute())
    print(render_outcomes(tuple(outcomes)))
    return 0 if all(outcome.passed for outcome in outcomes) else 1


def _import_benchmark_scenario(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"benchmark scenario cannot be imported: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ValueError(f"cannot import benchmark scenario {path}: {exc}") from exc
    return module


def _coerce_benchmark_cases(raw: object, source: str) -> tuple[Any, ...]:
    from agent_workspace.core.benchmarks import BenchmarkCase

    if isinstance(raw, BenchmarkCase):
        raw = (raw,)
    if not isinstance(raw, (tuple, list)):
        raise ValueError(
            f"benchmark scenario {source} must export CASES or build_cases() "
            "returning BenchmarkCase instances"
        )
    cases = tuple(raw)
    if not cases or not all(isinstance(case, BenchmarkCase) for case in cases):
        raise ValueError(
            f"benchmark scenario {source} must export CASES or build_cases() "
            "returning BenchmarkCase instances"
        )
    return cases


def _load_benchmark_scenario_file(path: Path) -> tuple[Any, ...]:
    from agent_workspace.core.benchmarks import BenchmarkCase

    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"benchmark scenario file does not exist: {resolved}")
    module = _import_benchmark_scenario(resolved, f"_agent_workspace_bench_{uuid4().hex}")
    raw_cases = getattr(module, "CASES", None)
    builder = getattr(module, "build_cases", None)
    if raw_cases is not None and builder is not None:
        raise ValueError(
            f"benchmark scenario {resolved} must define either CASES or build_cases(), not both"
        )
    if builder is not None:
        try:
            raw_cases = builder()
        except Exception as exc:
            raise ValueError(f"benchmark scenario {resolved} build_cases() failed: {exc}") from exc
    if raw_cases is None:
        raise ValueError(f"benchmark scenario {resolved} must export CASES or build_cases()")
    cases = _coerce_benchmark_cases(raw_cases, str(resolved))
    if not all(isinstance(case, BenchmarkCase) for case in cases):
        raise ValueError(f"benchmark scenario {resolved} contains a non-BenchmarkCase value")
    return cases


def _load_benchmark_cases(directory: Path) -> tuple[Any, ...]:
    from agent_workspace.core.benchmarks import BenchmarkCase

    resolved = directory.resolve()
    if not resolved.is_dir():
        raise ValueError(f"benchmark scenario directory does not exist: {resolved}")
    loaded: list[BenchmarkCase] = []
    for path in sorted(resolved.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        module = _import_benchmark_scenario(path, f"_agent_workspace_bench_{uuid4().hex}")
        raw_cases = getattr(module, "CASES", None)
        builder = getattr(module, "build_cases", None)
        if raw_cases is None and builder is None:
            continue
        if raw_cases is not None and builder is not None:
            raise ValueError(
                f"benchmark scenario {path} must define either CASES or build_cases(), not both"
            )
        if builder is not None:
            try:
                raw_cases = builder()
            except Exception as exc:
                raise ValueError(f"benchmark scenario {path} build_cases() failed: {exc}") from exc
        if raw_cases is None:
            continue
        loaded.extend(_coerce_benchmark_cases(raw_cases, str(path)))
    return tuple(loaded)


def _benchmark_cases(args: argparse.Namespace) -> tuple[Any, ...]:
    from agent_workspace.core.benchmarks import build_builtin_cases

    directories = cast(list[Path] | None, getattr(args, "scenario_directories", None))
    files = cast(list[Path] | None, getattr(args, "scenario_files", None))
    if directories or files:
        loaded: list[Any] = []
        for directory in directories or ():
            loaded.extend(_load_benchmark_cases(directory))
        for path in files or ():
            loaded.extend(_load_benchmark_scenario_file(path))
        cases = tuple(loaded)
    else:
        cases = build_builtin_cases()
    if not cases:
        raise ValueError("no benchmark cases were loaded")

    case_ids = [case.id for case in cases]
    duplicate_ids = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicate_ids:
        raise ValueError(f"duplicate benchmark case ids: {', '.join(duplicate_ids)}")

    requested = cast(list[str] | None, getattr(args, "case", None))
    if requested:
        by_id = {case.id: case for case in cases}
        unknown = [case_id for case_id in requested if case_id not in by_id]
        if unknown:
            raise ValueError(f"unknown benchmark case ids: {', '.join(unknown)}")
        cases = tuple(by_id[case_id] for case_id in requested)
    if not cases:
        raise ValueError("no benchmark cases were selected")
    return cases


def _benchmark_report_json(report: Any) -> dict[str, object]:
    return {
        "cases": report.cases,
        "passed": report.passed,
        "weighted_score": report.weighted_score,
        "by_category": {
            str(category.value): score for category, score in report.by_category.items()
        },
        "verdicts": [
            {
                "case_id": verdict.case_id,
                "category": verdict.category.value,
                "passed": verdict.passed,
                "score": verdict.score,
                "failures": list(verdict.failures),
            }
            for verdict in report.verdicts
        ],
    }


async def _bench_run(args: argparse.Namespace) -> int:
    from agent_workspace.core.benchmarks import run_benchmark

    cases = _benchmark_cases(args)
    workspace_arg = cast(str | None, args.workspace)
    with tempfile.TemporaryDirectory(prefix="agent-workspace-bench-") as temporary:
        workspace = Path(workspace_arg).resolve() if workspace_arg else Path(temporary).resolve()
        if not workspace.is_dir():
            raise ValueError(f"workspace is not a directory: {workspace}")
        database = Path(temporary) / "bench.db"
        config = _provider_config(args)
        runtime = build_runtime(
            workspace,
            database,
            config,
            autonomy=Autonomy.WORKSPACE,
            approval_callback=_console_approval,
            egress_approval_callback=_console_egress_approval,
        )
        primary_error: BaseException | None = None
        try:
            report = await run_benchmark(
                lambda: runtime.service,
                cases,
                workspace,
                config.model,
            )
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            await _close_runtime(runtime, primary_error)
    if args.json:
        print(json.dumps(_benchmark_report_json(report), ensure_ascii=False, sort_keys=True))
    else:
        print(report.render())
    return 0 if report.passed == report.cases else 1


def _sessions_cost(args: argparse.Namespace) -> int:
    from agent_workspace.core.cost import format_cost, session_cost

    database = Path(args.database).expanduser().resolve()
    session_id = cast(str, args.session_value)
    events = SQLiteEventStore.list_events_read_only(database, session_id)
    cost = session_cost(events)
    if args.json:
        print(
            json.dumps(
                {
                    "session_id": session_id,
                    "model_calls": cost.model_calls,
                    "input_tokens": cost.input_tokens,
                    "output_tokens": cost.output_tokens,
                    "cached_tokens": cost.cached_tokens,
                    "estimated": cost.estimated,
                    "cost_usd": cost.cost_usd,
                },
                sort_keys=True,
            )
        )
    else:
        print(format_cost(cost))
    return 0


async def _serve(args: argparse.Namespace) -> int:
    import secrets as _secrets

    from agent_workspace.application.serve_api import ServeApi

    workspace = cast(str, args.workspace or ".")
    autonomy = Autonomy(cast(str, args.autonomy or Autonomy.WORKSPACE.value))
    renderer = ConsoleRenderer(json_output=False)
    runtime, config = await _open_runtime(
        args,
        renderer,
        workspace=workspace,
        autonomy=autonomy,
    )
    supplied_token = cast(str | None, getattr(args, "token", None))
    token = supplied_token or _secrets.token_urlsafe(32)
    api = ServeApi(
        runtime,
        host=cast(str, args.host),
        port=cast(int, args.port),
        token=token,
        default_model=config.model,
    )
    api.start()
    # Only echo a generated token; a caller-supplied token is already known
    # and must not be re-printed to logs.
    token_notice = "" if supplied_token else f" (token: {token})"
    print(
        f"Serve API listening on {api.address}{token_notice}",
        file=sys.stderr,
        flush=True,
    )
    try:
        await asyncio.Event().wait()
    finally:
        api.stop()
        await _close_runtime(runtime, None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-workspace")
    subparsers = parser.add_subparsers(dest="command", required=True)

    completion_parser = subparsers.add_parser(
        "shell-completion", help="Print a shell completion script"
    )
    completion_parser.add_argument("--shell", choices=("bash", "zsh"), required=True)

    run_parser = subparsers.add_parser("run", help="Run one prompt")
    _add_runtime_options(run_parser)
    run_parser.add_argument("prompt")
    run_parser.add_argument("--session", help="Continue an existing session")

    chat_parser = subparsers.add_parser("chat", help="Start an interactive session")
    _add_runtime_options(chat_parser)
    chat_parser.add_argument("--session", help="Continue an existing session")

    agents_parser = subparsers.add_parser("agents", help="List workspace agent definitions")
    agents_parser.add_argument("action", nargs="?", choices=("list",), default="list")
    agents_parser.add_argument("--workspace", help="Workspace directory")
    agents_parser.add_argument("--json", action="store_true")

    skills_parser = subparsers.add_parser("skills", help="List workspace skill definitions")
    skills_parser.add_argument("action", nargs="?", choices=("list",), default="list")
    skills_parser.add_argument("--workspace", help="Workspace directory")
    skills_parser.add_argument("--json", action="store_true")

    optimizations_parser = subparsers.add_parser(
        "optimizations", help="Manage model optimization profiles"
    )
    optimization_commands = optimizations_parser.add_subparsers(
        dest="optimization_command", required=True
    )
    optimization_list = optimization_commands.add_parser("list", help="List profiles")
    optimization_list.add_argument("--workspace", help="Workspace directory")
    optimization_list.add_argument("--json", action="store_true")
    optimization_install = optimization_commands.add_parser(
        "install", help="Install/update profiles from a JSON bundle"
    )
    optimization_install.add_argument("source", type=Path)
    optimization_install.add_argument("--workspace", help="Workspace directory")
    for command_name in ("enable", "disable"):
        command = optimization_commands.add_parser(
            command_name, help=f"{command_name.title()} a profile"
        )
        command.add_argument("id")
        command.add_argument("--workspace", help="Workspace directory")
    optimization_verify = optimization_commands.add_parser(
        "verify", help="Show enabled profiles for a model id"
    )
    optimization_verify.add_argument("model")
    optimization_verify.add_argument("--workspace", help="Workspace directory")
    optimization_verify.add_argument("--json", action="store_true")
    optimization_template = optimization_commands.add_parser(
        "template", help="Write built-in optimization profiles as a JSON bundle"
    )
    optimization_template.add_argument("--output", required=True, type=Path)

    prompts_parser = subparsers.add_parser("prompts", help="Render versioned prompt templates")
    prompt_commands = prompts_parser.add_subparsers(dest="prompt_command", required=True)
    prompt_render = prompt_commands.add_parser("render", help="Render a template")
    prompt_render.add_argument("--template-file", required=True, type=Path)
    prompt_render.add_argument("id")
    prompt_render.add_argument("--var", action="append", metavar="NAME=VALUE")
    prompt_validate = prompt_commands.add_parser("validate", help="Validate a template file")
    prompt_validate.add_argument("--template-file", required=True, type=Path)

    prompt_batch_parser = subparsers.add_parser(
        "prompt-batch", help="Validate and convert prompt batch files"
    )
    prompt_batch_commands = prompt_batch_parser.add_subparsers(
        dest="prompt_batch_command", required=True
    )
    prompt_batch_validate = prompt_batch_commands.add_parser(
        "validate", help="Summarize a prompt batch file"
    )
    prompt_batch_validate.add_argument("--file", required=True, type=Path)
    prompt_batch_convert = prompt_batch_commands.add_parser(
        "convert", help="Convert a prompt batch between JSON and JSONL"
    )
    prompt_batch_convert.add_argument("--input", required=True, type=Path)
    prompt_batch_convert.add_argument("--output", required=True, type=Path)
    prompt_batch_convert.add_argument(
        "--format",
        choices=["json", "jsonl"],
        default="jsonl",
    )

    inspect_prompt_parser = subparsers.add_parser(
        "inspect-prompt", help="Score a prompt with the injection classifier"
    )
    inspect_prompt_parser.add_argument("prompt", nargs="?")
    inspect_prompt_parser.add_argument("--file", type=Path)
    inspect_prompt_parser.add_argument(
        "--allowlisted-instruction",
        action="append",
        default=[],
    )

    openapi_parser = subparsers.add_parser("openapi", help="Validate OpenAPI documents")
    openapi_parser.add_argument("file", type=Path)
    openapi_parser.add_argument("--json", action="store_true")

    nodes_parser = subparsers.add_parser("nodes", help="List remote execution nodes")
    nodes_parser.add_argument("--config", type=Path, default=None)
    nodes_parser.add_argument("--json", action="store_true")

    subagents_parser = subparsers.add_parser("subagents", help="Run an isolated subagent")
    subagents_parser.add_argument("--workspace", required=True)
    subagents_parser.add_argument("--database", default=str(default_database_path()))
    subagents_parser.add_argument("--prompt", required=True)
    subagents_parser.add_argument("--provider", help="Provider id (or AGENT_WORKSPACE_PROVIDER)")
    subagents_parser.add_argument("--profile", help="Saved Provider profile id")
    subagents_parser.add_argument(
        "--protocol",
        choices=[protocol.value for protocol in ProviderProtocol],
    )
    subagents_parser.add_argument("--base-url", help="API base URL (or AGENT_WORKSPACE_BASE_URL)")
    subagents_parser.add_argument("--model", help="Model id (or AGENT_WORKSPACE_MODEL)")
    subagents_parser.add_argument("--title", default="CLI subagent")
    subagents_parser.add_argument("--allowed-tool", action="append", default=[])
    subagents_parser.add_argument("--mode", default=Mode.CODING.value)
    subagents_parser.add_argument("--autonomy", default=Autonomy.WORKSPACE.value)

    workspaces_parser = subparsers.add_parser("workspaces", help="Manage workspace catalog")
    workspace_commands = workspaces_parser.add_subparsers(dest="workspace_command", required=True)
    workspace_list = workspace_commands.add_parser("list")
    workspace_list.add_argument("--json", action="store_true")
    workspace_add = workspace_commands.add_parser("add")
    workspace_add.add_argument("path", type=Path)
    workspace_add.add_argument("--name")
    workspace_remove = workspace_commands.add_parser("remove")
    workspace_remove.add_argument("path", type=Path)
    workspace_touch = workspace_commands.add_parser("touch")
    workspace_touch.add_argument("path", type=Path)

    registry_parser = subparsers.add_parser("model-registry", help="Inspect latest models")
    registry_commands = registry_parser.add_subparsers(dest="registry_command", required=True)
    registry_list = registry_commands.add_parser("list")
    registry_list.add_argument("--file", type=Path)
    registry_list.add_argument("--json", action="store_true")
    registry_resolve = registry_commands.add_parser("resolve")
    registry_resolve.add_argument("model")
    registry_resolve.add_argument("--file", type=Path)

    events_parser = subparsers.add_parser("events", help="Export session events")
    events_parser.add_argument("--database", default=str(default_database_path()))
    events_parser.add_argument("--session", action="append", default=[])
    events_parser.add_argument("--output", required=True, type=Path)
    events_parser.add_argument("--json", action="store_true")

    archive_parser = subparsers.add_parser("archive", help="Sign and verify files")
    archive_commands = archive_parser.add_subparsers(dest="archive_command", required=True)
    archive_sign = archive_commands.add_parser("sign")
    archive_sign.add_argument("file", type=Path)
    archive_sign.add_argument("--key-env", required=True)
    archive_sign.add_argument("--output", required=True, type=Path)
    archive_verify = archive_commands.add_parser("verify")
    archive_verify.add_argument("file", type=Path)
    archive_verify.add_argument("signature", type=Path)
    archive_verify.add_argument("--key-env", required=True)

    history_parser = subparsers.add_parser("file-history", help="Inspect file version history")
    history_parser.add_argument("--database", default=str(default_database_path()))
    history_parser.add_argument("--session", required=True)
    history_parser.add_argument("--path")
    history_parser.add_argument("--json", action="store_true")

    queue_parser = subparsers.add_parser("queue", help="Manage durable run queue")
    queue_commands = queue_parser.add_subparsers(dest="queue_command", required=True)
    queue_enqueue = queue_commands.add_parser("enqueue")
    queue_enqueue.add_argument("--workspace", required=True)
    queue_enqueue.add_argument("--prompt", required=True)
    queue_enqueue.add_argument("--model", required=True)
    queue_enqueue.add_argument("--database", default=str(default_database_path()))
    queue_list = queue_commands.add_parser("list")
    queue_list.add_argument("--database", default=str(default_database_path()))
    queue_list.add_argument("--status")
    queue_list.add_argument("--json", action="store_true")
    for queue_command in ("claim", "cancel"):
        queue_subparser = queue_commands.add_parser(queue_command)
        queue_subparser.add_argument("task_id")
        queue_subparser.add_argument("--database", default=str(default_database_path()))
    for queue_command in ("complete", "fail"):
        queue_subparser = queue_commands.add_parser(queue_command)
        queue_subparser.add_argument("task_id")
        queue_subparser.add_argument("--claim-token", required=True)
        queue_subparser.add_argument("--database", default=str(default_database_path()))
        if queue_command == "fail":
            queue_subparser.add_argument("--error", required=True)

    plans_parser = subparsers.add_parser("plans", help="Manage durable goals and plan steps")
    plan_commands = plans_parser.add_subparsers(dest="plan_command", required=True)
    plan_create = plan_commands.add_parser("create")
    plan_create.add_argument("--database", default=str(default_database_path()))
    plan_create.add_argument("--session", required=True)
    plan_create.add_argument("--goal-id", required=True)
    plan_create.add_argument("--title", required=True)
    plan_list = plan_commands.add_parser("list")
    plan_list.add_argument("--database", default=str(default_database_path()))
    plan_list.add_argument("--session", required=True)
    plan_list.add_argument("--json", action="store_true")
    plan_step = plan_commands.add_parser("step")
    plan_step.add_argument("--database", default=str(default_database_path()))
    plan_step.add_argument("--session", required=True)
    plan_step.add_argument("--goal-id", required=True)
    plan_step.add_argument("--step-id", required=True)
    plan_step.add_argument("--title", required=True)
    plan_step.add_argument("--status", default="pending")
    plan_step.add_argument("--position", type=int, default=0)
    plan_step.add_argument("--parent-step-id")
    plan_steps = plan_commands.add_parser("steps")
    plan_steps.add_argument("--database", default=str(default_database_path()))
    plan_steps.add_argument("--session", required=True)
    plan_steps.add_argument("--goal-id")
    plan_steps.add_argument("--json", action="store_true")
    plan_update = plan_commands.add_parser("update")
    plan_update.add_argument("--database", default=str(default_database_path()))
    plan_update.add_argument("--session", required=True)
    plan_update.add_argument("--goal-id", required=True)
    plan_update.add_argument("--status", required=True)

    pipelines_parser = subparsers.add_parser("pipelines", help="Manage durable pipelines")
    pipeline_commands = pipelines_parser.add_subparsers(dest="pipeline_command", required=True)
    pipeline_create = pipeline_commands.add_parser("create")
    pipeline_create.add_argument("--database", default=str(default_database_path()))
    pipeline_create.add_argument("--definition", required=True, type=Path)
    pipeline_list = pipeline_commands.add_parser("list")
    pipeline_list.add_argument("--database", default=str(default_database_path()))
    pipeline_list.add_argument("--json", action="store_true")
    pipeline_start = pipeline_commands.add_parser("start")
    pipeline_start.add_argument("pipeline_id")
    pipeline_start.add_argument("--database", default=str(default_database_path()))
    for pipeline_step_command in ("start-step", "complete-step"):
        pipeline_step = pipeline_commands.add_parser(pipeline_step_command)
        pipeline_step.add_argument("pipeline_id")
        pipeline_step.add_argument("step_id")
        pipeline_step.add_argument("--database", default=str(default_database_path()))
    pipeline_fail = pipeline_commands.add_parser("fail-step")
    pipeline_fail.add_argument("pipeline_id")
    pipeline_fail.add_argument("step_id")
    pipeline_fail.add_argument("--error", required=True)
    pipeline_fail.add_argument("--database", default=str(default_database_path()))

    evals_parser = subparsers.add_parser("evals", help="Run offline agent evaluations")
    evals_parser.add_argument("action", nargs="?", choices=("run",), default="run")
    evals_parser.add_argument("--directory", required=True, type=Path)
    evals_parser.add_argument("--workspace", help="Workspace directory")

    bench_parser = subparsers.add_parser("bench", help="Run weighted agent benchmarks")
    bench_parser.add_argument("action", nargs="?", choices=("run",), default="run")
    bench_parser.add_argument(
        "--workspace",
        help="Workspace directory (default: a fresh temporary workspace)",
    )
    bench_parser.add_argument(
        "--case",
        action="append",
        metavar="ID",
        help="Run only this benchmark case (repeatable)",
    )
    bench_parser.add_argument(
        "--directory",
        action="append",
        dest="scenario_directories",
        type=Path,
        help="Load benchmark scenarios from Python modules under this directory",
    )
    bench_parser.add_argument(
        "--scenario",
        action="append",
        dest="scenario_files",
        type=Path,
        help="Load a single benchmark scenario Python module",
    )
    bench_parser.add_argument("--profile", help="Saved Provider profile id")
    bench_parser.add_argument("--provider", help="Provider id (or AGENT_WORKSPACE_PROVIDER)")
    bench_parser.add_argument(
        "--protocol",
        choices=[protocol.value for protocol in ProviderProtocol],
    )
    bench_parser.add_argument("--base-url", help="API base URL (or AGENT_WORKSPACE_BASE_URL)")
    bench_parser.add_argument("--model", help="Model id (or AGENT_WORKSPACE_MODEL)")
    bench_parser.add_argument("--json", action="store_true", help="Emit the report as JSON")

    serve_parser = subparsers.add_parser("serve", help="Serve the authenticated remote API")
    _add_runtime_options(serve_parser)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--token", help="Bearer token (default: generated)")

    sessions_parser = subparsers.add_parser(
        "sessions", help="List, search, verify, import, or export sessions"
    )
    sessions_parser.add_argument(
        "session_action",
        nargs="?",
        choices=(
            "list",
            "search",
            "verify",
            "import",
            "export",
            "cost",
            "fork",
            "comment",
            "comments",
            "checkpoints",
        ),
        default="list",
    )
    sessions_parser.add_argument("session_value", nargs="?")
    sessions_parser.add_argument("--database", default=str(default_database_path()))
    sessions_parser.add_argument("--limit", type=int, default=50)
    sessions_parser.add_argument("--workspace", type=Path)
    sessions_parser.add_argument("--json", action="store_true")
    sessions_parser.add_argument("--output", type=Path)
    sessions_parser.add_argument("--comment", help="Comment text for sessions comment")
    sessions_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Copy the original session workspace into the fork destination",
    )

    todos_parser = subparsers.add_parser("todos", help="Manage durable session Todo items")
    todo_commands = todos_parser.add_subparsers(dest="todo_command", required=True)
    todo_list = todo_commands.add_parser("list", help="List Todo items")
    todo_list.add_argument("--session", required=True)
    todo_list.add_argument("--database", default=str(default_database_path()))
    todo_list.add_argument("--json", action="store_true")
    todo_add = todo_commands.add_parser("add", help="Add a Todo item")
    todo_add.add_argument("content")
    todo_add.add_argument("--session", required=True)
    todo_add.add_argument("--database", default=str(default_database_path()))
    for command_name in ("complete", "delete"):
        command = todo_commands.add_parser(command_name, help=f"{command_name.title()} a Todo")
        command.add_argument("id")
        command.add_argument("--session", required=True)
        command.add_argument("--database", default=str(default_database_path()))

    backups_parser = subparsers.add_parser("backups", help="Manage verified backups")
    backup_commands = backups_parser.add_subparsers(dest="backups_command", required=True)
    backup_create = backup_commands.add_parser("create", help="Create a verified backup")
    backup_create.add_argument("--database", default=str(default_database_path()))
    backup_create.add_argument("--directory", type=Path, default=default_backup_dir())
    backup_create.add_argument("--keep", type=int, default=10)
    backup_create.add_argument("--max-age-days", type=int, default=30)
    backup_create.add_argument("--max-total-bytes", type=int, default=10 * 1024 * 1024 * 1024)
    backup_create.add_argument(
        "--incremental",
        action="store_true",
        help="Record a parent backup digest for the snapshot chain",
    )
    backup_verify = backup_commands.add_parser("verify", help="Verify a backup")
    backup_verify.add_argument("backup", type=Path)
    backup_restore = backup_commands.add_parser("restore", help="Restore a backup")
    backup_restore.add_argument("backup", type=Path)
    backup_restore.add_argument("--destination", required=True, type=Path)

    db_parser = subparsers.add_parser("db", help="Inspect database and workspace storage")
    db_commands = db_parser.add_subparsers(dest="db_command", required=True)
    db_integrity = db_commands.add_parser("integrity", help="Run SQLite integrity checks")
    db_integrity.add_argument("--database", default=str(default_database_path()))
    db_disk = db_commands.add_parser("disk-usage", help="Report workspace disk usage")
    db_disk.add_argument("--workspace", default=".")
    db_disk.add_argument("--top-n", type=int, default=10)

    approval_batch_parser = subparsers.add_parser(
        "approval-batch", help="Review approvals in batch"
    )
    approval_batch_commands = approval_batch_parser.add_subparsers(
        dest="approval_batch_command", required=True
    )
    approval_batch_submit = approval_batch_commands.add_parser(
        "submit", help="Submit one approval request"
    )
    approval_batch_submit.add_argument("--file", required=True, type=Path)
    approval_batch_submit.add_argument("--tool", required=True)
    approval_batch_submit.add_argument("--arguments", required=True)
    approval_batch_submit.add_argument("--session")
    approval_batch_submit.add_argument("--priority", type=int, default=100)
    approval_batch_submit.add_argument("--ttl-seconds", type=float, default=300.0)
    approval_batch_list = approval_batch_commands.add_parser(
        "list", help="List pending approval requests"
    )
    approval_batch_list.add_argument("--file", required=True, type=Path)
    approval_batch_review = approval_batch_commands.add_parser(
        "review", help="Apply batch allow/deny decisions"
    )
    approval_batch_review.add_argument("--file", required=True, type=Path)
    approval_batch_review.add_argument("--allow", action="append", default=[])
    approval_batch_review.add_argument("--deny", action="append", default=[])
    approval_batch_review.add_argument("--reason", default="")
    approval_batch_review.add_argument("--dry-run", action="store_true")

    artifacts_parser = subparsers.add_parser(
        "artifacts", help="Manage the content-addressed build artifact cache"
    )
    artifact_commands = artifacts_parser.add_subparsers(dest="artifact_command", required=True)
    artifact_put = artifact_commands.add_parser("put", help="Store an artifact")
    artifact_put.add_argument("--cache", type=Path, required=True)
    artifact_put.add_argument("source", type=Path)
    artifact_get = artifact_commands.add_parser("get", help="Verify and locate an artifact")
    artifact_get.add_argument("--cache", type=Path, required=True)
    artifact_get.add_argument("digest")
    artifact_stats = artifact_commands.add_parser("stats", help="Summarize the artifact cache")
    artifact_stats.add_argument("--cache", type=Path, required=True)
    artifact_prune = artifact_commands.add_parser("prune", help="Prune oldest artifacts")
    artifact_prune.add_argument("--cache", type=Path, required=True)
    artifact_prune.add_argument("--max-bytes", type=int, required=True)
    artifact_prune.add_argument("--dry-run", action="store_true")

    audit_retention_parser = subparsers.add_parser(
        "audit-retention", help="Apply retention policy to exported audit logs"
    )
    audit_retention_parser.add_argument("--directory", type=Path, required=True)
    audit_retention_parser.add_argument("--max-age-days", type=int, default=365)
    audit_retention_parser.add_argument("--max-files", type=int, default=180)
    audit_retention_parser.add_argument(
        "--max-total-bytes",
        type=int,
        default=10 * 1024 * 1024 * 1024,
    )
    audit_retention_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("process-limits", help="Report current process resource usage and limits")

    env_parser = subparsers.add_parser("env", help="Manage workspace environment variables")
    env_commands = env_parser.add_subparsers(dest="env_command", required=True)
    env_list = env_commands.add_parser("list", help="List workspace environment variables")
    env_list.add_argument("--workspace", default=".")
    env_list.add_argument("--json", action="store_true")
    env_list.add_argument("--show-secrets", action="store_true")
    env_get = env_commands.add_parser("get", help="Read one workspace environment variable")
    env_get.add_argument("name")
    env_get.add_argument("--workspace", default=".")
    env_get.add_argument("--json", action="store_true")
    env_get.add_argument("--show-secrets", action="store_true")
    env_set = env_commands.add_parser("set", help="Set a workspace environment variable")
    env_set.add_argument("name")
    env_set.add_argument("value")
    env_set.add_argument("--workspace", default=".")
    env_set.add_argument("--secret", action="store_true")
    env_unset = env_commands.add_parser("unset", help="Remove a workspace environment variable")
    env_unset.add_argument("name")
    env_unset.add_argument("--workspace", default=".")

    schedule_parser = subparsers.add_parser("schedule", help="Inspect cron schedule triggers")
    schedule_commands = schedule_parser.add_subparsers(dest="schedule_command", required=True)
    schedule_preview_parser = schedule_commands.add_parser(
        "preview", help="Preview the next runs of a cron expression"
    )
    schedule_preview_parser.add_argument("expression")
    schedule_preview_parser.add_argument("--count", type=int, default=5)

    replay_patch_parser = subparsers.add_parser(
        "replay-patch", help="Plan event sequence patches for stored sessions"
    )
    replay_patch_parser.add_argument("--database", default=str(default_database_path()))
    replay_patch_parser.add_argument("--session")

    transcript_merge_parser = subparsers.add_parser(
        "transcript-merge", help="Merge multiple session transcripts chronologically"
    )
    transcript_merge_parser.add_argument(
        "--session",
        action="append",
        default=[],
        required=True,
        help="Session id to merge; repeat for multiple sessions",
    )
    transcript_merge_parser.add_argument("--database", default=str(default_database_path()))

    search_batch_parser = subparsers.add_parser(
        "search-batch", help="Run several queries across sessions and merge rankings"
    )
    search_batch_parser.add_argument(
        "--query",
        action="append",
        default=[],
        required=True,
        help="Search query; repeat for multiple queries",
    )
    search_batch_parser.add_argument("--database", default=str(default_database_path()))
    search_batch_parser.add_argument("--limit", type=int, default=20)

    context_probe_parser = subparsers.add_parser(
        "context-probe", help="Probe whether a prompt fits a model context window"
    )
    context_probe_parser.add_argument("--model", required=True)
    context_probe_parser.add_argument("--context-limit", type=int, required=True)
    context_probe_parser.add_argument("prompt", nargs="?")
    context_probe_parser.add_argument("--file", type=Path)
    context_probe_parser.add_argument("--system-prompt", default="")
    context_probe_parser.add_argument("--reserve-output", type=int, default=1024)

    doctor_parser = subparsers.add_parser("doctor", help="Check local configuration")
    _add_runtime_options(doctor_parser)
    doctor_parser.set_defaults(
        workspace=".",
        mode=Mode.CODING.value,
        autonomy=Autonomy.WORKSPACE.value,
    )

    credentials_parser = subparsers.add_parser(
        "credentials", help="Inspect and rotate credential age"
    )
    credential_commands = credentials_parser.add_subparsers(
        dest="credential_command", required=True
    )
    credential_status = credential_commands.add_parser("status")
    credential_status.add_argument("provider")
    credential_rotate = credential_commands.add_parser("rotate")
    credential_rotate.add_argument("provider")
    credential_rotate.add_argument("--secret-env", required=True)
    credential_recommend = credential_commands.add_parser("recommendations")
    credential_recommend.add_argument("--warn-days", type=float, default=60.0)
    credential_recommend.add_argument("--rotate-days", type=float, default=90.0)
    credential_health = credential_commands.add_parser(
        "health", help="Render credential health dashboard data"
    )
    credential_health.add_argument("--warn-days", type=float, default=60.0)
    credential_health.add_argument("--rotate-days", type=float, default=90.0)

    providers_parser = subparsers.add_parser("providers", help="Manage Provider profiles")
    provider_commands = providers_parser.add_subparsers(dest="provider_command", required=True)

    provider_list = provider_commands.add_parser("list", help="List Provider profiles")
    provider_list.add_argument("--json", action="store_true")

    provider_set = provider_commands.add_parser("set", help="Create or update a profile")
    provider_set.add_argument("id")
    provider_set.add_argument("--name")
    provider_set.add_argument(
        "--protocol",
        required=True,
        choices=[protocol.value for protocol in ProviderProtocol],
    )
    provider_set.add_argument("--base-url", required=True)
    provider_set.add_argument("--model", required=True)
    provider_set.add_argument(
        "--api-key-env",
        help="Read the key from this environment variable and store it securely",
    )
    provider_set.add_argument("--default", action="store_true")

    provider_delete = provider_commands.add_parser("delete", help="Delete a profile")
    provider_delete.add_argument("id")

    provider_default = provider_commands.add_parser("default", help="Set the default profile")
    provider_default.add_argument("id")

    provider_test = provider_commands.add_parser("test", help="Send a minimal model request")
    provider_test.add_argument("id", nargs="?")
    return parser


async def _async_main(args: argparse.Namespace) -> int:
    if args.command == "run":
        return await _run_once(args)
    if args.command == "chat":
        return await _chat(args)
    raise AssertionError(f"unsupported async command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "sessions":
            return _run_sessions(args)
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "credentials":
            return _credentials_run(args)
        if args.command == "providers":
            if args.provider_command == "list":
                return _provider_list(args)
            if args.provider_command == "set":
                return _provider_set(args)
            if args.provider_command == "delete":
                return _provider_delete(args)
            if args.provider_command == "default":
                return _provider_default(args)
            if args.provider_command == "test":
                return asyncio.run(_provider_test(args))
            raise AssertionError(f"unsupported provider command: {args.provider_command}")
        if args.command == "todos":
            if args.todo_command == "list":
                return _todo_list(args)
            return _todo_mutation(args)
        if args.command == "backups":
            return _run_backups(args)
        if args.command == "db":
            return _db_run(args)
        if args.command == "approval-batch":
            return _approval_batch_run(args)
        if args.command == "artifacts":
            return _artifacts_run(args)
        if args.command == "audit-retention":
            return _audit_retention_run(args)
        if args.command == "process-limits":
            return _process_limits_run(args)
        if args.command == "env":
            return _env_run(args)
        if args.command == "schedule":
            return _schedule_run(args)
        if args.command == "replay-patch":
            return _replay_patch_run(args)
        if args.command == "transcript-merge":
            return _transcript_merge_run(args)
        if args.command == "search-batch":
            return _search_batch_run(args)
        if args.command == "context-probe":
            return _context_probe_run(args)
        if args.command == "agents":
            return _agents_list(args)
        if args.command == "skills":
            return _skills_list(args)
        if args.command == "optimizations":
            if args.optimization_command == "list":
                return _optimizations_list(args)
            if args.optimization_command == "install":
                return _optimizations_install(args)
            if args.optimization_command == "enable":
                return _optimizations_set_enabled(args, enabled=True)
            if args.optimization_command == "disable":
                return _optimizations_set_enabled(args, enabled=False)
            if args.optimization_command == "verify":
                return _optimizations_verify(args)
            if args.optimization_command == "template":
                return _optimizations_template(args)
            raise AssertionError(f"unsupported optimization command: {args.optimization_command}")
        if args.command == "shell-completion":
            return _shell_completion_run(args)
        if args.command == "prompts":
            return _prompts_render(args)
        if args.command == "prompt-batch":
            return _prompt_batch_run(args)
        if args.command == "inspect-prompt":
            return _inspect_prompt_run(args)
        if args.command == "openapi":
            return _openapi_validate_run(args)
        if args.command == "nodes":
            return _nodes_run(args)
        if args.command == "subagents":
            return _subagents_run(args)
        if args.command == "workspaces":
            return _workspaces_run(args)
        if args.command == "model-registry":
            return _model_registry_run(args)
        if args.command == "events":
            return _events_run(args)
        if args.command == "archive":
            return _archive_run(args)
        if args.command == "file-history":
            return _file_history_run(args)
        if args.command == "queue":
            return _queue_run(args)
        if args.command == "plans":
            return _plans_run(args)
        if args.command == "pipelines":
            return _pipelines_run(args)
        if args.command == "evals":
            return _evals_run(args)
        if args.command == "bench":
            return asyncio.run(_bench_run(args))
        if args.command == "serve":
            return asyncio.run(_serve(args))
        return asyncio.run(_async_main(args))
    except AlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return _WRITE_LOCK_EXIT
    except ApprovalRequiredError as exc:
        print(f"approval required: {exc}", file=sys.stderr)
        return _APPROVAL_REQUIRED_EXIT
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except (
        BackupValidationError,
        BudgetExceededError,
        KeyError,
        OSError,
        ProviderError,
        ProviderEgressDeniedError,
        SearchIndexUnavailableError,
        TimeoutError,
        sqlite3.Error,
    ) as exc:
        print(f"runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
