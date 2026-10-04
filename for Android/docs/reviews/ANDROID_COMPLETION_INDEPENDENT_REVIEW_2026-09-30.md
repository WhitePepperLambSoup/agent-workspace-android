# Android Completion Independent Review

Date: 2026-09-30

Reviewed against the Android completion design and implementation plan dated
2026-09-30. This review concentrates on pairing, outgoing delivery, workflows,
evaluation evidence, extension authorization, and their controller and Web UI
integration. Source inspection also traced the embedded credential bridge.

## Findings And Status

Twelve defects were confirmed during the review and remediated in the shared
workspace. No unresolved defect was found in the final reread of those paths.
This statement does not certify the entire Android completion plan: the workflow
scope and native verification limits below remain material.

| Priority | Original finding and effect | Remediation and current source |
| --- | --- | --- |
| P1 | A cancellation during remote preflight could still send the cancelled action. | Dispatch now requires a conditional database claim from the expected state; cancellation also updates only pending entries. `mobile_delivery.py:135`, `mobile_delivery.py:242`. |
| P1 | Lost mobile submission responses were recorded as pending, allowing local cancellation to conceal possible remote execution. | Ambiguous writes remain uncertain; old timeout records are migrated. Reconciliation preserves the same request key. `mobile_delivery.py:19`, `mobile_delivery.py:147`. |
| P1 | Interrupted dispatches could not reconcile; inferring the original API from the current host could replay a legacy action after a host upgrade. | The dispatch claim persists its API. Automatic same-key recovery requires both original and current APIs to be mobile. Legacy and unknown dispatches remain uncertain. `mobile_delivery.py:135`, `mobile_delivery.py:214`. |
| P1 | Workflow verification could observe the next queued task's screen and falsely report success. | Preconditions are repeated when execution begins, and terminal observations are captured before releasing the controller execution lock. `mobile_runtime_controller.py:355`, `mobile_workflows.py:56`. |
| P1 | Invisible, sensitive, or unstable observations could satisfy terminal assertions. | Assertion matching rejects unstable snapshots and excludes invisible/password/sensitive nodes. `mobile_workflows.py:29`. |
| P1 | The battery evaluation could succeed with zero actions and only the Settings menu label, without reading a battery value. Other cases overstated what their terminal checks proved. | Automated success requires a confirmed executed Android action. Battery requires a battery-page marker and a 0-100 percentage; version, storage, and WiFi cases require visible matching values. Values are scoped to the foreground application's windows. Navigation-only cases now state terminal UI scope. `mobile_evaluation.py:204`, `mobile_evaluation.py:254`, `mobile_evaluation.py:417`. |
| P2 | A remote legacy POST returning 404 was treated as completed with an empty result. | Optional 404 handling is limited to capability discovery. Dispatch validates returned task/result data and records a fresh missing endpoint as failed. `mobile_connections.py:93`, `mobile_connections.py:129`, `mobile_delivery.py:147`. |
| P2 | The newest-200 outgoing limit hid and starved older active entries, also weakening the host-removal guard. | All active entries remain visible. Only terminal history is bounded; worker processing is oldest first. `mobile_delivery.py:45`, `mobile_delivery.py:57`. |
| P2 | Cancelling a later entry in a worker batch could terminate the delivery worker. | Each entry is reread before processing; stale or invalid entries do not end the loop. `mobile_delivery.py:251`. |
| P2 | Watcher cancellation was swallowed by controller waiting, so evaluation shutdown could report failure while the task was interrupted. | Cancellation of the waiter now propagates. Workflow verification becomes interrupted and evaluation verification becomes blocked. `mobile_runtime_controller.py:270`, `mobile_workflows.py:193`, `mobile_evaluation.py:417`. |
| P2 | An identical same-key submission omitting model/effort failed after defaults changed, impairing delivery recovery. | The original request content is persisted, and duplicate lookup occurs before resolving new defaults or checking new model capabilities. Content and budget conflicts still fail. `mobile_task_store.py:50`, `mobile_task_store.py:127`, `mobile_runtime_controller.py:190`. |
| P2 | Secondary-menu workflow/evaluation starts ignored the returned task, leaving monitoring, approval, and Stop controls unattached. | Both starts adopt the returned task into the existing chat lifecycle. Failed row actions display an error and reenable retry. `web_companion/static/app.js:1333`, `web_companion/static/management.js:24`, `web_companion/static/management.js:43`. |

Source paths in the table are relative to `for Android/`; line references identify
the remediated implementation, not a preserved pre-fix diff.

## Reproduction Evidence

The original review reproduced the delivery errors, the workflow terminal-screen
race, invalid observation matches, evaluation shutdown misclassification, default
changes breaking duplicate lookup, and the zero-action battery false success.

The delivery regression run initially had seven failures and nine passes. Further
migration and dispatch-provenance regressions were observed failing before their
fixes. Six new evaluation regressions also failed before implementation. They
cover no-action success, wrong battery screen, missing required values, unrelated
system-window values, and a valid value-based result.

After the controller changes, independent in-memory reproductions confirmed that
the workflow race produces unverified, captures its final observation before the
next task, classifies verification shutdown as blocked, and rejects invisible or
unstable matches. The final default-retry checks confirm the original task is
returned after settings changes and restart without scheduling another execution.

