"""Actual runner captures and initial-state model callbacks for V5 synthetic tasks."""

from __future__ import annotations

import copy
import inspect
import json
import os
import re
import shutil
import sys
from contextlib import ExitStack, contextmanager
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
    DeltaKind,
    Mode,
    ProviderDelta,
    Usage,
)
from agent_workspace.policy import ProviderEgressPolicy, WorkspacePolicy  # noqa: E402
from agent_workspace.storage import SQLiteEventStore  # noqa: E402
from agent_workspace.tools import ToolRegistry  # noqa: E402
from training.build_dataset import render_call  # noqa: E402
from training.controlled_http_v5 import controlled_http  # noqa: E402
from training.formats_v5 import render_artifact  # noqa: E402
from training.runtime_fixture_v4 import (  # noqa: E402
    AdvertisementOnlyTool,
    _thread_worker,
    _unwrap,
    digest,
    historical_read_results,
    transform_content,
    workspace_files,
)
from training.runtime_fixture_v4 import (  # noqa: E402
    load_catalog as _load_catalog,
)
from training.runtime_fixture_v4 import (  # noqa: E402
    load_system_source as _load_system_source,
)

FROZEN_SOURCE = ANDROID_ROOT / "training/data-v5"
DEFAULT_CATALOG = (
    FROZEN_SOURCE / "android-catalog-source.json"
    if (FROZEN_SOURCE / "android-catalog-source.json").is_file()
    else ANDROID_ROOT.parent / "output/qwen-device-live-tool-catalog-v5-source.json"
)
DEFAULT_SYSTEM = (
    FROZEN_SOURCE / "android-system-source.json"
    if (FROZEN_SOURCE / "android-system-source.json").is_file()
    else ANDROID_ROOT.parent / "output/qwen-device-live-system-v5-source-combined.json"
)
SCRATCH = ANDROID_ROOT.parent / "output/qwen-v5-disposable-runtime"
REAL_EXECUTABLE = {
    "list_files",
    "read_file",
    "write_file",
    "make_directory",
    "web_search",
    "web_fetch",
}


def load_catalog(path=DEFAULT_CATALOG):
    source = _load_catalog(Path(path))
    if "web_search" not in source["catalog"]:
        raise ValueError("V5 requires the new actual Android catalog containing web_search")
    return source


def load_system_source(path=DEFAULT_SYSTEM):
    source = _load_system_source(Path(path))
    for entry in source["entries"].values():
        if _ANDROID_SYSTEM_SUFFIX not in entry["live_system_suffix"]:
            raise ValueError(
                "V5 TASK and CODING must both use mobile admission with Android suffix"
            )
    return source


def strip_end_marker(raw):
    return re.sub(
        r"(?:<\|im_end\|>|<\|endoftext\|>)(?:\s*(?:<\|im_end\|>|<\|endoftext\|>))*\s*$", "", raw
    )


def generation_success(prediction):
    return not (
        prediction.get("prediction_generation_success") is False
        or prediction.get("generation_error")
        or prediction.get("error")
        or prediction.get("timed_out")
        or prediction.get("output_truncated")
        or prediction.get("output_limit_reached")
        or prediction.get("finish_reason") in {"length", "cancelled"}
        or (prediction.get("returncode") is not None and prediction["returncode"] != 0)
    )


def historical_tool_results(messages, name):
    ids, results = {}, []
    for message in messages:
        for call in message.get("tool_calls", []):
            function = call["function"]
            args = function["arguments"]
            ids[call["id"]] = (
                function["name"],
                json.loads(args) if isinstance(args, str) else args,
            )
        if message["role"] == "tool":
            tool_name, args = ids[message["tool_call_id"]]
            content = _unwrap(message["content"])
            if tool_name == name and not content.startswith("Tool failed ("):
                results.append({"arguments": args, "result": json.loads(content)})
    return results


def observed_document_urls(messages):
    return [
        item["result"]["source"]["url"]
        for item in historical_tool_results(messages, "web_fetch")
        if not item["result"]["truncated"]
    ]


