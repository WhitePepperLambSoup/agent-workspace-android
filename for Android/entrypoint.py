#!/usr/bin/env python3
"""Android / Termux 端主入口点。

负责在零侵入修改原项目的前提下:
1. 挂载 android_adapter 运行时垫片 (凭据、PTY、进程组、系统级工具);
2. 调度执行原项目的完整 CLI, 或启动专为手机触摸优化的 Web 伴侣服务。
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import os
import secrets
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

if TYPE_CHECKING:
    from mobile_workspaces import MobileWorkspaceCatalog, MobileWorkspaceController

    from agent_workspace.application.runtime import ApplicationRuntime
    from agent_workspace.config import ProviderConfig
    from agent_workspace.core.models import Autonomy

# 确保将当前适配层和主项目的 src 目录加载到 sys.path
THIS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = THIS_DIR.parent
SRC_DIR = AGENT_ROOT / "src"

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# 导入并应用内存运行时补丁
if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy":
    from android_adapter.chaquopy_runtime import install_android_runtime

    install_android_runtime()
else:
    from android_adapter.patcher import apply_android_patches

    apply_android_patches()


def _load_mobile_assets(token: str) -> tuple[str, dict[str, tuple[str, bytes]]]:
    web_root = THIS_DIR / "web_companion"
    encoded_token = quote(token, safe="")
    console_html = (
        (web_root / "index.html")
        .read_text(encoding="utf-8")
        .replace("__AGENT_TOKEN__", html.escape(token, quote=True))
    )
    console_html = console_html.replace(
        'href="/static/style.css"', f'href="/static/style.css?token={encoded_token}"'
    )
    console_html = console_html.replace(
        'src="/static/app.js"', f'src="/static/app.js?token={encoded_token}"'
    )
    console_html = console_html.replace(
        'src="/static/mobile-vendor.js"',
        f'src="/static/mobile-vendor.js?token={encoded_token}"',
    )
    console_html = console_html.replace(
        'src="/static/management.js"',
        f'src="/static/management.js?token={encoded_token}"',
    )
    console_html = console_html.replace(
        'src="/static/i18n.js"', f'src="/static/i18n.js?token={encoded_token}"'
    )
    console_html = console_html.replace(
        'src="/static/liquid-glass.js"',
        f'src="/static/liquid-glass.js?token={encoded_token}"',
    )
    console_html = console_html.replace(
        'href="/manifest.json"', f'href="/manifest.json?token={encoded_token}"'
    )
    assets = {
        "/static/style.css": (
            "text/css; charset=utf-8",
            (web_root / "static" / "style.css").read_bytes(),
        ),
        "/static/app.js": (
            "application/javascript; charset=utf-8",
            (web_root / "static" / "app.js").read_bytes(),
        ),
        "/static/mobile-vendor.js": (
            "application/javascript; charset=utf-8",
            (web_root / "static" / "mobile-vendor.js").read_bytes(),
        ),
        "/static/management.js": (
            "application/javascript; charset=utf-8",
            (web_root / "static" / "management.js").read_bytes(),
        ),
        "/static/i18n.js": (
            "application/javascript; charset=utf-8",
            (web_root / "static" / "i18n.js").read_bytes(),
        ),
        "/static/liquid-glass.js": (
            "application/javascript; charset=utf-8",
            (web_root / "static" / "liquid-glass.js").read_bytes(),
        ),
        "/manifest.json": (
            "application/manifest+json; charset=utf-8",
            (web_root / "manifest.json").read_bytes(),
        ),
    }
    return console_html, assets


async def _build_mobile_workspace_runtime(
    workspace: Path,
    database: Path,
    config: ProviderConfig,
    *,
    autonomy: Autonomy,
) -> tuple[ApplicationRuntime, MobileWorkspaceController, MobileWorkspaceCatalog]:
    """Build one lifecycle anchor and an independently owned runtime per conversation."""
    from mobile_extensions import MobileExtensionConsentStore
    from mobile_extensions import build_mobile_runtime_async as build_runtime_async
    from mobile_runtime_controller import (
        MobileRuntimeController,
        migrate_workspace_sessions_autonomy,
    )
    from mobile_task_store import MobileTaskStore
    from mobile_workspaces import MobileWorkspaceCatalog, MobileWorkspaceController

    from agent_workspace.application.ports import ApprovalDecision
    from agent_workspace.core.session import Session
    from agent_workspace.storage.lock import ProcessWriteLockGroup

    database = database.expanduser().resolve()
    catalog = MobileWorkspaceCatalog(database, workspace)
    writer_locks = ProcessWriteLockGroup()

    async def build_controller(
        root: Path, consent_path: Path, *, session_id: str | None = None
    ) -> tuple[MobileRuntimeController, ApplicationRuntime]:
        controller: MobileRuntimeController | None = None
        extension_consents = MobileExtensionConsentStore(consent_path, root)

        async def runtime_event_listener(event: object) -> None:
            if controller is not None:
                await controller.handle_runtime_event(event)  # type: ignore[arg-type]

        async def approval_callback(tool: object, arguments: dict[str, object]) -> ApprovalDecision:
            if controller is None:
                return ApprovalDecision(False, "mobile runtime controller is not ready")
            return await controller.authorize_tool(tool, arguments)  # type: ignore[arg-type]

        async def egress_approval_callback(request: object) -> ApprovalDecision:
            if controller is None:
                return ApprovalDecision(False, "mobile runtime controller is not ready")
            return await controller.authorize_egress(request)  # type: ignore[arg-type]

        runtime = await build_runtime_async(
            root,
            database,
            config,
            autonomy=autonomy,
            approval_callback=approval_callback,
            egress_approval_callback=egress_approval_callback,
            extension_consents=extension_consents,
            event_listener=runtime_event_listener,
            writer_lock_group=writer_locks,
        )
        try:
            extension_consents.bind_runtime(runtime)
            migrate_workspace_sessions_autonomy(runtime.store, root, autonomy)
            controller = MobileRuntimeController(
                runtime,
                default_model=config.model,
                default_reasoning_effort=os.getenv("AGENT_WORKSPACE_REASONING_EFFORT") or "auto",
                protocol=config.protocol.value,
                base_url=config.base_url,
                task_store=(
                    MobileTaskStore(runtime.store, session_id=session_id)
                    if session_id is not None
                    else None
                ),
            )
            controller.extension_consents = extension_consents
            return controller, runtime
        except BaseException:
            await runtime.aclose()
            raise

    base_controller, runtime = await build_controller(
        workspace,
        database.parent / "mobile-extensions.json",
    )

    async def child_controller(
        session: Session,
    ) -> tuple[MobileRuntimeController, ApplicationRuntime]:
        identity = hashlib.sha256(session.id.encode()).hexdigest()
        return await build_controller(
            Path(session.workspace),
            database.parent / "mobile-extension-consents" / f"{identity}.json",
            session_id=session.id,
        )

    router = MobileWorkspaceController(
        runtime.store,
        catalog,
        child_controller,
        base_controller=base_controller,
    )
    try:
        # Recover all visible durable tasks before lazily starting session controllers.
        await router.start()
    except BaseException:
        await runtime.aclose()
        raise
    return runtime, router, catalog


def _publish_serve_token(token: str) -> None:
    token_file = os.getenv("AGENT_WORKSPACE_SERVE_TOKEN_FILE")
    if not token_file:
        return
    token_path = Path(token_file).expanduser()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename, so a reader never sees a partial token.
    staging = token_path.with_name(f".{token_path.name}.tmp")
    staging.write_text(token, encoding="utf-8")
    with suppress(OSError):
        staging.chmod(0o600)
    os.replace(staging, token_path)


_STALL_LOG_BYTES = 256 * 1024


async def _stall_watchdog(log_path: Path, *, interval: float = 5.0, stall_after: float = 45.0) -> None:
    """Record every thread's stack once whenever the event loop stops running for stall_after s.

    faulthandler's timer runs in a C thread that needs neither the loop nor the GIL, so it still
    fires when the engine is wedged; each heartbeat re-arms it while the loop is healthy.
    """
    import faulthandler

    with suppress(OSError):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists() and log_path.stat().st_size > _STALL_LOG_BYTES:
            log_path.replace(log_path.with_suffix(".log.1"))
    try:
        handle = log_path.open("a", encoding="utf-8")
    except OSError:
        return
    try:
        while True:
            faulthandler.dump_traceback_later(stall_after, repeat=False, file=handle)
            await asyncio.sleep(interval)
    finally:
        faulthandler.cancel_dump_traceback_later()
        handle.close()


def _arm_stall_dump(log_path: Path, after: float) -> Any:
    """Dump every thread's stack to log_path if not disarmed within `after` seconds."""
    import faulthandler

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = log_path.open("a", encoding="utf-8")
    except OSError:
        return None
    handle.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} engine shutdown started\n")
    handle.flush()
    faulthandler.dump_traceback_later(after, repeat=False, file=handle)
    return handle


