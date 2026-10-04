# Android Agent Completion Implementation Plan

> Use subagent-driven-development for independent implementation and review.

**Goal:** Deliver the approved Android recommendations as usable secondary
menus and platform behavior, verify them, and update the connected phone.

**Architecture:** Android-only adapters extend the existing shared runtime.
The authenticated gateway coordinates durable state and native bridges.

**Tech Stack:** Python 3.12, SQLite events, httpx, Kotlin/Android API 26-35,
AccessibilityService, TTS, AlarmManager, WorkManager, trusted WebView.

## Constraints

- Preserve existing data, credentials, certificate and unrelated dirty files.
- New management controls belong in secondary menus.
- No shared desktop/source edits or competitor source copying.
- Tests first for new execution/persistence/security behavior.
- No commits requested. Deploy only using `adb install -r`.

## Task 1: APK Capabilities And Extensions

Owner: android_capabilities_extensions_impl.
Files: `for Android/android_adapter/chaquopy_runtime.py`, new capabilities and
embedded tools, `entrypoint.py`, `mobile_extensions.py`, focused tests.
Native interface: `capabilities.AndroidTextToSpeech.initialize(Context)`.
Runtime interface: `runtime.mobile_extension_consents.snapshot()` and
`decide(request_id, allowed, expected_digest)` / `revoke(...)`.

- [x] Reproduce unavailable Windows terminal/TTS and missing extension consent.
- [x] Adapt or hide tools; doctor reports actual prerequisites.
- [x] Persist digest-bound approvals; start with pending extensions disabled.
- [x] Run focused tests and inspect changes.

## Task 2: Android Observation And Actions

Owner: android_system_bridge_impl.
Files: new `automation/` Kotlin bridge/service, accessibility XML,
`android_adapter/android_system.py`, Python and native tests.
Interfaces: `AndroidSystemBridge.initialize(Context)`, `status(): String`,
`execute(requestJson: String): String`, `register_android_system_tools(registry)`.

- [x] Test stale snapshot rejection, typed arguments, refresh and assertions.
- [x] Implement bounded/redacted UI tree, screenshots and system actions.
- [x] Integrate engine process service and native permission/pause controls.
- [ ] Verify actual observations and harmless actions on the phone.
  The matcher/control checks and actual offscreen observation test passed.
  The actual action sequence initially returned a definite unexecuted stale
  snapshot rejection. A test-only bounded refresh/retry is installed; its rerun
  remains pending the user's unlock of the secure keyguard.

## Task 3: Schedules And Native Entry Points

Owner: android_scheduling_native_impl.
Files: `mobile_schedules.py`, native scheduling/voice/widget modules,
`TermuxDaemonService.kt`, `TaskNotifications.kt`, focused tests.
Interface: `MobileScheduleManager(controller, path)` exposes CRUD and
`dispatch_due`; native scheduler mirrors public due times using AlarmManager.

- [x] Test due dispatch deduplication, rejected unattended autonomy and recovery.
- [x] Implement persisted schedule management and WorkManager wake fallback.
- [x] Add voice drafts, widget/assistant launches and notification actions.
- [x] Integrate native manifest/dependency changes and verify device behavior.
  Manifest/dependency build, native schedule, notification polling/action and
  cold/warm task/schedule notification session navigation tests passed. Reboot
  and OEM background-freezing behavior are not certified.

## Task 4: Pairing, Handoff And Offline Delivery

Owner: root.
Files: `mobile_connections.py`, `mobile_delivery.py`, gateway routes,
focused Python tests and secondary menu UI.

- [x] Test endpoint validation, token redaction, persistence and duplicate keys.
- [x] Pair with authenticated Serve API, store tokens securely and expose paths.
- [x] Persist outgoing jobs before sending; reconcile ambiguous outcomes.
- [x] Add remote sessions/context handoff and queue controls.

## Task 5: Workflows, Evaluations And Local Model Diagnostics

Owner: root.
Files: `mobile_workflows.py`, `mobile_evaluation.py`, task specifications,
gateway routes, focused tests and secondary menu UI.

- [x] Test workflow preconditions/assertions and independent goal outcomes.
- [x] Add saved workflows and 24 reusable evaluation cases with fixed metadata.
- [x] Record task metrics separately from UI/contract test results.
- [x] Add actual hardware and optional local inference endpoint diagnostics.

## Task 6: Integration And Delivery

Owner: root, with independent integration review after implementation.
Files: Android Manifest, Gradle configuration, NativeJsBridge, WebUiActivity,
Web companion pages/styles, package assets and verification report.

- [x] Add all secondary pages, accessible labels and responsive constraints.
- [x] Run Android Python and Web UI tests, resolve failures, build APK.
- [ ] Run native instrumentation and responsive viewport/font checks.
  Python: 268 passed. Web: 82 passed. Viewport/motion: 172 states plus 3
  overflow retests; icon audit: 18 views and 1,552 controls; final guarded-height
  layout audit: 24 states. Device tests: 31 independent and 13 of 14 distinct
  visible methods passed, including real shell output/timeout/registry
  containment, native speech, restart, sharing and notification navigation.
  The Path filesystem-anchor bug found during deployment is fixed in both
  adapters. The phone's WebView 99 exposed unsupported `dvh` menu heights, fixed
  with `vh` bases and guarded `dvh` overrides. Its final menu-height assertion
  and corrected actual-operation test still await an unlocked device rerun.
- [x] Review tool, authorization, scheduling and cross-device behavior.
- [x] Preserve device data; install update and verify actual APK paths.
  Cover-install only. Installed APK hash and all 255 source / 9 Web assets
  match the final build. A fresh complete live check after reconnection verified
  served resources, all 4 original session IDs and 1,034 unchanged original
  events. DeepSeek Flash/auto and full_access remain selected.
- [x] Record results and any platform limits without overstating coverage.
  Final installed SHA256 and pending unlock-dependent verification are recorded
  in `for Android/docs/reviews/ANDROID_COMPLETION_VERIFICATION_2026-09-30.md`.
