"""
GestureOS application shell (Phase 1).

This is intentionally a *shell*: it opens a window, shows status, and
exits cleanly. The vision engine, gesture state machine, command router,
and macOS adapters are added in later phases and will be driven from the
``App.run()`` loop added here — gesture code must never talk to macOS
automation directly (Section 20), so this loop is where that
orchestration will live.
"""

from __future__ import annotations

import logging
import sys

import pygame

from gestureos.config import Config
from gestureos.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_WINDOW_TITLE,
    TARGET_FPS,
)
from gestureos.models import ControlState, RunMode, Theme

logger = logging.getLogger("gestureos.app")

# Phase 1 renders one static palette per theme; later phases (Section 24)
# will expand this into a full theming module under gestureos/ui/.
_THEME_COLORS: dict[Theme, dict[str, tuple[int, int, int]]] = {
    Theme.DARK: {"bg": (14, 16, 22), "fg": (230, 232, 240), "accent": (64, 200, 255)},
    Theme.LIGHT: {"bg": (245, 246, 248), "fg": (20, 20, 24), "accent": (0, 110, 200)},
    Theme.NEON: {"bg": (8, 6, 20), "fg": (240, 240, 255), "accent": (255, 0, 200)},
    Theme.HIGH_CONTRAST: {"bg": (0, 0, 0), "fg": (255, 255, 255), "accent": (255, 220, 0)},
}


class App:
    """Owns the window lifecycle for the Phase 1 shell."""

    def __init__(self, config: Config, run_mode: RunMode = RunMode.NORMAL) -> None:
        self.config = config
        self.run_mode = run_mode
        self.control_state = ControlState.ACTIVE
        self._screen: pygame.Surface | None = None
        self._clock: pygame.time.Clock | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        """Initialize pygame and open the window.

        Returns False (and logs a clear reason) instead of raising, so
        main.py can exit with a readable message rather than a traceback.
        """
        try:
            pygame.init()
            pygame.display.set_caption(f"{DEFAULT_WINDOW_TITLE}")
            self._screen = pygame.display.set_mode(DEFAULT_WINDOW_SIZE)
            self._clock = pygame.time.Clock()
        except pygame.error as exc:
            logger.error(
                "display_init_failed",
                extra={"fields": {"reason": str(exc)}},
            )
            return False
        return True

    def run(self) -> int:
        """Run the main loop until the window is closed or ESC is pressed.

        Returns a process exit code.
        """
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
                }
            },
        )

        try:
            while self._running:
                self._handle_events()
                self._render()
                self._clock.tick(TARGET_FPS)
        finally:
            self.cleanup()

        return 0

    def cleanup(self) -> None:
        """Central cleanup hook (Section 28).

        Phase 1 has no active mouse/keyboard state to release yet, but
        this is the single place later phases will call into on any
        camera failure, exception, Ctrl+C, or emergency stop — so the
        shape is established now rather than bolted on later.
        """
        logger.info("app_stopping", extra={"fields": {}})
        pygame.quit()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                logger.info("emergency_stop_keyboard", extra={"fields": {}})
                self._running = False

    def _render(self) -> None:
        assert self._screen is not None
        theme = self.config.settings.ui.theme
        colors = _THEME_COLORS.get(theme, _THEME_COLORS[Theme.DARK])

        self._screen.fill(colors["bg"])

        title_font = pygame.font.SysFont("Menlo,Consolas,monospace", 42, bold=True)
        subtitle_font = pygame.font.SysFont("Menlo,Consolas,monospace", 18)
        status_font = pygame.font.SysFont("Menlo,Consolas,monospace", 16)

        title_surf = title_font.render(APP_NAME.upper(), True, colors["accent"])
        self._screen.blit(title_surf, (40, 40))

        subtitle_surf = subtitle_font.render(
            "Phase 1 — macOS + VS Code Foundation", True, colors["fg"]
        )
        self._screen.blit(subtitle_surf, (40, 100))

        mode_label = "SIMULATION" if self.run_mode is RunMode.SIMULATION else "NORMAL"
        lines = [
            f"Version        {APP_VERSION}",
            f"Run mode       {mode_label}",
            f"Profile        {self.config.settings.active_profile}",
            f"Control state  {self.control_state.value.upper()}",
            f"Theme          {theme.value}",
            "",
            "Press ESC to exit.",
        ]
        y = 150
        for line in lines:
            surf = status_font.render(line, True, colors["fg"])
            self._screen.blit(surf, (40, y))
            y += 26

        pygame.display.flip()


def build_app(config: Config, run_mode: RunMode) -> App:
    return App(config=config, run_mode=run_mode)


def main_headless_smoke_test() -> None:  # pragma: no cover - manual utility
    """Small manual helper for verifying import/wiring without a display."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    cfg = Config()
    cfg.load()
    app = build_app(cfg, RunMode.NORMAL)
    ok = app.setup()
    print("setup ok:", ok, file=sys.stderr)
    app.cleanup()
