"""
Audio feedback (Section 26 — UX polish).

Synthesizes short tones for gesture events (click, release, app/space
switch, error) rather than shipping binary asset files — a handful of
numpy sine-wave buffers is simpler, smaller, and license-free.

Respects AudioSettings (enabled/volume); never raises if the audio
device can't be opened (e.g. a headless dev machine, or no speakers) —
``start()`` just reports False and every subsequent ``play()`` becomes
a silent no-op, the same "degrade, don't crash" pattern used by
camera.py and the macOS adapters.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger("gestureos.audio.feedback")

_SAMPLE_RATE = 44100


class FeedbackSound(str, Enum):
    CLICK = "click"
    RELEASE = "release"
    SWITCH = "switch"
    ERROR = "error"


# (frequency_hz, duration_s) per sound.
_TONES: dict[FeedbackSound, tuple[float, float]] = {
    FeedbackSound.CLICK: (880.0, 0.05),
    FeedbackSound.RELEASE: (660.0, 0.05),
    FeedbackSound.SWITCH: (523.0, 0.09),
    FeedbackSound.ERROR: (220.0, 0.15),
}


def synthesize_tone(frequency: float, duration_s: float, sample_rate: int = _SAMPLE_RATE):
    """Returns a numpy int16 stereo array for a short sine-wave tone
    with a linear fade-out (avoids an audible click at the end).

    Pure and side-effect-free — no pygame/audio-device dependency, so
    it's testable without a mixer.
    """
    import numpy as np

    n_samples = max(1, int(sample_rate * duration_s))
    t = np.linspace(0, duration_s, n_samples, endpoint=False)
    wave = np.sin(2 * np.pi * frequency * t)
    fade = np.linspace(1.0, 0.0, n_samples)
    wave = wave * fade
    stereo = np.column_stack((wave, wave))
    return (stereo * 32767 * 0.4).astype(np.int16)


class AudioFeedback:
    """Owns the pygame mixer and a small cache of pre-synthesized tones."""

    def __init__(self, enabled: bool = True, volume: float = 0.6) -> None:
        self.enabled = enabled
        self.volume = volume
        self._sounds: dict[FeedbackSound, Any] = {}
        self._ready = False

    def start(self) -> bool:
        """Initialize the mixer and synthesize all tones. Returns
        whether audio is actually usable — callers should treat False
        as a normal, non-fatal outcome.
        """
        if not self.enabled:
            return False
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=_SAMPLE_RATE, size=-16, channels=2)
            for sound_type, (freq, duration) in _TONES.items():
                waveform = synthesize_tone(freq, duration)
                self._sounds[sound_type] = pygame.sndarray.make_sound(waveform)
            self._ready = True
        except Exception as exc:  # noqa: BLE001 - no audio device, missing deps, etc.
            logger.warning("audio_unavailable", extra={"fields": {"error": type(exc).__name__}})
            self._ready = False
        return self._ready

    def play(self, sound: FeedbackSound) -> None:
        if not self.enabled or not self._ready:
            return
        cached = self._sounds.get(sound)
        if cached is None:
            return
        try:
            cached.set_volume(max(0.0, min(1.0, self.volume)))
            cached.play()
        except Exception as exc:  # noqa: BLE001
            logger.warning("audio_play_failed", extra={"fields": {"error": type(exc).__name__}})

    def stop(self) -> None:
        self._sounds.clear()
        self._ready = False
