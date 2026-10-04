# Android local context and original-task verification — 2026-10-01

**Measured result:** context/settings checks and explicit native allocation probes passed. The original HTML request and the v1/v2/v3 models' natural filesystem tasks failed. V3 native color and complete mobile color admission/recovery fixtures passed. The versioned v3 APK/model have been cover-installed. Final corrective training, its device acceptance, and full user-state preservation remain in progress. These results do not replace the historical alpha.4 verification or the separate model-training evaluation.

## Scope

The change exposes automatic or explicit local context choices (4K, 8K, 16K, 32K, 64K, 128K, 256K) and balanced/extended memory modes in the secondary Local Models menu. Automatic plans use measured available memory and remain bounded to 4K–32K; an explicit request retains its value and must pass both the model limit and memory feasibility checks. Qwen3.5's configured maximum is 262,144 tokens. Balanced mode preserves physical RAM headroom; extended mode also considers measured free swap while retaining physical working-memory reserves.

Inference fixtures use disposable workspaces/databases and existing installed weights. The original-task fixture preserves the exact request:

```text
请你做一个鹈鹕骑单车的动画 html文件
```

Its recorded runs use the real mobile admission path, AgentRunner, and JNI provider, with no injected tool-selection instructions or tool allowlist. The fixture guards the provider's httpx sends. This establishes local JNI inference; production workspace tools can use other network transports, so it is not a guarantee that the whole task ran without network access. Task success is assessed separately.

## Recorded checks

| Check | Measured result | Evidence and limit |
| --- | --- | --- |
| Earlier device policy/settings run | 27 passed; no failures or skips | [device-policy.log](../../output/android-local-context-device-policy.log). Context/memory calculations, persisted settings, and native request validation. |
| Broader device policy/native run | 32 passed; no failures or skips | [final-native.log](../../output/android-local-context-device-final-native.log). Includes overlapping policy/settings checks plus timeout accounting and explicit-context probes; do not add the two runs as unique tests. |
| Host regression | 674 passed, 2 skipped; no failures/errors | [final-host.xml](../../output/android-local-context-final-host.xml). 676 collected cases. This is host coverage, not real-device acceptance of every feature. |
| Selected host regression | 108 passed | [final-selected.xml](../../output/android-local-context-final-selected.xml). Overlaps broader host coverage. |
| Shared integration regression | 201 passed | [final-integration.xml](../../output/android-local-context-final-integration.xml). |
| Web regression | 107 passed; no failures/skips | [final-web.log](../../output/android-local-context-final-web.log). Menu/settings and renderer behavior; this does not verify all screen sizes on hardware. |
| Context-era APK and instrumentation build | Build succeeded | [final-build.log](../../output/android-local-context-final-build.log), [instrumentation-build.log](../../output/android-local-context-final-instrumentation-build.log). These are historical context builds, not the final v2 build gate. |

The native timeout fixture passed with a 1,000 ms requested deadline and a measured 1,178 ms elapsed time. Its current request retained `finish_reason=timeout`, zero generated tokens, and current-request metrics rather than stale successful usage: [timeout-device-report.json](../../output/android-local-context-timeout-device-report.json).

## Explicit context allocation

The real Qwen3.5 0.8B Q4_K_M device probe used extended memory mode and recorded:

| Requested / actual native context | Prompt tokens | Output tokens | Output | Elapsed |
| --- | ---: | ---: | --- | ---: |
| 8,192 / 8,192 | 16 | 1 | `OK` | 1,728 ms |
| 32,768 / 32,768 | 16 | 1 | `OK` | 1,872 ms |
| 262,144 / 262,144 | 16 | 1 | `OK` | 6,377 ms |

[device-probe.json](../../output/android-local-context-device-probe.json) records `success=true`, `settings_preserved=true`, and **`full_length_input_tested=false`**. At the 256K probe it measured 2,739,871,744 bytes available RAM, 5,186,482,176 bytes free swap, and a 4,696,927,328-byte required-memory estimate.

