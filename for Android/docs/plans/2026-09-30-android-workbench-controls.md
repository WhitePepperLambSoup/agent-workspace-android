# Android Workbench Controls Implementation Plan

> **For agentic workers:** Execute the scoped tasks in this session with focused tests, independent review, and final device verification.

**Goal:** Make Android conversations usable with real execution settings, model and reasoning selection, Markdown, task recovery, and attachments.

**Architecture:** Keep the Kotlin preference store and Keystore authoritative for provider configuration. Expose a secret-free native snapshot and a validated settings command; restarting the embedded daemon applies provider and autonomy changes. Send the selected model and reasoning effort with each task, persist them with its event, and reuse existing autonomy policies and durable task APIs.

**Tech Stack:** Kotlin, Android WebView, Chaquopy Python 3.12, existing application runtime, vanilla JavaScript, locally bundled unified/remark/rehype and Lucide.

## Global Constraints

- Preserve existing conversations, credentials, and unrelated dirty work.
- Provider API keys never appear in JavaScript, settings responses, test output, or screenshots.
- Native settings use `workspace`, `yolo`, and `full_access` as execution mode values; default remains `workspace`.
- Reasoning uses `auto`, `none`, `low`, `medium`, `high`, `xhigh`, and `max` only where the selected model supports them.
- A model or permission change may restart the daemon; the UI must preserve drafts and recover durable task state.
- Markdown and icons work offline from bundled assets. Links open outside the privileged WebView.
- Controls must fit 360px mobile and desktop viewports; no decorative section cards or oversized headings.

## Shared Interfaces

```typescript
type MobileSettings = {
  protocol: string;
  base_url: string;
  model: string;
  reasoning_effort: string;
  autonomy: "workspace" | "yolo" | "full_access";
  has_api_key?: boolean;
  models?: string[];
  model_efforts?: Record<string, string[]>;
};
// Kotlin JavascriptInterface methods return JSON strings.
AndroidBridge.getProviderSettings(): string;
AndroidBridge.applyRuntimeSettings(JSON.stringify({model, reasoning_effort, autonomy})): string;
AndroidBridge.openSettings(): void;
// applyRuntimeSettings returns {ok: true} or {ok: false, error: string}.
// Authenticated HTTP contracts:
GET /mobile/settings; // effective settings, with no credentials
POST /mobile/tasks; // {session_id, prompt, model?, reasoning_effort?}
POST /mobile/attachments; // {session_id, filename, content_base64}
// attachment response: {name, path, size}; path is relative to the workspace.
```

## Task 1: Runtime Settings And Durable Execution

**Owner:** Android runtime agent.

**Files:** `for Android/mobile_protocol.py`, `mobile_task_store.py`, `mobile_runtime_controller.py`, `mobile_gateway.py`, `entrypoint.py` server startup; `src/agent_workspace/application/service.py`, `runner.py`; focused Python tests.

- [ ] Verify failing cases for explicit model/effort, queued-task snapshots, restart recovery, and autonomy migration.
- [ ] Persist resolved model and effort at task creation. Add optional explicit effort through service and runner, with selection taking precedence after request rebuilding.
- [ ] Load configured execution mode, use existing policies, and append `autonomy.changed` events for matching mobile workspace sessions before serving them.
- [ ] Expose secret-free effective settings. Add authenticated bounded attachment import using base64 decoding, safe filenames, unique contained paths, and actual file bytes.
- [ ] Run relevant Android protocol/store/controller/gateway tests and core runner/provider regressions.

## Task 2: Native Configuration And Provider Effort

**Owner:** Native configuration agent.

**Files:** Kotlin `MobileProviderSettings.kt`, `NativeJsBridge.kt`, `WebUiActivity.kt`, embedded `mobile_embedded.py`, relevant provider adapters and focused tests.

- [ ] Verify settings persistence, unsupported effort normalization, bridge secrecy, and selected effort wire formats with failing tests.
- [ ] Persist effort and execution mode; provide the shared native snapshot and validated apply command. Full provider settings retain Keystore-managed keys.
- [ ] Apply supported provider-specific effort parameters. Avoid sending unsupported options or retaining stale values after a restart.
- [ ] Protect native bridge navigation by keeping external links outside the WebView; close the settings menu on Android Back.
- [ ] Add instrumentation checks for provider/model/effort/mode controls and configuration persistence.

## Task 3: Mobile Interface And Message Rendering

**Owner:** Android web UI agent.

**Files:** `for Android/web_companion/index.html`, `static/app.js`, `static/style.css`, local renderer/icon bundle source and generated artifact; `for Android/tests/web_companion.test.cjs`.

- [ ] Reproduce nested runtime event rendering, Markdown absence, task reload, and fake attachments in focused tests.
- [ ] Add the secondary settings menu with model/effort, execution mode, and local theme/text-size/quick-action preferences.
- [ ] Bundle and render sanitized GFM Markdown including lists, tables, links, fenced and inline code, with code copying.
- [ ] Unwrap runtime event data, retain correct streaming history, and add stop, resume, reconnect, draft/session persistence, and conversation export.
- [ ] Upload actual attachment bytes and show removable imported files; submission references real workspace paths.
- [ ] Run JSDOM tests and check layout in a real browser at mobile and desktop sizes.

## Task 4: Integration And Device Delivery

**Owner:** Root agent.

**Files:** Asset loader in `for Android/entrypoint.py`, packaging tests, verification artifacts only where needed.

- [ ] Register and authenticate all new local browser assets; verify archive packaging contains the current code and assets.
- [ ] Independently inspect changes and run the focused combined regression suites.
- [ ] Build final main/test APKs, install on device `326615796159`, and run native instrumentation.
- [ ] Launch the final Activity, verify authenticated health/settings and preserved session access, inspect UI rendering, and remove temporary ADB forwards.
- [ ] Report delivered features, verification evidence, and any actual remaining platform limitation.
