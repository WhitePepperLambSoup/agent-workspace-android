# Android Agent Dual-Host Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Android Termux host and standalone APK host without modifying Windows Agent source, Windows UI, Windows build logic, or Windows tests.

**Architecture:** Add an Android-only Mobile Gateway and Runtime Controller under `for Android/`. Reuse the stable public interfaces exposed by `src/agent_workspace/application/runtime.py`, including `build_runtime_async`, `ApplicationRuntime.service`, `EventStore`, and event listeners, but do not modify those shared modules. Termux and the APK foreground service only supervise the same Python runtime; the browser and WebView observe tasks instead of owning them.

**Tech Stack:** Python 3.11+, the existing `ApplicationRuntime`/`SQLiteEventStore`, Python `ThreadingHTTPServer`, SSE over `fetch()` streams, Kotlin, Android SDK 35, Android 10-15, ARM64-v8a, the existing Jetpack Compose dependencies, Android Keystore, foreground services, partial WakeLock, Termux:API, and Shizuku.

## Global Constraints

- Android changes may only enter `for Android/`, Android-specific tests, and this plan; never edit `desktop/`.
- Do not edit `src/agent_workspace/` or root Windows tests to accommodate Android. Read stable interfaces and wrap them from Android code.
- Do not stage existing Windows, shared-core, or unrelated documentation changes.
- Runtime data, task state, and event cursors must be reconstructable from persisted events; the browser, Activity, and Kotlin memory are observers only.
- Task states are `queued`, `running`, `waiting_approval`, `succeeded`, `failed`, `cancelled`, and `interrupted`; unknown tool calls must never be replayed automatically.
- The Android Gateway binds to loopback by default and uses a Bearer token. Only the existing console/static compatibility path may accept a query token.
- The Web UI submits asynchronous tasks and resumes an SSE stream with `after=<sequence>`; reconnecting never submits the task again.
- Destructive and system-level actions require explicit approval with complete package, path, command, and impact details. Shizuku denial must not be bypassed.
- APK distribution supports only a verified `arm64-v8a` rootfs. Missing or placeholder rootfs input must fail asset packaging and APK build.
- APK initialization uses staging, SHA-256, entrypoint/ABI checks, atomic activation, and rollback. Failure must preserve the previous active version.
- Each implementation task follows failing test -> minimal implementation -> passing test. Each independently reviewable task gets its own commit.

## File Map

### Android Python files

- Create `for Android/mobile_protocol.py`: task/runtime/capability enums, data classes, request validation, JSON serialization.
- Create `for Android/mobile_event_cursor.py`: sequence validation, duplicate suppression, and cursor resume helpers.
- Create `for Android/mobile_task_store.py`: `mobile.task.*` event projection and restart recovery over the existing `EventStore`.
- Create `for Android/mobile_approval.py`: tool and Provider approval broker.
- Create `for Android/mobile_runtime_controller.py`: runtime state machine, task submission, cancellation, resume, and event listener.
- Create `for Android/mobile_gateway.py`: Android HTTP API, compatibility routes, SSE, loopback, and token checks.
- Create `for Android/mobile_capabilities.py`: Termux:API, Shizuku, notification, battery, file picker, and screen-action capability report.
- Create `for Android/mobile_diagnostics.py`: read-only diagnostics projection and redacted export.
- Create `for Android/mobile_workspace.py`: bounded single-file browser, file read, and read-only diff.
- Create `for Android/android_adapter/redaction.py`: redaction for API keys, Bearer tokens, cookies, environment values, and user paths.
- Create `for Android/android_adapter/termux_lifecycle.py`: Termux process, signal, restart, and wake-lock policy.
- Modify `for Android/entrypoint.py`, `android_adapter/termux_api.py`, `android_adapter/shizuku.py`, `run_server.sh`, and `bootstrap.sh`.

### Android Python tests

- Create `for Android/tests/conftest.py`.
- Create `for Android/tests/test_mobile_protocol.py`.
- Create `for Android/tests/test_mobile_event_cursor.py`.
- Create `for Android/tests/test_mobile_task_store.py`.
- Create `for Android/tests/test_mobile_approval.py`.
- Create `for Android/tests/test_mobile_runtime_controller.py`.
- Create `for Android/tests/test_mobile_gateway.py`.
- Create `for Android/tests/test_mobile_capabilities.py`.
- Create `for Android/tests/test_mobile_workspace.py`.
- Create `for Android/tests/test_mobile_diagnostics.py`.
- Create `for Android/tests/test_android_redaction.py`.
- Create `for Android/tests/test_termux_lifecycle.py`.
- Create `for Android/tests/test_android_asset_contract.py`.
- Create `for Android/tests/test_android_scope.py`.
- Modify `for Android/test_android_stack.py`.

### Android Web files

- Create `for Android/web_companion/static/mobile_state.mjs`.
- Create `for Android/web_companion/static/mobile_state.test.mjs`.
- Modify `for Android/web_companion/index.html`, `static/app.js`, and `static/style.css`.

### Kotlin files

- Create `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/RuntimeState.kt`.
- Create `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/ProcessSupervisor.kt`.
- Create `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/WakeLockController.kt`.
- Create `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/NotificationController.kt`.
- Create `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/BootstrapManifest.kt`.
- Create `for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/embedded/ProcessSupervisorTest.kt`.
- Create `for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/embedded/WakeLockControllerTest.kt`.
- Create `for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/embedded/TermuxBootstrapTest.kt`.
- Create `for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/bridge/BridgePolicyTest.kt`.
- Create `for Android/kotlin_app/src/androidTest/kotlin/com/agentworkspace/mobile/AndroidLifecycleTest.kt`.
- Create: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/BridgePolicy.kt`.
- Modify: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxDaemonService.kt`, `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxBootstrap.kt`, `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/WebUiActivity.kt`, `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/NativeJsBridge.kt`, `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/PythonBridge.kt`, `for Android/kotlin_app/src/main/AndroidManifest.xml`, `for Android/kotlin_app/build.gradle.kts`, and `for Android/kotlin_app/gradle/libs.versions.toml`.

### Assets and documentation

- Modify `for Android/package_apk_assets.py`, `for Android/build_apk.py`, `for Android/README.md`, and `for Android/07_STEP_BY_STEP_IMPLEMENTATION_ROADMAP.md`.
- Generate `for Android/kotlin_app/src/main/assets/asset-manifest.json` at build time from real assets; never hand-author a fake manifest.

## Task 1: Mobile Protocol And Event Cursor

**Files:**
- Create: `for Android/mobile_protocol.py`
- Create: `for Android/mobile_event_cursor.py`
- Test: `for Android/tests/test_mobile_protocol.py`
- Test: `for Android/tests/test_mobile_event_cursor.py`

