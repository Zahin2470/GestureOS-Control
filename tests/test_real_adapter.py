import pytest

from gestureos.macos.real_adapter import RealMacOSAdapter


class FakeQuartzBackend:
    def __init__(self) -> None:
        self.moves: list[tuple[float, float, bool]] = []
        self.downs: list[str] = []
        self.ups: list[str] = []
        self.scrolls: list[tuple[float, float]] = []
        self.switch_next_calls = 0
        self.switch_previous_calls = 0
        self.launched: list[str] = []
        self.media_play_pause_calls = 0
        self.space_next_calls = 0
        self.space_previous_calls = 0

    def move_cursor(self, x: float, y: float, dragging: bool = False) -> None:
        self.moves.append((x, y, dragging))

    def mouse_down(self, button: str = "left") -> None:
        self.downs.append(button)

    def mouse_up(self, button: str = "left") -> None:
        self.ups.append(button)

    def scroll(self, dx: float, dy: float) -> None:
        self.scrolls.append((dx, dy))

    def switch_app_next(self) -> None:
        self.switch_next_calls += 1

    def switch_app_previous(self) -> None:
        self.switch_previous_calls += 1

    def launch_app(self, name: str) -> None:
        self.launched.append(name)

    def media_play_pause(self) -> None:
        self.media_play_pause_calls += 1

    def space_next(self) -> None:
        self.space_next_calls += 1

    def space_previous(self) -> None:
        self.space_previous_calls += 1


def test_move_cursor_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.move_cursor(123.0, 456.0)

    assert backend.moves == [(123.0, 456.0, False)]


def test_move_cursor_passes_dragging_flag_through() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.move_cursor(1.0, 2.0, dragging=True)

    assert backend.moves == [(1.0, 2.0, True)]


def test_mouse_down_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.mouse_down()

    assert backend.downs == ["left"]


def test_mouse_up_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.mouse_up("right")

    assert backend.ups == ["right"]


def test_unsupported_button_rejected() -> None:
    adapter = RealMacOSAdapter(backend_factory=lambda: FakeQuartzBackend())

    with pytest.raises(ValueError):
        adapter.mouse_down("middle")
    with pytest.raises(ValueError):
        adapter.mouse_up("middle")


def test_backend_is_created_lazily_once() -> None:
    created = []

    def factory():
        created.append(1)
        return FakeQuartzBackend()

    adapter = RealMacOSAdapter(backend_factory=factory)
    adapter.move_cursor(1.0, 1.0)
    adapter.move_cursor(2.0, 2.0)

    assert len(created) == 1


def test_scroll_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.scroll(1.5, -2.5)

    assert backend.scrolls == [(1.5, -2.5)]


def test_switch_app_next_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.switch_app_next()

    assert backend.switch_next_calls == 1


def test_switch_app_previous_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.switch_app_previous()

    assert backend.switch_previous_calls == 1


def test_launch_app_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.launch_app("Safari")

    assert backend.launched == ["Safari"]


@pytest.mark.parametrize(
    "call",
    [
        lambda a: a.key_press("a"),
    ],
)
def test_unimplemented_commands_raise_not_implemented(call) -> None:
    adapter = RealMacOSAdapter(backend_factory=lambda: FakeQuartzBackend())

    with pytest.raises(NotImplementedError):
        call(adapter)


def test_media_play_pause_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.media_play_pause()

    assert backend.media_play_pause_calls == 1


def test_space_next_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.space_next()

    assert backend.space_next_calls == 1


def test_space_previous_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.space_previous()

    assert backend.space_previous_calls == 1
