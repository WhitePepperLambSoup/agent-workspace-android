"""Truthful capability discovery for the embedded Android runtime.

The APK ships the same Python package as desktop, but it does not ship a
Windows shell, ConPTY, PowerShell, or a Docker daemon.  This module narrows
the registry to tools that can actually run in the current process and keeps a
bounded reason for every tool that was withheld.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .documents import document_status

_PROBE_CACHE: dict[str, Any] = {}
_DISCOVERY_LOCK = threading.Lock()
_EXECUTABLE_LIMIT = 32 * 1024 * 1024


def _executable(path: str | None) -> dict[str, str] | None:
    if not path:
        return None
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
        metadata = candidate.stat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > _EXECUTABLE_LIMIT
            or not os.access(candidate, os.X_OK)
        ):
            return None
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        return {"path": str(candidate), "sha256": digest}
    except (OSError, ValueError):
        return None


def _probe(path: str, name: str) -> bool:
    from .terminal import _run_sync

    arguments = [path, "--version"]
    if name == "shell":
        arguments = [path, "-c", "printf agent-workspace-shell"]
    elif name in {"toybox", "termux_api"}:
        # Termux:API commands may wait for another app; do not contact it during discovery.
        if name == "termux_api":
            return True
        arguments = [path, "--help"]
    try:
        result = _run_sync(arguments, str(Path.cwd()), 1, "", threading.Event())
        return result["returncode"] == 0 and not result["timed_out"]
    except Exception:
        return False


def discover_runnable_executables(
    workspace: str | os.PathLike[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Probe fixed runtime executables, excluding files inside the agent workspace."""
    embedded = os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy"
    from .toolchain import installed_toolchain

    toolchain = installed_toolchain(workspace)
    toolchain_executables = toolchain.executables() if toolchain is not None else {}
    cache_key = (
        sys.executable,
        os.environ.get("PATH"),
        embedded,
        str(workspace),
        tuple((key, value.get("sha256")) for key, value in toolchain_executables.items()),
    )
    with _DISCOVERY_LOCK:
        if (
            _PROBE_CACHE.get("key") == cache_key
            and time.monotonic() - _PROBE_CACHE.get("time", 0) < 30
        ):
            return {name: dict(entry) for name, entry in _PROBE_CACHE["executables"].items()}
    candidates: dict[str, str | None] = {
        "python": shutil.which("python3") if embedded else sys.executable,
        "shell": "/system/bin/sh" if os.name != "nt" else None,
        "toybox": "/system/bin/toybox" if os.name != "nt" else None,
        "git": shutil.which("git"),
        "node": shutil.which("node"),
        "termux_api": shutil.which("termux-clipboard-get"),
        "pylsp": shutil.which("pylsp"),
        "pyright": shutil.which("pyright-langserver"),
        "typescript_lsp": shutil.which("typescript-language-server"),
        "rust_analyzer": shutil.which("rust-analyzer"),
        "gopls": shutil.which("gopls"),
    }
    result: dict[str, dict[str, str]] = {}
    for name, path in candidates.items():
        executable = _executable(path)
        if executable is not None and workspace is not None:
            try:
                Path(executable["path"]).relative_to(Path(workspace).resolve())
            except ValueError:
                pass
            else:
                continue
        if executable is not None and _probe(executable["path"], name):
            result[name] = executable
    result.update(toolchain_executables)
    with _DISCOVERY_LOCK:
        _PROBE_CACHE.update(key=cache_key, time=time.monotonic(), executables=result)
    return result


