"""
Cooldown gate (Section 11).

A small, generic per-key rate limiter. The gesture state machine uses it
so a gesture that just ended cannot immediately restart (a noisy
release-then-re-pinch shouldn't double-trigger a click). It takes an
arbitrary hashable key rather than being pinch-specific, so later phases
can reuse it for command-level cooldowns (e.g. rate-limiting app
switches) without a new implementation.
"""

from __future__ import annotations

from collections.abc import Hashable


class CooldownGate:
    """Tracks a last-triggered timestamp per key and reports readiness."""

    def __init__(self, cooldown_s: float) -> None:
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be >= 0")
        self.cooldown_s = cooldown_s
        self._last_triggered: dict[Hashable, float] = {}

    def is_ready(self, key: Hashable, now: float) -> bool:
        last = self._last_triggered.get(key)
        if last is None:
            return True
        return (now - last) >= self.cooldown_s

    def mark_triggered(self, key: Hashable, now: float) -> None:
        self._last_triggered[key] = now

    def reset(self, key: Hashable | None = None) -> None:
        if key is None:
            self._last_triggered.clear()
        else:
            self._last_triggered.pop(key, None)
