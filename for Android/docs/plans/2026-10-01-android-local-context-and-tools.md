# Android local context and complete tool output

**Goal:** Remove universal 4096-token and 256-token local limits, preserve bounded
execution, and verify the user's actual Chinese HTML-generation failure.

**Architecture:** Keep the existing desktop/shared runner, durable actions and
context compaction. Resolve an Android context plan before constructing the
embedded provider. Native limits follow model metadata, with RAM and optional
actual free swap checked separately. Store configuration in the current provider
preferences and expose it in the Local Models secondary menu. These are runtime
changes to pinned Qwen weights; no weight fine tuning is performed or claimed.

**Constraints:** Preserve user files, histories, settings and credentials; no
uninstall, data clear, commit, push, or connectedDebugAndroidTest. Root owns ADB
and Gradle. Device model calls use an isolated fixture; no implicit cloud fallback.

- [x] Inspect the reported session and native diagnostics. The actual failed
  request had max_output_tokens=256, generated_tokens=256, prompt_tokens=1047,
  context_size=4096 and no engine error. Host HTML tool regression reproduces
  the incomplete-tool error before production changes.
- [ ] Native policy: add model-bounded context planning and supported choices;
  automatic selection uses actual available memory and a reserved margin.
  Extended mode counts actual free swap separately and preserves low-memory
  refusal. Widen prompt, context and output gates consistently across JNI/Kotlin.
- [ ] Provider: construct with configured/automatic context and memory mode;
  use an output reserve proportional to allocated context; preserve explicit
  smaller task budgets and schemas. Treat length truncation explicitly and never
  execute an unfinished proposal. Count every native attempt and usage correctly.
- [ ] Settings/UI: persist strict integer context and memory-mode settings;
  preserve them on model/provider changes; configureRuntime retains its admission
  lease. Show configured, effective and model maximum contexts and memory in the
  secondary Local Models menu. Forward settings through the Python environment.
- [ ] Host regressions: real runner long-file writes, truncated and malformed
  calls, reserved context, explicit small output allowance, cancellation, large
  context token accounting, factory routing, settings persistence and UI wiring.
- [ ] Device acceptance: explicit isolated native test with the exact prompt
  `请你做一个鹈鹕骑单车的动画 html文件`; require an actual complete HTML file and
  observable animation, preserve artifact for visual pelican/bicycle assessment.
- [ ] Cover-install verified APK; check runtime health, resources, user data and
  configuration; restore temporary state and forwards. Record exact results and
  limits, including the absence of comparable mainstream task-success benchmarks.
