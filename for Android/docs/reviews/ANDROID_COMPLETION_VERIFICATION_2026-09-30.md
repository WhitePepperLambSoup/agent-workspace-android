# Android Completion Verification

Date: 2026-09-30. Device: ZTE A2022P, Android 12 / API 31, arm64.

## Delivered Changes

- Capability diagnostics filter unavailable desktop tools and adapt Android
  shell/process execution and native TTS.
- Persistent MCP/custom extension consent binds to the exact configuration and
  can be revoked.
- Accessibility observations expose bounded, redacted UI trees, current display
  geometry and versioned references. Actions refresh observations and separate
  execution acknowledgement from verified goals. Pause/takeover is available.
- Secondary menus manage schedules, paired hosts, outgoing handoffs, reusable
  workflows, evaluation records and local model endpoint diagnostics.
- Mobile entry points include voice drafts, a widget and assistant activity.
  Notifications include task-specific actions and session navigation.
- Workflow/evaluation task adoption shares the existing Stop, polling and
  approval lifecycle; drafts and attachments remain available.
- Same-key retries retain original omitted/supplied settings across default
  changes and restart. Ambiguous remote writes are reconciled safely.
- Android registry wrappers preserve the complete selected workspace for Path,
  string and WorkspacePaths inputs. A Path's filesystem anchor is no longer
  mistaken for the execution directory, restoring shell/process discovery and
  their correct initial cwd boundary.
- Secondary menu opening and page navigation use opacity/transform transitions
  of 180/220 ms, directional returns, visible focus and parent scroll recovery.
  Reduced motion removes those animations.
- The installed Google WebView 99 does not support dynamic viewport height
  units. Shell, secondary sheet, approval and editor heights now use unconditional
  `vh` fallbacks with all `dvh` overrides inside `@supports (height: 100dvh)`.
  This also preserves the later short-height editor rules.

## Completed Checks

| Check | Result |
| --- | --- |
| Complete Android Python suite after workspace-boundary fix | 268 passed in 187.35 seconds |
| Complete Web suite after final viewport-unit compatibility guard | 82 passed; no failures or skips |
| Python static checks of changed controller, management, scheduling, platform and evaluation modules | Ruff passed |
| Browser viewport/font/motion checks | 172 initial states + 3 overflow retests; 70 initial screenshots |
| Viewport sizes | 360x800, 820x1180, 720x720, 960x540, each with 100% and 200% text |
| Reduced motion | All four viewport sizes: no menu animation and transform none |
| Refreshed icon browser audit | 18 views, 1,552 control checks; no missing geometry, zero-size visible icons, body overflow or page errors |
| Final guarded-height browser checks | 24 states across four viewports, 100%/200% text and home/model/scrolling views; no overflow or errors. Unsupported-unit analogue retains `vh` fallbacks; short 360x400 editor remains 200px/minimum 150px |
| Old APK schedule notification reproduction | Cold and warm navigation both failed at the target-session assertion |
| Installed engine/data check before final update | Health ready, 4 sessions, DeepSeek Flash/auto and full_access, 0 active tasks/approvals |
| APK build | `assembleDebug assembleDebugAndroidTest` completed successfully |
| Native tests independent of visible screen | `OK (31 tests)` in 11.644 seconds; no failures or skips |
| Startup/authenticated restart | `OK (1 test)` in 4.392 seconds |
| Viewport, installed WebView menu/Markdown/icons, provider UI and engine notification | `OK (5 tests)` in 4.099 seconds on the earlier production build |
| Share drafts and cold/warm task/schedule notification navigation, with repeated menu/provider checks | `OK (8 tests)` in 13.609 seconds; repeated methods are counted only once |
| Actual accessibility observations | Offscreen-goal rejection passed; the action sequence initially failed on a definite unexecuted `stale_snapshot`. The corrected test is installed and awaits an unlocked rerun |
| Real shell/TTS checks | Actual shell output, bounded timeout and discovered executable; registered shell cwd containment; real native short utterance completed; invalid speech rejected |
| Workspace regression reproduction | Both Path input wrappers failed before the fix; six desktop cases passed after it. Installed old APK failed with actual workspace `/`; installed fixed APK passed after canonicalizing equivalent Android data-directory aliases in the test |
| Cover-install | Production and instrumentation APKs installed with `adb install -r` |
| Installed artifact freshness | APK hash matches the build; 255 source files and 9 Web assets match current source; served JS/CSS match source |
| Original history preservation | Exact 4 session IDs and all 1,034 original event IDs/types/sequences/data preserved; current event total 1,042 |
| Installed management API | 10 management/usage endpoints respond; evaluation catalog has 24 scenarios |

The 14 native methods requiring visible Activity interaction have now been run:
13 distinct methods passed and one actual action sequence failed at its first
HOME request because Android Settings changed after the observed snapshot.
Production correctly returned `stale_snapshot` with `executed=false`. The test
now refreshes observations and rebuilds references, with at most three attempts
within eight seconds only for a definite unexecuted stale rejection. It never
retries an executed or unknown action; the deliberately stale BACK remains a
single request. No production safety rule was relaxed.

The phone was reconnected and the final APK's complete live deployment check
passed. It is still secured by the keyguard. The corrected actual-action test
and the new installed menu-height assertion need an unlocked screen. The earlier
installed WebView menu test passed before the final CSS guard; its pre-fix
screenshot exposed the collapsed sheet and must not be treated as a final
corrected screenshot. Tests fail early on a locked device. There are 44 distinct
native methods with successful evidence (31 independent plus 13 visible), not a
claim that all 45 pass together on the final build.