def browser_status() -> dict[str, Any]:
    import json
    import urllib.request
    from urllib.parse import urlsplit

    endpoint = os.getenv("AGENT_WORKSPACE_CDP_URL")
    if not endpoint:
        return {"available": False, "reason": "No local Chrome DevTools endpoint is configured"}
    try:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
        ):
            return {
                "available": False,
                "reason": "The configured CDP endpoint must use local HTTP discovery",
            }
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
            f"{parsed.scheme}://{parsed.netloc}/json/version", timeout=0.5
        ) as response:
            body = response.read(65537)
        if len(body) > 65536 or not isinstance(json.loads(body).get("webSocketDebuggerUrl"), str):
            raise ValueError("invalid CDP response")
        return {"available": True, "reason": None}
    except Exception:
        return {"available": False, "reason": "The configured local CDP endpoint is not responding"}


def _tool_reason(name: str, executables: dict[str, dict[str, str]]) -> str | None:
    if name in {"run_terminal", "start_service"} and "shell" not in executables:
        return "Android shell /system/bin/sh is unavailable on this runtime"
    if name in {"run_process"} and not executables:
        return "No executable is available to the Android app"
    if name.startswith("git_") and "git" not in executables:
        return "Git is not installed in the APK or visible on its PATH"
    if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy" and name in {
        "run_sandbox",
        "sandbox_status",
    }:
        return "The optional PRoot toolchain is not an OS sandbox; sandbox execution is unavailable"
    # These only handle changes made by run_sandbox, which the phone does not have: offering them
    # would cost every request their descriptions for nothing.
    if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy" and name in {
        "apply_sandbox_change",
        "inspect_sandbox_change",
        "review_sandbox_change",
        "sandbox_change_status",
        "list_sandbox_changesets",
    }:
        return "Sandbox changesets come from run_sandbox, which is unavailable on Android"
    if (
        os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy"
        and name
        in {
            "start_background_job",
            "background_job_status",
            "background_job_logs",
            "stop_background_job",
        }
        and "python" not in executables
    ):
        return "A verified standalone Python/toolchain runtime is required for background processes"
    if name == "preview_process":
        return (
            "Desktop process preview supports Windows shells; use Android direct process execution"
        )
    if name in {"lsp_diagnostics", "run_diagnostics"} and not any(
        name in executables
        for name in ("pylsp", "pyright", "typescript_lsp", "rust_analyzer", "gopls")
    ):
        return "No language server executable is installed in the APK environment"
    if name == "transcribe_audio" and not os.getenv("AGENT_WORKSPACE_AUDIO_BASE_URL"):
        # The app's offline recognizer (speech_tools) replaces the core's endpoint-based tool.
        from .speech_tools import speech_runtime_status

        status = speech_runtime_status()
        if status is None:
            return "No audio transcription endpoint is configured"
        if not status.get("runtime_available"):
            return "Offline speech recognition runs on 64-bit ARM phones only"
    if name in {"browser", "browser_view"}:
        from .browser import browser_available

        if browser_available():
            return None
        if name == "browser_view":
            return "The in-app browser needs the Android app"
        return browser_status()["reason"]
    return None


def speech_status() -> dict[str, Any]:
    try:
        from .speech import speech_status as status

        return status()
    except Exception:
        return {"ready": False, "reason": "Android TTS bridge is unavailable in this runtime"}


def _android_status() -> dict[str, Any]:
    try:
        from .android_system import get_android_system_status

        return get_android_system_status()
    except Exception:
        return {
            "available": False,
            "enabled": False,
            "connected": False,
            "reason": "Android accessibility bridge is unavailable",
        }