**Interfaces:**
- Produce `TaskState`, `RuntimeState`, `CapabilityStatus`, `MobileTaskRequest`, `MobileTask`, `MobileEvent`, `parse_mobile_task_request()`, and `serialize_event()`.
- Produce `EventCursor.accept(event_id: str, sequence: int) -> bool`, `EventCursor.advance(sequence: int) -> None`, and `EventCursor.last_sequence -> int`.

- [ ] **Step 1: Write the failing tests**

```python
from mobile_event_cursor import EventCursor
from mobile_protocol import TaskState, parse_mobile_task_request


def test_cursor_accepts_only_new_sequences_and_rejects_duplicate_ids():
    cursor = EventCursor(after=4)
    assert cursor.accept("event-5", 5) is True
    assert cursor.last_sequence == 5
    assert cursor.accept("event-5", 5) is False
    assert cursor.accept("event-4", 4) is False
    assert cursor.accept("event-6", 6) is True


def test_mobile_task_request_requires_non_empty_prompt_and_bounded_model():
    request = parse_mobile_task_request({"session_id": "s1", "prompt": "check files"})
    assert request.session_id == "s1"
    assert request.prompt == "check files"
    assert request.model is None
    assert request.state is TaskState.QUEUED


def test_invalid_mobile_task_request_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="prompt"):
        parse_mobile_task_request({"session_id": "s1", "prompt": "   "})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "for Android/tests/test_mobile_protocol.py" "for Android/tests/test_mobile_event_cursor.py" -q`

Expected: FAIL with import errors for `mobile_protocol` and `mobile_event_cursor`.

- [ ] **Step 3: Write the minimal implementation**

Implement the enums as `str, Enum`, cap prompt previews at 256 UTF-8 characters, validate `session_id` and `model` as non-empty strings, and make `EventCursor.accept()` reject sequences not greater than the current cursor or event IDs already observed. Use deterministic JSON-compatible values in `MobileTask.to_dict()` and `MobileEvent.to_dict()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "for Android/tests/test_mobile_protocol.py" "for Android/tests/test_mobile_event_cursor.py" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/mobile_protocol.py" "for Android/mobile_event_cursor.py" "for Android/tests/test_mobile_protocol.py" "for Android/tests/test_mobile_event_cursor.py"
git diff --cached --name-only -- desktop src
git commit -m "feat(android): add mobile protocol and event cursor"
```

Expected: the scoped diff command prints no path, and the commit contains only Android files.

## Task 2: Durable Mobile Tasks And Approval Broker

**Files:**
- Create: `for Android/mobile_task_store.py`
- Create: `for Android/mobile_approval.py`
- Test: `for Android/tests/test_mobile_task_store.py`
- Test: `for Android/tests/test_mobile_approval.py`

**Interfaces:**
- `MobileTaskStore(event_store: EventStore)` appends `mobile.task.created`, `mobile.task.started`, `mobile.task.waiting_approval`, `mobile.task.succeeded`, `mobile.task.failed`, `mobile.task.cancelled`, and `mobile.task.interrupted` events.
- Public methods: `create(session_id, prompt, model) -> MobileTask`, `get(task_id) -> MobileTask`, `list(session_id: str | None = None) -> list[MobileTask]`, `transition(task_id, state, *, reason=None, approval_id=None, resume_available=False) -> MobileTask`, `append_event(task_id, event_type, payload) -> MobileEvent`, `events(task_id, after=0) -> list[MobileEvent]`, and `recover_after_restart() -> list[MobileTask]`.
- `MobileApprovalBroker` exposes `request_tool(tool, arguments) -> Awaitable[ApprovalDecision]`, `request_egress(request) -> Awaitable[ApprovalDecision]`, `resolve(request_id, allowed, scope) -> bool`, and `pending(task_id: str | None = None) -> list[dict[str, object]]`.

- [ ] **Step 1: Write the failing persistence and approval tests**

```python
import asyncio

import pytest

from agent_workspace.core.models import Autonomy, Mode
from agent_workspace.core.session import Session
from agent_workspace.storage.sqlite import SQLiteEventStore
from mobile_approval import MobileApprovalBroker
from mobile_task_store import MobileTaskStore


def _store(tmp_path):
    store = SQLiteEventStore(tmp_path / "agent.db")
    session = Session(workspace=str(tmp_path), mode=Mode.CODING, autonomy=Autonomy.WORKSPACE)
    store.create_session(session)
    return store, session


def test_task_state_is_rebuilt_from_mobile_events(tmp_path):
    store, session = _store(tmp_path)
    tasks = MobileTaskStore(store)
    task = tasks.create(session.id, "run tests", "model-a")
    tasks.transition(task.task_id, "running")
    tasks.transition(task.task_id, "interrupted", reason="runtime restarted", resume_available=True)
    rebuilt = tasks.get(task.task_id)
    assert rebuilt.state.value == "interrupted"
    assert rebuilt.resume_available is True


def test_recovery_marks_nonterminal_tasks_interrupted_without_replaying(tmp_path):
    store, session = _store(tmp_path)
    tasks = MobileTaskStore(store)
    task = tasks.create(session.id, "write a file", None)
    tasks.transition(task.task_id, "running")
    recovered = tasks.recover_after_restart()
    assert [item.task_id for item in recovered] == [task.task_id]
    assert tasks.get(task.task_id).state.value == "interrupted"


@pytest.mark.asyncio
async def test_approval_broker_waits_for_explicit_resolution(tmp_path):
    store, session = _store(tmp_path)
    broker = MobileApprovalBroker(store)
    broker.set_active_task("task-1", session.id)
    request = asyncio.create_task(
        broker.request_tool("android_clean_app", {"package_name": "com.example.app"})
    )
    await asyncio.sleep(0)
    pending = broker.pending("task-1")
    assert len(pending) == 1
    assert broker.resolve(pending[0]["request_id"], True, "once") is True
    assert (await request).allowed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "for Android/tests/test_mobile_task_store.py" "for Android/tests/test_mobile_approval.py" -q`

Expected: FAIL because the Android task projection and approval broker do not exist.

- [ ] **Step 3: Write the minimal implementation**

Use `EventStore.append()` and `list_events()`; do not add a SQLite migration. Unknown `mobile.task.*` and `approval.requested` payloads must remain primitive JSON objects so current core validation accepts them without changing `src/`. Rebuild tasks in sequence order, reject invalid backward transitions, and set `resume_available=True` only for an interrupted task whose last durable core state is not terminal `turn.completed`, `turn.failed`, or `turn.cancelled`. Never call `ApplicationService.run()` during recovery.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "for Android/tests/test_mobile_task_store.py" "for Android/tests/test_mobile_approval.py" -q`

Expected: PASS, including the restart test proving no task is automatically replayed.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/mobile_task_store.py" "for Android/mobile_approval.py" "for Android/tests/test_mobile_task_store.py" "for Android/tests/test_mobile_approval.py"
git diff --cached --name-only -- desktop src
git commit -m "feat(android): persist mobile tasks and approvals"
```

### Task 3: Runtime Controller And Mobile Gateway

