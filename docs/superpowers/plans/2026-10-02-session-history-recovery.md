# Session History Recovery Implementation Plan

> **For agentic workers:** Use the subagent-driven-development skill to implement the independent tool task, then review its contract and code. Root owns runner integration, Android packaging and device verification. Steps use checkbox syntax for tracking.

**Goal:** Let the agent search and read stored current-session history after context compression.

**Architecture:** A contextual read-only tool uses the existing event store. The runner supplies the recovery entry and preserves untrusted/sensitive history boundaries. Android discovers the tool through its existing selector.

**Tech Stack:** Python, SQLite, existing tool schemas, Android embedded Python and Kotlin instrumentation.

## Global Constraints

- Current session and matching registry workspace only; no user-supplied database path or session ID.
- `MEMORY_READ`, `side_effect="none"`, no new database schema or external dependency.
- Search: literal query, forward cursor, limit 1–20 (default 10), bounded per-call scanning and explicit continuation.
- Read: content/tool_calls/event_data, character offset >= 0, max_chars 256–8192 (default 4096).
- Retrieved history is `UNTRUSTED_DATA` and `SENSITIVE` in the actual runner, subject to existing egress authorization.
- Root exclusively owns ADB/Gradle. No GPU work outside the existing training owner, no source pin edits, no commit/push/reset or clearing user data.
- Program tests do not prove the small model can use recovery or summarize faithfully.

### Task 1: Current-session search and read

Files: create `src/agent_workspace/tools/session_history.py` and `tests/test_session_history_tool.py`; modify `src/agent_workspace/tools/registry.py`.

Consumes: `EventStore.get_session(session_id)`, `list_events_paged(session_id, cursor=None, limit=100, reverse=False)`, existing stored text access when needed, and `ToolExecutionContext.session_id`.

Produces: `SessionHistoryTool(store, workspace)`, `.spec`, and async `.execute_with_context(arguments, context) -> str`. Search matches expose sequence/type/field/offset/snippet plus continuation; read exposes field text and next character offset. Direct `.execute` rejects missing context.

- [x] Write failing actual SQLite tests, beginning with `assert "session_history" in {s.name for s in ToolRegistry.for_workspace(workspace, store=store).specs()}`. Add two sessions containing distinct secrets and require every search/read to stay inside the bound context.
- [x] Run `.venv\Scripts\python.exe -m pytest tests/test_session_history_tool.py -q --junitxml=output/session-history-tool-red-20261002.xml`; preserve the expected missing-feature failures.
- [x] Implement the bounded contextual tool and register it beside existing memory tools. Reject bool/negative cursors, foreign workspace contexts, arbitrary extra fields and non-conversation internal events. Do not infer completion from recorded proposals.
- [x] Require Unicode content reconstructed from all read chunks to equal the stored text, and structured tool arguments reconstructed from chunks to equal the stored JSON object. Require paged searching to reach a match after more than 5,000 events.
- [x] Run the same tests with a new green evidence filename, then the affected registry/memory/store tests and owned Ruff checks.

### Task 2: Compaction recovery and data boundaries

Files: modify `src/agent_workspace/application/runner.py`; create `tests/test_context_history_recovery.py`.

Consumes: the registered `session_history` spec and existing compaction/rebuild machinery.

Produces: a recovery hint conditional on tool availability, plus actual untrusted/sensitive tool messages.

- [x] Write failing tests that compact a real stored conversation, call the new tool through the actual runner and retrieve an earlier requirement; a controlled provider checks the request boundary without claiming model fidelity.
- [x] Assert `message.trust is ContentTrust.UNTRUSTED_DATA` and `message.sensitivity is ContentSensitivity.SENSITIVE` for retrieved history. Assert denied sensitive egress prevents the next remote request.
- [x] Run `.venv\Scripts\python.exe -m pytest tests/test_context_history_recovery.py -q --junitxml=output/context-history-recovery-red-20261002.xml` before production edits.
- [x] Add availability-aware recovery guidance to both summary and plain compaction paths, and add the tool to the runner's sensitive-result classification. Keep original task and tool-group preservation.
- [x] Run green evidence and the existing summary integrity/accounting/trust regressions once; independent reviewer checks source diffs and saved evidence.

### Task 3: Android discovery and deployment

Files: modify `for Android/android_adapter/local_context.py` only if discovery needs explicit categories; add focused tests there and a current-session isolated instrumentation test. Update `for Android/export_android_source.py` document/test allowlist.

- [x] First verify the tool can be selected through existing local selection and the generated embedded source contains it; add failing tests for missing selection/bundling before changing production.
- [x] Implement only the required selector/bundling integration. Explain that the active frozen V5 evaluation uses its own previous tool catalog.
- [x] Root uses the existing low-memory build driver to create a fresh revision; cover-install preserves existing preferences and history.
- [x] Run the new history instrumentation case once on an isolated session, without native model generation, then restart the workbench and verify the original 4 sessions/1090 events, settings and credentials.
- Final source sealing/manifest/compiled-source acceptance is recorded in the external `output/android-context-r8-source-audit-20261002.json` receipt after archive creation; restored stay-awake/forwarding is in `output/android-context-r8-postrestoration-health-20261002.json`.

No approval or commit step is added: the user's prior authorization covers these fixes, and the session prohibits commit/push. The two tasks with separate file ownership run concurrently; packaging follows passing program checks.

### Deployment follow-up: transient memory must not disable settings

- [x] Preserve r7 history-device pass and the actual service startup failure. Keep Kotlin memory planning and generation guards unchanged.
- [x] RED/GREEN tests: defer only `insufficient_memory` at factory creation, expose planning readiness, retry pending plans before task budgeting, and preserve failed task/user history without compaction or native generation.
- [x] RED/GREEN diagnostics and submenu: keep saved auto 0/extended, display pending memory and permit settings access; 19 Python and 122 Web tests pass.
- [x] Independently review the minimal fix, run the isolated installed runtime/HTTP recovery case, then cover-install the reviewed revision and verify health plus all original settings/credentials/history.
- Final source sealing/manifest/compiled-source acceptance is recorded in the external `output/android-context-r8-source-audit-20261002.json` receipt after archive creation; restored stay-awake/forwarding is in `output/android-context-r8-postrestoration-health-20261002.json`.
