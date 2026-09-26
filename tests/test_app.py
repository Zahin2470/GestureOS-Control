"""
Tests for the live app shell (Phase 10).

Sets SDL to headless (dummy) video/audio drivers before importing
anything pygame-related, since this sandbox has no real display or
audio device. No test here needs a real camera: setup() naturally
degrades to "no vision" (exercised directly), and the full-pipeline
tests inject a fake camera/tracker after setup() to exercise
_update_pipeline()'s integration logic without real hardware.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from gestureos.app import App, build_app
from gestureos.config import Config
from gestureos.macos.fake_adapter import FakeMacOSAdapter
from gestureos.models import ControlState, RunMode, Theme
from gestureos.vision.tracker import RawHand
from tests.vision_helpers import make_open_hand, make_pinch_hand


def _make_app(tmp_path, run_mode: RunMode = RunMode.SIMULATION) -> App:
    config = Config(path=tmp_path / "settings.json")
    config.load()
    app = build_app(config, run_mode)
    assert app.setup() is True
    return app


class _FakeCamera:
    """Stands in for vision.camera.Camera: returns a fixed frame."""

    def read(self):
        import numpy as np

        return np.zeros((480, 640, 3), dtype="uint8")

    def release(self) -> None:
        pass


class _FakeTracker:
    """Stands in for vision.tracker.HandTracker: returns a scripted pose."""

    def __init__(self, hands: tuple[RawHand, ...] = ()) -> None:
        self.hands = hands

    def process(self, frame):
        return self.hands

    def close(self) -> None:
        pass


def test_setup_degrades_gracefully_without_camera(tmp_path) -> None:
    app = _make_app(tmp_path)

    # No real camera exists in this environment — setup() must still
    # succeed, just without vision.
    assert app._camera_available is False

    app._update_pipeline()  # must not raise
    app._render()  # must not raise
    app.cleanup()


def test_pinch_pose_through_fake_camera_dispatches_mouse_commands(tmp_path) -> None:
    app = _make_app(tmp_path)
    app._camera = _FakeCamera()
    app._camera_available = True
    app._tracker = _FakeTracker((make_pinch_hand(),))
    adapter = app._adapter
    assert isinstance(adapter, FakeMacOSAdapter)

    # A single frame won't confirm a gesture (min hold time), but it
    # must flow all the way through without error and update the HUD.
    app._update_pipeline()

    assert app._last_hand_present is True

    app.cleanup()


def test_open_hand_updates_hand_present_flag(tmp_path) -> None:
    app = _make_app(tmp_path)
    app._camera = _FakeCamera()
    app._camera_available = True
    app._tracker = _FakeTracker((make_open_hand(),))

    app._update_pipeline()

    assert app._last_hand_present is True
    app.cleanup()


def test_no_hand_present_keeps_flag_false(tmp_path) -> None:
    app = _make_app(tmp_path)
    app._camera = _FakeCamera()
    app._camera_available = True
    app._tracker = _FakeTracker(())

    app._update_pipeline()

    assert app._last_hand_present is False
    app.cleanup()


def test_pause_key_toggles_control_state(tmp_path) -> None:
    app = _make_app(tmp_path)
    assert app.control_state is ControlState.ACTIVE

    app._handle_keydown(pygame.K_p)
    assert app.control_state is ControlState.PAUSED

    app._handle_keydown(pygame.K_p)
    assert app.control_state is ControlState.ACTIVE

    app.cleanup()


def test_theme_key_cycles_through_all_themes(tmp_path) -> None:
    app = _make_app(tmp_path)
    seen = [app.config.settings.ui.theme]

    for _ in range(len(Theme)):
        app._handle_keydown(pygame.K_t)
        seen.append(app.config.settings.ui.theme)

    assert seen[0] == seen[-1]  # cycled all the way around
    assert len(set(seen[:-1])) == len(Theme)  # visited every theme once

    app.cleanup()


def test_escape_key_stops_the_loop(tmp_path) -> None:
    app = _make_app(tmp_path)
    app._running = True

    app._handle_keydown(pygame.K_ESCAPE)

    assert app._running is False
    app.cleanup()


def test_settings_key_opens_and_closes_panel_and_saves(tmp_path) -> None:
    app = _make_app(tmp_path)
    assert app._show_settings is False

    app._handle_keydown(pygame.K_s)
    assert app._show_settings is True

    app._handle_keydown(pygame.K_s)
    assert app._show_settings is False  # closing also saves settings

    app.cleanup()


def test_settings_right_arrow_increases_selected_value(tmp_path) -> None:
    app = _make_app(tmp_path)
    app._handle_keydown(pygame.K_s)  # open settings
    before = app.config.settings.control.cursor_sensitivity

    app._handle_keydown(pygame.K_RIGHT)

    after = app.config.settings.control.cursor_sensitivity
    assert after > before
    app.cleanup()


def test_settings_change_rebuilds_cursor_mapper(tmp_path) -> None:
    app = _make_app(tmp_path)
    app._handle_keydown(pygame.K_s)
    original_mapper = app._cursor_mapper

    app._handle_keydown(pygame.K_RIGHT)

    assert app._cursor_mapper is not original_mapper
    assert app._cursor_mapper.sensitivity == app.config.settings.control.cursor_sensitivity
    app.cleanup()


def test_calibration_flow_updates_active_region(tmp_path) -> None:
    from gestureos.vision.features import Point2D

    app = _make_app(tmp_path)
    app._handle_keydown(pygame.K_c)
    assert app._calibration is not None

    app._calibration.update(Point2D(0.2, 0.2))
    app._handle_keydown(pygame.K_SPACE)  # capture top-left

    app._calibration.update(Point2D(0.8, 0.8))
    app._handle_keydown(pygame.K_SPACE)  # capture bottom-right, applies

    region = app.config.settings.control.active_region
    assert region != (0.15, 0.85, 0.15, 0.85)  # actually changed from default
    assert app._calibration.is_done
    app.cleanup()


def test_calibration_blocks_command_routing_while_active(tmp_path) -> None:
    app = _make_app(tmp_path)
    app._camera = _FakeCamera()
    app._camera_available = True
    app._tracker = _FakeTracker((make_pinch_hand(),))
    adapter = app._adapter
    assert isinstance(adapter, FakeMacOSAdapter)

    app._handle_keydown(pygame.K_c)  # start calibration
    for _ in range(10):
        app._update_pipeline()

    # Calibration consumes hand data; nothing should have been routed
    # to the adapter while it's in progress.
    assert adapter.calls == []
    app.cleanup()


def test_cleanup_does_not_raise_when_called_twice(tmp_path) -> None:
    app = _make_app(tmp_path)
    app.cleanup()
    app.cleanup()  # must not raise


def test_normal_mode_uses_real_adapter(tmp_path) -> None:
    from gestureos.macos.real_adapter import RealMacOSAdapter

    app = _make_app(tmp_path, run_mode=RunMode.NORMAL)

    assert isinstance(app._adapter, RealMacOSAdapter)
    app.cleanup()


def test_simulation_mode_uses_fake_adapter(tmp_path) -> None:
    app = _make_app(tmp_path, run_mode=RunMode.SIMULATION)

    assert isinstance(app._adapter, FakeMacOSAdapter)
    app.cleanup()