**Files:**
- Create: `for Android/mobile_runtime_controller.py`
- Create: `for Android/mobile_gateway.py`
- Test: `for Android/tests/test_mobile_runtime_controller.py`
- Test: `for Android/tests/test_mobile_gateway.py`
- Modify: `for Android/entrypoint.py`

**Interfaces:**
- `RuntimePort` is an injected protocol with `run_task(task_id, session_id, prompt, model, emit) -> Awaitable[None]`, `cancel_task(task_id) -> Awaitable[None]`, and `close() -> Awaitable[None]`.
- `MobileRuntimeController(workspace, database, config, task_store, approval_broker, runtime_port_factory)` exposes `start()`, `close()`, `submit(request: MobileTaskRequest) -> Awaitable[MobileTask]`, `get(task_id) -> MobileTask`, `cancel(task_id) -> Awaitable[MobileTask]`, and `events(task_id, after=0) -> list[MobileEvent]`.
- `MobileGateway(controller, token, host="127.0.0.1", port=8080)` exposes `start()`, `stop()`, and `address`; its handler implements `POST /mobile/tasks`, `GET /mobile/tasks/{task_id}`, `POST /mobile/tasks/{task_id}/cancel`, `GET /mobile/tasks/{task_id}/events?after=<sequence>`, `GET /mobile/capabilities`, and `GET /mobile/health`.
- `MobileGateway` must preserve the existing `/health`, `/sessions`, `/sessions/{id}/run`, `/sessions/{id}/events`, and static console routes by delegating them to the existing `ServeApi` or a compatibility adapter. The new Android UI must never call the synchronous compatibility route.

- [ ] **Step 1: Write the failing controller and HTTP tests**

```python
import asyncio
import json
import urllib.request

import pytest

from mobile_gateway import MobileGateway
from mobile_protocol import parse_mobile_task_request
from mobile_runtime_controller import MobileRuntimeController


class FakeRuntimePort:
    def __init__(self):
        self.calls = []
        self.cancelled = []

    async def run_task(self, task_id, session_id, prompt, model, emit):
        self.calls.append((task_id, session_id, prompt, model))
        await emit("assistant.delta", {"text": "mobile ok"})
        await emit("task.completed", {"text": "mobile ok"})

    async def cancel_task(self, task_id):
        self.cancelled.append(task_id)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_submit_runs_once_and_survives_observer_disconnect(tmp_path):
    port = FakeRuntimePort()
    controller = MobileRuntimeController.for_test(tmp_path, port)
    await controller.start()
    task = await controller.submit(
        parse_mobile_task_request({"session_id": "session-1", "prompt": "check files"})
    )
    await asyncio.sleep(0)
    assert len(port.calls) == 1
    assert controller.get(task.task_id).state.value == "succeeded"
    assert [event.payload["text"] for event in controller.events(task.task_id)] == ["mobile ok"]


@pytest.mark.asyncio
async def test_cancel_is_durable_and_does_not_replay(tmp_path):
    port = FakeRuntimePort()
    controller = MobileRuntimeController.for_test(tmp_path, port)
    await controller.start()
    task = await controller.submit(
        parse_mobile_task_request({"session_id": "session-1", "prompt": "long task"})
    )
    await controller.cancel(task.task_id)
    assert port.cancelled == [task.task_id]
    assert controller.get(task.task_id).state.value == "cancelled"


def test_gateway_requires_bearer_and_returns_task_json(tmp_path):
    port = FakeRuntimePort()
    controller = MobileRuntimeController.for_test(tmp_path, port)
    gateway = MobileGateway.for_test(controller, token="mobile-token")
    gateway.start()
    try:
        url = f"{gateway.address}/mobile/tasks"
        request = urllib.request.Request(
            url,
            data=json.dumps({"session_id": "session-1", "prompt": "hello"}).encode(),
            headers={"Authorization": "Bearer mobile-token", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            body = json.loads(response.read())
        assert response.status == 202
        assert body["state"] == "queued"
        assert body["task_id"]
    finally:
        gateway.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "for Android/tests/test_mobile_runtime_controller.py" "for Android/tests/test_mobile_gateway.py" -q`

Expected: FAIL because the controller and gateway modules do not exist.

- [ ] **Step 3: Write the minimal implementation**

Implement the controller as the sole owner of running tasks. Create and persist the task before calling `asyncio.create_task`; keep the coroutine in an internal map keyed by `task_id`; emit every provider/tool/approval/completion event through `MobileTaskStore.append_event`; transition to `succeeded`, `failed`, `cancelled`, or `interrupted` exactly once. Use an `asyncio.Lock` around submission and cancellation so two taps cannot create two runtime calls. On `start()`, call `recover_after_restart()` and expose interrupted tasks without replaying them. The real runtime-port factory must wrap `build_runtime_async(..., event_listener=...)` from `src/agent_workspace/application/runtime.py` and call only the stable `ApplicationRuntime.service` interface.

Implement the gateway with `ThreadingHTTPServer` and a request handler that parses JSON with a bounded body size, validates the Bearer token using constant-time comparison, and emits JSON with `Content-Type: application/json`. The SSE endpoint must set `Cache-Control: no-cache`, send `event`, `id`, and `data` fields in sequence order, and close after the current durable backlog when no live subscription is requested. Reject non-loopback binds unless an explicit future configuration flag is added with a separate approval test. Return `401` for a missing or invalid token, `404` for an unknown task, `409` for an invalid state transition, and `202` for accepted submissions.

In `entrypoint.py`, instantiate the Android controller and gateway for `serve-mobile`, keep the existing compatibility assets, and close both objects from the existing `finally` block. Do not import or modify any Windows UI or shared-core file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "for Android/tests/test_mobile_runtime_controller.py" "for Android/tests/test_mobile_gateway.py" -q`

Expected: PASS, including the single-call assertion and Bearer-token rejection coverage.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/mobile_runtime_controller.py" "for Android/mobile_gateway.py" "for Android/entrypoint.py" "for Android/tests/test_mobile_runtime_controller.py" "for Android/tests/test_mobile_gateway.py"
git diff --cached --name-only -- desktop src tests
git commit -m "feat(android): add mobile runtime controller and gateway"
```

### Task 4: Capabilities Diagnostics Workspace And Redaction

**Files:**
- Create: `for Android/mobile_capabilities.py`
- Create: `for Android/mobile_diagnostics.py`
- Create: `for Android/mobile_workspace.py`
- Create: `for Android/android_adapter/redaction.py`
- Test: `for Android/tests/test_mobile_capabilities.py`
- Test: `for Android/tests/test_mobile_workspace.py`
- Test: `for Android/tests/test_android_redaction.py`
- Modify: `for Android/mobile_gateway.py`

