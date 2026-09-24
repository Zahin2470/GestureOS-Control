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

> **Status: Phase 6 — Click + Drag.**
> `RealMacOSAdapter.mouse_down`/`mouse_up` are now real (Quartz), and
> `move_cursor` gained a `dragging` flag so held-button movement posts
> proper `LeftMouseDragged` events instead of plain `MouseMoved` ones.
> The command layer now tracks a pinch's position through its whole
> lifecycle: `PINCH START` snaps the cursor to the click point,
> `PINCH HOLD` moves it — but only once the hand has moved past a small
> deadzone, so a quick pinch stays a stable click instead of nudging the
> cursor by a stray pixel — and `PINCH END` issues one final move if a
> drag was in progress. Deciding "was this actually a click or a drag"
> for UI purposes is otherwise left to whatever app receives the events,
> same as a real trackpad.
>
> Same caveats as Phase 5: not yet wired into the live app loop, and
> `move_cursor`/`mouse_down`/`mouse_up`'s real Quartz behavior can't be
> exercised in this Linux sandbox — everything around them (mapping,
> deadzone logic, router dispatch, safety) is genuinely tested here.
> See [Roadmap](#roadmap) below.

---

## Platform

**macOS only**, developed and run from **VS Code**. Windows/Linux are not
targets for this project. The code can technically be imported and unit
tested on other platforms (that's how the test suite is developed prior
to macOS-specific phases), but the app itself assumes macOS.

## Requirements

- macOS
- VS Code, with the Python extension
- Python 3.10+
- A local webcam (built-in Mac camera works) — not used until Phase 2
- **Accessibility permission** (System Settings → Privacy & Security →
  Accessibility) — required from Phase 5 onward for `RealMacOSAdapter`
  to move the cursor. Not needed in Simulation Mode.

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
   - **GestureOS** — normal run
   - **GestureOS — Debug** — verbose logging
   - **GestureOS — Simulation** — debug logging + `--simulate` (no real
     macOS commands are ever issued in this mode; meaningful starting in
     Phase 4)
   - **GestureOS — Camera 1** — targets camera index 1 (flag is accepted
     now, functional starting in Phase 2)
5. Press **Run**. A window titled "GestureOS" should open showing the
   current version, run mode, active profile, and control state.
6. Press `Esc` or close the window to exit.

No Terminal commands are required after the initial `pip install`.

## Command-Line Interface

```bash
python main.py
python main.py --debug
python main.py --simulate
python main.py --camera 0
python main.py --profile default
```

`--debug` is fully functional (raises log verbosity). `--camera` and
`--profile` are accepted and stored for forward compatibility but have no
effect until the phases that implement the vision engine and profile
system land.

## Project Structure (Phase 1)

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
│   ├── app.py            # Basic UI shell (pygame window, event loop)
│   ├── config.py         # Local settings load/save (JSON)
│   ├── constants.py      # App metadata, paths, defaults
│   ├── models.py         # Settings schema, RunMode, ControlState, Theme
│   ├── utils/
│   │   ├── logging.py    # Structured key=value logging
│   │   └── timing.py     # Stopwatch / rolling average / FPS counter
│   ├── vision/
│   │   ├── camera.py         # OpenCV capture wrapper (injectable backend)
│   │   ├── tracker.py         # MediaPipe hand tracking adapter
│   │   ├── features.py       # Raw landmarks → structured HandFeatures
│   │   ├── normalization.py  # Palm-width scale normalization
│   │   └── smoothing.py      # Per-hand exponential smoothing (EMA)
│   ├── interaction/
│   │   ├── gestures.py       # Gesture vocabulary (per-frame classification)
│   │   ├── confidence.py     # Temporal voting (rolling majority vote)
│   │   ├── state_machine.py  # Per-hand START/HOLD/END lifecycle
│   │   ├── cooldown.py       # Generic per-key cooldown/rate-limiter
│   │   └── engine.py         # Orchestrates the above into Intent events
│   ├── commands/
│   │   ├── types.py          # CommandType enum + Command dataclass
│   │   ├── registry.py       # Gesture/phase → CommandType binding table
│   │   ├── safety.py         # Control-state gate + rate limiting
│   │   └── router.py         # Intent → Command → safety check → adapter call
│   ├── commands/
│   │   ├── types.py          # CommandType enum + Command dataclass
│   │   ├── registry.py       # Gesture/phase → CommandType binding table
│   │   ├── safety.py         # Control-state gate + rate limiting
│   │   ├── drag.py           # Click-vs-drag engagement deadzone
│   │   └── router.py         # Intent → Command → safety check → adapter call
│   └── macos/
│       ├── adapter.py        # MacOSAdapter Protocol (stable contract, no impl)
│       ├── fake_adapter.py   # Simulation-mode adapter: records, never acts
│       ├── real_adapter.py   # Quartz-backed adapter: cursor + click are real
│       ├── permissions.py    # Accessibility permission check/request
│       └── screen.py         # Primary screen size (AppKit, with fallback)
└── tests/
    ├── test_config.py
    ├── test_camera.py
    ├── test_tracker.py       # incl. one real-MediaPipe integration test
    ├── test_features.py
    ├── test_normalization.py
    ├── test_smoothing.py
    ├── test_mapping.py
    ├── test_gestures.py
    ├── test_confidence.py
    ├── test_cooldown.py
    ├── test_state_machine.py
    ├── test_engine.py        # vision + gesture pipeline integration test
    ├── test_registry.py
    ├── test_safety.py
    ├── test_router.py        # incl. click/drag deadzone behavior
    ├── test_simulation.py    # full pipeline → fake adapter integration test
    ├── test_permissions.py
    ├── test_real_adapter.py
    └── vision_helpers.py     # synthetic hand-pose builders used by tests
```

The full recommended structure (`ui/`, `audio/`, `persistence/`) is
added incrementally as each phase needs it, rather than scaffolded empty
up front.

## Privacy (current state)

All processing is local. The vision pipeline (Phase 2) never logs,
saves, or uploads a camera frame — only scalar feature values ever leave
`camera.py`/`tracker.py` (Section 33). `FakeMacOSAdapter` (Simulation
Mode) only records calls in memory. `RealMacOSAdapter` can move the
cursor and click (Phases 5-6) via Quartz once Accessibility permission
is granted — nothing else on the real OS yet.

## Testing

```bash
pytest              # full suite, including one real-MediaPipe smoke test
pytest -m "not integration"   # skip the real-MediaPipe test (fakes only)
```

Camera, hand-tracking, permission, and real-adapter tests all use
injected fake backends — no physical webcam, no macOS process, and no
permission prompt is required to run the suite. One test (marked
`integration`) exercises the real MediaPipe runtime against a synthetic
blank frame. `test_simulation.py` runs the entire pipeline — synthetic
hand poses → vision → gesture engine → command router → fake adapter —
end to end. Timing-sensitive tests (state machine, safety rate limiting,
drag engagement) all use an explicit fake/deterministic clock rather
than real wall time — real time introduced a genuine flaky-test bug
during Phase 6 development (rate limiting occasionally tripped on
back-to-back calls purely from Python's own per-statement overhead),
which is exactly the kind of failure a fake clock is meant to prevent.
`RealMacOSAdapter`'s actual Quartz calls are not exercised by this suite
(there's no macOS/display to run them against here) — everything around
them (mapping math, permission logic, drag deadzone, router dispatch
and error handling) is. The suite never touches the real mouse,
keyboard, or a real macOS application.

## Roadmap

1. **macOS + VS Code foundation** ✅
2. **Vision** ✅ — OpenCV camera, MediaPipe hand tracking, feature
   extraction, palm-width normalization, EMA smoothing
3. **Gesture intelligence** ✅ — gesture vocabulary
   (pinch/open_palm/fist/point), temporal voting, state machine with
   hysteresis + min hold time, per-gesture cooldown
4. **Simulation** ✅ — command registry, router, safety policy
   (control-state gate + rate limiting, with a release-never-blocked
   exception), fake macOS adapter
5. **macOS cursor** ✅ — Accessibility permission check/request,
   fingertip-to-screen mapping (mirror + active region + sensitivity +
   smoothing), Quartz-backed cursor movement
6. **Click + drag** ✅ *(this phase)* — real Quartz mouse_down/mouse_up,
   dragging-aware cursor movement, click-vs-drag engagement deadzone
7. Scroll
4. Simulation — command registry, router, safety layer, fake macOS adapter
5. macOS cursor — permissions, fingertip mapping, cursor movement
6. Click + drag
7. Scroll
8. App switching + safe launcher
9. Media + Spaces
10. Product polish — calibration wizard, settings UI, themes, audio
11. Reliability — permission UX, stress testing, latency profiling
12. Documentation — full README, architecture diagram, troubleshooting
