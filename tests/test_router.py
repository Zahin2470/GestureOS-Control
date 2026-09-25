from gestureos.commands.router import CommandRouter
from gestureos.commands.safety import SafetyPolicy
from gestureos.interaction.gestures import GestureType
from gestureos.interaction.state_machine import Intent, IntentPhase
from gestureos.macos.fake_adapter import FakeMacOSAdapter
from gestureos.models import ControlState
from gestureos.vision.features import Point2D


def _intent(
    gesture: GestureType,
    phase: IntentPhase,
    timestamp: float = 0.0,
    position: Point2D | None = None,
) -> Intent:
    return Intent(
        gesture=gesture,
        phase=phase,
        confidence=0.9,
        handedness="right",
        timestamp=timestamp,
        position=position,
    )


class _Ticker:
    """A clock that advances by a full second on every call, so the
    safety policy's rate limiter never interferes with tests that make
    several route_intent() calls back to back.
    """

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def test_pinch_start_dispatches_mouse_down_on_adapter() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    command = router.route_intent(_intent(GestureType.PINCH, IntentPhase.START))

    assert command is not None
    assert len(adapter.calls_of("mouse_down")) == 1


def test_pinch_end_dispatches_mouse_up_on_adapter() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START))
    command = router.route_intent(_intent(GestureType.PINCH, IntentPhase.END))

    assert command is not None
    assert len(adapter.calls_of("mouse_up")) == 1


def test_unbound_gesture_dispatches_nothing() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    command = router.route_intent(_intent(GestureType.OPEN_PALM, IntentPhase.START))

    assert command is None
    assert adapter.calls == []


def test_paused_control_blocks_mouse_down_but_not_mouse_up() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.PAUSED)
    router = CommandRouter(adapter=adapter, safety=safety)

    down = router.route_intent(_intent(GestureType.PINCH, IntentPhase.START))
    up = router.route_intent(_intent(GestureType.PINCH, IntentPhase.END))

    assert down is None
    assert up is not None
    assert adapter.calls_of("mouse_down") == []
    assert len(adapter.calls_of("mouse_up")) == 1


def test_route_intents_processes_a_batch_and_drops_unbound_ones() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    intents = (
        _intent(GestureType.OPEN_PALM, IntentPhase.START),  # unbound
        _intent(GestureType.PINCH, IntentPhase.START),  # bound
    )

    commands = router.route_intents(intents)

    assert len(commands) == 1
    assert commands[0].type.value == "mouse_down"


class _RaisingAdapter:
    """An adapter whose mouse_down isn't implemented yet, like
    RealMacOSAdapter before Phase 6 lands.
    """

    def mouse_down(self, button: str = "left") -> None:
        raise NotImplementedError("Click support lands in Phase 6")

    def mouse_up(self, button: str = "left") -> None:
        raise RuntimeError("some unexpected OS-level failure")

    def move_cursor(self, x: float, y: float, dragging: bool = False) -> None: ...
    def scroll(self, dx: float, dy: float) -> None: ...
    def key_press(self, key: str) -> None: ...
    def switch_app_next(self) -> None: ...
    def switch_app_previous(self) -> None: ...
    def launch_app(self, name: str) -> None: ...
    def media_play_pause(self) -> None: ...
    def space_next(self) -> None: ...
    def space_previous(self) -> None: ...


def test_not_implemented_adapter_method_is_caught_not_raised() -> None:
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=_RaisingAdapter(), safety=safety)

    command = router.route_intent(_intent(GestureType.PINCH, IntentPhase.START))

    assert command is None  # no exception propagates out of route_intent


def test_unexpected_adapter_exception_is_caught_not_raised() -> None:
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=_RaisingAdapter(), safety=safety)

    command = router.route_intent(_intent(GestureType.PINCH, IntentPhase.END))

    assert command is None


def test_mouse_down_snaps_cursor_to_click_position() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START, position=Point2D(0.5, 0.5)))

    moves = adapter.calls_of("move_cursor")
    assert len(moves) == 1
    assert moves[0].kwargs.get("dragging") is False


def test_small_movement_during_hold_does_not_move_cursor() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START, position=Point2D(0.5, 0.5)))
    command = router.route_intent(
        _intent(GestureType.PINCH, IntentPhase.HOLD, position=Point2D(0.505, 0.5))
    )

    assert command is None  # still inside the click deadzone
    assert len(adapter.calls_of("move_cursor")) == 1  # only the initial snap from START


def test_large_movement_during_hold_engages_drag_and_moves_cursor() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START, position=Point2D(0.5, 0.5)))
    command = router.route_intent(
        _intent(GestureType.PINCH, IntentPhase.HOLD, position=Point2D(0.6, 0.5))
    )

    assert command is not None
    drag_moves = [c for c in adapter.calls_of("move_cursor") if c.kwargs.get("dragging") is True]
    assert len(drag_moves) == 1


def test_mouse_up_after_engaged_drag_issues_a_final_move() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.PINCH, IntentPhase.HOLD, position=Point2D(0.6, 0.5)))
    router.route_intent(_intent(GestureType.PINCH, IntentPhase.END, position=Point2D(0.65, 0.5)))

    drag_moves = [c for c in adapter.calls_of("move_cursor") if c.kwargs.get("dragging") is True]
    assert len(drag_moves) == 2  # one during HOLD, one final snap at END
    assert len(adapter.calls_of("mouse_up")) == 1


