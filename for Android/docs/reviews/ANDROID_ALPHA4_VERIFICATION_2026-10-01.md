# Android alpha.4 integration and image verification

Status: final phone deployment, data preservation, packaged-source verification
and independent clean source build are complete. Local 0.8B and the selected
cloud model passed actual image recognition. 2B vision on this phone remains
unverified, as described below.

The update preserves the installed application identity, provider credentials,
session history and drafts. It adds optional Qwen3.5 visual components, durable
image task input, shared cloud image protocols, and bounded offline CPU image
encoding. Management, model downloads and usage stay in secondary menus.

## Host evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Complete mobile Web regression after image input, durable request-ID and pending-draft recovery fixes | 104 passed, 0 skipped | `output/android-vision-web-final.log` |
| Download manager including projector compatibility and integrity | 22 passed | `output/android-vision-manager-final.log` |
| Generic image pipeline, actual provider HTTP payloads, ownership and recovery | 43 passed, 1 Windows symlink privilege skip, including missing/corrupt durable input | Independent review regression; final full-suite evidence below |
| Shared runner image compaction, recovery and context manifests | 39 passed | `output/shared-image-compaction-regression.xml` |
| Android local provider and image regression after shared runner fixes | 56 passed | `output/qwen-local-image-regression.xml` |
| Real Agent Android screenshot input: cloud/local, current/next/reopened SQLite turns, combined regressions | 64 passed; all six screenshot scenarios reproduced missing images before the fix | `output/android-screenshot-images-green.xml` |
| Complete Android Python regression after all Python/JNI/image changes | 483 passed, 2 Windows symlink privilege skips, 344.38 seconds | `output/android-alpha4-multimodal-frozen-final-python.log` |
| Final packaging/source parity regressions after the last export/Gradle changes | 13 passed, including complete runtime/Web byte parity, legacy-rootfs preservation and Termux placeholder rejection | `output/android-alpha4-packaging-final-green.log` |
| Independent build from the final 421-file source export in a fresh directory | Exit 0; 53 of 53 Gradle tasks executed, 221.718 seconds; packaged runtime/Web source sets and bytes match the installed APK | `output/android-alpha4-clean-build-verification.json`, `output/android-alpha4-final-apk-comparison.json` |

The cloud payload tests use real provider adapters with a mock HTTP transport.
They check the exact image bytes for OpenAI Chat Completions, OpenAI Responses,
Anthropic, Gemini and Ollama; they are not live service acceptance.
The Python backend and native image engine remain at the tested versions.
Subsequent changes cover Web draft recovery and build/export packaging, with
their final regression evidence recorded above.

## Phone evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Qwen3.5 2B Q4, 512 context native generation | 3 passed, 2.369 generated tokens/s | `output/android-alpha4-qwen2b-512-inference-smoke.json` |
| Qwen3.5 2B Q4, default 4096 context complete Agent | Strict greeting and actual tool task passed, 5 JNI calls, zero model HTTP calls | `output/android-alpha4-qwen2b-4096-agent-inference-report.json` |
| 2B actual CPU prompt cancellation | Settled in 70 ms after cancellation | `output/android-alpha4-qwen2b-active-cancel-report.json` |
| Optional development toolchain | Actual shell, Git, Python, Node, npm and Pyright passed | `output/android-alpha4-toolchain-final-report.json` |
| 0.8B visual component installation | Device size and SHA256 match pinned artifact | `output/android-alpha4-vision-projection-install-report.json` |
| JNI and complete-Agent image regressions on the diagnostic image APK | 7 passed, including actual colors, active image cancellation and missing 2B projector rejection | `output/android-alpha4-vision-native.log` |
| Local 0.8B image Agent and immutable input recovery | Strict red/blue recognition passed in 10.837/9.733 seconds; SQLite recovery passed, zero model HTTP calls | `output/android-alpha4-vision-agent-inference-report.json` |
| 0.8B actual CPU image-encoder cancellation | Settled in 97 ms after cancellation | `output/android-alpha4-vision-cancel-report.json` |
| Selected cloud model's actual geometric image recognition | 1 passed, strict red-circle/blue-square JSON; deepseek-flash, 1 model call/attempt, 1.646-second Agent run | `output/android-alpha4-cloud-vision-explicit-report.json` |
| Text JNI with new mtmd engine, 2B at 512 context | 3 passed, 9 generated tokens, no image/projector, 12.811-second generation | `output/android-alpha4-vision-qwen2b-512-inference-report.json` |
| Native memory policy and provider coordinator with image engine | 18 passed | `output/android-alpha4-vision-memory-provider-native.log` |
| Complete routine native regression, including system actions and real speech | 73 passed, 0 skipped, 42.7 seconds; all 37 native/Dex entries match the final installed APK byte for byte | `output/android-alpha4-final-routine-result.json`, `output/android-alpha4-final-web-preservation.json` |
| Installed native UI/startup checks after final Web draft and packaging fixes | 9 passed, 0 skipped, 10.029 seconds; final delivery retains the same tested main binary | `output/android-alpha4-final-packaging-ui-native.log` |