def _resolved_step(step, request):
    if step["kind"] in {"terminal", "ordinary"}:
        return [], step["text"]
    messages = [message.to_dict() for message in request.messages]
    reads = historical_read_results({"messages": messages})
    calls = []
    for specification in step["calls"]:
        call = {
            "name": specification["name"],
            "arguments": copy.deepcopy(specification["arguments"]),
        }
        args = call["arguments"]
        if specification.get("content_from_read"):
            observed = reads[specification["content_from_read"]]["content"]
            args["content"] = transform_content(observed, specification.get("edit"))
        if specification.get("sha_from_read"):
            args["expected_sha256"] = reads[specification["sha_from_read"]]["sha256"]
        if specification.get("url_from_search") is not None:
            search = historical_tool_results(messages, "web_search")[-1]["result"]
            args["url"] = search["results"][specification["url_from_search"]]["url"]
        if specification.get("artifact_from_brief"):
            contract = json.loads(reads[specification["artifact_from_brief"]]["content"])
            args["content"] = render_artifact(contract["kind"], contract["task"])
        if specification.get("artifact_from_web"):
            brief = json.loads(reads[specification["artifact_from_web"]]["content"])
            items = []
            for receipt in historical_tool_results(messages, "web_fetch"):
                result = receipt["result"]
                if result["truncated"]:
                    raise ValueError("Synthetic artifact requires a complete observed source")
                fact = json.loads(result["content"])
                items.append(
                    {
                        "name": fact["name"],
                        "quantity": fact["quantity"],
                        "source": result["source"]["url"],
                    }
                )
            contract = {
                "title": brief["title"],
                "items": items,
                "function_name": brief["function_name"],
                "require_citations": True,
            }
            args["content"] = render_artifact(brief["kind"], contract)
        calls.append(call)
    return calls, "\n".join(render_call(call) for call in calls)


class CaptureProvider(EmbeddedQwenProvider):
    def __init__(self, program, root, *, prediction=None, stop_at=None, generate_visible=None):
        super().__init__(
            "synthetic-live-v5",
            model_root=root.parent / "models",
            context_size=32768,
            memory_mode="extended",
        )
        self.program, self.root = program, root
        self.expected_live_system = load_system_source()["entries"][program["mode"]][
            "live_system_suffix"
        ]
        self.prediction, self.stop_at, self.generate_visible = prediction, stop_at, generate_visible
        self.records, self.requests = [], []

    def directories(self):
        return sorted(
            path.relative_to(self.root).as_posix() for path in self.root.rglob("*") if path.is_dir()
        )

    async def stream(self, request):
        index = len(self.requests)
        self.requests.append(request)
        if self.records:
            self.records[-1]["after_files"] = workspace_files(self.root)
            self.records[-1]["after_directories"] = self.directories()
        if self.stop_at is not None and index > self.stop_at:
            raw, calls, generation = "Synthetic replay boundary reached.", [], None
        else:
            messages = [
                {
                    key: value
                    for key, value in message.to_dict().items()
                    if key != "provider_metadata"
                }
                for message in request.messages
            ]
            if not messages or messages[0]["content"] != self.expected_live_system:
                raise ValueError("Current mobile runtime system differs from the V5 phone capture")
            state = self.runtime.runner._android_local_context.turns[self.session.id]
            record = {
                "messages": messages,
                "tools": [spec.to_openai() for spec in request.tools],
                "before_files": workspace_files(self.root),
                "before_directories": self.directories(),
                "captured_runtime_prompt_sha256": digest(build_qwen_prompt(request)),
                "runtime_available_tools": sorted(state.available),
                "runtime_selected_tools": list(state.selected),
                "expected_calls": [],
                "target_response": "",
                "generation": None,
            }
            self.records.append(record)
            if self.generate_visible is not None:
                generated = self.generate_visible(
                    build_qwen_prompt(request), f"{self.program['id']}-turn-{index:03d}"
                )
                generation = await generated if inspect.isawaitable(generated) else generated
                if not isinstance(generation, dict) or not isinstance(
                    generation.get("raw_output"), str
                ):
                    raise ValueError(
                        "Generation callback must return raw_output and measured status"
                    )
                raw, calls = strip_end_marker(generation["raw_output"]), []
                record["generation"] = copy.deepcopy(generation)
                record["target_response"] = raw
                if not generation_success(generation):
                    raise ValueError("Actual model generation failed or reached the output limit")
            else:
                calls, raw = _resolved_step(self.program["steps"][index], request)
                generation = None
                if self.prediction is not None and index == self.stop_at:
                    raw = self.prediction
            record["expected_calls"], record["target_response"] = calls, raw
        deltas = parse_qwen_output(raw, request, f"synthetic-v5-step-{index}")
        for delta in deltas:
            yield delta
        yield ProviderDelta(DeltaKind.USAGE, usage=Usage(1, 1, estimated=True))
        yield ProviderDelta(
            DeltaKind.FINISH,
            finish_reason="tool_calls"
            if any(delta.kind is DeltaKind.TOOL_CALL for delta in deltas)
            else "stop",
        )


@contextmanager
def _fixture_directory(name):
    base = SCRATCH.resolve()
    if not name or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in name
    ):
        raise ValueError("Invalid disposable V5 fixture name")
    directory = (base / name).resolve()
    if not directory.is_relative_to(base) or directory == base:
        raise ValueError("Disposable V5 fixture escaped its scratch root")
    base.mkdir(parents=True, exist_ok=True)
    directory.mkdir()
    try:
        yield directory
    finally:
        checked = directory.resolve()
        if checked.is_relative_to(base) and checked != base and not directory.is_symlink():
            shutil.rmtree(checked)


