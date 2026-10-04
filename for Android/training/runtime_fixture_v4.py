"""Replay the historical V4 request profile through real tools, never a model or phone.

The immutable catalog is a read-only capture from an installed Android runtime.
The frozen descriptions and system text are restored explicitly; they do not
represent the current installed Android prompt. Only real filesystem/selection
tools execute. Other real advertisements remain
in the applicable inventory, with execution deliberately unavailable here.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import shutil
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ANDROID_ROOT = Path(__file__).resolve().parents[1]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from android_adapter.local_context import install_local_context_profile  # noqa: E402
from android_adapter.local_provider import (  # noqa: E402
    EMBEDDED_BASE_URL,
    EmbeddedQwenProvider,
    build_qwen_prompt,
    parse_qwen_output,
)
from mobile_runtime_controller import _ANDROID_SYSTEM_SUFFIX  # noqa: E402

from agent_workspace.application.service import ApplicationService  # noqa: E402
from agent_workspace.core.budgets import TaskBudget  # noqa: E402
from agent_workspace.core.models import (  # noqa: E402
    Autonomy,
    Capability,
    ChatMessage,
    DeltaKind,
    Mode,
    ProviderDelta,
    Role,
    ToolSpec,
    Usage,
    capabilities_for_mode,
)
from agent_workspace.policy import ProviderEgressPolicy, WorkspacePolicy  # noqa: E402
from agent_workspace.storage import SQLiteEventStore  # noqa: E402
from agent_workspace.tools import ToolRegistry  # noqa: E402
from agent_workspace.tools.base import ToolError  # noqa: E402
from training.build_dataset import render_call  # noqa: E402

FROZEN_SOURCE = ANDROID_ROOT / "training/data-v4"
DEFAULT_CATALOG = (
    FROZEN_SOURCE / "android-catalog-source.json"
    if (FROZEN_SOURCE / "android-catalog-source.json").is_file()
    else ANDROID_ROOT.parent / "output/qwen-device-live-tool-catalog-v4-source.json"
)
DEFAULT_SYSTEM = (
    FROZEN_SOURCE / "android-system-source.json"
    if (FROZEN_SOURCE / "android-system-source.json").is_file()
    else ANDROID_ROOT.parent / "output/qwen-device-live-system-v4-source-combined.json"
)
SCRATCH = ANDROID_ROOT.parent / "output/qwen-v4-disposable-runtime"
REAL_EXECUTABLE = {"list_files", "read_file", "write_file", "make_directory"}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict:
    capture_text = path.read_bytes().decode("utf-8")
    source = json.loads(capture_text)
    if not (
        source.get("success") is True
        and source.get("user_content_captured") is False
        and source.get("tool_execution_performed") is False
        and source.get("model_inference_performed") is False
        and source.get("workspace_is_disposable") is True
        and source.get("database_is_disposable") is True
    ):
        raise ValueError("A verified read-only Android catalog capture is required")
    if source["android_system_suffix"] != _ANDROID_SYSTEM_SUFFIX:
        raise ValueError("Android system suffix changed since the catalog capture")
    catalog = source["catalog"]
    for mode in (Mode.CODING, Mode.TASK):
        actual = sorted(
            name
            for name, entry in catalog.items()
            if Capability(entry["capability"]) in capabilities_for_mode(mode)
        )
        if actual != sorted(source["applicable_catalogs"][mode.value]):
            raise ValueError("Captured applicable menu is not the full mode inventory")
    return {
        "catalog": copy.deepcopy(catalog),
        "applicable_catalogs": copy.deepcopy(source["applicable_catalogs"]),
        "catalog_source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "catalog_source": source["source"],
        "android_system_suffix": source["android_system_suffix"],
        "source_contains_user_content": False,
        "catalog_capture_text": capture_text,
    }


def load_system_source(path: Path = DEFAULT_SYSTEM):
    capture_text = path.read_bytes().decode("utf-8")
    source = json.loads(capture_text)
    if (
        source.get("user_content_included") is not False
        or source.get("new_inference_performed") is not False
    ):
        raise ValueError("Only a system-only read-only phone capture is accepted")
    modes = {entry["mode"]: entry for entry in source["entries"]}
    if set(modes) != {"task", "coding"}:
        raise ValueError("Both actual TASK and CODING system variants are required")
    for entry in modes.values():
        if (
            entry["user_message_or_file_content_included"] is not False
            or digest(entry["serialized_system"]) != entry["serialized_system_sha256"]
        ):
            raise ValueError("Captured live system provenance changed")
    return {
        "entries": modes,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "capture_text": capture_text,
    }


def tool_spec(name, entry):
    function = entry["advertisement"]["function"]
    return ToolSpec(
        name,
        function["description"],
        entry["execution_schema"],
        entry["side_effect"],
        capability=Capability(entry["capability"]),
        provider_input_schema=function["parameters"],
    )


class AdvertisementOnlyTool:
    hard_cancellable = False

    def __init__(self, name, entry):
        self.spec = tool_spec(name, entry)

    async def execute(self, _arguments):
        raise ToolError("This CPU file fixture does not execute native or unrelated tools")


class HistoricalDescriptionTool:
    """Restore only historical metadata while delegating to the actual executor."""

    hard_cancellable = False

    def __init__(self, tool, entry):
        description = entry["advertisement"]["function"]["description"]
        restored = replace(tool.spec, description=description)
        if (
            restored.to_openai() != entry["advertisement"]
            or restored.input_schema != entry["execution_schema"]
            or restored.capability.value != entry["capability"]
            or restored.side_effect != entry["side_effect"]
        ):
            raise ValueError("Historical V4 execution contract changed since the phone capture")
        self.spec = restored
        self._tool = tool

    def __getattr__(self, name):
        return getattr(self._tool, name)

    async def execute(self, arguments):
        return await self._tool.execute(arguments)

    async def execute_with_context(self, arguments, context):
        method = getattr(self._tool, "execute_with_context", None)
        return await method(arguments, context) if method else await self._tool.execute(arguments)


def _unwrap(content):
    if content.startswith("[UNTRUSTED TOOL DATA:"):
        return content.split("\n", 1)[1].rsplit("\n[END UNTRUSTED TOOL DATA]", 1)[0]
    return content


def historical_read_results(row):
    names, results = {}, {}
    for message in row["messages"]:
        for call in message.get("tool_calls", []):
            function = call["function"]
            names[call["id"]] = (function["name"], function["arguments"])
        if message["role"] == "tool":
            name, arguments = names[message["tool_call_id"]]
            raw = _unwrap(message["content"])
            if name == "read_file" and not raw.startswith("Tool failed ("):
                result = json.loads(raw)
                if not result["truncated"]:
                    results[arguments["path"]] = result
    return results


def observed_reads(request):
    return historical_read_results(
        {"messages": [message.to_dict() for message in request.messages]}
    )


def transform_content(content, edit):
    if edit is None:
        return content
    if edit["operation"] == "replace":
        if content.count(edit["old"]) != 1:
            raise ValueError("Synthetic replace expects one observed occurrence")
        return content.replace(edit["old"], edit["new"], 1)
    if edit["operation"] == "append":
        return content + edit["new"]
    if edit["operation"] == "remove":
        if content.count(edit["old"]) != 1:
            raise ValueError("Synthetic remove expects one observed occurrence")
        return content.replace(edit["old"], "", 1)
    raise ValueError("Unknown independently generated edit operation")


def resolve_step(step, request):
    if "text" in step:
        return [], step["text"]
    reads = observed_reads(request)
    calls = []
    for specification in step["calls"]:
        call = {
            "name": specification["name"],
            "arguments": copy.deepcopy(specification["arguments"]),
        }
        args = call["arguments"]
        source = specification.get("content_from_read")
        if source is not None:
            args["content"] = transform_content(reads[source]["content"], specification.get("edit"))
        preimage = specification.get("sha_from_read")
        if preimage is not None:
            args["expected_sha256"] = reads[preimage]["sha256"]
        calls.append(call)
    return calls, "\n".join(render_call(call) for call in calls)


def workspace_files(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes().decode("utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class CaptureProvider(EmbeddedQwenProvider):
    def __init__(self, program, root, *, prediction=None, stop_at=None):
        super().__init__(
            "synthetic-live-v4",
            model_root=root.parent / "models",
            context_size=32768,
            memory_mode="extended",
        )
        self.program, self.root = program, root
        self.prediction, self.stop_at = prediction, stop_at
        self.records, self.requests = [], []

    async def stream(self, request):
        index = len(self.requests)
        self.requests.append(request)
        if self.records:
            self.records[-1]["after_files"] = workspace_files(self.root)
            self.records[-1]["after_directories"] = self.directories()
        if self.stop_at is not None and index > self.stop_at:
            raw = "Synthetic replay boundary reached."
        else:
            step = self.program["steps"][index]
            calls, raw = resolve_step(step, request)
            if self.prediction is not None and index == self.stop_at:
                raw = self.prediction
            messages = []
            for message in request.messages:
                visible = message.to_dict()
                messages.append(
                    {key: value for key, value in visible.items() if key != "provider_metadata"}
                )
            state = self.runtime.runner._android_local_context.turns[self.session.id]
            self.records.append(
                {
                    "messages": messages,
                    "tools": [spec.to_openai() for spec in request.tools],
                    "target_response": raw,
                    "expected_calls": calls,
                    "before_files": workspace_files(self.root),
                    "before_directories": self.directories(),
                    "captured_runtime_prompt_sha256": digest(build_qwen_prompt(request)),
                    "runtime_available_tools": sorted(state.available),
                    "runtime_selected_tools": list(state.selected),
                }
            )
        deltas = parse_qwen_output(raw, request, f"synthetic-step-{index}")
        for delta in deltas:
            yield delta
        yield ProviderDelta(DeltaKind.USAGE, usage=Usage(1, 1, estimated=True))
        yield ProviderDelta(
            DeltaKind.FINISH,
            finish_reason="tool_calls"
            if any(delta.kind is DeltaKind.TOOL_CALL for delta in deltas)
            else "stop",
        )

    def directories(self):
        return sorted(
            path.relative_to(self.root).as_posix() for path in self.root.rglob("*") if path.is_dir()
        )


async def _thread_worker(function, *arguments, allow_children=False):
    # Chaquopy uses the same thread-worker strategy. No executor is replaced.
    return await asyncio.to_thread(function, *arguments)


@contextmanager
def _fixture_directory(name):
    base = SCRATCH.resolve()
    if not name or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in name
    ):
        raise ValueError("Invalid disposable fixture name")
    directory = (base / name).resolve()
    if not directory.is_relative_to(base) or directory == base:
        raise ValueError("Disposable fixture escaped its owned scratch root")
    base.mkdir(parents=True, exist_ok=True)
    directory.mkdir()
    try:
        yield directory
    finally:
        checked = directory.resolve()
        if checked.is_relative_to(base) and checked != base and not directory.is_symlink():
            shutil.rmtree(checked)


async def capture_program(program, catalog, *, prediction=None, stop_at=None):
    with _fixture_directory(program["fixture_name"]) as directory, ExitStack() as stack:
        root = directory / "workspace"
        root.mkdir()
        for path in program["initial_directories"]:
            (root / path).mkdir(parents=True, exist_ok=True)
        for path, text in program["initial_files"].items():
            file = root / path
            if file.is_absolute() and not file.resolve().is_relative_to(root.resolve()):
                raise ValueError("Synthetic file escaped the disposable workspace")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(text.encode("utf-8"))
        old = os.environ.get("AGENT_WORKSPACE_EMBEDDED_PYTHON")
        os.environ["AGENT_WORKSPACE_EMBEDDED_PYTHON"] = "chaquopy"
        install_local_context_profile()
        if old is None:
            os.environ.pop("AGENT_WORKSPACE_EMBEDDED_PYTHON", None)
        else:
            os.environ["AGENT_WORKSPACE_EMBEDDED_PYTHON"] = old
        for module in ("filesystem", "manage"):
            stack.enter_context(
                patch(f"agent_workspace.tools.{module}.run_in_process", _thread_worker)
            )
        # This disposable CPU fixture validates runner behavior and committed
        # events, not power-loss durability. User databases retain their policy.
        store = SQLiteEventStore(directory / "events.db", synchronous="OFF")
        stack.callback(store.close)
        provider = CaptureProvider(program, root, prediction=prediction, stop_at=stop_at)
        original = ToolRegistry.for_workspace(root, store, allow_host_process=False)
        tools = []
        for name, entry in catalog.items():
            if name == "select_local_tools":
                continue
            if name in REAL_EXECUTABLE:
                tool = original.get(name)
                tools.append(HistoricalDescriptionTool(tool, entry))
            else:
                tools.append(AdvertisementOnlyTool(name, entry))
        registry = ToolRegistry(tools)
        app = ApplicationService(
            store,
            provider,
            registry,
            WorkspacePolicy(root, Autonomy.FULL_ACCESS),
            egress_policy=ProviderEgressPolicy(EMBEDDED_BASE_URL, Autonomy.FULL_ACCESS),
            execution_workspace=root,
            execution_autonomy=Autonomy.FULL_ACCESS,
        )
        historical_system = load_system_source()["entries"][program["mode"]]["live_system_suffix"]
        app.runner._cached_system_message = lambda *_arguments, **_options: ChatMessage(
            Role.SYSTEM, historical_system
        )
        session = app.create_session(
            root, mode=Mode(program["mode"]), autonomy=Autonomy.FULL_ACCESS
        )
        provider.runtime, provider.session = app, session
        error = None
        try:
            await app.run(
                session,
                program["prompt"],
                "qwen3.5-0.8b-q4-k-m",
                budget=TaskBudget(max_model_calls=len(program["steps"]) + 2, max_turn_seconds=30),
                system_suffix=program.get("android_system_suffix", _ANDROID_SYSTEM_SUFFIX),
                allowed_tools=None,
            )
        except Exception as failure:
            error = f"{type(failure).__name__}: {failure}"
        finally:
            if provider.records:
                provider.records[-1]["after_files"] = workspace_files(root)
                provider.records[-1]["after_directories"] = provider.directories()
            events = store.list_events(session.id)
            tool_events = [
                {
                    "type": event.type,
                    "name": event.data.get("name"),
                    "error": event.data.get("error"),
                    "result": event.data.get("result"),
                }
                for event in events
                if event.type in {"tool.failed", "tool.settled", "tool.rejected"}
            ]
            compacted = any(event.type == "context.compacted" for event in events)
            store.close()
            await original.aclose()
        return {
            "records": provider.records,
            "error": error,
            "tool_events": tool_events,
            "compacted": compacted,
            "workspace": str(root),
            "historical_request_profile_restored": True,
            "current_android_prompt_capture": False,
        }