def configure_android_registry(
    registry: Any, workspace: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    """Remove unavailable desktop tools and retain reasons for the doctor UI."""
    executables = discover_runnable_executables(workspace)
    unavailable: dict[str, str] = dict(getattr(registry, "_android_unavailable", {}))
    from agent_workspace.tools.base import json_result
    from agent_workspace.tools.command import DiscoverExecutablesTool

    from .speech import AndroidSpeakTool
    from .terminal import AndroidRunProcessTool, AndroidRunTerminalTool

    tools = getattr(registry, "_tools", {})
    if not hasattr(registry, "_android_original_tools"):
        registry._android_original_tools = dict(tools)
    originals = registry._android_original_tools
    if not hasattr(registry, "_android_host_process"):
        registry._android_host_process = "run_process" in tools
    if workspace is None:
        workspace = getattr(registry, "_android_workspace", None)
    if workspace is None:
        first = next((tool for tool in tools.values() if hasattr(tool, "paths")), None)
        workspace = getattr(getattr(first, "paths", None), "root", None)
    if workspace is not None:
        registry._android_workspace = str(workspace)
    factories: dict[str, Any] = {"speak_text": AndroidSpeakTool}
    from .clock_calendar import clock_available, clock_calendar_tools

    if clock_available():
        factories.update(clock_calendar_tools())
    from .personal_tools import personal_tools, personal_tools_available

    if personal_tools_available():
        factories.update(personal_tools())
    from .app_audit_tools import app_audit_available, app_audit_tools

    if app_audit_available():
        factories.update(app_audit_tools())
    from .notification_tools import notification_tools, notification_tools_available

    if notification_tools_available():
        factories.update(notification_tools())
    from .speech_tools import TranscribeAudioTool, speech_runtime_status

    speech = speech_runtime_status()
    if workspace is not None and speech is not None and speech.get("runtime_available"):
        # Offered before the model is downloaded too: it then says where to download it.
        factories["transcribe_audio"] = lambda: TranscribeAudioTool(workspace)
    from .browser import AndroidBrowserTool, AndroidBrowserViewTool, browser_available

    if browser_available():
        # The phone's own WebView replaces the desktop Chrome DevTools browser.
        factories["browser"] = lambda: AndroidBrowserTool(workspace=workspace)
        factories["browser_view"] = lambda: AndroidBrowserViewTool(workspace=workspace)
    if os.getenv("AGENT_WORKSPACE_DATA_DIR"):
        # Phone-wide memory (Memory page) replaces the per-workspace core memory tools.
        factories["memory_search"] = lambda: _memory_tools()[0]
        factories["memory_write"] = lambda: _memory_tools()[1]
        # What earlier tasks learned about an app, shown when a task enters it (mobile_app_notes).
        factories["app_note"] = _app_note_tool
        # The phone-wide knowledge base (Knowledge page): the user's own documents.
        from .knowledge_tools import KnowledgeAddTool, KnowledgeSearchTool, KnowledgeUseTool

        factories["knowledge_search"] = KnowledgeSearchTool
        factories["knowledge_use"] = KnowledgeUseTool
        # Installed skill packs (Skills page): instructions the agent loads when a job matches.
        from .skill_tools import SaveSkillTool, UseSkillTool

        factories["use_skill"] = UseSkillTool
        factories["save_skill"] = SaveSkillTool
        # Helpers that look into independent parts of a task side by side (mobile_subagents).
        from mobile_subagents import RunSubagentsTool

        factories["run_subagents"] = RunSubagentsTool
        # This app's own settings: found, opened or proposed for the user to apply with a tap.
        from .app_settings_tool import AppSettingsTool

        factories["app_settings"] = AppSettingsTool
        # A part of the task handed to a paired computer (mobile_link, docs/DEVICE_LINK_V2.md 2.10).
        from .computer_tools import AskComputerTool, computer_tools_available

        if computer_tools_available():
            factories["ask_computer"] = AskComputerTool
        if workspace is not None:
            factories["knowledge_add"] = lambda: KnowledgeAddTool(workspace)
    documents = document_status()
    native_pdf = bool(documents.get("available"))
    if workspace is not None:
        from .documents import AndroidCreatePdfTool, AndroidReadDocumentTool, AndroidRenderPdfTool
        from .toolchain import AndroidLspDiagnosticsTool

        if native_pdf and documents.get("render_pdf") and documents.get("ocr"):
            factories["read_document"] = lambda: AndroidReadDocumentTool(workspace)
        elif "read_document" in originals:
            tools["read_document"] = originals["read_document"]
        if native_pdf and documents.get("create_pdf"):
            factories["create_pdf"] = lambda: AndroidCreatePdfTool(workspace)
        if native_pdf and documents.get("render_pdf"):
            factories["render_pdf"] = lambda: AndroidRenderPdfTool(workspace)
        for name in ("create_pdf", "render_pdf"):
            if name not in factories:
                unavailable[name] = str(documents.get("reason") or "Native PDF tool is unavailable")
        factories["run_terminal"] = lambda: AndroidRunTerminalTool(workspace)
        factories["run_diagnostics"] = lambda: AndroidLspDiagnosticsTool(workspace)
        # Word and Excel files without Office: plain Office Open XML written in Python.
        from .office_files import CreateDocxTool, CreateXlsxTool

        factories["create_docx"] = lambda: CreateDocxTool(workspace)
        factories["create_xlsx"] = lambda: CreateXlsxTool(workspace)
        # The desktop app's literature and office tools (shared core): papers, references, Word
        # revisions, workbooks with formulas, PDF pages, documents from templates.
        if os.getenv("AGENT_WORKSPACE_DATA_DIR"):
            factories.update(_research_and_office_tools(workspace))
        if os.getenv("AGENT_WORKSPACE_DATA_DIR"):
            from .service_tools import (
                ListServicesTool,
                ServiceLogsTool,
                StartServiceTool,
                StopServiceTool,
            )

            factories["start_service"] = lambda: StartServiceTool(workspace)
            factories["list_services"] = ListServicesTool
            factories["service_logs"] = ServiceLogsTool
            factories["stop_service"] = StopServiceTool
        if registry._android_host_process:
            factories["run_process"] = lambda: AndroidRunProcessTool(workspace)
    if "python" in executables and registry._android_host_process:
        from .toolchain import AndroidStartBackgroundJobTool

        original_background = originals.get("start_background_job")
        if original_background is not None:
            original_background.manager._process = AndroidRunProcessTool(workspace)
            factories["start_background_job"] = lambda: AndroidStartBackgroundJobTool(
                original_background.manager
            )

    class AndroidDiscoverExecutablesTool(DiscoverExecutablesTool):
        hard_cancellable = False

        async def execute(self, _arguments: dict[str, Any]) -> str:
            return json_result({"executables": discover_runnable_executables(workspace)})

    if registry._android_host_process:
        factories["discover_executables"] = AndroidDiscoverExecutablesTool
    considered = set(tools) | set(factories) | set(unavailable)
    for name in sorted(considered):
        reason = _tool_reason(name, executables)
        if name in {"create_pdf", "render_pdf"} and name not in factories:
            reason = unavailable.get(name, "Native PDF tool is unavailable")
        if name == "speak_text":
            status = speech_status()
            reason = (
                None
                if status.get("ready")
                else str(status.get("reason") or "Android TTS engine is unavailable")
            )
        if reason:
            unavailable[name] = reason
            tools.pop(name, None)
        else:
            unavailable.pop(name, None)
            if name in factories:
                tools[name] = factories[name]()
            elif name not in tools and name in originals:
                tools[name] = originals[name]
            if (name.startswith("git_") or name == "run_diagnostics") and name in tools:
                tools[name].hard_cancellable = False
    registry._android_unavailable = unavailable
    registry._android_capabilities = {"executables": executables}
    try:
        from .android_system import register_android_system_tools

        register_android_system_tools(registry)
    except ImportError:
        pass
    return {
        "executables": executables,
        "unavailable": dict(unavailable),
        "android": _android_status(),
        "documents": documents,
    }


_MEMORY_TOOLS: tuple[Any, Any] | None = None


def _memory_tools() -> tuple[Any, Any]:
    """One shared pair, so the per-task save counter survives registry refreshes."""
    global _MEMORY_TOOLS
    if _MEMORY_TOOLS is None:
        from .memory_tools import MobileMemorySearchTool, MobileMemoryWriteTool

        _MEMORY_TOOLS = (MobileMemorySearchTool(), MobileMemoryWriteTool())
    return _MEMORY_TOOLS


_RECENT_WORKS: Any | None = None
# Shared-core tools the phone leaves out: e-mail drafts are .eml files for Outlook on a computer, and
# meeting transcription uses the desktop's speech service (the phone has transcribe_audio).
_DESKTOP_ONLY_OFFICE = frozenset({"email_files", "meeting_transcribe"})
# The literature and office tools, named here so the registry can list them before their modules
# load (tests check this against the shared core).
RESEARCH_AND_OFFICE_TOOLS = (
    "check_references", "export_references", "office_read", "office_template", "paper_lookup", "paper_search",
    "pdf_tools", "read_paper", "reference_library", "slides_from_template", "spreadsheet", "word_document",
)
_DEFERRED_TOOLS: list[_DeferredTool] = []


class _DeferredTool:
    """A tool whose modules are slow to import (pypdf, the office formats: about 2 s on a phone).

    It is built on first use, or by preload_deferred_tools() once the engine is serving, so the start
    is not slower.
    """

    def __init__(self, name: str, load: Any) -> None:
        self._name = name
        self._load = load
        self._tool: Any | None = None
        self._lock = threading.Lock()

    def _real(self) -> Any:
        if self._tool is None:
            with self._lock:
                if self._tool is None:
                    self._tool = self._load()[self._name]
        return self._tool

    def _loaded(self) -> Any | None:
        try:
            return self._real()
        except Exception:
            return None

    @property
    def spec(self) -> Any:
        tool = self._loaded()
        if tool is not None:
            return tool.spec
        from agent_workspace.core.models import ToolSpec

        return ToolSpec(self._name, "Unavailable: its modules did not load.", {"type": "object"}, "none")

    def offered(self) -> bool:
        # One whose modules did not load is left out of the model's list.
        tool = self._loaded()
        offered = getattr(tool, "offered", None)
        return tool is not None and (not callable(offered) or bool(offered()))

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._real(), name)


