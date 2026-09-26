"""
Permission walkthrough (Phase 11).

Phase 5 could only report Accessibility permission status once at
startup. This adds the actual guided flow:

  - ``open_accessibility_settings()`` opens System Settings directly to
    the right pane, instead of just telling the user where to go.
  - ``PermissionFlow`` re-checks periodically through a running
    session, so granting permission *while GestureOS is running* is
    noticed within one recheck interval — no restart required.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from gestureos.macos.permissions import PermissionStatus, check_accessibility_permission

logger = logging.getLogger("gestureos.macos.permission_flow")

ACCESSIBILITY_PANE_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)


def _default_open_url(url: str) -> bool:
    from AppKit import NSURL, NSWorkspace  # Lazy: only needed on a real Mac.

    ns_url = NSURL.URLWithString_(url)
    return bool(NSWorkspace.sharedWorkspace().openURL_(ns_url))


def open_accessibility_settings(open_url: Callable[[str], bool] = _default_open_url) -> bool:
    """Open System Settings → Privacy & Security → Accessibility.

    Returns whether the URL was handed off successfully — that's not
    the same as the user having granted permission yet, just that the
    settings pane opened rather than the request failing outright.
    """
    try:
        opened = open_url(ACCESSIBILITY_PANE_URL)
    except Exception as exc:  # noqa: BLE001 - not on macOS, AppKit missing, etc.
        logger.warning("open_settings_failed", extra={"fields": {"error": type(exc).__name__}})
        return False
    logger.info("opened_accessibility_settings", extra={"fields": {"opened": opened}})
    return opened


class PermissionFlow:
    """Tracks Accessibility permission status across a running session.

    ``poll()`` is cheap to call every frame — it only actually re-checks
    once per ``recheck_interval_s``, so the real (possibly slow) system
    call doesn't run 60 times a second.
    """

    def __init__(
        self,
        recheck_interval_s: float = 3.0,
        clock: Callable[[], float] | None = None,
        checker: Callable[[], PermissionStatus] = check_accessibility_permission,
    ) -> None:
        if recheck_interval_s <= 0:
            raise ValueError("recheck_interval_s must be positive")
        self.recheck_interval_s = recheck_interval_s
        self._clock = clock or time.monotonic
        self._checker = checker
        self.status: PermissionStatus = PermissionStatus.UNAVAILABLE
        self._last_check: float | None = None

    def check_now(self) -> PermissionStatus:
        """Force an immediate check, bypassing the recheck interval."""
        previous = self.status
        self.status = self._checker()
        self._last_check = self._clock()
        if self.status != previous:
            logger.info(
                "permission_status_changed",
                extra={"fields": {"from": previous.value, "to": self.status.value}},
            )
        return self.status

    def poll(self) -> PermissionStatus:
        """Call every frame; only actually re-checks every
        ``recheck_interval_s``.
        """
        now = self._clock()
        if self._last_check is None or (now - self._last_check) >= self.recheck_interval_s:
            self.check_now()
        return self.status

    @property
    def needs_attention(self) -> bool:
        return self.status is not PermissionStatus.GRANTED