## Fresh Verification

The following commands were run against the final reviewed source after the
evaluation formatting pass. All completed with exit code 0.

| Check | Observed result |
| --- | --- |
| `pytest -q "for Android/tests/test_mobile_workflows_evaluation.py" "for Android/tests/test_mobile_management_gateway.py"` | 17 passed in 4.45s |
| `pytest -q "for Android/tests/test_mobile_connections.py" "for Android/tests/test_mobile_idempotency.py"` | 21 passed in 4.83s: 19 connection/delivery tests and 2 durable idempotency tests |
| `pytest -q "for Android/tests/test_mobile_runtime_controller.py" -k submission_retry` | 2 passed, 17 deselected in 0.70s |
| `node --test --test-name-pattern "adop\|secondary menu\|secondary row action\|recovers a task started elsewhere" "for Android/tests/web_companion.test.cjs"` | 9 passed, 0 failed; covers task adoption, approvals, Stop, recovery races, secondary-menu starts, row-action errors, and a motion contract selected by the pattern |
| Ruff check of `mobile_evaluation.py`, `test_mobile_workflows_evaluation.py`, `mobile_connections.py`, `mobile_delivery.py`, and `test_mobile_connections.py` | All checks passed |

Python commands used `uv run --offline --no-sync` and unique temporary-directory
basetemps. Counts are focused checks, not a replacement for the complete Android
suite or an aggregate device success rate. Full Web, native, build, and phone
verification from other agents must be recorded separately by the main task.

## Trust And Persistence Assessment

- Pairing verifies the authenticated `/sessions` API before persisting a host.
  HTTPS is the default. Cleartext remote HTTP requires an explicitly enabled
  private LAN IP; loopback is also supported. Redirect following and environment
  proxy inheritance are disabled, and response size is bounded.
- Connection rows and public responses do not contain the bearer token. The APK
  credential path reaches `AndroidCredentialStore` and `EmbeddedSecrets`, where
  credentials are encrypted with an Android Keystore AES-GCM key. This is a source
  trace, not a fresh hardware-backed storage experiment.
- Outgoing content is persisted before dispatch. Pending cancellation and dispatch
  claims are conditional database updates. Active records survive bounded history
  views, and interrupted sending records become uncertain. Recovery of an unknown
  or legacy dispatch cannot infer idempotency from a later host upgrade.
- Mobile task events persist both original request fields and resolved execution
  settings. New duplicate submissions compare original request content; older
  events retain the conservative fallback to their resolved fields.
- Handoff submits the chosen prompt and explicitly opted-in conversation text.
  Pairing credentials and provider configuration are not attached by this flow.
  The remote host and selected workspace remain visible in the connection page.
- Extension authorization binds to the configuration digest and rechecks current
  consent and identity on held tool references. Revocation and configuration
  changes therefore block subsequent guarded execution. No further actionable
  revocation bypass was confirmed in the inspected paths.
- Goal verification remains distinct from a completed agent run. Evaluation
  success stores snapshot version, terminal values, confirmed action event IDs,
  and verification scope; interruption does not become a successful outcome.

## Integration Verdict

The delivery fixes require no additional management or Web API change.
`mobile_management.py` already lists the outbox, calls reconciliation, and checks
active entries before removing a host. Its existing `outbox.list()` call now sees
all active records. The Web outbox already offers reconciliation for submitted
and uncertain entries and cancellation only for pending entries.

Workflow and evaluation starts now use the returned task in the chat. The selected
Web regressions verify that approval controls are reachable, Stop works, drafts
are retained, and stale session-recovery responses cannot disable the composer
after an adopted task finishes.

## Remaining Scope And Verification Limits

1. Saved workflows are reusable goal prompts with checks at the task execution
   boundary and independent terminal assertions. They do not define an encoded
   sequence of steps with a separately enforced precondition before every step.
   The design's per-step workflow wording is therefore broader than this delivered
   representation and must not be reported as fully verified.
2. The 24-case evaluation catalog checks terminal UI navigation or visible values.
   A successful navigation case does not prove a correct reading answer, search
   result selection, or completed input-and-clear interaction. The case prompts
   and `verification_scope` now describe the narrower checks. These tests are not
   24 actual task executions on a phone.
3. Legacy and unknown ambiguous deliveries require remote inspection. They retain
   an uncertain state and do not replay automatically. Only originally compatible
   mobile dispatches can recover using the persisted request key.
4. This reviewer did not run Gradle, native instrumentation, ADB, APK installation,
   or phone operations. Native Accessibility behavior, screenshot restrictions,
   display geometry, Android lifecycle wakeups, APK asset freshness, signature,
   and device-data preservation need the main task's separate evidence.
5. The review preserves the dirty workspace and makes no commit. Authorized source
   changes from this reviewer are confined to evaluation evidence and its focused
   tests; the delegated delivery fixes are confined to the connection/delivery
   modules and their focused test file.

The corrected code paths pass the focused regression checks above. Completion of
the full plan still depends on accurately documenting the workflow scope and
obtaining the separate native and device verification evidence.
