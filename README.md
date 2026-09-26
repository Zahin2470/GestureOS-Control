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

> **Status: complete — all 12 phases delivered.**
>
> GestureOS went from an empty repo to a fully-wired live application in
> twelve phases: foundation → vision → gesture recognition → a simulated
> command layer → real macOS cursor control → click/drag → scroll → app
> switching + a fail-closed app launcher → media/Spaces → live pipeline
> wiring with a calibration wizard, settings panel, themes, and audio →
> reliability (permission walkthrough, stress testing, latency profiling)
> → this documentation. See [docs/CHANGELOG.md](docs/CHANGELOG.md) for
> exactly what each phase delivered, in order, including the two real
> bugs found and fixed along the way.
>
> **What's genuinely verified vs. what isn't:** everything through the
> command router — vision, gesture recognition, temporal voting, state
> machines, safety policy, command routing, the live app shell's own
> logic — runs against real code with real (if synthetic, camera-less)
> inputs and is covered by the test suite. `RealMacOSAdapter`'s actual
> Quartz/AppKit calls and on-screen cursor/click/scroll/switching
> behavior have never run against a real Mac at any point in this
> project's development, because one was never available. That gap is
> named plainly in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and in
> the [Known Limitations](#known-limitations) section below rather than
> glossed over.
>
> See [Roadmap](#roadmap) for the full phase list, or jump to
> [Documentation](#documentation) for the architecture, troubleshooting,
> and contribution guides.

---

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
├── LICENSE
├── docs/
│   ├── ARCHITECTURE.md
│   ├── TROUBLESHOOTING.md
│   ├── CONTRIBUTING.md
│   └── CHANGELOG.md
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
11. **Reliability** ✅ — periodic permission re-checking plus a
    one-key System Settings walkthrough, thousands-of-frames stress
    testing with real invariant checks, per-stage latency profiling in
    the HUD and logs
12. **Documentation** ✅ *(this phase)* — architecture diagram,
    troubleshooting guide, contribution notes, changelog, license

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — pipeline diagram,
  the types that flow between layers, and the reasoning behind the
  bigger design decisions (why safety is a separate layer, why the fake
  and real adapters share one interface, how the test suite avoids
  needing real hardware).
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — organized by
  symptom, mapping real log events (`camera_unavailable`,
  `command_blocked`, `accessibility_permission_missing`, etc.) to
  causes and fixes.
- **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** — the conventions
  every phase followed (lazy macOS imports, injectable backends, fake
  clocks, structured logging, degrade-don't-crash), how to add a new
  gesture or command binding, and a map of what each test file covers.
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** — what every phase
  actually delivered, in the order it was built, including the two real
  bugs found and fixed along the way (a flaky rate-limiter test in
  Phase 6, a wasted-frame cooldown transition in Phase 3).

## Known Limitations

- **Never run on a real Mac.** This entire project was developed in a
  Linux sandbox with no camera, no display, and no macOS. Every Quartz/
  AppKit call in `RealMacOSAdapter`, and the live camera-to-cursor
  behavior end to end, is written correctly against documented APIs and
  covered by tests wherever the logic around it can be isolated — but
  the calls themselves have not been executed against a real Mac. This
  is the single biggest thing to verify before relying on this project.
- **No profile system.** `--profile`/`active_profile` only ever store a
  name; no phase built switchable binding sets.
- **No per-user gesture retraining.** The five gestures are fixed
  geometric heuristics. Unusual hand shapes or camera angles aren't
  something you can retrain — only the cursor's active region is
  user-calibratable.
- **App launching has no UI yet.** `SafetyPolicy`'s allowlist mechanism
  and `RealMacOSAdapter.launch_app` are both real and tested, but
  nothing in the live app currently configures an allowlist or binds a
  gesture to a specific app — Phase 8 built the (fail-closed) mechanism,
  not a way to use it yet.
- **Media-key simulation relies on an undocumented macOS technique**
  (see `real_adapter.py`'s `media_play_pause` and
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)) since there is no public
  Quartz constant for it. It's a widely-used pattern, but "undocumented"
  means Apple could change its behavior in a future macOS release
  without notice.
- **No GPU acceleration toggle** for MediaPipe inference, which is
  consistently the most expensive pipeline stage (see
  [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#high-latency--low-fps)).

## FAQ

**Does this actually work?**
The logic does, and is genuinely tested — 270+ tests, no mocking
library, real (if synthetic) inputs throughout. Whether the real Quartz
calls behave exactly as written on your specific macOS version is the
one thing only running it on a real Mac can confirm.

**Why VS Code specifically, and not a packaged .app?**
That's how the original project spec was scoped from Phase 1 — run and
debug from the editor, not distributed as a signed, notarized
application. Packaging it that way would be a reasonable future
direction but isn't part of this project.

**Can I use this with just a webcam and no Mac, e.g. to test the vision
pipeline?**
Yes — `--simulate` runs the entire pipeline including real camera
capture and real MediaPipe tracking, it just never calls into Quartz/
AppKit. That's exactly how most of this project's own manual testing
was done.

**Why does clicking sometimes feel like it "snaps" the cursor?**
By design — `PINCH START` snaps the cursor exactly to the pinch point
before clicking, for precision, rather than clicking wherever the
cursor happened to already be.

**I found a bug. Now what?**
See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the conventions
and test-file map before diving in — the injectable-backend and
fake-clock patterns in particular make most bugs reproducible without
needing the same hardware that triggered them.

## License

[MIT](LICENSE).