These results establish allocation and short-prompt generation at all three requested context sizes on this phone. They do not establish processing a full 256K input, useful retrieval throughout that input, long-session compaction, or sustained performance under memory pressure. Measured free swap in this run also does not establish that every Android device's advertised memory expansion is available to the process.

## Original HTML request

| Run | Outcome | Evidence |
| --- | --- | --- |
| Base model, earlier 32K run | Failed at the 180,000 ms generation deadline; no HTML file | [html-progress.json](../../output/android-local-context-html-progress.json), [html-core-device.log](../../output/android-local-context-html-core-device.log). |
| Base model, final context-era 32K run | Failed: incomplete tool call; no generated files | [html-final-progress.json](../../output/android-local-context-html-final-progress.json), [html-core-final-device.log](../../output/android-local-context-html-core-final-device.log). |
| v1 model, 32K run | Failed: incomplete tool call; no generated files | [v1-device-html.json](../../output/qwen-trained-mtp-device-html.json), [v1-device-html.log](../../output/qwen-trained-mtp-device-html.log). |

The final context-era base call allowed 4,096 output tokens and a 674,400 ms deadline. It stopped after 886 generated tokens with 904 prompt tokens in 85,721 ms, leaving an incomplete tool envelope. This failure was not caused by reaching the advertised 4,096-token output allowance. The v1 run also used 32K/4,096 and stopped with invalid/incomplete calls; its overall elapsed time was approximately 141.4 seconds.

All three reports retain `success=false`, `automated_success=false`, `core_success=false`, and `manual_review_status=pending`. No browser animation or recognizable pelican/bicycle subject was accepted because no valid HTML artifact reached that gate. The browser fixture requires natural bitmap changes and separate subject review; source assertions are not evidence of successful generated animation. A new-build 256-token-cap comparison is not established by the evidence indexed here.

## v1 natural tool tasks and vision

The v1 natural-language tool holdout completed **0/3 scenarios**, despite real JNI inference, a 32K context, and 4,096-token output allowance. Per-scenario limits were six model calls, eight provider attempts, eight tool calls, and 420 seconds. No tool-selection hint was added to the user requests.

| Scenario | Measured failure |
| --- | --- |
| Copy existing file | Model attempted `write_file` without first reading; provider rejected arguments that did not match the advertised schema. No tool settled. |
| Edit existing file | Repeated `write_file` six times without reading the source, then exhausted the model-call budget. Content preservation and SHA-256 CAS acceptance failed. |
| Create directory and save | Model called an inactive/unadvertised tool; provider rejected the call. |

Evidence: [v1-device-tool-holdout.json](../../output/qwen-trained-mtp-device-tool-holdout.json), [v1-device-tool-holdout.log](../../output/qwen-trained-mtp-device-tool-holdout.log). The base comparison also completed 0/3: [base-device-tool-holdout.json](../../output/qwen-base-device-tool-holdout.json). Successful parsing or native generation alone is insufficient for natural task acceptance.

The earlier base-model mobile vision test failed its strict instruction gate (one instrumentation test failed). Both synthetic red/blue images reached the core as immutable attachments and survived database recovery. The model identified both colors, but answered with sentences rather than the required exact color word; each scenario has `instruction_followed=false` and `verified_result=false`. Evidence: [vision-device-report.json](../../output/android-local-context-vision-device-report.json), [vision-device.log](../../output/android-local-context-vision-device.log).

The later **v1 native vision fixture passed one test and both color scenarios (2/2)**. It returned `red` and `blue` using the matching installed 0.8B vision projector, 4,096 actual context tokens, 97 prompt tokens, 64 image tokens, and one generated token per image. Evidence: [v1-vision-grounding.json](../../output/qwen-trained-mtp-device-vision-grounding.json), [v1-vision-grounding.log](../../output/qwen-trained-mtp-device-vision-grounding.log). This is a small native image-grounding fixture; it does not replace the full mobile vision admission/recovery test or establish general visual-agent competence.

## Build identity and state preservation

