# Contributing

This project was built phase-by-phase (see [CHANGELOG.md](CHANGELOG.md)
for the full history), and every phase followed the same conventions
below. Sticking to them keeps the pattern that's let 40+ source files
and 270+ tests stay consistent throughout.

## Setup for development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

```bash
ruff check .          # lint
ruff check --fix .    # lint, auto-fixing what's safe to
mypy gestureos        # type-check (the package only — tests aren't type-checked)
```

All three should be clean before a change is considered done. CI isn't
set up for this project, so this is on the honor system.

## Core conventions

### Lazy-import anything macOS-specific or hardware-specific

`Quartz`, `AppKit`, `ApplicationServices`, `cv2`, and `mediapipe` are
all imported *inside* the function/method that actually needs them, not
at module level. This is why every module in `macos/` and `vision/` can
be imported (and unit tested) on any platform — only calling the real
functionality needs the real dependency. See `macos/real_adapter.py`'s
`_default_quartz_backend()` for the pattern.

### Injectable backends over mocking libraries

Nothing in this project uses `unittest.mock` or a mocking framework.
Instead, anything that talks to hardware, the OS, or wall-clock time
takes an injectable backend/clock as a constructor parameter with a
sensible real default:

```python
class Camera:
    def __init__(self, index=0, backend_factory=_default_backend_factory):
        ...
```

Tests pass a small hand-written fake implementing just the needed
surface. This is more code up front than mocking would be, but the
fakes double as living documentation of exactly what each component
actually needs from its dependency — see `tests/test_camera.py`'s
`FakeBackend`, `tests/test_real_adapter.py`'s `FakeQuartzBackend`, or
`tests/test_app.py`'s `_FakeCamera`/`_FakeTracker` for examples.

### Never trust wall-clock time in a test

Every state machine, safety policy, and gesture controller that cares
about elapsed time takes an injectable `clock: Callable[[], float]`
parameter, defaulting to `time.monotonic`. Tests pass a manually-
advanceable fake clock (see `tests/test_state_machine.py`'s
`FakeClock`, reused throughout). This isn't a style preference — a real
flaky-test bug during Phase 6 (a rate limiter occasionally tripping on
back-to-back calls purely from Python's own per-statement overhead, not
the logic being tested) is why this is a hard rule.

### Structured logging, not print statements

Every log call goes through `utils/logging.py`'s `KeyValueFormatter`,
producing `LEVEL message key=value key=value` lines — see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the full list of event
names already in use. Camera frames, screen contents, and raw landmark
coordinates are never logged (Section 33's local-only, don't-leak-
imagery rule) — only scalar metadata.

### Degrade, don't crash

A missing camera, a denied permission, an unimplemented adapter method,
a corrupted settings file, an audio device that won't open — none of
these raise an unhandled exception up to the user. Each has an explicit
fallback path and a log line explaining what happened. If you add
something that can fail in a way the user doesn't control, it should
fail this way too.

## How to add a new gesture

1. Add a `GestureType` entry in `interaction/gestures.py`.
2. Write a `_..._score(features: HandFeatures) -> float` function
   (0.0-1.0) and add it to the `scores` dict in `classify_gesture()`.
   Use `tests/vision_helpers.py`'s existing pose builders as a
   reference for constructing a synthetic test fixture for the new pose.
3. Write `tests/test_gestures.py` cases confirming your new pose
   classifies correctly and doesn't get confused with existing poses.

Nothing else needs to change — `confidence.py`, `state_machine.py`, and
`engine.py` are all gesture-agnostic.

## How to bind a gesture to a command

1. If the command needs a new `CommandType`, add it in
   `commands/types.py`.
2. Add a `(GestureType, IntentPhase) -> CommandType` entry in
   `commands/registry.py`'s `_BINDINGS` dict.
3. If the command is stateless (fires once, no tracked position), add
   a lambda to `CommandRouter._dispatch` in `router.py`. If it needs to
   track movement across HOLD frames (like drag, scroll, or swipe),
   write a small controller following the `begin()`/`update()`/`end()`
   shape used by `drag.py`/`scroll.py`/`switch.py`, and add an explicit
   `elif command_type is CommandType.YOUR_TYPE:` branch in
   `route_intent()`.
4. Implement the real behavior in `macos/real_adapter.py` (or leave it
   raising `NotImplementedError` with a clear message if it's not
   ready yet — the router already handles that safely).
5. Add tests in `tests/test_registry.py`, `tests/test_router.py`, and
   `tests/test_real_adapter.py`.

## Test file map

| File | Covers |
|---|---|
| `test_config.py` | Settings persistence (load/save/corruption recovery) |
| `test_camera.py`, `test_tracker.py` | Vision hardware wrappers (fakes; one real-MediaPipe integration test) |
| `test_features.py`, `test_normalization.py`, `test_smoothing.py`, `test_mapping.py` | Pure vision geometry |
| `test_gestures.py`, `test_confidence.py`, `test_cooldown.py`, `test_state_machine.py`, `test_engine.py` | Gesture classification and lifecycle |
| `test_registry.py`, `test_safety.py`, `test_router.py` (incl. drag), `test_scroll.py`, `test_switch.py` | Command layer |
| `test_permissions.py`, `test_permission_flow.py`, `test_real_adapter.py` | macOS integration (fakes) |
| `test_simulation.py` | Full pipeline → fake adapter, end to end |
| `test_calibration.py`, `test_settings_panel.py`, `test_audio.py` | Product-polish UI logic |
| `test_profiling.py`, `test_stress.py` | Reliability: latency measurement, adversarial-input invariants |
| `test_app.py` | The live app shell itself — injects a fake camera/tracker after a real `setup()` |

## What this project intentionally doesn't have

- **A profile system.** `--profile`/`active_profile` exist in settings
  but only ever store a name — no phase committed to building
  switchable binding sets, and none did.
- **Per-user gesture retraining.** Gesture classification is a fixed
  geometric heuristic (see `interaction/gestures.py`); there's no
  calibration step for the pose thresholds themselves, only for the
  cursor's active region.
- **CI.** Tests, lint, and type-checking are run locally; there's no
  GitHub Actions workflow in this repo.

If you pick any of these up, keep the conventions above — especially
the injectable-backend and fake-clock patterns — and the rest of the
codebase should stay easy to extend the same way it has been through
all twelve phases.