**Interfaces:**
- `CapabilitySnapshot` contains exactly the capability names from the design and a status in `available`, `permission_required`, `dependency_missing`, `denied`, `degraded`, or `unavailable`.
- `collect_capabilities(env: Mapping[str, str], command_exists: Callable[[str], bool]) -> CapabilitySnapshot` performs read-only checks and never executes an arbitrary user command.
- `MobileDiagnostics(controller, capabilities, redactor).snapshot() -> dict[str, object]` returns a JSON-safe, read-only projection with host, runtime, task, version, ABI, Android, port, battery, network, notification, Termux:API, Shizuku, and recent failure fields.
- `WorkspaceBrowser(root, max_file_bytes=1_048_576)` exposes `read_file(relative_path) -> str`, `list_files(relative_dir="") -> list[dict[str, object]]`, and `unified_diff(relative_path, before, after) -> str`; all paths must remain inside `root`.
- `Redactor.redact(text: str) -> str` masks API keys, Bearer tokens, cookies, environment assignments, and absolute user-home paths while preserving line structure.

- [ ] **Step 1: Write the failing capability, workspace, and redaction tests**

```python
from mobile_capabilities import collect_capabilities
from mobile_workspace import WorkspaceBrowser
from android_adapter.redaction import Redactor


def test_missing_android_dependencies_are_reported_without_failing(tmp_path):
    snapshot = collect_capabilities({"TERMUX_VERSION": ""}, command_exists=lambda name: False)
    assert snapshot.values["termux_api"] == "dependency_missing"
    assert snapshot.values["shizuku"] == "dependency_missing"
    assert snapshot.values["screen_actions"] == "unavailable"


def test_workspace_browser_rejects_escape_and_limits_file_size(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "ok.txt").write_text("ok", encoding="utf-8")
    browser = WorkspaceBrowser(root, max_file_bytes=2)
    assert browser.read_file("ok.txt") == "ok"
    try:
        browser.read_file("../outside.txt")
    except ValueError as exc:
        assert "workspace" in str(exc)
    else:
        raise AssertionError("path traversal was accepted")


def test_redactor_masks_secrets_and_paths():
    text = "Authorization: Bearer abc123\nOPENAI_API_KEY=sk-secret\n/home/u/project"
    redacted = Redactor().redact(text)
    assert "abc123" not in redacted
    assert "sk-secret" not in redacted
    assert "/home/u/project" not in redacted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "for Android/tests/test_mobile_capabilities.py" "for Android/tests/test_mobile_workspace.py" "for Android/tests/test_android_redaction.py" -q`

Expected: FAIL because the capability, workspace, and redaction modules do not exist.

- [ ] **Step 3: Write the minimal implementation**

Keep capability detection declarative: check `termux-*` executable presence, the Shizuku/rish marker, notification permission input, battery/network provider callbacks, and the host type. Map missing optional dependencies to `dependency_missing` rather than raising. Add `GET /mobile/capabilities` and a read-only `GET /mobile/diagnostics` route to the gateway; diagnostics must not expose the gateway token, provider key, cookie, full environment, or arbitrary command output.

Resolve workspace paths with `Path(root, relative_path).resolve()` and reject paths whose resolved value is outside `root.resolve()`. Reject files larger than `max_file_bytes` before reading. Return a bounded directory listing and use `difflib.unified_diff` for read-only diffs. Do not add write or command execution methods to this module.

Redact case-insensitively the values after `Authorization: Bearer`, `Cookie`, common `*_API_KEY`, `*_TOKEN`, `*_SECRET`, and `*_PASSWORD` assignments, and absolute paths under `Path.home()` or the configured workspace root. Apply redaction to process logs, diagnostics, and exported event text before returning them.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "for Android/tests/test_mobile_capabilities.py" "for Android/tests/test_mobile_workspace.py" "for Android/tests/test_android_redaction.py" -q`

Expected: PASS, including path traversal rejection and secret masking.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/mobile_capabilities.py" "for Android/mobile_diagnostics.py" "for Android/mobile_workspace.py" "for Android/android_adapter/redaction.py" "for Android/mobile_gateway.py" "for Android/tests/test_mobile_capabilities.py" "for Android/tests/test_mobile_workspace.py" "for Android/tests/test_android_redaction.py"
git diff --cached --name-only -- desktop src tests
git commit -m "feat(android): add mobile capabilities diagnostics and workspace"
```

### Task 5: Termux Lifecycle And Power Policy

**Files:**
- Create: `for Android/android_adapter/termux_lifecycle.py`
- Test: `for Android/tests/test_termux_lifecycle.py`
- Modify: `for Android/entrypoint.py`
- Modify: `for Android/android_adapter/termux_api.py`
- Modify: `for Android/run_server.sh`
- Modify: `for Android/bootstrap.sh`

**Interfaces:**
- `TermuxLifecycle(run_command, min_restart_delay=1.0, max_restart_delay=60.0)` exposes `observe(runtime_state, active_task_count)`, `restart_delay(attempt)`, `stop()`, and `wake_lock_held`.
- `TermuxPowerAdapter(run_command)` exposes `acquire_for_tasks()`, `release_when_idle()`, and `status() -> dict[str, object]`.
- `run_server.sh` starts one server process, records its PID in a private runtime directory, traps `INT`, `TERM`, and `EXIT`, and releases the Termux wake lock only after the server exits.

- [ ] **Step 1: Write the failing lifecycle tests**

```python
from android_adapter.termux_lifecycle import TermuxLifecycle, TermuxPowerAdapter


def test_wake_lock_only_follows_active_tasks():
    calls = []
    power = TermuxPowerAdapter(calls.append)
    power.acquire_for_tasks()
    power.acquire_for_tasks()
    power.release_when_idle()
    assert calls == [["termux-wake-lock"], ["termux-wake-unlock"]]


def test_restart_delay_is_bounded_exponential_backoff():
    lifecycle = TermuxLifecycle(lambda command: None, min_restart_delay=1, max_restart_delay=8)
    assert [lifecycle.restart_delay(n) for n in range(5)] == [1, 2, 4, 8, 8]


def test_failed_runtime_does_not_hold_wake_lock():
    calls = []
    lifecycle = TermuxLifecycle(calls.append)
    lifecycle.observe("FAILED", 0)
    assert lifecycle.wake_lock_held is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "for Android/tests/test_termux_lifecycle.py" -q`

Expected: FAIL because the lifecycle and power policy modules do not exist.

- [ ] **Step 3: Write the minimal implementation**

Implement the power adapter as an idempotent state machine. Acquire `termux-wake-lock` only when `active_task_count > 0` and the runtime is `RUNNING`; release it for `READY`, `BATTERY_SAVER`, `FAILED`, `STOPPED`, and zero active tasks. Capture command failures as degraded diagnostics rather than stopping the Agent. Keep `termux-api` command wrappers bounded by a timeout and return explicit unavailable results when the executable is absent.

