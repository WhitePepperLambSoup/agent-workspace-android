# Android Feature And Layout Verification

## Delivered

- Secondary-menu pages for task history, stopping/resuming tasks, workspace files,
  text editing, session names, notification settings, and Token/cost statistics.
- Model prices are a child page of statistics. Chat does not show accounting panels.
- Input/output/cache Token counts, model call counts, session/workspace and date
  filters, estimated-usage labels, custom USD-per-million rates, and historical repricing.
- Unknown prices remain unpriced; zero rates are valid. Cache is included in input
  tokens and is not added twice to total tokens. Core reference rates remain estimates.
- Files use digest-checked atomic saves. Conflicts preserve local drafts. Binary and
  oversized previews are read only. Session aliases use the desktop presentation format.
- Native completion, failure, and approval notifications work independently of WebView.
  Persistent deduplication survives restarts; notification taps open the relevant session.
- Narrow-screen bottom menus, wider-screen side menus, constrained chat width, safe
  areas, keyboard resizing, system font scaling, and supported viewport-segment handling.
- Rotation and unfolding preserve conversation and editor drafts. Long model names
  cannot squeeze the execution mode into a vertical label.
- Existing Markdown, model/reasoning controls, YOLO, attachments, search, share-to-draft,
  export, reconnect, and task recovery remain covered by regression tests.

## Verification

| Check | Result |
| --- | --- |
| Final Android Python suite | 153 passed |
| Combined Android/core settings, credentials, reasoning, autonomy, cost regressions | 260 passed, 1 platform guard skipped |
| Workspace/usage HTTP suite | 42 passed |
| Web UI suite | 65 passed |
| Local CLI/toolchain/context end-to-end suite | 10 passed |
| Real Chrome layout matrix | 256 states passed, 0 layout defects, 0 JavaScript errors |
| Installed Android instrumentation suite | 27 passed |
| Main and test APK builds | Passed with cached Gradle 8.11.1 |
| Python source lint | Ruff passed |
| APK archive comparison | Final gateway/workspace/usage and Web UI source bytes match |

Counts from overlapping suites are not additive. One combined run predates the final
HTTP/error-path additions; those are included in the final 153-test Android run.

The browser matrix uses representative mocked conversation, GFM, task, file, and usage
data in installed Chrome. It covers 320x720, 360x800, 600x960, 800x600, 1024x768,
900x900, 1280x800, and 800x360, with 100%/200% text scaling, large message text,
rotation/unfolding, menu scrolling, and a 350px keyboard-reduced viewport.

Matrix report and screenshots: `output/playwright/mobile-parity-matrix/`.
Final native log: `output/android-native-final-tests.txt`.

The initial native run had four test failures. One incorrectly assumed the user's
persisted reasoning choice was Auto. Three involved ActivityScenario matching lifecycle
events against a launch Intent later changed by real share/notification delivery.
Tests now establish their reasoning fixture and restore the launch Intent in cleanup;
all original interaction assertions remain enabled. The complete 27-test rerun passed.

## Device Delivery

Device: ZTE A2022P, serial `326615796159`, Android API 31.
The main APK was installed with `adb install -r` using the original debug certificate.
Only the temporary test application was replaced to align its certificate.

APK: `for Android/kotlin_app/build/outputs/apk/debug/AgentWorkspaceMobile-debug.apk`.
SHA-256: `1EA90CE3F3D3CC17875E4CCCCB41F0380F251EA384834330003D0C893FFCFAD0`.

The database and provider settings had identical hashes before and immediately after
the update. The four original sessions remain accessible, and the provider settings
hash is unchanged after instrumentation. The final authenticated health and usage
checks passed: 23 model calls and 447,457 total tokens in the existing workspace.
These models currently have no configured rate and therefore show unpriced.

Temporary ADB forwarding and the charging stay-awake setting were restored after testing.

## Limits

- Physical device verification covers the connected API 31 phone. Tablet/foldable
  sizes and 200% text were tested in the browser; no physical tablet, foldable,
  Android 13 permission prompt, or Android 15 device was available.
- Viewport-segment hinge avoidance depends on the browser exposing that feature.
- Costs are estimates based on reference/custom rates, not provider invoices.
- OS background-service and notification restrictions still apply. Tests verify
  native polling/publishing and navigation without paid model requests.
- The mobile workbench now covers the listed desktop workflows; this is not a claim
  that every desktop integration or operating-system tool exists on Android.
