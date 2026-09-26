# Changelog

GestureOS was built in twelve phases, each delivered, tested, and
packaged before moving to the next. This is the real order things were
built in — later phases sometimes revised earlier decisions (noted
below) rather than every choice being right the first time.

## Phase 12 — Documentation

- Added `docs/ARCHITECTURE.md`, `docs/TROUBLESHOOTING.md`,
  `docs/CONTRIBUTING.md`, and this changelog.
- Added `LICENSE` (MIT).
- Expanded the main README with Known Limitations, FAQ, and License
  sections.

## Phase 11 — Reliability

- `macos/permission_flow.py`: `PermissionFlow` re-checks Accessibility
  permission periodically through a running session (not just once at
  startup) and `open_accessibility_settings()` opens System Settings
  directly to the right pane.
- `utils/profiling.py`: `PipelineProfiler`/`StageTimer` — rolling-
  average latency per pipeline stage, shown in the HUD and logged
  every 5 seconds.
- `tests/test_stress.py`: thousands of randomized/adversarial hand-pose
  frames (including a hand flickering in and out of frame on every
  single frame) through the full real pipeline, checking invariants —
  no exceptions, no stranded `mouse_down`, bounded per-hand state, no
  `NaN` ever reaching a dispatched command.
- Added the `A` key (open Accessibility settings) to the live app.

## Phase 10 — Product Polish

- **The pipeline was wired into the live app loop for the first time.**
  Phases 2-9 had all built and thoroughly tested their pieces in
  isolation; this phase connected camera → tracker → features →
  gesture engine → command router → adapter inside `app.py`'s actual
  frame loop, with graceful degradation on a missing camera or screen
  API.
- `ui/calibration.py`: a guided flow to capture a custom cursor active
  region instead of the hardcoded default.
- `ui/settings_panel.py`: live, keyboard-driven adjustment of cursor
  sensitivity/smoothing, scroll sensitivity, and audio volume.
- `audio/feedback.py`: synthesized tones (no asset files) for click,
  release, and switch events.
- New keys: `P` (pause/resume), `T` (theme cycle), `C`/`Space`
  (calibration), `S` (settings).
- `--camera` finally wired to actually select a camera (was a Phase 1
  placeholder).

## Phase 9 — Media + Spaces

- `OPEN_PALM` bound at `START` only → `MEDIA_PLAY_PAUSE` (a one-shot
  toggle — `HOLD`/`END` deliberately left unbound).
- `POINT` bound at all three phases → `SPACE_SWITCH`, reusing Phase 8's
  `SwipeController` via a shared `_handle_swipe` router helper, with a
  second, fully independent controller instance.
- `RealMacOSAdapter.media_play_pause` implemented via macOS's
  undocumented (but widely relied-upon) `NSSystemDefined` event
  technique — there's no public Quartz constant for a media key.
  `space_next`/`space_previous` use the documented Control+Arrow
  Mission Control shortcut instead.
- All five gestures were bound to something for the first time.
- Fixed three pre-existing tests whose "the unbound gesture" example
  was `OPEN_PALM` — no longer true once it got a real binding.

## Phase 8 — App Switching + Safe Launcher

- `commands/switch.py`: `SwipeController` — a held `FIST` that moves
  far enough horizontally fires exactly one `switch_app_next`/
  `switch_app_previous`, "consuming" itself so continued movement
  doesn't rapid-fire.
- `SafetyPolicy` gained a **fail-closed** app-launch allowlist:
  `LAUNCH_APP` is blocked by default with no allowlist configured, not
  allowed by default.
- `RealMacOSAdapter.switch_app_next/previous` (Quartz Cmd+Tab/
  Cmd+Shift+Tab) and `.launch_app` (AppKit `NSWorkspace`) implemented.

## Phase 7 — Scroll

- Added a fifth gesture, `TWO_FINGER_SCROLL` (index + middle extended).
- `commands/scroll.py`: `ScrollController` converts frame-to-frame
  movement into incremental scroll deltas (not an absolute position),
  with a natural-scrolling sign convention and an invert option.
- `RealMacOSAdapter.scroll` implemented via
  `CGEventCreateScrollWheelEvent`.

## Phase 6 — Click + Drag

- `commands/drag.py`: a click-vs-drag engagement deadzone — the cursor
  doesn't move during a pinch until the hand has moved past a
  threshold from where the pinch started, keeping quick clicks stable.
- `Intent` gained a `position` field; `PINCH`+`HOLD` bound to a new
  `MOUSE_MOVE` command type.
