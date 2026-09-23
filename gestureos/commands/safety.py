"""
Safety policy (Section 22) — the last gate every Command passes through
before the router will dispatch it to a macOS adapter.

Two independent checks:

  1. Control state — commands are blocked whenever the app is paused
     (ControlState.PAUSED), regardless of gesture confidence. This is
     the same control_state the UI shell already displays (Phase 1).

  2. Rate limiting — a defensive cap on command frequency, independent
     of the gesture-level cooldown already enforced upstream (Section
     11), so a malfunctioning binding can't spam the OS.

One deliberate exception to both checks: RELEASE_COMMAND_TYPES (e.g.
MOUSE_UP) are always allowed through. Blocking a *release* is more
dangerous than allowing one — it can leave a mouse button stuck down on
the real OS. Pausing control or hitting the rate limit should never be
able to do that.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from gestureos.commands.types import RELEASE_COMMAND_TYPES, Command
from gestureos.models import ControlState

logger = logging.getLogger("gestureos.commands.safety")


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str | None = None


class SafetyPolicy:
    def __init__(
        self,
        get_control_state: Callable[[], ControlState],
        max_commands_per_second: float = 20.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_commands_per_second <= 0:
            raise ValueError("max_commands_per_second must be positive")
        self._get_control_state = get_control_state
        self._min_interval_s = 1.0 / max_commands_per_second
        self._clock = clock or time.monotonic
        self._last_command_time: float | None = None

    def check(self, command: Command) -> SafetyDecision:
        if command.type in RELEASE_COMMAND_TYPES:
            return SafetyDecision(allowed=True)

        if self._get_control_state() is not ControlState.ACTIVE:
            return SafetyDecision(allowed=False, reason="control_paused")

        now = self._clock()
        if (
            self._last_command_time is not None
            and (now - self._last_command_time) < self._min_interval_s
        ):
            return SafetyDecision(allowed=False, reason="rate_limited")

        self._last_command_time = now
        return SafetyDecision(allowed=True)
