"""
Primary screen size (Section 12 — needed to build a CursorMapper).

A single small function, lazily importing AppKit so this module can be
imported on any platform. On a real failure (not macOS, or AppKit
unavailable) it falls back to a common default resolution and logs a
warning rather than crashing — losing exact screen dimensions should
degrade cursor accuracy, not take down the app.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("gestureos.macos.screen")

_FALLBACK_SIZE = (1920.0, 1080.0)


def get_primary_screen_size() -> tuple[float, float]:
    try:
        from AppKit import NSScreen

        frame = NSScreen.mainScreen().frame()
        width, height = frame.size.width, frame.size.height
        if width <= 0 or height <= 0:
            raise ValueError(f"invalid screen size reported: {width}x{height}")
        return float(width), float(height)
    except Exception as exc:  # noqa: BLE001 - any failure here just falls back
        logger.warning(
            "screen_size_unavailable_using_fallback",
            extra={"fields": {"error": type(exc).__name__, "fallback": _FALLBACK_SIZE}},
        )
        return _FALLBACK_SIZE
