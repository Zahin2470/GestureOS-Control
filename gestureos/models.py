"""
Shared data models for GestureOS.

Phase 1 only needs the persisted-settings schema and a couple of small
enums for the app shell. Vision/interaction models (Intent, CommandSpec,
etc. — see Sections 9, 20-21 of the master spec) are added in the phases
that introduce them, so this module is not overbuilt ahead of need.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from gestureos.constants import DEFAULT_CAMERA_INDEX, DEFAULT_PROFILE_NAME


class RunMode(str, Enum):
    """How the app is executing (Section 27 — Simulation Mode)."""

    NORMAL = "normal"
    SIMULATION = "simulation"


class ControlState(str, Enum):
    """Whether GestureOS is currently allowed to act (Section 22)."""

    ACTIVE = "active"
    PAUSED = "paused"


class Theme(str, Enum):
    DARK = "dark"
    LIGHT = "light"
    NEON = "neon"
    HIGH_CONTRAST = "high_contrast"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class VisionSettings:
    camera_index: int = DEFAULT_CAMERA_INDEX
    resolution: tuple[int, int] = (1280, 720)
    mirror: bool = True
    detection_confidence: float = 0.7
    tracking_confidence: float = 0.7

    def validate(self) -> None:
        self.camera_index = max(0, int(self.camera_index))
        self.detection_confidence = _clamp(float(self.detection_confidence), 0.0, 1.0)
        self.tracking_confidence = _clamp(float(self.tracking_confidence), 0.0, 1.0)


@dataclass
class ControlSettings:
    cursor_sensitivity: float = 1.0
    smoothing: float = 0.5
    pinch_threshold: float = 0.045
    scroll_sensitivity: float = 1.0
    gesture_hold_time_s: float = 0.15
    cooldown_s: float = 0.35
    active_region: tuple[float, float, float, float] = (0.15, 0.85, 0.15, 0.85)
    # (x_min, x_max, y_min, y_max) — set by the calibration wizard
    # (Phase 10); defaults match mapping.ActiveRegion's own defaults.

    def validate(self) -> None:
        self.cursor_sensitivity = _clamp(float(self.cursor_sensitivity), 0.1, 5.0)
        self.smoothing = _clamp(float(self.smoothing), 0.0, 1.0)
        self.pinch_threshold = _clamp(float(self.pinch_threshold), 0.005, 0.5)
        self.scroll_sensitivity = _clamp(float(self.scroll_sensitivity), 0.1, 5.0)
        self.gesture_hold_time_s = _clamp(float(self.gesture_hold_time_s), 0.0, 3.0)
        self.cooldown_s = _clamp(float(self.cooldown_s), 0.0, 5.0)
        self._validate_active_region()

    def _validate_active_region(self) -> None:
        try:
            x_min, x_max, y_min, y_max = (float(v) for v in self.active_region)
        except (TypeError, ValueError):
            self.active_region = (0.15, 0.85, 0.15, 0.85)
            return
        x_min = _clamp(x_min, 0.0, 0.99)
        x_max = _clamp(x_max, 0.0, 1.0)
        y_min = _clamp(y_min, 0.0, 0.99)
        y_max = _clamp(y_max, 0.0, 1.0)
        if x_max - x_min < 0.1 or y_max - y_min < 0.1:
            self.active_region = (0.15, 0.85, 0.15, 0.85)
        else:
            self.active_region = (x_min, x_max, y_min, y_max)


@dataclass
class UISettings:
    theme: Theme = Theme.DARK
    hud_visible: bool = True
    trail_visible: bool = True
    animations_enabled: bool = True

    def validate(self) -> None:
        if not isinstance(self.theme, Theme):
            try:
                self.theme = Theme(self.theme)
            except ValueError:
                self.theme = Theme.DARK


@dataclass
class AudioSettings:
    enabled: bool = True
    volume: float = 0.6

    def validate(self) -> None:
        self.volume = _clamp(float(self.volume), 0.0, 1.0)


@dataclass
class SafetySettings:
    control_enabled: bool = True
    simulation_mode: bool = False

    def validate(self) -> None:
        pass


@dataclass
class Settings:
    """Root settings object persisted to disk (Section 26)."""

    active_profile: str = DEFAULT_PROFILE_NAME
    vision: VisionSettings = field(default_factory=VisionSettings)
    control: ControlSettings = field(default_factory=ControlSettings)
    ui: UISettings = field(default_factory=UISettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    safety: SafetySettings = field(default_factory=SafetySettings)

    def validate(self) -> Settings:
        """Coerce and clamp all nested settings in place. Returns self."""
        self.vision.validate()
        self.control.validate()
        self.ui.validate()
        self.audio.validate()
        self.safety.validate()
        if not isinstance(self.active_profile, str) or not self.active_profile.strip():
            self.active_profile = DEFAULT_PROFILE_NAME
        return self

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ui"]["theme"] = Theme(self.ui.theme).value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        """Build a Settings object from a (possibly partial/stale) dict.

        Unknown top-level keys are ignored; missing keys fall back to
        defaults. This is what lets Config.load() survive a corrupted or
        older-format settings.json (Section 31).
        """
        settings = cls(
            active_profile=data.get("active_profile", DEFAULT_PROFILE_NAME),
            vision=VisionSettings(**data.get("vision", {})),
            control=ControlSettings(**data.get("control", {})),
            ui=UISettings(**data.get("ui", {})),
            audio=AudioSettings(**data.get("audio", {})),
            safety=SafetySettings(**data.get("safety", {})),
        )
        return settings.validate()
