"""
GestureOS application shell.

Phase 1 built a static UI shell. Phase 10 wires the whole pipeline into
its main loop: each frame, if a camera is available, a raw frame flows
through vision (Phase 2) → gesture engine (Phase 3) → command router
(Phases 4-9), and the router dispatches to a real or simulated macOS
adapter depending on run mode. This loop is also where the calibration
wizard, in-app settings panel, theme cycling, and audio feedback
(Phase 10) live — gesture/vision code never talks to macOS automation
or rendering directly (Section 20); this is the one place all of it is
orchestrated together.

Camera absence, tracker start failure, and any other setup problem
degrade to "run without vision" rather than refusing to start — the app
shell and its settings/theme/calibration UI are still useful without a
working camera (and are exactly what's exercised by this project's
headless tests, which have no real camera to offer).
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import pygame

from gestureos.audio.feedback import AudioFeedback, FeedbackSound
from gestureos.commands.router import CommandRouter
from gestureos.commands.safety import SafetyPolicy
from gestureos.commands.types import Command, CommandType
from gestureos.config import Config
from gestureos.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_WINDOW_TITLE,
    TARGET_FPS,
)
from gestureos.interaction.engine import GestureEngine
from gestureos.macos.fake_adapter import FakeMacOSAdapter
from gestureos.macos.permissions import PermissionStatus, check_accessibility_permission
from gestureos.macos.real_adapter import RealMacOSAdapter
from gestureos.macos.screen import get_primary_screen_size
from gestureos.models import ControlState, RunMode, Theme
from gestureos.ui.calibration import CalibrationWizard
from gestureos.ui.settings_panel import SettingsPanel
from gestureos.utils.timing import FPSCounter
from gestureos.vision.camera import Camera
from gestureos.vision.features import FeatureExtractor
from gestureos.vision.mapping import ActiveRegion, CursorMapper
from gestureos.vision.normalization import normalize_frame_features
from gestureos.vision.smoothing import FeatureSmoother
from gestureos.vision.tracker import HandTracker

if TYPE_CHECKING:
    from gestureos.macos.adapter import MacOSAdapter

logger = logging.getLogger("gestureos.app")

_THEME_COLORS: dict[Theme, dict[str, tuple[int, int, int]]] = {
    Theme.DARK: {"bg": (14, 16, 22), "fg": (230, 232, 240), "accent": (64, 200, 255)},
    Theme.LIGHT: {"bg": (245, 246, 248), "fg": (20, 20, 24), "accent": (0, 110, 200)},
    Theme.NEON: {"bg": (8, 6, 20), "fg": (240, 240, 255), "accent": (255, 0, 200)},
    Theme.HIGH_CONTRAST: {"bg": (0, 0, 0), "fg": (255, 255, 255), "accent": (255, 220, 0)},
}
_THEME_ORDER = (Theme.DARK, Theme.LIGHT, Theme.NEON, Theme.HIGH_CONTRAST)

_CAMERA_PREVIEW_SIZE = (160, 90)
_CAMERA_PREVIEW_MARGIN = 20

_SOUND_FOR_COMMAND = {
    CommandType.MOUSE_DOWN: "click",
    CommandType.MOUSE_UP: "release",
    CommandType.APP_SWITCH: "switch",
    CommandType.SPACE_SWITCH: "switch",
    CommandType.MEDIA_PLAY_PAUSE: "switch",
}


class App:
    """Owns the window lifecycle and the live gesture pipeline."""

    def __init__(self, config: Config, run_mode: RunMode = RunMode.NORMAL) -> None:
        self.config = config
        self.run_mode = run_mode
        self.control_state = ControlState.ACTIVE
        self._screen: pygame.Surface | None = None
        self._clock: pygame.time.Clock | None = None
        self._running = False

        # Pipeline components (built in setup()).
        self._camera: Camera | None = None
        self._camera_available = False
        self._tracker: HandTracker | None = None
        self._extractor: FeatureExtractor | None = None
        self._smoother: FeatureSmoother | None = None
        self._engine: GestureEngine | None = None
        self._cursor_mapper: CursorMapper | None = None
        self._safety: SafetyPolicy | None = None
        self._adapter: MacOSAdapter | None = None
        self._router: CommandRouter | None = None
        self._audio: AudioFeedback | None = None
        self._permission_status: PermissionStatus | None = None
        self._fps_counter = FPSCounter()

        # UI state.
        self._settings_panel: SettingsPanel | None = None
        self._show_settings = False
        self._calibration: CalibrationWizard | None = None
        self._camera_surface: pygame.Surface | None = None
        self._fonts: dict[str, pygame.font.Font] = {}

        # HUD-only state, refreshed each processed frame.
        self._last_hand_present = False
        self._last_gesture_label = "—"
        self._last_fps = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        """Initialize pygame, the window, and the full gesture pipeline.

        Returns False (and logs a clear reason) instead of raising, so
        main.py can exit with a readable message rather than a
        traceback — but only for display failure. A missing camera or
        macOS permission degrades gracefully instead (see module
        docstring); it's still a successful setup().
        """
        try:
            pygame.init()
            pygame.display.set_caption(DEFAULT_WINDOW_TITLE)
            self._screen = pygame.display.set_mode(DEFAULT_WINDOW_SIZE)
            self._clock = pygame.time.Clock()
            self._fonts = {
                "title": pygame.font.SysFont("Menlo,Consolas,monospace", 42, bold=True),
                "subtitle": pygame.font.SysFont("Menlo,Consolas,monospace", 18),
                "status": pygame.font.SysFont("Menlo,Consolas,monospace", 16),
                "overlay": pygame.font.SysFont("Menlo,Consolas,monospace", 20, bold=True),
            }
        except pygame.error as exc:
            logger.error("display_init_failed", extra={"fields": {"reason": str(exc)}})
            return False

        self._setup_pipeline()
        return True

    def _setup_pipeline(self) -> None:
        settings = self.config.settings

        self._camera = Camera(index=settings.vision.camera_index, resolution=settings.vision.resolution)
        self._camera_available = self._camera.open()
        if not self._camera_available:
            logger.warning("camera_unavailable_running_without_vision", extra={"fields": {}})

        self._tracker = HandTracker(
            detection_confidence=settings.vision.detection_confidence,
            tracking_confidence=settings.vision.tracking_confidence,
        )
        if self._camera_available:
            try:
                self._tracker.start()
            except Exception as exc:  # noqa: BLE001 - e.g. MediaPipe unavailable
                logger.error(
                    "tracker_start_failed", extra={"fields": {"error": type(exc).__name__}}
                )
                self._camera_available = False

        self._extractor = FeatureExtractor()
        self._smoother = FeatureSmoother()
        self._engine = GestureEngine(
            min_hold_time_s=settings.control.gesture_hold_time_s,
            cooldown_s=settings.control.cooldown_s,
        )

        self._cursor_mapper = self._build_cursor_mapper()
        self._safety = SafetyPolicy(get_control_state=lambda: self.control_state)
        self._adapter = (
            FakeMacOSAdapter() if self.run_mode is RunMode.SIMULATION else RealMacOSAdapter()
        )
        self._router = CommandRouter(self._adapter, self._safety, cursor_mapper=self._cursor_mapper)

        self._audio = AudioFeedback(enabled=settings.audio.enabled, volume=settings.audio.volume)
        self._audio.start()

        if self.run_mode is RunMode.NORMAL:
            self._permission_status = check_accessibility_permission()
            if self._permission_status is not PermissionStatus.GRANTED:
                logger.warning(
                    "accessibility_permission_missing",
                    extra={"fields": {"status": self._permission_status.value}},
                )

        self._settings_panel = SettingsPanel(settings)

    def _build_cursor_mapper(self) -> CursorMapper:
        settings = self.config.settings
        screen_w, screen_h = get_primary_screen_size()
        x_min, x_max, y_min, y_max = settings.control.active_region
        return CursorMapper(
            screen_w,
            screen_h,
            active_region=ActiveRegion(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max),
            mirror=settings.vision.mirror,
            sensitivity=settings.control.cursor_sensitivity,
            smoothing_alpha=settings.control.smoothing or None,
        )

    def run(self) -> int:
        """Run the main loop until the window is closed or ESC is pressed."""
        if self._screen is None or self._clock is None:
            raise RuntimeError("App.run() called before App.setup()")

        self._running = True
        logger.info(
            "app_started",
            extra={
                "fields": {
                    "version": APP_VERSION,
                    "run_mode": self.run_mode.value,
                    "profile": self.config.settings.active_profile,
                    "camera_available": self._camera_available,
                }
            },
        )

        try:
            while self._running:
                self._handle_events()
                self._update_pipeline()
                self._last_fps = self._fps_counter.tick()
                self._render()
                self._clock.tick(TARGET_FPS)
        finally:
            self.cleanup()

        return 0

    def cleanup(self) -> None:
        """Central cleanup hook (Section 28) — releases every resource
        setup() may have acquired, in a safe order, and persists any
        settings changes made during the session (theme, sensitivity,
        calibration). Called on normal exit, Ctrl+C, or a fatal error.
        """
        logger.info("app_stopping", extra={"fields": {}})
        if self._tracker is not None:
            self._tracker.close()
        if self._camera is not None:
            self._camera.release()
        if self._audio is not None:
            self._audio.stop()
        try:
            self.config.save()
        except OSError as exc:
            logger.warning("settings_save_failed", extra={"fields": {"error": type(exc).__name__}})
        pygame.quit()

    # ------------------------------------------------------------------
    # Per-frame pipeline
    # ------------------------------------------------------------------

    def _update_pipeline(self) -> None:
        if not self._camera_available:
            return
        assert self._camera is not None
        assert self._tracker is not None
        assert self._extractor is not None
        assert self._smoother is not None
        assert self._engine is not None
        assert self._router is not None

        frame = self._camera.read()
        if frame is None:
            return

        self._update_camera_preview(frame)

        raw_hands = self._tracker.process(frame)
        frame_features = self._extractor.process(raw_hands)
        frame_features = normalize_frame_features(frame_features)
        frame_features = self._smoother.smooth_frame(frame_features)

        primary_hand = frame_features.hands[0] if frame_features.hands else None
        self._last_hand_present = bool(primary_hand and primary_hand.hand_present)

        if self._calibration is not None and not self._calibration.is_done:
            position = primary_hand.index_tip if primary_hand and primary_hand.hand_present else None
            self._calibration.update(position)
            return  # don't route commands to macOS while calibrating

        intents = self._engine.process(frame_features)
        if intents:
            self._last_gesture_label = intents[-1].gesture.value

        commands = self._router.route_intents(intents)
        for command in commands:
            self._play_feedback_for(command)

    def _update_camera_preview(self, frame: object) -> None:
        try:
            import cv2
            import numpy as np

            small = cv2.resize(frame, _CAMERA_PREVIEW_SIZE)  # type: ignore[call-overload]
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            self._camera_surface = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
        except Exception as exc:  # noqa: BLE001 - preview is cosmetic only
            logger.debug("camera_preview_failed", extra={"fields": {"error": type(exc).__name__}})

    def _play_feedback_for(self, command: Command) -> None:
        if self._audio is None:
            return
        sound_name = _SOUND_FOR_COMMAND.get(command.type)
        if sound_name is None:
            return
        self._audio.play(FeedbackSound(sound_name))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

    def _handle_keydown(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            logger.info("emergency_stop_keyboard", extra={"fields": {}})
            self._running = False
            return

        if key == pygame.K_p:
            self._toggle_control_state()
            return

        if key == pygame.K_t:
            self._cycle_theme()
            return

        if key == pygame.K_s:
            self._show_settings = not self._show_settings
            if not self._show_settings:
                self.config.save()
            return

        if self._show_settings and self._settings_panel is not None:
            self._handle_settings_key(key)
            return

        if key == pygame.K_c:
            self._calibration = CalibrationWizard()
            logger.info("calibration_started", extra={"fields": {}})
            return

        if key == pygame.K_SPACE and self._calibration is not None:
            advanced = self._calibration.confirm()
            if advanced and self._calibration.is_done:
                self._apply_calibration()

    def _handle_settings_key(self, key: int) -> None:
        assert self._settings_panel is not None
        if key == pygame.K_UP:
            self._settings_panel.move_selection(-1)
        elif key == pygame.K_DOWN:
            self._settings_panel.move_selection(1)
        elif key == pygame.K_LEFT:
            self._settings_panel.adjust_selected(-1)
            self._apply_settings_change()
        elif key == pygame.K_RIGHT:
            self._settings_panel.adjust_selected(1)
            self._apply_settings_change()

    def _toggle_control_state(self) -> None:
        self.control_state = (
            ControlState.PAUSED
            if self.control_state is ControlState.ACTIVE
            else ControlState.ACTIVE
        )
        logger.info("control_state_toggled", extra={"fields": {"state": self.control_state.value}})

    def _cycle_theme(self) -> None:
        current = self.config.settings.ui.theme
        index = _THEME_ORDER.index(current) if current in _THEME_ORDER else 0
        self.config.settings.ui.theme = _THEME_ORDER[(index + 1) % len(_THEME_ORDER)]

    def _apply_settings_change(self) -> None:
        if self._router is None or self._cursor_mapper is None:
            return
        self._cursor_mapper = self._build_cursor_mapper()
        self._router.set_cursor_mapper(self._cursor_mapper)
        if self._audio is not None:
            self._audio.volume = self.config.settings.audio.volume

    def _apply_calibration(self) -> None:
        if self._calibration is None or self._calibration.result is None:
            return
        region = self._calibration.result
        self.config.settings.control.active_region = (
            region.x_min,
            region.x_max,
            region.y_min,
            region.y_max,
        )
        self._apply_settings_change()
        self.config.save()
        logger.info("calibration_applied", extra={"fields": {}})

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        assert self._screen is not None
        theme = self.config.settings.ui.theme
        colors = _THEME_COLORS.get(theme, _THEME_COLORS[Theme.DARK])
        self._screen.fill(colors["bg"])

        self._render_header(colors)
        self._render_status(colors)
        self._render_camera_preview()

        if self._calibration is not None and not self._calibration.is_done:
            self._render_calibration_overlay(colors)
        elif self._show_settings and self._settings_panel is not None:
            self._render_settings_overlay(colors)

        pygame.display.flip()

    def _render_header(self, colors: dict[str, tuple[int, int, int]]) -> None:
        assert self._screen is not None
        title_surf = self._fonts["title"].render(APP_NAME.upper(), True, colors["accent"])
        self._screen.blit(title_surf, (40, 40))
        subtitle_surf = self._fonts["subtitle"].render(
            "Phase 10 — Product Polish", True, colors["fg"]
        )
        self._screen.blit(subtitle_surf, (40, 100))

    def _render_status(self, colors: dict[str, tuple[int, int, int]]) -> None:
        assert self._screen is not None
        mode_label = "SIMULATION" if self.run_mode is RunMode.SIMULATION else "NORMAL"
        permission_label = (
            self._permission_status.value.upper() if self._permission_status else "N/A"
        )
        camera_label = "AVAILABLE" if self._camera_available else "UNAVAILABLE"
        hand_label = "YES" if self._last_hand_present else "no"

        lines = [
            f"Version        {APP_VERSION}",
            f"Run mode       {mode_label}",
            f"Profile        {self.config.settings.active_profile}",
            f"Control state  {self.control_state.value.upper()}",
            f"Theme          {self.config.settings.ui.theme.value}",
            f"Camera         {camera_label}",
            f"Accessibility  {permission_label}",
            f"Hand detected  {hand_label}",
            f"Last gesture   {self._last_gesture_label}",
            f"FPS            {self._last_fps:.0f}",
            "",
            "ESC quit   P pause/resume   T theme   C calibrate   S settings",
        ]
        y = 150
        for line in lines:
            surf = self._fonts["status"].render(line, True, colors["fg"])
            self._screen.blit(surf, (40, y))
            y += 24

    def _render_camera_preview(self) -> None:
        assert self._screen is not None
        if self._camera_surface is None:
            return
        width, height = DEFAULT_WINDOW_SIZE
        preview_w, preview_h = _CAMERA_PREVIEW_SIZE
        position = (
            width - preview_w - _CAMERA_PREVIEW_MARGIN,
            height - preview_h - _CAMERA_PREVIEW_MARGIN,
        )
        self._screen.blit(self._camera_surface, position)

    def _render_calibration_overlay(self, colors: dict[str, tuple[int, int, int]]) -> None:
        assert self._screen is not None and self._calibration is not None
        width, height = DEFAULT_WINDOW_SIZE
        overlay = pygame.Surface((width, 90))
        overlay.set_alpha(230)
        overlay.fill(colors["bg"])
        self._screen.blit(overlay, (0, height - 90))
        prompt_surf = self._fonts["overlay"].render(
            self._calibration.prompt, True, colors["accent"]
        )
        self._screen.blit(prompt_surf, (40, height - 60))

    def _render_settings_overlay(self, colors: dict[str, tuple[int, int, int]]) -> None:
        assert self._screen is not None and self._settings_panel is not None
        width, height = DEFAULT_WINDOW_SIZE
        panel_width = 360
        overlay = pygame.Surface((panel_width, height))
        overlay.set_alpha(235)
        overlay.fill(colors["bg"])
        self._screen.blit(overlay, (width - panel_width, 0))

        header_surf = self._fonts["overlay"].render("Settings", True, colors["accent"])
        self._screen.blit(header_surf, (width - panel_width + 24, 30))

        y = 80
        for row in self._settings_panel.display_rows():
            surf = self._fonts["status"].render(row, True, colors["fg"])
            self._screen.blit(surf, (width - panel_width + 24, y))
            y += 28

        hint_surf = self._fonts["status"].render(
            "↑↓ select   ←→ adjust   S close", True, colors["fg"]
        )
        self._screen.blit(hint_surf, (width - panel_width + 24, height - 40))


def build_app(config: Config, run_mode: RunMode) -> App:
    return App(config=config, run_mode=run_mode)


def main_headless_smoke_test() -> None:  # pragma: no cover - manual utility
    """Small manual helper for verifying import/wiring without a display."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    cfg = Config()
    cfg.load()
    app = build_app(cfg, RunMode.SIMULATION)
    ok = app.setup()
    print("setup ok:", ok, file=sys.stderr)
    app.cleanup()