[built-artifact.json](../../output/android-local-context-built-artifact.json) records the historical context-era APK `AgentWorkspaceMobile-0.1.0-alpha.4-context-debug.apk`, size 57,003,468 bytes, SHA-256 `a10bcb58f3447d0571c7740a1b7753aa92a3cb80049f6a9c45ec21a5c003d01d`, and matching packaged source/web counts of 267/9. This identifies that recorded artifact; it does not identify the latest APK or establish final v2 installed asset parity.

The explicit-context probe records restored settings. The base/v1 natural holdouts and v1 HTML report each record `provider_settings_unchanged=true`. Those checks cover the tested provider-settings snapshots. They do not prove preservation of every existing session/event, credential, draft, notification, or system setting. [before.json](../../output/android-local-context-before.json) is a prior state snapshot, not a complete final before/after acceptance result.

## Subsequent real training and v3 installation

The v3 language adapter was actually trained for 100 optimizer updates (400
examples); development selection chose step 60, reflecting 240 examples. Its
strictly verified Q4_K_M artifact is 541,903,296 bytes, SHA-256
`18aa0364bb3c936096ecd0f2de3351b8115de6588cb7c6343594f903106c4471`.
The v3 APK build succeeded and `adb install -r` succeeded for main/test APKs;
main APK SHA-256 is
`b9a2533c1adb0ce264e6dec27b1a39fc94fec23d88a68f0d8b3f192874d445b8`.
The explicit private model import passed one instrumentation test with the
expected model bytes/digest and unchanged provider settings:
[deployment.json](../../output/qwen3.5-0.8b-agent-v3-q4-k-m-deployment.json),
[import.json](../../output/qwen-v3-device-import.json).

The unchanged natural phone holdout still completed **0/3** with a 32K context:
new-file source-digest CAS and omitted trailing newline, imperfect edit/retry
behavior, and an inactive directory call. It preserved provider settings:
[natural.json](../../output/qwen-v3-device-natural-holdout.json).
V3 native red/blue grounding passed 2/2 and full mobile image admission, exact
color answers, immutable attachment and database recovery passed 2/2:
[native.json](../../output/qwen-v3-device-vision.json),
[mobile.json](../../output/qwen-v3-device-vision-agent.json).
These small color fixtures do not establish general visual-agent competence.

Fresh frozen comparisons and the math preservation failure are documented in
[the training report](ANDROID_QWEN_TOOL_FINETUNING_2026-10-01.md). The offline
96-record GGUF comparison's fixed 4096 evaluation context is a controlled short
sample benchmark, not a new application cap. The phone's unchanged automatic
extended mode resolved to 32768 for the natural tasks. The explicit 256K probe
above still establishes allocation/short generation only.

Corrective v4 data preparation is in progress. Final installed-asset parity,
the latest APK/menu acceptance, before/after preservation and restoration of
temporary system settings must be added after that work finishes.

V3's original HTML fixture also failed, creating no files after a 720-second
wait. It executed a real network `web_fetch` (HTTP 200, truncated 65,536-byte
page), then spent about 598 seconds pre-filling a 22,106-token native prompt
without generating a first token before cancellation. This does not establish
useful long-task performance. The original report's empty httpx call list does
not imply that its web tool was offline:
[HTML.json](../../output/qwen-v3-device-html.json),
[transport-review.json](../../output/qwen-v3-html-transport-independent-review.json).

The V3 menu/Markdown/animation/Unicode run passed 13 instrumentation tests with
no failures or skips; a real menu switch selected the verified experimental
model and restored all configuration. Full post-v3 comparison preserved four
sessions, 1090 original events, preferences and encrypted credentials and matched
installed APK, 268 Python resources and nine Web assets:
[menu.json](../../output/qwen-v3-device-menu.json),
[preservation.json](../../output/android-qwen-v3-state-preservation.json).
This is the post-v3 snapshot; temporary stay-awake remains active until the
subsequent work ends, and the final post-v4 snapshot is still required.