The default 2B Agent run took 291.524 seconds for two scenarios; the tool scenario
took about 160 seconds. Sampled PSS reached 1,535,929 kB. These observations prove
the measured cases can run, and do not establish arbitrary task reliability.

The 0.8B visual run sampled aggregate PSS up to 1,036,592 kB and RSS up to
1,114,164 kB, with a minimum sampled MemAvailable of 1,690,284 kB across 17
observations. These are sampled values, not continuous peak measurements.
The real model recognition tests ran on the diagnostic image APK. Final delivery
also includes Web request-ID, pending-draft and durable/shared image recovery fixes;
the final artifact/source checks below establish that packaged implementation.

The Web tests prove a lost task response, retries and reload retain the same
request ID and create one server execution. Confirmed failed tasks receive a
new ID for an explicit retry. Failure to save the pending request prevents the
POST and preserves the draft. Durable image corruption or loss fails before
calling a model; latest repeated images and tool screenshots survive context
compaction, or cause an explicit context-budget error if their bytes cannot fit.

Pending POST, response loss and one or repeated reloads restore the original
text/images and retain request identity. Recovery ownership is persisted with
the draft and checked against the pending ID, text and normalized attachments.
History admission clears only unchanged recovered input. Existing new drafts
and edits made while history loads remain intact. These boundary cases were
reproduced before their fixes and pass in the complete 104-test Web regression.

Android screenshot tools now forward their immutable recorded PNG bytes to the
current tool message, subsequent turns and reopened SQLite history. This is
verified with actual Agent execution and provider adapters (mock cloud HTTP and
fake local JNI), separately from the real JNI and cloud model recognition above.

The previous Apply action failure was traced to a public test fixture crash:
its separate test APK lacked `kotlin.jvm.internal.Intrinsics` in the click
listener. The fixture now uses only Java and Android framework classes, without
changing production action safety or weakening verified-goal assertions. All
four system-bridge device tests now pass, including actual Apply dispatch with
strict goal verification and protected/offscreen refusal. Root-cause and
repair evidence are in `output/android-alpha4-system-bridge-live-diagnostic.json`
and `output/android-alpha4-system-bridge-repair-verification.json`.

The earlier 54-test run had a separate intermittent OEM TTS synthesis failure.
Independent synthesis, a strong speak check and the later complete 73-test
routine run passed. Those observations do not certify every voice/locale or
prove an OEM speech engine can never fail; the historical failure remains in
`output/android-alpha4-text-full-native-final.log`.

## Limits

- Inference uses CPU, with a maximum 4096-token context. No GPU acceleration is claimed.
- PNG, JPEG, WebP and GIF are supported inputs. Local GIF uses the first frame.
  Mobile uploads allow four files of at most 4 MiB each. Unsupported or damaged
  images fail explicitly instead of becoming text file prompts.
- The local four-image inference limit includes history and tool screenshots.
  A new session is needed once the retained context exceeds that limit.
- 2B text success does not certify 2B vision on this device: visual memory also
  includes the entire projector and 256 MiB extra compute reserve.
- A cloud model or third-party endpoint must actually support its image protocol.
  Rejection remains an error; no implicit cloud/model fallback is used.
- OEM scheduling, secure lock screens, speech engines, thermal pressure and
  memory pressure remain device conditions that require separate evidence.

## Final deployment