Use `TermuxLifecycle` in `entrypoint.py` around the gateway/controller lifetime. Handle `SIGTERM` and `SIGINT` by stopping acceptance of new tasks, allowing the current cancellation path to persist `interrupted`, closing the gateway, releasing the wake lock, and closing the runtime. Restart only the Python runtime worker, not the gateway, with `min(max_restart_delay, min_delay * 2**attempt)` and reset the attempt counter after a stable run. Update `run_server.sh` and `bootstrap.sh` to avoid a second server instance and to report the active process, token file, and power state without printing secrets.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "for Android/tests/test_termux_lifecycle.py" -q`

Expected: PASS, including duplicate acquire/release suppression and bounded backoff.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/android_adapter/termux_lifecycle.py" "for Android/android_adapter/termux_api.py" "for Android/entrypoint.py" "for Android/run_server.sh" "for Android/bootstrap.sh" "for Android/tests/test_termux_lifecycle.py"
git diff --cached --name-only -- desktop src tests
git commit -m "feat(android): add Termux lifecycle and power policy"
```

### Task 6: APK Foreground Service, Process Supervision, Notifications And WakeLock

**Files:**
- Create: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/RuntimeState.kt`
- Create: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/ProcessSupervisor.kt`
- Create: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/WakeLockController.kt`
- Create: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/NotificationController.kt`
- Create: `for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/embedded/ProcessSupervisorTest.kt`
- Modify: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxDaemonService.kt`
- Modify: `for Android/kotlin_app/src/main/AndroidManifest.xml`
- Modify: `for Android/kotlin_app/build.gradle.kts`
- Modify: `for Android/kotlin_app/gradle/libs.versions.toml`

**Interfaces:**
- `EngineState` contains `STOPPED`, `STARTING`, `READY`, `RUNNING`, `PAUSED_BY_SYSTEM`, `RECOVERING`, and `FAILED`.
- `RuntimeSnapshot(state, activeTaskCount, lastError, restartAttempt)` is immutable and serializable for notification/diagnostics projection.
- `ProcessSupervisor(command, environment, processFactory, sleeper, policy)` exposes `start()`, `requestStop()`, `snapshot()`, and `join()`; it guarantees one child process and uses bounded exponential restart delay.
- `WakeLockController(powerManager, tag)` exposes `setTaskActive(active: Boolean)`, `setBatterySaver(paused: Boolean)`, and `release()`; it never acquires a lock for an idle runtime.
- `NotificationController(context)` exposes `show(snapshot)`, `showApproval(taskId, summary)`, `showCompletion(taskId, success)`, and `cancel(taskId)`.

- [ ] **Step 1: Write the failing JVM tests**

```kotlin
class ProcessSupervisorTest {
    @Test
    fun startIsIdempotentAndCreatesOnlyOneChild() = runTest {
        val factory = FakeProcessFactory()
        val supervisor = ProcessSupervisor(
            command = listOf("python3", "entrypoint.py"),
            environment = emptyMap(),
            processFactory = factory,
            sleeper = { },
        )
        supervisor.start()
        supervisor.start()
        assertEquals(1, factory.starts)
        supervisor.requestStop()
        supervisor.join()
    }

