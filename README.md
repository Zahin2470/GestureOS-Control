# GestureOS

**Control your Mac without touching it.**

GestureOS is a touchless control layer for macOS: a webcam-driven pipeline
that turns hand gestures into safe, deliberate Mac commands (cursor, click,
drag, scroll, app switching, media, Spaces) — developed and run directly
from VS Code.

```text
Mac Webcam → OpenCV Capture → MediaPipe Hand Tracking → Normalized Features
    → Temporal Smoothing → Gesture/Intent State Machine → Safety Policy
    → macOS Command Router → Quartz/macOS APIs → Cursor • Click • Drag •
      Scroll • Media • Apps • Spaces
```

> **Status: Phase 11 — Reliability.**
> Three additions, all aimed at GestureOS surviving a real, long-running
> session rather than just a demo:
>
> - **Permission walkthrough.** Phase 5 could only report Accessibility
>   permission status once at startup. `PermissionFlow` now re-checks
>   periodically through the whole session (so granting it *while
>   GestureOS is running* is noticed within a few seconds, no restart
>   needed), and pressing `A` opens System Settings directly to the
>   right pane via `open_accessibility_settings()` instead of just
>   telling you where to go.
> - **Stress testing.** `test_stress.py` runs thousands of frames of
>   randomized, adversarial hand-pose sequences (including a hand
>   flickering in and out of frame on literally every frame) through
>   the full pipeline, checking real invariants: no exceptions, no
>   `mouse_down` left without a matching `mouse_up`, no unbounded growth
>   in the engine's or controllers' per-hand state, no NaN ever reaching
>   a dispatched command's position.
> - **Latency profiling.** `PipelineProfiler` times each pipeline stage
>   (capture, tracking, features, gesture engine, routing) as a rolling
>   average, shown live in the HUD and logged periodically — so a real
>   slowdown on a real Mac is visible directly, not just inferable from
>   a dropped frame rate.
>
> Same honest caveat as Phases 5-10: the permission-flow *mechanics* are
> fully tested here (periodic re-checking, URL opening, status-change
> detection), but I can't watch it actually open System Settings or
> notice a real permission grant — there's no macOS to do that on. The
> stress and profiling work, by contrast, needed no real hardware at all
> and is exercised exactly as it would be on a Mac.
>
> See [Roadmap](#roadmap) below.

---

## Platform

**macOS only**, developed and run from **VS Code**. Windows/Linux are not
targets for this project. The code can technically be imported and unit
tested on other platforms (that's how the test suite is developed), but
the app itself assumes macOS.

## Requirements

- macOS
- VS Code, with the Python extension
- Python 3.10+
- A local webcam (built-in Mac camera works)
- **Accessibility permission** (System Settings → Privacy & Security →
  Accessibility) — required for `RealMacOSAdapter` to control the cursor,
  click, scroll, switch apps, or launch apps. Not needed in Simulation
  Mode. GestureOS checks this on startup and shows the status in the HUD;
  it does not yet walk you through granting it (that's Phase 11).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

For development (tests, formatting, linting):

```bash
pip install -r requirements-dev.txt
```

## Running GestureOS From VS Code on macOS

1. Open the `GestureOS/` folder in VS Code.
2. `Cmd+Shift+P` → **Python: Select Interpreter** → choose `.venv/bin/python`.
3. Install requirements (see above) in the integrated terminal.
4. Open **Run and Debug** and pick a configuration:
   - **GestureOS** — normal run, real macOS control
   - **GestureOS — Debug** — verbose logging
   - **GestureOS — Simulation** — debug logging + `--simulate` (every
     command is recorded by `FakeMacOSAdapter`, never sent to the real OS)
   - **GestureOS — Camera 1** — targets camera index 1
5. Press **Run**. A window opens showing live status: FPS, whether a hand
   is detected, the last recognized gesture, Accessibility permission
   status, camera availability, control state, and theme.
6. Show your hand to the camera and try a pinch (click/drag), a
   two-finger hold-and-move (scroll), a fist swipe (switch app), an open
   palm (media play/pause), or a point-and-swipe (switch Space).
7. Press `Esc` or close the window to exit — settings are saved
   automatically.

No Terminal commands are required after the initial `pip install`.

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Esc` | Quit (emergency stop) |
| `P` | Pause / resume control (`ControlState`) |
| `T` | Cycle theme (dark → light → neon → high-contrast) |
| `A` | Open System Settings → Accessibility (only shown when permission is missing) |
| `C` | Start the calibration wizard |
| `Space` | Confirm the current calibration step |
| `S` | Open/close the settings panel |
| `↑` `↓` (settings open) | Select a setting |
| `←` `→` (settings open) | Decrease / increase the selected value |

## Command-Line Interface

```bash
python main.py
python main.py --debug
python main.py --simulate
python main.py --camera 0
python main.py --profile default
```

`--debug`, `--simulate`, and (as of Phase 10) `--camera` are all fully
functional. `--profile` is still accepted and recorded in settings but
doesn't switch anything yet — full named-profile support (swapping entire
binding sets) was never committed to by this project's 12-phase plan and
remains a possible future enhancement.

## Gesture Reference

| Gesture | Start | Hold | End |
|---|---|---|---|
| **Pinch** | Mouse down (cursor snaps to pinch point) | Mouse move, once past a small click-vs-drag deadzone | Mouse up |
| **Two-finger hold** (index + middle) | — | Scroll, following hand movement (natural-scrolling direction) | — |
| **Fist** | — | Switch app (once per hold, on a big enough horizontal swipe) | — |
| **Open palm** | Media play/pause (once) | — | — |
| **Point** (index only) | — | Switch Space (once per hold, on a big enough horizontal swipe) | — |

## Project Structure

```text
GestureOS/
├── .vscode/
│   ├── launch.json
│   └── settings.json
├── .gitignore
├── .env.example
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── main.py
├── gestureos/
│   ├── app.py             # Live app shell: pygame loop wiring the full pipeline
│   ├── config.py          # Local settings load/save (JSON)
│   ├── constants.py       # App metadata, paths, defaults
│   ├── models.py          # Settings schema, RunMode, ControlState, Theme
│   ├── utils/
│   │   ├── logging.py     # Structured key=value logging
│   │   ├── timing.py      # Stopwatch / rolling average / FPS counter
│   │   └── profiling.py   # Per-stage pipeline latency (StageTimer/PipelineProfiler)
│   ├── vision/
│   │   ├── camera.py         # OpenCV capture wrapper (injectable backend)
│   │   ├── tracker.py        # MediaPipe hand tracking adapter
│   │   ├── features.py       # Raw landmarks → structured HandFeatures
│   │   ├── normalization.py  # Palm-width scale normalization
│   │   ├── smoothing.py      # Per-hand exponential smoothing (EMA)
│   │   └── mapping.py        # Fingertip → screen pixel (mirror/region/sensitivity/smoothing)
│   ├── interaction/
│   │   ├── gestures.py       # Gesture vocabulary (per-frame classification)
│   │   ├── confidence.py     # Temporal voting (rolling majority vote)
│   │   ├── state_machine.py  # Per-hand START/HOLD/END lifecycle
│   │   ├── cooldown.py       # Generic per-key cooldown/rate-limiter
│   │   └── engine.py         # Orchestrates the above into Intent events
│   ├── commands/
│   │   ├── types.py          # CommandType enum + Command dataclass
│   │   ├── registry.py       # Gesture/phase → CommandType binding table
│   │   ├── safety.py         # Control-state gate + launch allowlist + rate limiting
│   │   ├── drag.py           # Click-vs-drag engagement deadzone
│   │   ├── scroll.py         # Frame-to-frame movement → scroll deltas
│   │   ├── switch.py         # Swipe detector → single next/previous call
│   │   └── router.py         # Intent → Command → safety check → adapter call
│   ├── macos/
│   │   ├── adapter.py         # MacOSAdapter Protocol (stable contract)
│   │   ├── fake_adapter.py    # Simulation-mode adapter: records, never acts
│   │   ├── real_adapter.py    # Quartz/AppKit-backed adapter: all but key_press are real
│   │   ├── permissions.py     # Accessibility permission check/request (single call)
│   │   ├── permission_flow.py # Periodic re-check + "open settings" walkthrough
│   │   └── screen.py          # Primary screen size (AppKit, with fallback)
│   ├── ui/
│   │   ├── calibration.py    # Calibration wizard state machine (pure logic)
│   │   └── settings_panel.py # In-app settings adjustment (pure logic)
│   └── audio/
│       └── feedback.py       # Synthesized tone playback for gesture events
└── tests/
    ├── test_config.py
    ├── test_camera.py
    ├── test_tracker.py        # incl. one real-MediaPipe integration test
    ├── test_features.py
    ├── test_normalization.py
    ├── test_smoothing.py
    ├── test_mapping.py
    ├── test_gestures.py
    ├── test_confidence.py
    ├── test_cooldown.py
    ├── test_state_machine.py
    ├── test_engine.py         # vision + gesture pipeline integration test
    ├── test_registry.py
    ├── test_safety.py         # incl. launch allowlist
    ├── test_router.py         # incl. click/drag, scroll, app-switch, space-switch, media
    ├── test_scroll.py
    ├── test_switch.py         # SwipeController, reused by both app- and space-switch
    ├── test_simulation.py     # full pipeline → fake adapter integration test
    ├── test_permissions.py
    ├── test_permission_flow.py
    ├── test_real_adapter.py
    ├── test_calibration.py
    ├── test_settings_panel.py
    ├── test_audio.py
    ├── test_profiling.py
    ├── test_stress.py         # thousands of randomized frames; invariant checks
    ├── test_app.py            # live app shell: full pipeline, keys, calibration, settings
    └── vision_helpers.py      # synthetic hand-pose builders used by tests
```

`persistence/` (beyond the settings JSON file already handled by
`config.py`) is the only piece of the originally-recommended structure
not yet added — nothing so far has needed more than that.

## Privacy (current state)

All processing is local. The vision pipeline never logs, saves, or
uploads a camera frame — only scalar feature values ever leave
`camera.py`/`tracker.py` (Section 33); the live camera preview shown in
the app window is rendered directly from the in-memory frame and never
written to disk. `FakeMacOSAdapter` (Simulation Mode) only records calls
in memory. `RealMacOSAdapter` can move the cursor, click/drag, scroll,
switch apps/Spaces, toggle media, and launch apps via Quartz/AppKit once
Accessibility permission is granted — app launches are additionally
gated by an explicit, fail-closed allowlist.

## Safety notes

- **App launches are denied by default.** `SafetyPolicy` blocks every
  `LAUNCH_APP` command unless constructed with an explicit `allowed_apps`
  set. The live app doesn't configure one yet, so launches are blocked
  end to end for now — consistent with fail-closed being the right
  default until there's a UI for the user to actually choose one.
- **Releases always go through.** `MOUSE_UP` bypasses both the
  control-state pause and the rate limiter, so pausing GestureOS or
  hitting the rate limit can never leave a mouse button stuck down.
- **One swipe-triggered action per hold**, and **one toggle per
  palm-open** — see the Gesture Reference table above. Phase 11's stress
  tests now actively verify this holds across thousands of randomized
  frames, not just the specific sequences the Phase 6-9 unit tests cover.
- **Calibration and settings changes never bypass validation.** Both the
  calibration wizard and the settings panel write into the same
  `Settings` object that `Config.save()`/`load()` validate and clamp —
  there's no separate, less-checked path for UI-driven changes.
- **A missing camera, denied permission, or unimplemented adapter method
  never crashes the app** — each degrades to "keep running without that
  piece," logged clearly, rather than taking down the whole loop.
- **Permission status can change mid-session without a restart.**
  `PermissionFlow` re-checks periodically (every 3 seconds by default),
  so granting Accessibility while GestureOS is already running is
  picked up on its own.

## Testing

```bash
pytest              # full suite, including one real-MediaPipe smoke test
pytest -m "not integration"   # skip the real-MediaPipe test (fakes only)
```

Camera, hand-tracking, permission, real-adapter, and app tests all use
injected fake backends — no physical webcam, macOS process, permission
prompt, or real display is required to run the suite (SDL's dummy video
and audio drivers stand in for both). One test (marked `integration`)
exercises the real MediaPipe runtime against a synthetic blank frame.
`test_simulation.py` runs the vision-through-command-router pipeline
end to end against a fake adapter; `test_app.py` goes one level further
and exercises the actual live app shell — injecting a fake camera and
tracker after a real `setup()`, then calling the same `_update_pipeline()`
the real run loop uses, to confirm gesture data really does flow from a
"camera frame" through to adapter calls, HUD state, calibration, and
settings, without needing real hardware.

`test_stress.py` (Phase 11) runs thousands of frames of randomized,
adversarial hand-pose sequences — including a hand appearing and
disappearing on literally every frame — through the full pipeline,
checking that no exception is ever raised, no `mouse_down` is ever left
without an eventual matching `mouse_up`, the gesture engine's and
controllers' per-hand state never grows unbounded, and no `NaN` ever
reaches a dispatched command. `test_profiling.py` and
`test_permission_flow.py` cover the two other Phase 11 additions with
the same fake-clock approach used everywhere timing matters in this
project.

Timing-sensitive tests throughout use an explicit fake/deterministic
clock rather than real wall time — real time introduced a genuine
flaky-test bug during Phase 6 development, which is exactly the kind of
failure a fake clock prevents. `RealMacOSAdapter`'s actual Quartz/AppKit
calls, `open_accessibility_settings()` actually opening System Settings,
and the live camera/cursor behavior end to end are not exercised by this
suite — there's no macOS/display/webcam to run them against here. The
suite never touches the real mouse, keyboard, or a real macOS
application.

## Roadmap

1. **macOS + VS Code foundation** ✅ — repo scaffolding, config, logging,
   CLI, basic UI shell
2. **Vision** ✅ — OpenCV camera, MediaPipe hand tracking, feature
   extraction, palm-width normalization, EMA smoothing
3. **Gesture intelligence** ✅ — gesture vocabulary, temporal voting,
   state machine with hysteresis + min hold time, per-gesture cooldown
4. **Simulation** ✅ — command registry, router, safety policy, fake
   macOS adapter
5. **macOS cursor** ✅ — Accessibility permission, fingertip-to-screen
   mapping, Quartz-backed cursor movement
6. **Click + drag** ✅ — real mouse_down/mouse_up, dragging-aware cursor
   movement, click-vs-drag engagement deadzone
7. **Scroll** ✅ — two-finger scroll gesture, real Quartz scroll events
8. **App switching + safe launcher** ✅ — fist-swipe app switching, real
   NSWorkspace launching gated by a fail-closed allowlist
9. **Media + Spaces** ✅ — open-palm media toggle, point-swipe Spaces
   navigation; all five gestures bound to something
10. **Product polish** ✅ — live pipeline wiring into the app loop,
    calibration wizard, in-app settings panel, theme cycling, audio
    feedback
11. **Reliability** ✅ *(this phase)* — periodic permission re-checking
    plus a one-key System Settings walkthrough, thousands-of-frames
    stress testing with real invariant checks, per-stage latency
    profiling in the HUD and logs
12. Documentation — architecture diagram, troubleshooting guide,
    contribution notes
