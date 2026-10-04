# Android Public Alpha Completion Implementation Plan

> For agentic workers: use parallel implementation with independent review and
> verification-before-completion. The user has authorized execution in this chat.

**Goal:** Close the identified Android gaps with actual local Qwen inference,
downloadable models, durable replay, usable tooling and public build preparation.

**Architecture:** Extend Android adapters and native bridges around the existing
shared runtime; keep cloud provider/core behavior intact and management in child pages.

**Tech Stack:** Python 3.12, Kotlin, llama.cpp/JNI/CMake/NDK, SQLite, HTTP Range,
Gradle 8.11.1, Android foreground services/WorkManager.

## Global Constraints

- Preserve unrelated dirty changes, all user data and the installed signing identity.
- No commits, public upload, uninstall, app-data clear or connectedDebugAndroidTest.
- Cover-install with adb install -r; instrumentation runs directly through am instrument.
- Explicitly exclude PrivateProviderRecoveryTest from routine native test runs.
- No secure-keyguard bypass, unknown-action retry or implicit cloud fallback.
- Third-party dependencies/models are pinned with source/size/digest and notices.

## Task 1: Embedded Qwen Engine And Provider

Owner: android_qwen_native_engine.
Files: new native/localmodels code, CMake, Android-only local provider adapter,
factory installation in chaquopy_runtime.py, focused provider/native tests.

- [x] Verify small Qwen sources, official base models and publisher-specific GGUF artifacts; report pinned metadata.
- [x] Write failing adapter tests for prompt/tool-call parsing, bounds and cancellation.
- [x] Implement pinned llama.cpp JNI, bounded generation, unload and cancellation.
- [x] Implement local provider for the reserved embedded-qwen base URL.
- [x] Verify native compilation and real 0.8B/2B generation on the phone.

## Task 2: Durable Workflow Replay And Measured Evaluations

Owner: android_workflow_replay.
Files: mobile_workflows.py, new mobile_workflow_replay.py, focused tests and
evaluation execution/export helpers. Root owns management dispatch and Web UI.

- [x] Add failing tests for semantic selectors, steps, checkpoints and ambiguous actions.
- [x] Implement validated steps, fresh-reference dispatch, per-step assertions and records.
- [x] Implement reviewed action import, bounded export/import and explicit resume semantics.
- [x] Add fixed-metadata evaluation export/runner; keep catalog and measured runs distinct.
- [x] Run full workflow/evaluation regression subset and report interfaces to root.

## Task 3: Optional Mobile Toolchain And Recovery

Owner: android_toolchain_recovery.
Files: new toolchain manager/adapters/native bridges, native service/scheduling
recovery files and focused tests. Root owns Gradle/Manifest final integration.

- [x] Verify Android-compatible launcher/rootfs source and execution constraints.
- [x] Add failing install/integrity/workspace/cancellation tests; implement usable tooling.
- [x] Add real Git/shell/Python/Node probes and discover only installed working tools.
- [x] Improve service/schedule recovery and battery exemption/state diagnostics.
- [x] Run focused regressions and provide runtime/probe/UI interfaces to root.

## Task 4: Model Manager And Secondary Menu Integration

Owner: root.
Files: mobile_local_models.py/new model manager/catalog, mobile_management.py,
web_companion/index.html/static/management.js/static/style.css and tests.

- [x] Verify and pin model catalog metadata independently.
- [x] Write failing download tests: Range resume, ignored Range, cancellation,
  hash mismatch, origin/content drift, disk limits and atomic install.
- [x] Implement download/progress/remove/select/unload routes and persistent state.
- [x] Add model, replay, toolchain and recovery child-page controls with clear statuses.
- [x] Preserve existing model/provider settings and UI state across updates.

## Task 5: Reproducible Build And Public Documentation

Owner: root, delegate when an implementation slot becomes free.
Files: Gradle wrapper/config, Android CI/release scripts, README/onboarding,
Android notices/contribution guidance and .gitignore.

- [x] Restore checksummed wrapper and align Gradle/JDK/SDK/NDK versions.
- [x] Add Android CI, artifact checks and optional signed release build.
- [x] Correct stale architecture/background claims and document actual installation.
- [x] Exclude device backups/private state from public source artifacts.
- [ ] Verify a clean source export builds without machine-specific paths.

## Task 6: Final Integration, Review And Device Delivery

Owner: root with independent reviewers.

- [x] Run Android Python/Web/native subsets and representative layout/font/motion checks.
- [x] Perform real smallest-Qwen offline generation and actual installed toolchain probes.
- [x] Run deterministic workflow/error/recovery scenarios and record measured outcomes.
- [ ] Cover-install final production/test APKs and verify served source/data preservation.
- [ ] Restore all temporary OS settings and ADB forwards; record actual limitations.

## Task 7: Local And Cloud Image Input (User Extension, 2026-10-01)

Owners: root (projection artifacts/secondary menu/attachment Web payload),
android_qwen_native_engine (mtmd/JNI/local provider), android_workflow_replay
(mobile durable image references/shared cloud provider delivery). The native
audit retains exclusive ADB/Gradle ownership. No new approval is required.

- [x] Pin compatible Qwen3.5 visual projectors with public source, size and SHA256.
- [x] Add resumable visual-component downloads and honest installed capability status.
- [x] Deliver owned image bytes through queued/retried/recovered mobile tasks.
- [x] Verify actual image payloads for cloud provider protocols and reject bad references.
- [x] Integrate mtmd CPU image encoding, visual context bounds, memory and cancellation.
- [ ] Test image results on the phone, then rebuild/export/install the final source.
- [x] Verify durable request IDs prevent duplicate execution after response loss/reload.
- [x] Reject missing/corrupt durable user images before invoking a model; preserve latest repeated images and tool images during compaction.
- [x] Verify Android screenshot artifacts reach local/cloud model input immediately and after history recovery.
- [x] Restore uncertain submissions across response loss and repeated reloads with persistent recovery ownership; preserve newer drafts and clear only unchanged admitted input.

Current evidence and remaining deployment gates are tracked in
`for Android/docs/reviews/ANDROID_ALPHA4_VERIFICATION_2026-10-01.md`.