- `RealMacOSAdapter.mouse_down/mouse_up` implemented; `move_cursor`
  gained a `dragging` flag to post `LeftMouseDragged` instead of plain
  `MouseMoved` while a button is held.
- **Found and fixed a real flaky-test bug**: a safety-policy rate
  limiter occasionally tripped on back-to-back test calls purely from
  Python's own per-statement overhead exceeding the configured
  interval — not a bug in the logic under test. Fixed by using
  explicit, manually-advanceable fake clocks everywhere timing
  matters, rather than trusting real wall time to be "fast enough."
  This became a hard rule for the rest of the project (see
  [CONTRIBUTING.md](CONTRIBUTING.md)).

## Phase 5 — macOS Cursor

- `vision/mapping.py`: `CursorMapper` — mirroring, an active-region
  remap (only the center of the camera frame maps to the full screen),
  sensitivity, and smoothing, all pure geometry with no macOS
  dependency.
- `macos/permissions.py`: Accessibility permission check/request.
- `macos/screen.py`: primary screen size via AppKit, with a fallback.
- `macos/real_adapter.py` introduced: `RealMacOSAdapter.move_cursor`
  implemented via Quartz; every other method declared on the
  `MacOSAdapter` Protocol but raising `NotImplementedError` with a
  pointer to the phase that would implement it.
- `CommandRouter` hardened to catch `NotImplementedError` and any other
  adapter exception, so an unimplemented or failing real command never
  crashes the app.

## Phase 4 — Simulation

- `commands/{types,registry,safety,router}.py` introduced: the
  gesture-to-command binding table, the safety policy (control-state
  gate + rate limiting, with `MOUSE_UP` always exempted), and the
  router that ties them together.
- `macos/{adapter,fake_adapter}.py`: the `MacOSAdapter` Protocol and
  `FakeMacOSAdapter`, which only records calls — used for
  `RunMode.SIMULATION` and by nearly every test in the project from
  this point forward.
- Only binding: `PINCH` start/end → `MOUSE_DOWN`/`MOUSE_UP`.

## Phase 3 — Gesture Intelligence

- `interaction/gestures.py`: a four-gesture vocabulary (`PINCH`,
  `OPEN_PALM`, `FIST`, `POINT`) via per-frame geometric pose scoring.
- `interaction/confidence.py`: rolling-window temporal voting to
  smooth single-frame classification flicker.
- `interaction/state_machine.py`: per-hand `IDLE → CONFIRMING → ACTIVE
  → COOLDOWN` lifecycle producing `START`/`HOLD`/`END` `Intent` events,
  with hysteresis, minimum hold time, and a post-release cooldown.
- **Found and fixed a real bug** in the same phase: right after a
  cooldown expired, the state machine wasted a full frame before it
  would start confirming a new gesture, because the reset-to-idle
  transition didn't immediately evaluate the frame that triggered it.
  Fixed so cooldown-expiry and the next candidate are handled in the
  same `update()` call.

## Phase 2 — Vision

- `vision/{camera,tracker,features,normalization,smoothing}.py`:
  OpenCV camera capture and MediaPipe hand tracking behind injectable
  backends, structured `HandFeatures` extraction (presence, handedness,
  key points, finger extension, pinch distance, palm orientation,
  velocity, motion direction, two-hand state), palm-width scale
  normalization, and per-hand EMA smoothing.
- Confirmed both `opencv-python` and MediaPipe's legacy Hands solution
  actually run fully offline (no network access needed — the model
  ships inside the package) in the development sandbox, and added one
  integration test against the real runtime alongside the fakes-only
  unit tests.

## Phase 1 — macOS + VS Code Foundation

- Repository scaffolding, `.vscode` run/debug configurations, pinned
  `requirements.txt`/`requirements-dev.txt`.
- `config.py` (JSON settings persistence with corrupted-file recovery),
  `constants.py`, `models.py` (the `Settings` schema, `RunMode`,
  `ControlState`, `Theme` — all designed with later phases' needs in
  mind, e.g. `ControlSettings.cooldown_s` sat unused until Phase 3).
- `utils/{logging,timing}.py`: structured `key=value` logging and
  timing primitives (`Stopwatch`, `RollingAverage`, `FPSCounter`) reused
  as-is all the way through Phase 11.
- `main.py`'s CLI surface (`--debug`, `--simulate`, `--camera`,
  `--profile`) was defined in full from the start, with flags accepted
  but not yet functional until the phase that implemented them —
  `--camera` waited until Phase 10, `--profile` was never committed to.
- A basic pygame UI shell: a window, an event loop, and cleanup —
  nothing else yet.
