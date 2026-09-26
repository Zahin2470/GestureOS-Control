# Troubleshooting

GestureOS logs structured `key=value` lines for everything that
matters (see `utils/logging.py`). This guide is organized by symptom;
each entry names the log event(s) you'd see with `--debug` so you can
confirm you're looking at the right cause.

Run with `python main.py --debug` to see everything below at `INFO`/
`DEBUG` level in the console and in the log file (path shown in the
[README](../README.md)'s Setup section — under your platform's
application-support directory).

---

## The window opens but nothing tracks my hand

**Check the HUD first.** It shows `Camera: AVAILABLE/UNAVAILABLE` and
`Hand detected: YES/no` directly — that's the fastest diagnosis.

### Camera shows UNAVAILABLE

Look for `camera_unavailable` (index shown in `fields`) or
`camera_open_exception` in the log.

- **Most common cause on a real Mac: the Camera permission, not
  Accessibility.** The first time GestureOS opens the webcam, macOS
  prompts for Camera access separately from the Accessibility
  permission the HUD tracks. If you dismissed or denied that prompt,
  `cv2.VideoCapture` fails silently from Python's side — it just looks
  like "no camera." Check System Settings → Privacy & Security →
  Camera, and enable it for the app running GestureOS (Terminal, VS
  Code, or whichever process launched `python main.py`).
- **Wrong camera index.** `--camera 1` targets a second camera; if you
  only have a built-in webcam, use `--camera 0` (the default) or omit
  the flag.
- **Another app is holding the camera.** macOS generally allows only
  one process to read a given camera at a time. Close Zoom/FaceTime/
  Photo Booth/etc. and relaunch.
- **Running in this project's own test/dev sandbox**: there is no
  camera at all, and `camera_unavailable` is expected — the app is
  designed to keep running without vision in that case
  (`camera_unavailable_running_without_vision`).

### Camera shows AVAILABLE but Hand detected stays "no"

- Make sure your whole hand is in frame, reasonably well lit, and not
  too close to the edge — MediaPipe's detection confidence
  (`vision.detection_confidence` in settings, default `0.7`) has to be
  met.
- Try lowering `detection_confidence`/`tracking_confidence` via a
  direct settings.json edit (there's no in-app control for these yet —
  the settings panel covers control-layer values, not vision-model
  thresholds).
- If you're consistently too close or too far, that's what the
  calibration wizard's active region is for once tracking works — it
  doesn't fix detection itself, only where in-frame the cursor range
  sits.

---

## Gestures aren't recognized reliably

- **Check `Last gesture` in the HUD** — if it's flickering between
  values or stuck on `none`, the issue is upstream classification, not
  the command bindings.
- Gestures need to be held steady for `gesture_hold_time_s` (default
  0.15s) before they're confirmed — a very quick pose won't register,
  by design (this is the same debounce that keeps a stray frame from
  misfiring a click).
- `FIST` and `POINT` in particular rely on a simple tip-vs-joint
  distance heuristic (see `interaction/gestures.py`); unusual hand
  poses or an unusual camera angle can confuse it. There's no
  per-user gesture retraining in this project — the heuristic is fixed.
- Two hands in frame at once are tracked independently; if you only
  meant to gesture with one, keep the other clearly out of frame or
  resting out of camera view, since a second hand showing a
  recognizable pose will also route commands.

---

## The cursor doesn't move (or clicks don't do anything) on a real Mac

Check the HUD's `Accessibility` field.

- **`DENIED`**: press `A` to open System Settings directly to the
  Accessibility pane (`open_accessibility_settings` in the log), then
  enable GestureOS (or the terminal/VS Code process running it).
  `PermissionFlow` re-checks automatically every few seconds — no
  restart needed once you grant it (watch for
  `permission_status_changed` in the log).
- **`UNAVAILABLE`**: the permission check itself failed — this
  normally means you're not running on macOS at all (this project's own
  test/dev sandbox always shows this).
- **`GRANTED` but still nothing happens**: check for
  `command_not_implemented` (an adapter method isn't built yet — see
  the Gesture Reference table in the README for what's actually wired)
  or `command_dispatch_failed` (an unexpected OS-level error; the
  `error` field names the exception type).
- **Running with `--simulate`**: this is expected — `FakeMacOSAdapter`
  never touches the real OS. Remove `--simulate` for real control.

---

## A command seems to silently do nothing

Every command that doesn't dispatch logs exactly why:

| Log event | Meaning |
|---|---|
| `command_blocked` (`reason=control_paused`) | You pressed `P` (or control is otherwise paused) |
| `command_blocked` (`reason=rate_limited`) | Commands are arriving faster than `max_commands_per_second` allows |
| `command_blocked` (`reason=no_allowlist_configured`) | A `LAUNCH_APP` command with no allowlist set — blocked by design, fail-closed |
| `command_blocked` (`reason=app_not_allowed`) | A `LAUNCH_APP` command for an app not in the allowlist |
| `command_unhandled` | The registry resolved a `CommandType` the router has no handler for — this would be a real bug, please report it |
| `command_not_implemented` | The adapter method exists but isn't built for this phase yet |
| `command_dispatch_failed` | The adapter raised something unexpected; `error` names the exception |

None of these crash the app — that's intentional (see
[ARCHITECTURE.md](ARCHITECTURE.md#why-safety-is-a-separate-layer-from-the-router)).

---

## Settings changes (calibration, sensitivity) don't seem to stick

- Settings only save on: closing the settings panel (`S` again),
  finishing calibration, or normal app exit. If GestureOS is killed
  forcefully (not via `Esc` or window close), the last save is what's
  on disk.
- Check for `settings_save_failed` in the log — this means the settings
  directory couldn't be written to (permissions issue on the
  application-support directory).
- A corrupted `settings.json` falls back to defaults automatically and
  logs `settings_corrupted_using_defaults` rather than crashing —
  if your changes seem to have vanished, check for that line.

---

## High latency / low FPS

The HUD shows `FPS` and `Latency` (total across all pipeline stages)
directly. For a breakdown by stage, check the periodic `pipeline_latency`
log line (every 5 seconds) — it lists `capture`, `tracking`, `features`,
`gesture_engine`, and `routing` individually, each a rolling average in
milliseconds.

- **`tracking` dominates**: this is MediaPipe's own inference cost —
  expected to be the largest single stage. There's no GPU-acceleration
  toggle in this project.
- **`capture` is unexpectedly high**: often a camera resolution
  mismatch — `vision.resolution` in settings defaults to 1280x720;
  a very high native resolution camera without an explicit resolution
  request can cost more per frame than expected.
- **Everything is fast but FPS is still low**: check you're not running
  with `--debug` writing to a slow disk, or that nothing else on the
  system is contending for the camera/CPU.

---

## Audio feedback doesn't play

- Check `audio_unavailable` in the log — this fires whenever the mixer
  can't initialize (no audio device, or `audio.enabled` is `false` in
  settings) and is treated as non-fatal everywhere, by design.
- Volume is controlled via the settings panel (`S`, then arrow keys on
  "Audio volume") or `audio.volume` in settings.json directly.

---

## Something else is wrong

Run with `--debug` and look for the specific structured log line right
before the problem — every failure mode in this project logs a named
event with enough context (`fields={...}`) to identify it, rather than
failing silently. If you find a genuine gap, see
[CONTRIBUTING.md](CONTRIBUTING.md) for how the test suite is organized
before filing or fixing it.