The installed capability API now discovers `/system/bin/sh` and toybox, and marks
both `run_terminal` and `run_process` available. This is corroborated by actual
Chaquopy shell execution and the registry regression above. The native TTS engine
completed a real short utterance on this device; this check does not certify every
locale or voice. The accessibility service remains in its original disabled
state after tests and needs the user's Android system authorization for automation.

Installed APK: `for Android/kotlin_app/build/outputs/apk/debug/AgentWorkspaceMobile-debug.apk`.
SHA256: `68596369F60B3F085FEEAF486B8779460F2DD885E183BBDE3FDA147C5765F2DE`.
Evidence: `output/android-final-native-green-20260930.log`,
`output/android-final-python-post-registry-20260930.log`,
`output/android-registry-native-red-20260930.log` and
`output/android-final-reconnected-deployment-20260930.json`. This latest live
report checks the final hash, served resources and original history;
`output/android-final-deployment-20260930.json` records an earlier build.
The strengthened restart test
requires a new healthy authentication token after restart and refuses to run
with active/queued tasks or pending approvals; its visible console/restart
check passed in `output/android-final-startup-ui-20260930.log`.
Other device evidence is in `output/android-final-workbench-ui-20260930.log`,
`output/android-final-navigation-share-ui-20260930.log` and
`output/android-final-system-ui-20260930.log`. The last file preserves the
original action-test failure rather than hiding it.
Final build and Web regression evidence:
`output/android-final-build-vh-guard-20260930.log` and
`output/android-final-web-vh-guard-20260930.log`.
The actual-service tests' cleanup now uses nested `finally` blocks so returning
to the app, restoring exact secure settings and restoring pause/takeover state
are each attempted even if another cleanup step fails. The subsequent build
passed in `output/android-final-cleanup-build-20260930.log`; the production APK
hash remained unchanged. The updated instrumentation APK was cover-installed,
SHA256 `BF18A982016AD0C2B84C98F00D50D237DC75A6B77C1EC27F9DE09573E5CCB84C`.

Browser evidence: `output/playwright/android-motion-20260930/report.log` and
`overflow-report.log`; refreshed-icon screenshots are in the same directory.
Final CSS guard evidence:
`output/playwright/android-motion-20260930/fallback-guard-verification.md` and
the 24 `fallback-guard-*` screenshots in that directory. Its unsupported-unit
probe is a browser analogue, not certification of WebView 99 on the phone.
Independent behavioral review:
[ANDROID_COMPLETION_INDEPENDENT_REVIEW_2026-09-30.md](ANDROID_COMPLETION_INDEPENDENT_REVIEW_2026-09-30.md).

## Data Preservation

The earlier recovery database contains 4 sessions and 1,034 events. Its integrity
check passed. The full pre-update app archive is
`output/android-before-final-update.tar`, SHA256
`B64FD15DE389B782CF3C39F9D42FFB19B722A305D5B1992E9818BB64297B19BE`.

The prior test installation had erased preferences. Sessions were restored from
the preserved database. Provider credentials were recovered from the desktop
secure store through private adb stdin and the Android Keystore recovery test;
the temporary recovery file was deleted. Last recorded model/effort was
DeepSeek Flash/auto; all four original sessions used full_access, which was
restored. No credential is baked into the APK or printed in the recovery log.

Current deployment uses only `adb install -r` and direct `am instrument`.
`connectedDebugAndroidTest`, uninstall and application-data clearing are excluded.
Native tests were audited to restore provider preferences and drafts, avoid
creating real conversations, and restore temporary accessibility settings.
The dedicated private credential recovery method is excluded from routine
verification. After the final locked-device check, the temporary stay-awake
setting was restored to its original `0`, the task's `tcp:18086` forward was
removed, and secure accessibility settings were confirmed at their original
`enabled_accessibility_services=null` / `accessibility_enabled=0` values.

## Boundaries

- The 24 evaluation cases verify declared terminal UI states or visible values.
  They are a reusable catalog, not 24 measured real-device model task outcomes
  or a competitive success-rate result.
- Workflows are saved goal prompts with checks at the execution boundary and
  terminal assertions. They do not implement declarative step-by-step replay.
- The APK has no embedded model weights or Android inference engine. Existing
  local Ollama/OpenAI-compatible HTTP endpoints can be diagnosed and used.
- Git, language servers, CDP browser automation and standalone Python workers
  require their actual platform dependencies and remain unavailable when absent.
- Android system permissions require OS authorization. Background scheduling
  remains subject to Android/OEM restrictions and may require the user to launch
  the app. A physical reboot and OEM battery-policy behavior are not certified
  by the scheduled metadata/lifecycle tests.
- When the device slept, the engine's main thread was observed in Linux
  `__refrigerator` state and its listening HTTP port timed out. Waking and
  launching the app allowed the final live checks to complete. This is actual
  OEM process freezing; the update does not certify permanent background
  availability while the device is locked or asleep.
- Tablet/foldable coverage uses real Chromium/WebView layouts and simulated
  geometries; it does not certify hinge posture or every hardware model.
- Token costs are estimates from recorded usage and configured rates, not a
  provider invoice.