async def capture_program(
    program, catalog, *, prediction=None, stop_at=None, generate_visible=None, max_turns=16
):
    with _fixture_directory(program["fixture_name"]) as directory, ExitStack() as stack:
        root = directory / "workspace"
        root.mkdir()
        for path in program["initial_directories"]:
            folder = (root / path).resolve()
            if not folder.is_relative_to(root.resolve()):
                raise ValueError("Synthetic directory escaped its disposable workspace")
            folder.mkdir(parents=True, exist_ok=True)
        for name, content in program["initial_files"].items():
            file = (root / name).resolve()
            if not file.is_relative_to(root.resolve()):
                raise ValueError("Synthetic file escaped its disposable workspace")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content.encode("utf-8"))
        old = os.environ.get("AGENT_WORKSPACE_EMBEDDED_PYTHON")
        os.environ["AGENT_WORKSPACE_EMBEDDED_PYTHON"] = "chaquopy"
        install_local_context_profile()
        stack.callback(
            lambda: (
                os.environ.pop("AGENT_WORKSPACE_EMBEDDED_PYTHON", None)
                if old is None
                else os.environ.__setitem__("AGENT_WORKSPACE_EMBEDDED_PYTHON", old)
            )
        )
        for module in (
            "agent_workspace.tools.filesystem",
            "agent_workspace.tools.manage",
            "agent_workspace.tools.web",
            "agent_workspace.tools.web_search",
        ):
            stack.enter_context(patch(module + ".run_in_process", _thread_worker))
        transport = (
            stack.enter_context(controlled_http(program["http_fixture"], directory / "http"))
            if program.get("http_fixture")
            else None
        )
        store = SQLiteEventStore(directory / "events.db", synchronous="OFF")
        stack.callback(store.close)
        original = ToolRegistry.for_workspace(root, store, allow_host_process=False)
        tools = []
        for name, entry in catalog.items():
            if name == "select_local_tools":
                continue
            if name in REAL_EXECUTABLE:
                tool = original.get(name)
                if (
                    tool.spec.to_openai() != entry["advertisement"]
                    or tool.spec.input_schema != entry["execution_schema"]
                ):
                    raise ValueError("Actual V5 executable schema changed since the phone capture")
                tool.hard_cancellable = False
                tools.append(tool)
            else:
                tools.append(AdvertisementOnlyTool(name, entry))
        provider = CaptureProvider(
            program, root, prediction=prediction, stop_at=stop_at, generate_visible=generate_visible
        )
        app = ApplicationService(
            store,
            provider,
            ToolRegistry(tools),
            WorkspacePolicy(root, Autonomy.FULL_ACCESS),
            egress_policy=ProviderEgressPolicy(EMBEDDED_BASE_URL, Autonomy.FULL_ACCESS),
            execution_workspace=root,
            execution_autonomy=Autonomy.FULL_ACCESS,
        )
        session = app.create_session(
            root, mode=Mode(program["mode"]), autonomy=Autonomy.FULL_ACCESS
        )
        provider.runtime, provider.session = app, session
        error, run_result = None, None
        try:
            completed = await app.run(
                session,
                program["prompt"],
                "qwen3.5-0.8b-q4-k-m",
                budget=TaskBudget(
                    max_model_calls=max_turns if generate_visible else len(program["steps"]) + 2,
                    max_turn_seconds=3600 if generate_visible else 60,
                ),
                system_suffix=_ANDROID_SYSTEM_SUFFIX,
                allowed_tools=None,
            )
            run_result = {"text": completed.text, "returned_normally": True}
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
                    "arguments": event.data.get("arguments"),
                }
                for event in events
                if event.type in {"tool.failed", "tool.settled", "tool.rejected", "tool.proposed"}
            ]
            compacted = any(event.type == "context.compacted" for event in events)
            turn_events = [
                {"type": event.type, "data": copy.deepcopy(event.data)}
                for event in events
                if event.type.startswith("turn.")
            ]
            final_files, final_directories = workspace_files(root), provider.directories()
            store.close()
            await original.aclose()
        return {
            "records": provider.records,
            "error": error,
            "tool_events": tool_events,
            "compacted": compacted,
            "run_result": run_result,
            "turn_events": turn_events,
            "turn_completed": bool(
                run_result and any(event["type"] == "turn.completed" for event in turn_events)
            ),
            "workspace": str(root),
            "final_files": final_files,
            "final_directories": final_directories,
            "transport": copy.deepcopy(transport),
            "source_scope": (
                "Actual mobile runner; real file/selector/search/fetch tools, "
                "other catalog entries advertise only"
            ),
        }
