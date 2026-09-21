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

> **Status: Phase 2 — Vision.**
> Camera capture, MediaPipe hand tracking, feature extraction, scale
> normalization, and jitter smoothing are implemented and tested. There is
> no gesture recognition or macOS command execution yet — the vision
> engine only produces structured per-frame hand features. See
> [Roadmap](#roadmap) below.

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
│   └── vision/
│       ├── camera.py         # OpenCV capture wrapper (injectable backend)
│       ├── tracker.py         # MediaPipe hand tracking adapter
│       ├── features.py       # Raw landmarks → structured HandFeatures
│       ├── normalization.py  # Palm-width scale normalization
│       └── smoothing.py      # Per-hand exponential smoothing (EMA)
└── tests/
    ├── test_config.py
    ├── test_camera.py
    ├── test_tracker.py       # incl. one real-MediaPipe integration test
    ├── test_features.py
    ├── test_normalization.py
    ├── test_smoothing.py
    └── vision_helpers.py     # synthetic hand-pose builders used by tests
```

The full recommended structure (`interaction/`, `commands/`, `macos/`,
`ui/`, `audio/`, `persistence/`) is added incrementally as each phase
needs it, rather than scaffolded empty up front.

## Privacy (current state)

All processing is local. The vision pipeline (Phase 2) never logs, saves,
or uploads a camera frame — only scalar feature values (positions,
distances, states) ever leave `camera.py`/`tracker.py` (Section 33).

## Testing

```bash
pytest              # full suite, including one real-MediaPipe smoke test
pytest -m "not integration"   # skip the real-MediaPipe test (fakes only)
```

Camera and hand-tracking tests use injected fake backends — no physical
webcam is required to run the suite. One test (marked `integration`)
exercises the real MediaPipe runtime against a synthetic blank frame as
an end-to-end sanity check. Each later phase adds its own test module
(gesture state machine, safety policy, macOS adapters via mocks, etc.)
per the spec's test plan — the suite never touches the real mouse,
keyboard, or a real macOS application.

## Roadmap

1. **macOS + VS Code foundation** ✅
2. **Vision** ✅ *(this phase)* — OpenCV camera, MediaPipe hand tracking,
   feature extraction, palm-width normalization, EMA smoothing
3. Gesture intelligence — state machine, temporal confirmation, cooldown
4. Simulation — command registry, router, safety layer, fake macOS adapter
5. macOS cursor — permissions, fingertip mapping, cursor movement
6. Click + drag
7. Scroll
8. App switching + safe launcher
9. Media + Spaces
10. Product polish — calibration wizard, settings UI, themes, audio
11. Reliability — permission UX, stress testing, latency profiling
12. Documentation — full README, architecture diagram, troubleshooting