def preload_deferred_tools() -> None:
    """Builds the deferred tools now (from a worker thread once the engine is up)."""
    for tool in list(_DEFERRED_TOOLS):
        try:
            tool._real()
        except Exception:  # first use reports it with the tool's own error
            return


def _build_research_and_office_tools(workspace: str | os.PathLike[str]) -> dict[str, Any]:
    global _RECENT_WORKS
    from agent_workspace.office.tools import office_tools
    from agent_workspace.scholar.library import RecentWorks
    from agent_workspace.scholar.literature_tools import literature_tools
    from agent_workspace.scholar.papers import ReadPaperTool
    from agent_workspace.storage.file_versions import FileVersions
    from agent_workspace.tools.filesystem import WriteFileTool

    if _RECENT_WORKS is None:
        # Works looked up lately, so reference_library can add one by its number in any workspace.
        _RECENT_WORKS = RecentWorks()
    root = Path(workspace)
    data_dir = Path(os.environ["AGENT_WORKSPACE_DATA_DIR"])
    versions = FileVersions(data_dir / "file-versions")
    tools = (
        *literature_tools(root, data_dir=data_dir, writer=WriteFileTool(root, versions), recent=_RECENT_WORKS),
        ReadPaperTool(root),
        *(tool for tool in office_tools(root, data_dir, versions, lambda: None) if tool.spec.name not in _DESKTOP_ONLY_OFFICE),
    )
    return {tool.spec.name: tool for tool in tools}