def _disarm_stall_dump(handle: Any) -> None:
    import faulthandler

    if handle is None:
        return
    faulthandler.cancel_dump_traceback_later()
    with suppress(OSError):
        handle.close()


async def _run_mobile_web_server(
    host: str,
    port: int,
    *,
    workspace: Path,
    database: Path,
) -> None:
    from mobile_gateway import MobileGateway
    from mobile_runtime_controller import configured_mobile_autonomy

    from agent_workspace.config import ProviderConfig, provider_origin
    from agent_workspace.core.model_registry import builtin_latest_models

    config = ProviderConfig.from_environment()
    autonomy = configured_mobile_autonomy()
    runtime, controller, workspace_catalog = await _build_mobile_workspace_runtime(
        workspace, database, config, autonomy=autonomy
    )
    token = os.getenv("AGENT_WORKSPACE_SERVE_TOKEN") or secrets.token_urlsafe(32)
    console_html, assets = _load_mobile_assets(token)
    family_by_endpoint = {
        ("openai-compatible", "api.openai.com"): ("openai-gpt",),
        ("openai-compatible", "api.deepseek.com"): ("deepseek-v4", "deepseek-v4.1"),
        ("anthropic", "api.anthropic.com"): ("anthropic-claude",),
        ("gemini", "generativelanguage.googleapis.com"): ("google-gemini",),
        ("openai-compatible", "api.x.ai"): ("xai-grok",),
        ("openai-compatible", "dashscope.aliyuncs.com"): ("alibaba-qwen",),
        ("openai-compatible", "dashscope-intl.aliyuncs.com"): ("alibaba-qwen",),
        ("openai-compatible", "api.moonshot.ai"): ("moonshot-kimi",),
        ("openai-compatible", "api.moonshot.cn"): ("moonshot-kimi",),
        ("openai-compatible", "api.z.ai"): ("zai-glm",),
        ("openai-compatible", "open.bigmodel.cn"): ("zai-glm",),
    }
    families = family_by_endpoint.get(
        (config.protocol.value, provider_origin(config.base_url)[1]), ()
    )
    models = [config.model]
    for snapshot in builtin_latest_models().snapshots():
        if snapshot.family in families and snapshot.status in {"current", "preview"}:
            models.append(
                "deepseek-v4-pro" if snapshot.id.startswith("deepseek-v4-pro-") else snapshot.id
            )
    api = MobileGateway(
        runtime,
        controller,
        host=host,
        port=port,
        token=token,
        default_model=config.model,
        settings={
            "protocol": config.protocol.value,
            "base_url": config.base_url,
            "autonomy": autonomy.value,
            "local_context_tokens": int(os.getenv("AGENT_WORKSPACE_LOCAL_CONTEXT_TOKENS", "0")),
            "local_memory_mode": os.getenv("AGENT_WORKSPACE_LOCAL_MEMORY_MODE", "balanced"),
            "models": models,
        },
        console_html=console_html,
        static_assets=assets,
        workspace_catalog=workspace_catalog,
    )
    api.start()
    # Publish the token only once this engine owns the port. Writing it earlier let a new engine
    # that failed to bind (a stalled predecessor still listening) advertise a token that nothing
    # on the port could prove, and the app waited on the identity check forever.
    _publish_serve_token(token)
    console_url = f"{api.address}/console"
    if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") != "chaquopy":
        console_url += f"?token={token}"
    print(
        f"Agent Workspace mobile Serve API listening on {console_url}",
        flush=True,
    )
    data_dir = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    watchdog = (
        asyncio.create_task(_stall_watchdog(Path(data_dir) / "logs" / "engine-stalls.log"))
        if data_dir
        else None
    )
    try:
        await asyncio.Event().wait()
    finally:
        if watchdog is not None:
            watchdog.cancel()
            with suppress(asyncio.CancelledError):
                await watchdog
        # The Android service gives a stopping engine 10 s before replacing its process. If shutdown
        # hangs, record where at 8 s so the cause survives the replacement.
        shutdown_log = _arm_stall_dump(Path(data_dir) / "logs" / "engine-stalls.log", 8.0) if data_dir else None
        try:
            api.stop()
            try:
                await api.aclose_management()
            finally:
                try:
                    await controller.aclose()
                finally:
                    try:
                        await controller.base_controller.aclose()
                    finally:
                        await runtime.aclose()
        finally:
            _disarm_stall_dump(shutdown_log)


def run_mobile_web_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start the authenticated mobile API backed by the real application runtime."""
    workspace = (
        Path(os.getenv("AGENT_WORKSPACE_ANDROID_WORKSPACE") or os.getcwd())
        .expanduser()
        .resolve(strict=True)
    )
    database = (
        Path(
            os.getenv("AGENT_WORKSPACE_ANDROID_DATABASE")
            or (Path.home() / ".agent-workspace" / "data" / "agent.db")
        )
        .expanduser()
        .resolve()
    )
    database.parent.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(_run_mobile_web_server(host, port, workspace=workspace, database=database))
    except KeyboardInterrupt:
        return


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("serve-mobile", "--web"):
        host = "127.0.0.1"
        port = 8080
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        if "--host" in sys.argv:
            idx = sys.argv.index("--host")
            if idx + 1 < len(sys.argv):
                host = sys.argv[idx + 1]
        run_mobile_web_server(host=host, port=port)
    else:
        # 委托给原项目的 CLI 逻辑
        from agent_workspace.cli import main as cli_main

        cli_main()


if __name__ == "__main__":
    main()
