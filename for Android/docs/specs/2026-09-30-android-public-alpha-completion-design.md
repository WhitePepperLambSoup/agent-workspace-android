# Android Public Alpha And Local Qwen Design

The user has authorized implementing all gaps identified in the Android comparison,
including selectable downloadable small Qwen models. This extends the existing
Android completion work rather than replacing it. No commits or public publication
are requested. Existing sessions, credentials, drafts and signing identity must be
preserved. All management remains in secondary menus.

## Local Inference And Model Distribution

Embed a pinned, MIT-licensed llama.cpp CPU backend through Android JNI. Prefer
verified official Qwen GGUF repositories for small instruct models. The catalog
records repository revision, exact file, SHA256, size, license, source page and
minimum/recommended memory. Start with verified 0.6B/1.7B-class Qwen models;
additional newer small models enter the catalog only if both source metadata and
the pinned engine support are verified. Weights are optional downloads, not APK
assets. An unavailable or incompatible model must never be labeled installed.

A persistent Python model manager owns resumable Range downloads, cancellation,
retry, integrity validation, atomic installation and removal. Partial files stay
separate from usable weights. Origin changes invalidate resume unless the same
pinned content is proven. The model page provides official source links, progress,
storage/memory checks, download/cancel/remove and explicit select/unload controls.
The smallest model is used for a real offline generation smoke test on the phone.

The native bridge has initialize(Context), status(): String, generate(String):
String, cancel(), and unload(). Requests specify a verified model path, bounded
context/output/thread settings, and chat content. The Android-only provider factory
recognizes the reserved base URL http://127.0.0.1:8080/embedded-qwen/v1 and returns
a JNI provider without making any HTTP request. Cloud credentials remain in their
existing per-origin Keystore entries. Tool calls use the Qwen chat format and are
validated before entering the existing approval/tool runner. No silent cloud fallback.

## Reusable Automation

Keep existing saved-goal workflows. Add versioned declarative steps with semantic
selectors, fresh observations, per-step preconditions and postconditions, bounded
timeouts and durable execution records. Never replay an unknown/executed action
after interruption. Resume verifies the last confirmed state, requires explicit
user action, and uses the task approval and cancellation policy. Record imports
capture reviewed executed actions, redact sensitive inputs, and never save stale
node references or plaintext protected fields. Export/import is bounded JSON.

## Toolchain And Background Behavior

Provide an optional verified Android-compatible toolchain with Git, shell, Python
and Node/language-server prerequisites rather than advertising desktop executables
as usable. Evaluate PRoot with official runtime artifacts and the Android executable
location restrictions; package compatible launcher libraries where necessary.
Expose download/install/probe state in the device/tools page and discover real
executables only after successful installation and smoke checks. Preserve workspace
containment. Any unsupported architecture gets an explicit reason.

Improve foreground service recovery, missed-schedule reconciliation, persisted
user stop, battery exemption diagnostics and recovery entry points. The app may
request the user's normal Android system authorization but cannot override OEM
freezing or a secure keyguard. Handle those states visibly and without duplicate
execution. Validate recovery on the connected phone when unlocked and disclose
hardware/OS coverage precisely.

## Image Input Extension Authorized On 2026-10-01

The user corrected the text-only boundary: Qwen3.5 0.8B is natively multimodal,
and both downloaded local models and cloud models must receive real image input.
The existing attachment picker remains the entry point. Shared ImagePart and
provider image encoders are reused; an attachment path in a prompt is not image
delivery. Mobile requests carry bounded, owned image references whose original
bytes/digest survive queueing, idempotent retries and restart. Ordinary files keep
their existing workflow. Cloud OpenAI-compatible, Anthropic, Gemini and Ollama
requests are verified at the HTTP payload boundary without exposing credentials.

The pinned llama.cpp CPU engine gains its mtmd image adapter and verified,
optional Qwen3.5 projection downloads. Text inference works independently of the
visual component; the secondary model page reports its size, integrity and
installation state. Projection files stay in the same private storage boundary
and download queue as weights. Native image decoding has finite encoded-byte,
pixel, image-count and context limits. Visual tokens count toward the context;
no image can silently disappear to satisfy a text budget. Image requests retain
cancellation, memory protection and explicit errors, without cloud fallback.

Acceptance includes actual image bytes in every cloud protocol, session/path/
digest/recovery failures, original text/tool regression checks and real local
image understanding with a non-private fixture. A physical CPU measurement is
reported separately from protocol or unit-test coverage. The earlier text-only
test results remain historical evidence and do not certify this extension.

## Public Build And Acceptance

Restore a checksummed standard Gradle wrapper at the actual supported version.
Add Android Python/Web/build CI, an emulator/native subset where feasible, release
signing through optional CI secrets and a local release command. Do not replace
the installed debug identity. Refresh Android onboarding/build documentation,
dependency/model notices, contribution guidance, and private-artifact ignore rules.

Expand the existing evaluation catalog with executable scenarios, fixed metadata,
machine-readable result export and reproducible run instructions. Report actual
measured model results separately from unit tests and declared scenarios. Run
offline inference, toolchain, replay/error/restart and layout tests, then build and
cover-install the finished APK. Physical device or service restrictions are reported
as limitations, not represented as passed tests.