def _research_and_office_tools(workspace: str | os.PathLike[str]) -> dict[str, Any]:
    """The desktop app's literature and office tools for this workspace (ui_gateway/research.py).

    Files they write keep a version in <data>/file-versions, like write_file's. Conversions that need
    Office or LibreOffice, and the Windows text recognition of scanned PDFs, say so when asked.
    """
    built: dict[str, Any] = {}
    failure: list[Exception] = []
    lock = threading.Lock()

    def load() -> dict[str, Any]:
        with lock:
            if failure:  # an import that failed fails again: not retried on every request
                raise failure[0]
            if not built:
                try:
                    built.update(_build_research_and_office_tools(workspace))
                except Exception as error:
                    failure.append(error)
                    raise
        return built

    deferred = {name: _DeferredTool(name, load) for name in RESEARCH_AND_OFFICE_TOOLS}
    _DEFERRED_TOOLS[:] = deferred.values()
    return {name: (lambda tool=tool: tool) for name, tool in deferred.items()}


_APP_NOTE_TOOL: Any | None = None


def _app_note_tool() -> Any:
    """One shared instance, so the per-task save counter survives registry refreshes."""
    global _APP_NOTE_TOOL
    if _APP_NOTE_TOOL is None:
        from .app_notes_tool import AppNoteTool

        _APP_NOTE_TOOL = AppNoteTool()
    return _APP_NOTE_TOOL


