from types import SimpleNamespace

import pytest

from gestureos.vision.tracker import NUM_LANDMARKS, HandTracker


def _make_mp_style_result(hands: list[dict]):
    """Builds an object shaped like a real mediapipe Hands result:
    .multi_hand_landmarks[i].landmark[j].{x,y,z}
    .multi_handedness[i].classification[0].{label,score}
    """
    if not hands:
        return SimpleNamespace(multi_hand_landmarks=None, multi_handedness=None)

    multi_landmarks = []
    multi_handedness = []
    for hand in hands:
        landmark_objs = [
            SimpleNamespace(x=x, y=y, z=0.0) for (x, y) in hand["points"]
        ]
        multi_landmarks.append(SimpleNamespace(landmark=landmark_objs))
        multi_handedness.append(
            SimpleNamespace(
                classification=[
                    SimpleNamespace(label=hand["label"], score=hand["score"])
                ]
            )
        )
    return SimpleNamespace(multi_hand_landmarks=multi_landmarks, multi_handedness=multi_handedness)


class FakeMediaPipeBackend:
    def __init__(self, result) -> None:
        self._result = result
        self.closed = False

    def process(self, frame):
        return self._result

    def close(self) -> None:
        self.closed = True


def _flat_points() -> list[tuple[float, float]]:
    return [(0.01 * i, 0.02 * i) for i in range(NUM_LANDMARKS)]


def test_no_hands_in_result_returns_empty_tuple() -> None:
    backend = FakeMediaPipeBackend(_make_mp_style_result([]))
    tracker = HandTracker(backend=backend)
    tracker.start()

    hands = tracker.process(object())

    assert hands == ()


def test_single_hand_converted_correctly() -> None:
    result = _make_mp_style_result(
        [{"points": _flat_points(), "label": "Right", "score": 0.93}]
    )
    backend = FakeMediaPipeBackend(result)
    tracker = HandTracker(backend=backend)
    tracker.start()

    hands = tracker.process(object())

    assert len(hands) == 1
    hand = hands[0]
    assert len(hand.landmarks) == NUM_LANDMARKS
    assert hand.handedness == "right"  # lower-cased
    assert hand.handedness_confidence == pytest.approx(0.93)
    assert hand.landmarks[0].x == pytest.approx(0.0)


def test_two_hands_converted_correctly() -> None:
    result = _make_mp_style_result(
        [
            {"points": _flat_points(), "label": "Left", "score": 0.9},
            {"points": _flat_points(), "label": "Right", "score": 0.95},
        ]
    )
    backend = FakeMediaPipeBackend(result)
    tracker = HandTracker(backend=backend)
    tracker.start()

    hands = tracker.process(object())

    assert len(hands) == 2
    assert {h.handedness for h in hands} == {"left", "right"}


def test_process_before_start_raises() -> None:
    # No injected backend and start() never called: process() must raise
    # before it would ever touch a real MediaPipe import.
    tracker = HandTracker(backend=None)

    with pytest.raises(RuntimeError):
        tracker.process(object())


def test_close_calls_backend_close_when_owned() -> None:
    backend = FakeMediaPipeBackend(_make_mp_style_result([]))
    tracker = HandTracker(backend=None)
    tracker._backend = backend  # simulate ownership without importing mediapipe
    tracker._owns_backend = True

    tracker.close()

    assert backend.closed is True


def test_context_manager_starts_and_closes() -> None:
    backend = FakeMediaPipeBackend(_make_mp_style_result([]))
    tracker = HandTracker(backend=backend)

    with tracker as t:
        assert t.process(object()) == ()


@pytest.mark.integration
def test_real_mediapipe_processes_blank_frame_without_crashing() -> None:
    """Integration smoke test against the real MediaPipe runtime (no
    camera needed — a synthetic black frame is enough to prove the
    pipeline wiring works end-to-end on this machine).
    """
    np = pytest.importorskip("numpy")
    pytest.importorskip("mediapipe")

    tracker = HandTracker(max_num_hands=2)
    tracker.start()
    try:
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hands = tracker.process(blank_frame)
        assert hands == ()  # no hand in a blank frame
    finally:
        tracker.close()
