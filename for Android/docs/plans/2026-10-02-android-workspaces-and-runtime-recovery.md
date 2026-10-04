# Android Workspaces and Runtime Recovery

**Goal:** Recover task admission after model maintenance, fix local model controls, and let users run conversations across chosen folders concurrently.

**Architecture:** A durable workspace catalog maps canonical directories to IDs. Sessions keep their existing workspace path and gain an API workspace ID. A mobile controller router creates an independent runtime and approval broker per conversation, sharing the database writer lease. The WebView switches its visible task monitor without stopping background work.

**Constraints:** Preserve existing sessions, provider settings, artifacts, and unrelated worktree edits. Do not change the frozen Qwen V5 r3 training source, data, steps, checkpoints, or acceptance thresholds. Do not start a new training process until the application changes are tested and the running attempt has been independently audited.

## Work

- [x] Reproduce benchmark lease expiry and fix restart recovery without bypassing genuine provider changes.
- [x] Correct local model recommendation identity, unavailable control reasons, and summary spacing.
- [x] Add catalog persistence, workspace-scoped file/usage routes, session membership, and controller routing.
- [x] Bind per-conversation runtimes to a shared writer lease with independent events and approvals.
- [x] Add workspaces to the secondary menu, folder picker, session filtering, independent drafts, and switching during active tasks.
- [x] Scope generated-file open/share/save to the originating workspace.
- [x] Test separate workspace tasks, multiple conversations, approval routing, cancellation, restart recovery, and file isolation.
- [x] Build matching APKs, install with `adb install -r`, and run focused device tests and layout checks.
- [ ] Deferred per the user's latest instruction: train new weights after delivering the application. The existing V5 attempt was audited and is not qualified for deployment; its heartbeat is paused.

Delivered `output/AgentWorkspaceMobile-0.1.0-alpha.5.apk`. See `output/android-alpha5-acceptance-20261002.md` for exact test stages, source binding, device evidence and remaining limits. The final review also corrected repeated cancellation of editor saves; affected regression suites and installed workspace/startup checks were rerun afterward.

## Folder Access

App-private folders work directly. A system directory picker grants consent for local storage folders. Python and command tools require Android all-files access for shared storage; the menu exposes its actual status and the system permission screen. Nonlocal document providers are rejected because they do not expose a filesystem directory.

## Verification

Run Python mobile tests and Node companion tests without loading a model on the desktop GPU. Use native instrumentation for benchmark recovery, folder path validation, task routing, generated files, and session preservation. Exercise phone, tablet, and foldable proportions and large text with browser screenshots. Check actual model evaluation separately from code tests before any weight registration or deployment.
