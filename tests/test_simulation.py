from gestureos.commands.router import CommandRouter
from gestureos.commands.safety import SafetyPolicy
from gestureos.interaction.engine import GestureEngine
from gestureos.macos.fake_adapter import FakeMacOSAdapter
from gestureos.models import ControlState
from gestureos.vision.features import FeatureExtractor
from gestureos.vision.normalization import normalize_frame_features
from gestureos.vision.smoothing import FeatureSmoother
from tests.test_state_machine import FakeClock
from tests.vision_helpers import make_open_hand, make_pinch_hand


def _build_pipeline(clock):
    extractor = FeatureExtractor()
    smoother = FeatureSmoother()
    engine = GestureEngine(min_hold_time_s=0.05, cooldown_s=0.1, vote_window_size=3, clock=clock)
    adapter = FakeMacOSAdapter(clock=clock)
    safety = SafetyPolicy(get_control_state=lambda: ControlState.ACTIVE, clock=clock)
    router = CommandRouter(adapter=adapter, safety=safety)
    return extractor, smoother, engine, router, adapter


def _step(raw_hands, extractor, smoother, engine, router):
    frame = smoother.smooth_frame(normalize_frame_features(extractor.process(raw_hands)))
    intents = engine.process(frame)
    return router.route_intents(intents)


def test_full_pinch_click_cycle_is_simulated_end_to_end() -> None:
    clock = FakeClock()
    extractor, smoother, engine, router, adapter = _build_pipeline(clock)

    all_commands = []
    for _ in range(5):
        all_commands.extend(_step((make_pinch_hand(),), extractor, smoother, engine, router))
        clock.advance(0.03)
    for _ in range(3):
        all_commands.extend(_step((make_open_hand(),), extractor, smoother, engine, router))
        clock.advance(0.03)

    types = [c.type.value for c in all_commands]
    assert "mouse_down" in types
    assert "mouse_up" in types
    assert types.index("mouse_down") < types.index("mouse_up")

    # The adapter recorded exactly what the router dispatched — nothing
    # more, and nothing touched a real mouse.
    assert len(adapter.calls_of("mouse_down")) == 1
    assert len(adapter.calls_of("mouse_up")) == 1


def test_paused_control_prevents_click_but_still_releases() -> None:
    clock = FakeClock()
    extractor, smoother, engine, router, adapter = _build_pipeline(clock)
    router._safety = SafetyPolicy(get_control_state=lambda: ControlState.PAUSED, clock=clock)

    all_commands = []
    for _ in range(5):
        all_commands.extend(_step((make_pinch_hand(),), extractor, smoother, engine, router))
        clock.advance(0.03)
    for _ in range(3):
        all_commands.extend(_step((make_open_hand(),), extractor, smoother, engine, router))
        clock.advance(0.03)

    # mouse_down was blocked by the paused safety policy, but the
    # subsequent mouse_up (a release) was still let through.
    assert adapter.calls_of("mouse_down") == []
    assert len(adapter.calls_of("mouse_up")) == 1


def test_sustained_open_hand_triggers_media_play_pause_once() -> None:
    clock = FakeClock()
    extractor, smoother, engine, router, adapter = _build_pipeline(clock)

    all_commands = []
    for _ in range(6):
        all_commands.extend(_step((make_open_hand(),), extractor, smoother, engine, router))
        clock.advance(0.03)

    types = [c.type.value for c in all_commands]
    assert types == ["media_play_pause"]  # fires once on START, not on every HOLD frame
    assert len(adapter.calls_of("media_play_pause")) == 1
