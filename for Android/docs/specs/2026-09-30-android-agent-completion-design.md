# Android Agent Completion Design

The user approved implementation of the recommendations in
`for Android/docs/reviews/ANDROID_AGENT_GITHUB_COMPARISON_2026-09-30.md`.

## Scope

1. Make the embedded APK advertise runnable platform tools, adapt shell and
   speech, expose an actual capability doctor, and persist extension consent.
2. Add Android Accessibility observation, versioned node references, typed
   actions, screenshot support, post-action observations, assertions, and pause.
3. Add 24 reproducible task specifications and evidence-based evaluation
   records, including usage, retries, elapsed time, and human takeover.
4. Add mobile schedules with durable deduplication, native alarm/WorkManager
   wakeup and reboot recovery, voice input, widget/assistant entrypoints, and
   actionable notifications.
5. Pair a trusted desktop/mobile Serve host with a bearer token, inspect remote
   workspaces, hand off prompts/context, and retain an outgoing queue locally.
6. Save reusable app workflows with preconditions and terminal assertions.
   Evaluate optional local inference through existing Ollama/OpenAI-compatible
   engines using explicit device and endpoint diagnostics.

## Architecture

Keep changes under `for Android/` and Android documentation. Preserve the
shared desktop runtime and existing dirty work. The APK keeps a loopback gateway
and Chaquopy in the engine process. Android Accessibility and TTS bridges run
in that same process. Android standard APIs provide system actions; no
competitor source is copied.

Native foreground work is bounded by Android lifecycle constraints. Alarm
receivers use WorkManager and report when user launch is required; reboot must
not unconditionally start a restricted dataSync foreground service.

Secondary menu pages own device permissions, capabilities, extensions,
schedules, paired hosts, outgoing requests, workflows, and evaluation records.
The chat retains task content and its existing execution controls. Voice input
inserts a draft before sending.

## Trust And Persistence

Extension approvals bind to a digest of the exact configuration, require
explicit consent, survive restart, and can be revoked. YOLO does not grant
Android system permissions or authorize arbitrary configured extensions.

Pairing validates a remote identity through an authenticated API. Store tokens
using the APK's Android Keystore bridge. HTTPS is the default; explicit private
LAN endpoints are allowed and visibly identified. No unauthenticated listener
is added. Remote host/workspace paths are visible in the connection page.
Only user-selected context is handed off. Never automatically transfer API keys.

Queue entries persist before dispatch and distinguish pending, sending,
submitted, completed, failed, cancelled, and uncertain. A connection loss after
dispatch is uncertain and requires reconciliation; it must not replay a
potentially executed action. Compatible mobile hosts use idempotency keys.

System actions require current snapshot versions and current display geometry.
Password nodes are redacted. Screenshot unavailability (older API, secure
window, permission denial) is explicit. Execution acknowledgement is separate
from goal verification. Saved workflows recheck declared preconditions when
their task acquires the execution lock and check terminal assertions before
reporting success. Each Android action checks its current snapshot and display
geometry. Saved workflows represent reusable goal prompts, without an encoded
multi-step replay sequence or a separately declared assertion for every step.

## Verification

New behavior gets meaningful regression tests and a failure observed before
implementation. Run Python Android tests, Web UI tests, Gradle build, native
instrumentation, responsive layouts, and actual device capability checks.
Retain APK signature and use `adb install -r`; preserve provider settings and
existing sessions. Record actual task outcomes separately from UI regression
results. Local inference diagnostics do not claim embedded model weights or
unmeasured speed; report hardware and endpoint availability accurately.