def test_click_with_no_movement_never_engages_drag() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.PINCH, IntentPhase.END, position=Point2D(0.5, 0.5)))

    drag_moves = [c for c in adapter.calls_of("move_cursor") if c.kwargs.get("dragging") is True]
    assert drag_moves == []
    assert len(adapter.calls_of("mouse_up")) == 1


def test_cursor_mapper_is_applied_when_configured() -> None:
    from gestureos.vision.mapping import CursorMapper

    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    mapper = CursorMapper(1000, 800, mirror=False, smoothing_alpha=None)
    router = CommandRouter(adapter=adapter, safety=safety, cursor_mapper=mapper)

    router.route_intent(_intent(GestureType.PINCH, IntentPhase.START, position=Point2D(0.5, 0.5)))

    moves = adapter.calls_of("move_cursor")
    assert moves[0].args == (500.0, 400.0)


def test_scroll_start_only_sets_reference_and_dispatches_nothing() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    command = router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.START, position=Point2D(0.5, 0.5))
    )

    assert command is None
    assert adapter.calls_of("scroll") == []


def test_scroll_hold_with_movement_dispatches_scroll() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.START, position=Point2D(0.5, 0.5))
    )
    router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.HOLD, position=Point2D(0.5, 0.5))
    )
    command = router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.HOLD, position=Point2D(0.5, 0.6))
    )

    assert command is not None
    assert len(adapter.calls_of("scroll")) == 1


def test_scroll_end_dispatches_nothing_but_clears_state() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.START, position=Point2D(0.5, 0.5))
    )
    router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.HOLD, position=Point2D(0.5, 0.5))
    )
    command = router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.END, position=Point2D(0.5, 0.6))
    )

    assert command is None
    assert adapter.calls_of("scroll") == []


def test_paused_control_blocks_scroll() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.PAUSED, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.START, position=Point2D(0.5, 0.5))
    )
    router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.HOLD, position=Point2D(0.5, 0.5))
    )
    command = router.route_intent(
        _intent(GestureType.TWO_FINGER_SCROLL, IntentPhase.HOLD, position=Point2D(0.5, 0.9))
    )

    assert command is None
    assert adapter.calls_of("scroll") == []


def test_app_switch_start_only_sets_reference_and_dispatches_nothing() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)
    router = CommandRouter(adapter=adapter, safety=safety)

    command = router.route_intent(
        _intent(GestureType.FIST, IntentPhase.START, position=Point2D(0.5, 0.5))
    )

    assert command is None
    assert adapter.calls_of("switch_app_next") == []
    assert adapter.calls_of("switch_app_previous") == []


def test_rightward_swipe_dispatches_switch_app_next() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.FIST, IntentPhase.START, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.5, 0.5)))
    command = router.route_intent(
        _intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.7, 0.5))
    )

    assert command is not None
    assert len(adapter.calls_of("switch_app_next")) == 1
    assert adapter.calls_of("switch_app_previous") == []


def test_leftward_swipe_dispatches_switch_app_previous() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.FIST, IntentPhase.START, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.5, 0.5)))
    command = router.route_intent(
        _intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.3, 0.5))
    )

    assert command is not None
    assert len(adapter.calls_of("switch_app_previous")) == 1
    assert adapter.calls_of("switch_app_next") == []


def test_only_one_switch_fires_per_fist_hold() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.FIST, IntentPhase.START, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.7, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.9, 0.5)))

    assert len(adapter.calls_of("switch_app_next")) == 1


def test_new_fist_hold_can_swipe_again_after_previous_ends() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.FIST, IntentPhase.START, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.7, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.END, position=Point2D(0.7, 0.5)))

    router.route_intent(_intent(GestureType.FIST, IntentPhase.START, position=Point2D(0.2, 0.2)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.2, 0.2)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.4, 0.2)))

    assert len(adapter.calls_of("switch_app_next")) == 2


def test_paused_control_blocks_app_switch() -> None:
    adapter = FakeMacOSAdapter()
    safety = SafetyPolicy(get_control_state=lambda: ControlState.PAUSED, clock=_Ticker())
    router = CommandRouter(adapter=adapter, safety=safety)

    router.route_intent(_intent(GestureType.FIST, IntentPhase.START, position=Point2D(0.5, 0.5)))
    router.route_intent(_intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.5, 0.5)))
    command = router.route_intent(
        _intent(GestureType.FIST, IntentPhase.HOLD, position=Point2D(0.7, 0.5))
    )

    assert command is None
    assert adapter.calls_of("switch_app_next") == []


def test_launch_app_blocked_without_allowlist() -> None:
    from gestureos.commands.types import Command, CommandType

    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE)

    # LAUNCH_APP isn't gesture-bound yet, so exercise the safety policy
    # directly — confirming it fails closed with no allowlist configured
    # (gesture binding for launch is a future phase's concern).
    decision = safety.check(
        Command(
            type=CommandType.LAUNCH_APP,
            source_gesture=GestureType.FIST,
            source_phase=IntentPhase.START,
            handedness="right",
            timestamp=0.0,
            params={"name": "Safari"},
        )
    )

    assert decision.allowed is False