    @Test
    fun crashesUseBoundedBackoffBeforeRestart() = runTest {
        val factory = FakeProcessFactory(exitImmediately = true)
        val waits = mutableListOf<Long>()
        val supervisor = ProcessSupervisor(
            command = listOf("python3"),
            environment = emptyMap(),
            processFactory = factory,
            sleeper = { waits += it },
            policy = RestartPolicy(minDelayMs = 1000, maxDelayMs = 4000),
        )
        supervisor.start()
        supervisor.requestStop()
        supervisor.join()
        assertEquals(listOf(1000L, 2000L, 4000L), waits.take(3))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat test --tests "com.agentworkspace.mobile.embedded.ProcessSupervisorTest"` from `for Android/kotlin_app`.

Expected: FAIL because the state, supervisor, and WakeLock abstractions do not exist.

- [ ] **Step 3: Write the minimal implementation**

Move all child-process ownership into `ProcessSupervisor`. `TermuxDaemonService.onCreate()` must create the notification channel, call `startForeground()`, and launch exactly one supervisor coroutine. Remove the fixed 60-minute `acquire()` call. Resolve the embedded Python path from the activated Bootstrap directory; if it is missing, publish `FAILED` with a diagnostic error and do not fall back to a host `python3` binary. Redirect child output to a bounded rolling log buffer and pass redacted lines to Logcat. On unexpected exit, transition to `RECOVERING`, wait using the policy, and restart until `requestStop()` or a maximum consecutive-failure threshold transitions to `FAILED`.

Use `WakeLockController` whenever the Python gateway reports a positive active-task count and the runtime is not in `BATTERY_SAVER`. Release immediately after the task count reaches zero, on `onDestroy()`, and when the service enters `FAILED`. Do not infer task activity from Activity visibility. `NotificationController` must expose open-agent, cancel-task, restart-engine, and diagnostics `PendingIntent` actions; missing `POST_NOTIFICATIONS` permission must only suppress notification updates and must not stop the runtime. Keep the notification text free of prompt contents, credentials, and full user paths.

Declare only the foreground-service and notification permissions needed by the current target SDK, use the existing loopback WebView architecture, and add the Kotlin test dependencies already used by the project rather than introducing a second test framework.

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat test --tests "com.agentworkspace.mobile.embedded.ProcessSupervisorTest"` from `for Android/kotlin_app`.

Expected: PASS, including the one-child invariant and the bounded restart sequence.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/RuntimeState.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/ProcessSupervisor.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/WakeLockController.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/NotificationController.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxDaemonService.kt" "for Android/kotlin_app/src/main/AndroidManifest.xml" "for Android/kotlin_app/build.gradle.kts" "for Android/kotlin_app/gradle/libs.versions.toml" "for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/embedded/ProcessSupervisorTest.kt"
git diff --cached --name-only -- desktop src tests
git commit -m "feat(android): supervise embedded runtime in foreground service"
```

### Task 7: Atomic APK Bootstrap And Verified Assets

**Files:**
- Create: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/BootstrapManifest.kt`
- Create: `for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/embedded/TermuxBootstrapTest.kt`
- Create: `for Android/tests/test_android_asset_contract.py`
- Modify: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxBootstrap.kt`
- Modify: `for Android/package_apk_assets.py`
- Modify: `for Android/build_apk.py`

**Interfaces:**
- `BootstrapManifest(version, agentVersion, webVersion, rootfsVersion, abi, files)` contains SHA-256 and byte size for every packaged asset and exposes `fromJson(text)`, `toJson()`, and `verify(root: File, supportedAbi: String)`.
- `TermuxBootstrap.installAtomic(context, expectedAbi, onProgress) -> InstallResult` validates the manifest, extracts into a unique staging directory, checks the Python entrypoint and ABI marker, atomically swaps `active` and preserves the previous version for rollback.
- `TermuxBootstrap.isInstalled(context) -> Boolean` returns true only when the active marker, manifest, Python executable, and Android entrypoint all verify.
- `package_apk_assets.py` must fail with a non-zero exit code for absent, invalid, placeholder, wrong-ABI, or under-sized rootfs input; it must generate `asset-manifest.json` only after all hashes and required files pass.

- [ ] **Step 1: Write the failing asset and rollback tests**

```python
import zipfile

import pytest

from package_apk_assets import _validate_bootstrap_rootfs


def test_placeholder_rootfs_is_rejected(tmp_path):
    archive = tmp_path / "rootfs.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("usr/bin/python3", "#!/bin/sh\necho starter")
    with pytest.raises(ValueError, match="placeholder|real Termux"):
        _validate_bootstrap_rootfs(archive)


def test_asset_contract_requires_arm64_and_entrypoint(tmp_path):
    manifest = tmp_path / "asset-manifest.json"
    manifest.write_text(
        '{"abi":"arm64-v8a","files":{"agent_code.zip":{"sha256":"bad","size":1}}}',
        encoding="utf-8",
    )
    result = run_asset_contract(manifest, tmp_path)
    assert result.ok is False
    assert "sha256" in result.reason
```

```kotlin
@Test
fun failedInstallLeavesPreviousActiveVersion() {
    val context = testContextWithActiveVersion("old")
    val badAsset = assetZipWithTraversalEntry()
    assertFailsWith<SecurityException> {
        TermuxBootstrap.installAtomic(context, "arm64-v8a", asset = badAsset)
    }
    assertEquals("old", readActiveVersion(context))
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "for Android/tests/test_android_asset_contract.py" -q` and `./gradlew.bat test --tests "com.agentworkspace.mobile.embedded.TermuxBootstrapTest"` from `for Android/kotlin_app`.

Expected: FAIL because the manifest contract and atomic installer do not exist.

- [ ] **Step 3: Write the minimal implementation**

Remove the duplicate fallback implementation in `package_apk_assets.py`; the only accepted source is an existing real ARM64 archive or an explicitly supplied external archive that passes `_validate_bootstrap_rootfs`. Validate the ZIP before copying it, require `usr/bin/python3` or `usr/bin/python`, reject starter stubs, require a realistic file count and uncompressed size, reject unsafe names, and require an explicit `arm64-v8a` marker from the supplied asset metadata. Do not synthesize directories, stubs, or a fake rootfs. Make `build_apk.py` stop before Gradle when asset packaging returns non-zero.

Build the manifest from the final Web assets, `agent_code.zip`, and rootfs archive. Record the application version, Agent code version, Web UI version, rootfs version, ABI, file size, and SHA-256. The manifest is generated in the assets directory and is included in the APK; it is never hand-authored. The asset contract test must use a temporary staging directory and must not modify the checked-in placeholder archive.

Replace direct extraction into `filesDir` with `staging/<uuid>`. Verify every ZIP entry stays under the staging root, reject symlinks and duplicate normalized names, extract with bounded file sizes, set executable bits only for expected runtime files, verify the manifest after extraction, and write a version marker only after validation. Rename the previous `active` directory to `rollback` and atomically rename staging to `active`; if any step fails, delete staging and keep the previous active directory untouched. `isInstalled()` must verify the active manifest instead of trusting a marker alone.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "for Android/tests/test_android_asset_contract.py" -q` and `./gradlew.bat test --tests "com.agentworkspace.mobile.embedded.TermuxBootstrapTest"` from `for Android/kotlin_app`.

Expected: PASS; running the normal packaging command against the current 1363-byte placeholder must fail clearly before APK compilation.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/BootstrapManifest.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxBootstrap.kt" "for Android/kotlin_app/src/test/kotlin/com/agentworkspace/mobile/embedded/TermuxBootstrapTest.kt" "for Android/package_apk_assets.py" "for Android/build_apk.py" "for Android/tests/test_android_asset_contract.py"
git diff --cached --name-only -- desktop src tests
git commit -m "fix(android): make APK bootstrap atomic and asset verified"
```

### Task 8: Mobile Web Async Tasks, SSE Resume And Approval-First UX

**Files:**
- Create: `for Android/web_companion/static/mobile_state.mjs`
- Create: `for Android/web_companion/static/mobile_state.test.mjs`
- Modify: `for Android/web_companion/index.html`
- Modify: `for Android/web_companion/static/app.js`
- Modify: `for Android/web_companion/static/style.css`
- Modify: `for Android/kotlin_app/src/main/assets/web/index.html`
- Modify: `for Android/kotlin_app/src/main/assets/web/static/app.js`
- Modify: `for Android/kotlin_app/src/main/assets/web/static/style.css`

**Interfaces:**
- `MobileState` exposes `submitTask(input)`, `cancelTask(taskId)`, `connectTask(taskId, after)`, `applyEvent(event)`, `lastSequence(taskId)`, and `snapshot()`.
- `parseSseChunk(buffer) -> { events, remainder }` parses `event`, `id`, and multi-line `data` fields without assuming one network chunk equals one event.
- `dedupeEvent(state, event) -> boolean` accepts only a strictly newer sequence or a new event ID and never moves the cursor backwards.
- The UI calls `/mobile/tasks`, `/mobile/tasks/{id}`, `/mobile/tasks/{id}/cancel`, and `/mobile/tasks/{id}/events?after=<sequence>` with the Bearer token from the injected page state. It never calls `/sessions/{id}/run` for new work.

- [ ] **Step 1: Write the failing JavaScript tests**

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { MobileState, parseSseChunk } from "./mobile_state.mjs";

test("SSE parser handles split JSON and multiline data", () => {
  const first = parseSseChunk("id: 5\nevent: assistant.delta\ndata: {\"text\":\n");
  assert.equal(first.events.length, 0);
  const second = parseSseChunk(first.remainder + "data: \"ok\"}\n\n");
  assert.equal(second.events[0].sequence, 5);
  assert.equal(second.events[0].payload.text, "ok");
});

test("duplicate and stale events do not change the cursor", () => {
  const state = new MobileState();
  assert.equal(state.applyEvent({ taskId: "t1", sequence: 2, eventId: "e2" }), true);
  assert.equal(state.applyEvent({ taskId: "t1", sequence: 2, eventId: "e2" }), false);
  assert.equal(state.applyEvent({ taskId: "t1", sequence: 1, eventId: "e1" }), false);
  assert.equal(state.lastSequence("t1"), 2);
});

test("reconnect uses the last cursor and never resubmits", async () => {
  const calls = [];
  const state = new MobileState({ fetchImpl: async (url) => {
    calls.push(url);
    return new Response("", { status: 200 });
  }});
  state.applyEvent({ taskId: "t1", sequence: 7, eventId: "e7" });
  await state.connectTask("t1");
  assert.equal(calls[0], "/mobile/tasks/t1/events?after=7");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test "for Android/web_companion/static/mobile_state.test.mjs"`

Expected: FAIL because `mobile_state.mjs` does not exist.

- [ ] **Step 3: Write the minimal implementation**

Implement the state module with a per-task event map, a per-task cursor, a pending submission map, and an explicit connection state. `submitTask()` must POST once, store the returned `task_id` and `last_sequence`, and then call `connectTask()`; it must not retry the POST automatically. `connectTask()` must use a `fetch()` stream so the Authorization header is available, parse arbitrary chunk boundaries, apply only new events, and reconnect with bounded backoff using the current cursor. A reconnect after a completed task must first query task status and stop when the state is terminal. A reconnect after an approval event must keep the approval panel visible until `resolve` is sent by the existing approval route.

Rebuild `index.html` and `app.js` around the mobile three-layer layout: top connection/runtime/session status, a scrollable timeline, and a bottom composer plus fixed approval area. Replace `prompt()` and `alert()` with inline validation, a cancel button, a retry status, and a bottom-sheet session/task history view. Render tool calls as collapsible rows with waiting/running/succeeded/failed/unknown states; show the complete approval target including package, path, command, and impact. Preserve draft text when the keyboard or Activity changes and use `env(safe-area-inset-*)`, minimum 44px touch targets, and a single-column file/diff view. Keep the static asset copies synchronized with `web_companion` through the existing asset packer rather than editing the APK copies by hand.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test "for Android/web_companion/static/mobile_state.test.mjs"`.

Expected: PASS, including split SSE frames, deduplication, cursor resume, and no duplicate submission.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/web_companion/index.html" "for Android/web_companion/static/mobile_state.mjs" "for Android/web_companion/static/mobile_state.test.mjs" "for Android/web_companion/static/app.js" "for Android/web_companion/static/style.css" "for Android/kotlin_app/src/main/assets/web/index.html" "for Android/kotlin_app/src/main/assets/web/static/app.js" "for Android/kotlin_app/src/main/assets/web/static/style.css"
git diff --cached --name-only -- desktop src tests
git commit -m "feat(android): add reconnectable mobile task console"
```

### Task 9: WebView Lifecycle And Native Bridge Safety

**Files:**
- Create: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/BridgePolicy.kt`
- Create: `for Android/kotlin_app/src/androidTest/kotlin/com/agentworkspace/mobile/AndroidLifecycleTest.kt`
- Modify: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/WebUiActivity.kt`
- Modify: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/NativeJsBridge.kt`
- Modify: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/PythonBridge.kt`
- Modify: `for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxDaemonService.kt`
- Modify: `for Android/kotlin_app/src/main/AndroidManifest.xml`

**Interfaces:**
- `BridgePolicy.isAllowedExternalUri(uri: Uri) -> Boolean` returns true only for HTTP and HTTPS URIs with a non-empty host; it rejects `file`, `content`, `javascript`, `intent`, custom schemes, empty hosts, and malformed values.
- `NativeJsBridge` exposes `vibrate`, `showToast`, `copyToClipboard`, `shareText`, `openExternal`, `getBatteryLevel`, `getBatterySaverEnabled`, and `notifyTask`; every method is bounded and UI-safe.
- `WebUiActivity` persists the active task ID, session ID, and event cursor in `onSaveInstanceState`, reconnects in `onStart`/`onResume`, and never stops the foreground service from `onDestroy()`.
- `PythonBridge` exposes `submitTask(context, sessionId, prompt) -> Flow<AgentStreamChunk>`, `connectTaskEvents(context, taskId, after) -> Flow<AgentStreamChunk>`, and `cancelTask(context, taskId)` using the asynchronous Mobile Gateway routes.

- [ ] **Step 1: Write the failing bridge and lifecycle tests**

```kotlin
class BridgePolicyTest {
    @Test
    fun onlyHttpAndHttpsUrisWithHostsAreAllowed() {
        assertTrue(BridgePolicy.isAllowedExternalUri(Uri.parse("https://example.com/path")))
        assertTrue(BridgePolicy.isAllowedExternalUri(Uri.parse("http://127.0.0.1:8080")))
        assertFalse(BridgePolicy.isAllowedExternalUri(Uri.parse("file:///sdcard/a.txt")))
        assertFalse(BridgePolicy.isAllowedExternalUri(Uri.parse("javascript:alert(1)")))
        assertFalse(BridgePolicy.isAllowedExternalUri(Uri.parse("intent://settings")))
        assertFalse(BridgePolicy.isAllowedExternalUri(Uri.parse("https:///missing-host")))
    }
}
```

```kotlin
@RunWith(AndroidJUnit4::class)
class AndroidLifecycleTest {
    @Test
    fun destroyingActivityDoesNotStopTheRuntimeService() {
        val scenario = launchActivity<WebUiActivity>()
        scenario.onActivity { it.saveActiveTaskForTest("task-1", "session-1", 9) }
        scenario.moveToState(Lifecycle.State.DESTROYED)
        assertTrue(serviceManager.isRunning(TermuxDaemonService::class.java))
        assertEquals(9, savedStateStore.cursorFor("task-1"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat testDebugUnitTest --tests "com.agentworkspace.mobile.bridge.BridgePolicyTest"` and `./gradlew.bat connectedDebugAndroidTest` from `for Android/kotlin_app`.

Expected: FAIL because the bridge policy, lifecycle state persistence, and asynchronous native bridge methods do not exist.

- [ ] **Step 3: Write the minimal implementation**

Add `BridgePolicy` and use it before constructing every external-link `Intent`. Keep the loopback console URL inside the WebView; only user-requested HTTP/HTTPS links leave the app. Do not expose a generic command, filesystem, reflection, or arbitrary URL bridge. Clamp vibration duration, catch missing system services, and route clipboard/share/file-picker errors to a visible inline status instead of throwing into JavaScript. `notifyTask` must use the same notification controller as the service and must not include secrets.

Refactor `WebUiActivity` so bootstrap/service startup is idempotent, the WebView is recreated without losing task/session/cursor state, and `onDestroy()` only releases Activity-owned callbacks and WebView resources. The foreground service remains the owner of Python and task execution. On Android 13 and later, request notification permission from the Activity when needed, but allow the Gateway and background task to continue when permission is denied. Use the existing file chooser with persistable URI permission only for the user-selected URI and reject unsupported MIME targets.

Replace `PythonBridge`'s synchronous `/sessions/{id}/run` call with one POST to `/mobile/tasks`, then consume the SSE stream using the returned task ID and cursor. Cancellation sends exactly one POST to `/mobile/tasks/{id}/cancel`. A transport reconnect resumes from the last emitted sequence and never creates a new task. Keep the old overload only as a compatibility wrapper that requires an explicit context/token and delegates to the asynchronous implementation.

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat testDebugUnitTest --tests "com.agentworkspace.mobile.bridge.BridgePolicyTest"` and `./gradlew.bat connectedDebugAndroidTest` from `for Android/kotlin_app`.

Expected: PASS on the JVM bridge tests; the connected test must prove Activity destruction does not stop the service and that a non-HTTP URI is rejected.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/BridgePolicy.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/NativeJsBridge.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/PythonBridge.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/WebUiActivity.kt" "for Android/kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxDaemonService.kt" "for Android/kotlin_app/src/main/AndroidManifest.xml" "for Android/kotlin_app/src/androidTest/kotlin/com/agentworkspace/mobile/AndroidLifecycleTest.kt"
git diff --cached --name-only -- desktop src tests
git commit -m "feat(android): harden WebView lifecycle and native bridge"
```

### Task 10: Android Regression Suite, Scope Guard And Documentation

**Files:**
- Create: `for Android/tests/conftest.py`
- Create: `for Android/tests/test_android_scope.py`
- Modify: `for Android/test_android_stack.py`
- Modify: `for Android/README.md`
- Modify: `for Android/07_STEP_BY_STEP_IMPLEMENTATION_ROADMAP.md`
- Modify: `for Android/10_APK_BUILD_AND_RELEASE_GUIDE.md`

**Interfaces:**
- `for Android/tests/conftest.py` adds the Android directory and repository `src` to `sys.path` without changing process-wide test configuration outside Android tests.
- `test_android_scope.py` checks the staged path list and fails if any staged path is outside `for Android/` or the approved Android design/plan document paths.
- `test_android_stack.py` retains the existing credential, Termux:API, Shizuku, patcher, static-resource, compatibility-route, and provider E2E checks and adds one Mobile Gateway task submission, SSE resume, cancellation, redaction, and malformed-asset check.

- [ ] **Step 1: Write the failing scope and regression tests**

```python
import subprocess


def test_staged_android_change_does_not_touch_windows_or_shared_core():
    paths = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"], text=True
    ).splitlines()
    allowed = (
        "for Android/",
        "for Android/docs/specs/2026-09-22-android-agent-dual-host-design.md",
        "for Android/docs/plans/2026-09-22-android-agent-dual-host-plan.md",
    )
    unexpected = [path for path in paths if not path.startswith(allowed)]
    assert unexpected == []
```

```python
def test_mobile_task_is_not_duplicated_after_sse_reconnect(android_server):
    task = android_server.submit({"session_id": "s1", "prompt": "one task"})
    first = android_server.events(task["task_id"], after=0)
    second = android_server.events(task["task_id"], after=first[-1]["sequence"] - 1)
    assert len({event["event_id"] for event in first + second}) == len(
        {event["event_id"] for event in first}
    )
    assert android_server.provider_call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "for Android/tests/test_android_scope.py" "for Android/test_android_stack.py" -q`

Expected: FAIL until the Android test fixtures and new asynchronous regression paths are present.

- [ ] **Step 3: Write the minimal implementation**

Add the Android-only pytest fixture setup and update `test_android_stack.py` to exercise the new routes with the existing fake OpenAI-compatible provider. Verify: task submission returns one task ID; the provider receives one request; the SSE stream can resume from a saved sequence; cancellation persists `cancelled`; a simulated restart persists `interrupted` without replay; missing Termux:API and Shizuku produce capability states; diagnostics contain no token or API key; and malformed/placeholder rootfs input exits non-zero.

Run the full Android test matrix from the repository root:

```powershell
python -m pytest "for Android/tests" "for Android/test_android_stack.py" -q
node --test "for Android/web_companion/static/mobile_state.test.mjs"
Push-Location "for Android/kotlin_app"
./gradlew.bat testDebugUnitTest
./gradlew.bat lintDebug
Pop-Location
```

Run the packaging contract separately because the checked-in rootfs is intentionally invalid:

```powershell
python "for Android/package_apk_assets.py"
```

Expected: the Python/Kotlin/Web tests pass, while the packaging command fails with a clear real-rootfs/ABI validation message until a verified ARM64 rootfs is supplied. Do not turn that expected failure into a success by adding a stub asset.

Update the Android README and roadmap with the two supported hosts, the Mobile Gateway endpoints, task recovery semantics, capability statuses, token/loopback security, the real-rootfs prerequisite, and the exact verification commands. Document that Windows source remains outside the Android change set. Remove claims that the APK is ready when the only bundled rootfs is the placeholder archive.

- [ ] **Step 4: Run test to verify it passes**

Run the commands in Step 3 and then stage only the Android implementation and approved Android documents. Confirm the scope guard with:

```powershell
git diff --cached --name-only -- desktop src tests
```

Expected: no output from the scope command, all Android tests pass, and the asset packaging command fails only for the known missing real ARM64 rootfs.

- [ ] **Step 5: Commit**

```powershell
git add -- "for Android" "for Android/docs/specs/2026-09-22-android-agent-dual-host-design.md" "for Android/docs/plans/2026-09-22-android-agent-dual-host-plan.md"
git diff --cached --name-only -- desktop src tests
git commit -m "test(android): add isolated regression and release checks"
```

## Plan Self-Review

Before handing the plan to an implementer, perform these checks against the approved design:

1. **Coverage:** Design sections 1 and 3 are covered by Tasks 3, 5, and 6; section 2 by the global constraints and Task 10; section 4 by Tasks 2, 3, 8, and 9; section 5 by Tasks 5 and 6; section 6 by Tasks 8 and 9; section 7 by Tasks 4, 5, and 9; section 8 by Tasks 2, 4, and 10; section 9 by Task 7; section 10 by Task 4; section 11 by Task 10; and section 12 by the ordered tasks 3 through 10.
2. **Interface consistency:** Task 1 defines `MobileTaskRequest`, `MobileTask`, `MobileEvent`, and `EventCursor`; Task 2 adds durable task/event projection and approval resolution; Task 3 consumes those exact names and adds the runtime/gateway boundary; Task 8 and Task 9 use the same task IDs and sequence cursors. No later task introduces a second task state enum or a second token mechanism.
3. **Isolation:** Every implementation file is under `for Android/`. The only document paths approved for staging are the Android design and plan documents. No task edits `desktop/`, `src/agent_workspace/`, root Windows tests, or shared build logic.
4. **Security:** Loopback and Bearer-token checks are tested; static query tokens are limited to console asset loading; workspace traversal, secret redaction, URI schemes, Shizuku denial, approval details, and notification leakage all have explicit tests.
5. **Failure behavior:** Placeholder rootfs, wrong ABI, corrupted hashes, ZIP traversal, process crashes, missing optional dependencies, notification denial, Activity destruction, network loss, and provider failure each have a defined outcome and do not silently discard task state.
6. **No unfinished steps:** Every task has exact files, interfaces, a failing test, a failure command, an implementation instruction, a passing command, and a scoped commit. Search the plan for unfinished markers before saving; any match must be replaced by a concrete command, assertion, or implementation rule.

## Execution Handoff

Plan complete and saved to `for Android/docs/plans/2026-09-22-android-agent-dual-host-plan.md`. Two execution options:

1. **Subagent-Driven implementation** - dispatch a fresh worker per task and review between tasks.
2. **Inline implementation** - execute the tasks in this session with checkpoints.

Choose `1` or `2` for the implementation phase.