def refresh_android_registry(registry: Any) -> dict[str, Any]:
    status = _android_status()
    names = ("android_observe", "android_action", "android_verify", "android_screenshot")
    if not status.get("enabled") or not status.get("connected"):
        for name in names:
            getattr(registry, "_tools", {}).pop(name, None)
    elif not status.get("screenshot_supported"):
        getattr(registry, "_tools", {}).pop("android_screenshot", None)
    return configure_android_registry(registry, getattr(registry, "_android_workspace", None))


def runtime_capabilities(runtime: Any | None = None) -> dict[str, Any]:
    """Return a bounded JSON-safe capability matrix for ``GET /mobile/capabilities``."""
    registry = None
    if runtime is not None:
        runner = getattr(getattr(runtime, "service", None), "runner", None)
        registry = getattr(runner, "_tools", None)
    if registry is not None and hasattr(registry, "_android_workspace"):
        refresh_android_registry(registry)
    executables = discover_runnable_executables(getattr(registry, "_android_workspace", None))
    unavailable = (
        dict(getattr(registry, "_android_unavailable", {})) if registry is not None else {}
    )
    names = set(getattr(registry, "_tools", {}).keys()) if registry is not None else set()
    names.update(unavailable)
    names.update(
        {"run_terminal", "run_process", "speak_text", "browser", "run_sandbox", "sandbox_status"}
    )
    rows = []
    for name in sorted(names):
        reason = unavailable.get(name) or _tool_reason(name, executables)
        if name == "speak_text":
            status = speech_status()
            reason = (
                None
                if status.get("ready")
                else str(status.get("reason") or "Android TTS engine is unavailable")
            )
        registered = registry is not None and name in getattr(registry, "_tools", {})
        rows.append(
            {
                "name": name,
                "registered": registered,
                "available": registered and name not in unavailable and reason is None,
                "reason": reason
                or (None if registered else "Tool is not registered in this runtime"),
            }
        )
    return {
        "runtime": "chaquopy"
        if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy"
        else "termux",
        "embedded_python": os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy",
        "termux_environment": bool(
            os.getenv("PREFIX")
            and Path(os.environ["PREFIX"]).is_dir()
            and (Path(os.environ["PREFIX"]) / "bin" / "bash").is_file()
        ),
        "executables": executables,
        "tools": rows,
        "android": _android_status(),
        "documents": document_status(),
        "doctor": {"ok": not any(row["registered"] and not row["available"] for row in rows)},
        "toolchain": _toolchain_snapshot(),
    }


def _toolchain_snapshot() -> dict[str, Any]:
    from .toolchain import installed_toolchain

    manager = installed_toolchain()
    return (
        manager.snapshot()
        if manager is not None
        else {"available": False, "state": "not_installed"}
    )


__all__ = [
    "browser_status",
    "configure_android_registry",
    "discover_runnable_executables",
    "refresh_android_registry",
    "runtime_capabilities",
    "speech_status",
]
