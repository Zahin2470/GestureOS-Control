import pytest

from gestureos.vision.camera import Camera, CameraError


class FakeBackend:
    def __init__(self, opened: bool = True, frames: list | None = None) -> None:
        self._opened = opened
        self._frames = frames if frames is not None else ["frame"]
        self._frame_index = 0
        self.released = False
        self.set_calls: list[tuple[int, float]] = []

    def isOpened(self) -> bool:
        return self._opened

    def read(self):
        if self._frame_index >= len(self._frames):
            return False, None
        frame = self._frames[self._frame_index]
        self._frame_index += 1
        if frame is None:
            return False, None
        return True, frame

    def release(self) -> None:
        self.released = True

    def set(self, prop_id, value) -> bool:
        self.set_calls.append((prop_id, value))
        return True

    def get(self, prop_id) -> float:
        return 0.0


def test_open_succeeds_when_backend_opens() -> None:
    camera = Camera(index=0, backend_factory=lambda i: FakeBackend(opened=True))

    assert camera.open() is True
    assert camera.is_open is True


def test_open_fails_when_backend_reports_not_opened() -> None:
    camera = Camera(index=3, backend_factory=lambda i: FakeBackend(opened=False))

    assert camera.open() is False
    assert camera.is_open is False


def test_open_fails_gracefully_when_factory_raises() -> None:
    def broken_factory(index: int):
        raise RuntimeError("driver exploded")

    camera = Camera(index=0, backend_factory=broken_factory)

    assert camera.open() is False


def test_read_before_open_raises_camera_error() -> None:
    camera = Camera(index=0, backend_factory=lambda i: FakeBackend())

    with pytest.raises(CameraError):
        camera.read()


def test_read_returns_frame_on_success() -> None:
    camera = Camera(index=0, backend_factory=lambda i: FakeBackend(frames=["frame1"]))
    camera.open()

    assert camera.read() == "frame1"


def test_read_returns_none_on_dropped_frame() -> None:
    camera = Camera(index=0, backend_factory=lambda i: FakeBackend(frames=[None]))
    camera.open()

    assert camera.read() is None


def test_release_marks_backend_released_and_clears_state() -> None:
    backend = FakeBackend()
    camera = Camera(index=0, backend_factory=lambda i: backend)
    camera.open()

    camera.release()

    assert backend.released is True
    assert camera.is_open is False


def test_release_is_idempotent() -> None:
    camera = Camera(index=0, backend_factory=lambda i: FakeBackend())
    camera.open()
    camera.release()

    camera.release()  # must not raise


def test_context_manager_raises_when_camera_unavailable() -> None:
    with pytest.raises(CameraError):
        with Camera(index=0, backend_factory=lambda i: FakeBackend(opened=False)):
            pass


def test_context_manager_releases_on_exit() -> None:
    backend = FakeBackend()
    with Camera(index=0, backend_factory=lambda i: backend) as camera:
        assert camera.is_open is True

    assert backend.released is True
