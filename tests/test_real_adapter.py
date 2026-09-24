import pytest

from gestureos.macos.real_adapter import RealMacOSAdapter


class FakeQuartzBackend:
    def __init__(self) -> None:
        self.moves: list[tuple[float, float, bool]] = []
        self.downs: list[str] = []
        self.ups: list[str] = []
        self.scrolls: list[tuple[float, float]] = []

    def move_cursor(self, x: float, y: float, dragging: bool = False) -> None:
        self.moves.append((x, y, dragging))

    def mouse_down(self, button: str = "left") -> None:
        self.downs.append(button)

    def mouse_up(self, button: str = "left") -> None:
        self.ups.append(button)

    def scroll(self, dx: float, dy: float) -> None:
        self.scrolls.append((dx, dy))


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


@pytest.mark.parametrize(
    "call",
    [
        lambda a: a.key_press("a"),
        lambda a: a.switch_app_next(),
        lambda a: a.switch_app_previous(),
        lambda a: a.launch_app("Safari"),
        lambda a: a.media_play_pause(),
        lambda a: a.space_next(),
        lambda a: a.space_previous(),
    ],
)
def test_unimplemented_commands_raise_not_implemented(call) -> None:
    adapter = RealMacOSAdapter(backend_factory=lambda: FakeQuartzBackend())

    with pytest.raises(NotImplementedError):
        call(adapter)


def test_scroll_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.scroll(1.5, -2.5)

    assert backend.scrolls == [(1.5, -2.5)]
