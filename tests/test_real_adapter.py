import pytest

from gestureos.macos.real_adapter import RealMacOSAdapter


class FakeQuartzBackend:
    def __init__(self) -> None:
        self.moves: list[tuple[float, float]] = []

    def move_cursor(self, x: float, y: float) -> None:
        self.moves.append((x, y))


def test_move_cursor_dispatches_to_backend() -> None:
    backend = FakeQuartzBackend()
    adapter = RealMacOSAdapter(backend_factory=lambda: backend)

    adapter.move_cursor(123.0, 456.0)

    assert backend.moves == [(123.0, 456.0)]


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
        lambda a: a.mouse_down(),
        lambda a: a.mouse_up(),
        lambda a: a.scroll(0, 0),
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
