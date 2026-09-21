"""
Camera capture (Section 30).

Wraps a capture backend (OpenCV's VideoCapture by default) behind a small
Protocol so this module never has to import OpenCV to be unit tested —
tests inject a fake backend and exercise every error path (camera
unavailable, invalid index, dropped frames) without a physical webcam.

This module never saves or logs frame contents (Section 32/33) — only
scalar metadata (camera index, resolution, whether a frame arrived).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger("gestureos.vision.camera")


class CaptureBackend(Protocol):
    """The minimal surface of cv2.VideoCapture this module depends on."""

    def isOpened(self) -> bool: ...
    def read(self) -> tuple[bool, object]: ...
    def release(self) -> None: ...
    def set(self, prop_id: int, value: float) -> bool: ...
    def get(self, prop_id: int) -> float: ...


def _default_backend_factory(index: int) -> CaptureBackend:
    import cv2  # Imported lazily: importing gestureos.vision.camera must
    # never require a working OpenCV install — only actually opening a
    # real camera does.

    return cv2.VideoCapture(index)


class CameraError(Exception):
    """Raised when the camera cannot be opened or read from."""


class Camera:
    """Owns one physical (or injected) capture device.

    Not assumed to be index 0 (Section 30) — the caller picks the index;
    on failure this raises/returns a clear diagnostic rather than
    crashing so the app can prompt the user to pick another index.
    """

    def __init__(
        self,
        index: int = 0,
        resolution: tuple[int, int] | None = None,
        backend_factory: Callable[[int], CaptureBackend] = _default_backend_factory,
    ) -> None:
        self.index = index
        self.resolution = resolution
        self._backend_factory = backend_factory
        self._backend: CaptureBackend | None = None

    @property
    def is_open(self) -> bool:
        return self._backend is not None

    def open(self) -> bool:
        try:
            backend = self._backend_factory(self.index)
        except Exception as exc:  # noqa: BLE001 - camera drivers raise all sorts
            logger.error(
                "camera_open_exception",
                extra={"fields": {"index": self.index, "error": type(exc).__name__}},
            )
            return False

        if backend is None or not backend.isOpened():
            logger.error("camera_unavailable", extra={"fields": {"index": self.index}})
            return False

        if self.resolution is not None:
            width, height = self.resolution
            _set_resolution(backend, width, height)

        self._backend = backend
        logger.info(
            "camera_opened",
            extra={"fields": {"index": self.index, "resolution": self.resolution}},
        )
        return True

    def read(self) -> object | None:
        """Read one frame. Returns None (and logs a warning) on failure —
        callers should treat a lost/blocked camera as "no hand this
        frame", never as a crash.
        """
        if self._backend is None:
            raise CameraError("Camera.read() called before open()")

        ok, frame = self._backend.read()
        if not ok or frame is None:
            logger.warning("camera_frame_missing", extra={"fields": {"index": self.index}})
            return None
        return frame

    def release(self) -> None:
        if self._backend is not None:
            self._backend.release()
            logger.info("camera_released", extra={"fields": {"index": self.index}})
            self._backend = None

    def __enter__(self) -> Camera:
        if not self.open():
            raise CameraError(f"Could not open camera index {self.index}")
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


def _set_resolution(backend: CaptureBackend, width: int, height: int) -> None:
    import cv2

    backend.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    backend.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