The final APK was cover-installed with `adb install -r` on ZTE A2022P,
Android 12/API 31, serial `326615796159`. Both final installation commands
returned `Success`, and the normal activity launch returned `Status: ok`.
The delivered artifact hash exactly matches the installed APK hash.
Evidence: `output/android-alpha4-final-ultimate-install.log`,
`output/android-alpha4-final-ultimate-app-launch.log`, and
`output/android-alpha4-final-delivery-and-restoration.json`.

The final application build passed installation and all data checks: four
original sessions and all 1,034 original events are unchanged (1,042 current
events); provider and encrypted credential file hashes are unchanged. The
WebView's existing session selection and draft-storage hashes also match. Its
draft key was absent before and after this update, so this is not a claim that
a nonempty real user draft was present; the pending-draft behavior is verified
by the Web regressions above.

Cold model-menu integrity checks exceeded the deployment script's 15-second
read timeout on the first request. The route runs full SHA verification in a
worker thread; the Web client has no corresponding 15-second abort. A fresh
process measurement on the final APK returned all eight model and two vision
component records after 19.656 seconds, within the server's 30-second operation
limit. All 24 concurrent health requests succeeded (maximum measured 32 ms);
the warm model snapshot took 0.125 seconds. Full model-file integrity remains
required. The original timeout evidence is retained, with the successful cold
measurement in `output/android-alpha4-final-cold-model-diagnostics.json`.
This measured timing is not a guarantee for slower or heavily loaded devices.

APK comparison found two vendor-build `.mjs` source files absent from the export
allowlist, plus an old Termux bootstrap archive left in the original assets
directory. The exporter now includes `.mjs` and AGP excludes the exact old
bootstrap filename from the Chaquopy APK, preserving the original source asset
and all ten default Android ignored-asset patterns.
The original rebuilt APK now has 267 complete runtime-source entries and nine
Web assets, all matching the workspace byte for byte. This packaging follow-up
made no change to model credentials, the image engine, provider protocols or
action safety.
The old bootstrap is a 1,363-byte placeholder, not a 5 MB runtime. Comparison
found its compressed payload and both scripts total only 2,420 bytes; the
approximately 4.8 MB APK size difference is almost entirely unused gaps from
incremental ZIP updates. Both compared signing blocks are 4,096 bytes.
The original source/runtime files present in both builds already match exactly.

The final independent build used the exported source in a fresh directory,
without copying original-project build outputs. Its 421 source files and the
workspace's corresponding source files did not drift after the build. Both APKs
contain the same 238 ZIP entry names, 56 asset entry names and 26 native library
names. Their 267 runtime sources, nine Web assets, toolchain corresponding
sources and license bytes match exactly. Native/Dex and generated package bytes
can differ between the independent build and the installed build; no claim of
bit-identical APK reproducibility or device testing of the independent APK is
made. The installed, tested APK is the canonical delivery.

Temporary device state has been restored: plugged-in stay-on is `0`,
accessibility services are the original `null` with accessibility enabled `0`,
automation pause and takeover flags are false, the task's `tcp:18086` forwarding
is removed, `tcp:18087` is absent, and other forwards are unchanged. The app and
engine were left normally running. All build, instrumentation and diagnostic
execution sessions have completed.

## Final artifacts

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `artifacts/AgentWorkspaceMobile-0.1.0-alpha.4-debug.apk` (installed and tested) | 54,036,831 | `b0186452c47cf19c301a00d747d8e921bc2a6de8f6c05df39dbd5edda5bfcac6` |
| `artifacts/AgentWorkspaceMobile-0.1.0-alpha.4-clean-build.apk` (independent build verification) | 49,223,789 | `c088b171a83dfd499d1f0a219add9f03f4da6a8f33c14810ed2a124094d4c83b` |
| `artifacts/android-alpha4-source.zip` (421 source files) | 1,595,269 | `c9b7d6b38fa75426b891aaf97b4a64559069b6616ff882a670d04900e16ee717` |

The deployment/runtime checks are recorded in
`output/android-alpha4-final-ultimate-deployment-run.log`; settings and draft
preservation are recorded in `output/android-alpha4-final-web-preservation.json`.
Artifact identity and device restoration are recorded in
`output/android-alpha4-final-delivery-and-restoration.json`.

No public release, commit, uninstall or application data clear is part of this task.
