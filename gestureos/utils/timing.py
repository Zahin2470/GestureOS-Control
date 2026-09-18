"""
Timing utilities shared by later phases (vision latency, FPS, command
latency — Section 29). Phase 1 only needs these as generic, tested
building blocks; nothing here fabricates a metric — every value returned
is a real measurement of real elapsed time (Engineering Rule #19).
"""

from __future__ import annotations

import time
from collections import deque


class Stopwatch:
    """Context manager / manual timer for measuring elapsed wall time.

    Usage:
        sw = Stopwatch()
        with sw:
            do_work()
        print(sw.elapsed_ms)
    """

    def __init__(self) -> None:
        self._start: float | None = None
        self.elapsed_s: float = 0.0

    def start(self) -> None:
        self._start = time.perf_counter()

    def stop(self) -> float:
        if self._start is None:
            raise RuntimeError("Stopwatch.stop() called before start()")
        self.elapsed_s = time.perf_counter() - self._start
        self._start = None
        return self.elapsed_s

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_s * 1000.0

    def __enter__(self) -> Stopwatch:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


class RollingAverage:
    """Fixed-window rolling average, used for smoothing real measurements
    (e.g. FPS, per-frame latency) — not for smoothing gesture geometry,
    which belongs to the vision-engine smoothing module in a later phase.
    """

    def __init__(self, window_size: int = 30) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        self._window: deque[float] = deque(maxlen=window_size)

    def add(self, value: float) -> None:
        self._window.append(value)

    @property
    def value(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    def __len__(self) -> int:
        return len(self._window)


class FPSCounter:
    """Real FPS counter driven by actual frame timestamps."""

    def __init__(self, window_size: int = 30) -> None:
        self._avg = RollingAverage(window_size)
        self._last_tick: float | None = None

    def tick(self) -> float:
        """Call once per frame. Returns the current smoothed FPS."""
        now = time.perf_counter()
        if self._last_tick is not None:
            delta = now - self._last_tick
            if delta > 0:
                self._avg.add(1.0 / delta)
        self._last_tick = now
        return self._avg.value
