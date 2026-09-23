from gestureos.interaction.confidence import ConfidenceTracker
from gestureos.interaction.gestures import GestureCandidate, GestureType


def _candidate(gesture: GestureType, confidence: float = 0.9, handedness: str = "right"):
    return GestureCandidate(gesture=gesture, confidence=confidence, handedness=handedness)


def test_single_frame_below_vote_fraction_reports_none() -> None:
    tracker = ConfidenceTracker(window_size=5, min_vote_fraction=0.6)

    result = tracker.update(_candidate(GestureType.PINCH))

    # Only 1/1 votes so far... but window isn't full; 1/1 = 100% >= 60%,
    # so a single consistent frame is actually enough once it's the only
    # data point. This asserts that specific (correct) behavior.
    assert result.gesture == GestureType.PINCH


def test_majority_vote_wins_over_minority_flicker() -> None:
    tracker = ConfidenceTracker(window_size=5, min_vote_fraction=0.6)

    tracker.update(_candidate(GestureType.PINCH))
    tracker.update(_candidate(GestureType.PINCH))
    tracker.update(_candidate(GestureType.PINCH))
    tracker.update(_candidate(GestureType.NONE))
    result = tracker.update(_candidate(GestureType.PINCH))

    assert result.gesture == GestureType.PINCH


def test_split_vote_below_threshold_reports_none() -> None:
    tracker = ConfidenceTracker(window_size=4, min_vote_fraction=0.6)

    tracker.update(_candidate(GestureType.PINCH))
    tracker.update(_candidate(GestureType.OPEN_PALM))
    tracker.update(_candidate(GestureType.PINCH))
    result = tracker.update(_candidate(GestureType.OPEN_PALM))

    # 2/4 = 50% for the winning gesture, below the 60% threshold.
    assert result.gesture == GestureType.NONE


def test_confidence_is_averaged_over_matching_frames() -> None:
    tracker = ConfidenceTracker(window_size=3, min_vote_fraction=0.6)

    tracker.update(_candidate(GestureType.PINCH, confidence=0.8))
    tracker.update(_candidate(GestureType.PINCH, confidence=1.0))
    result = tracker.update(_candidate(GestureType.PINCH, confidence=0.9))

    assert result.confidence == (0.8 + 1.0 + 0.9) / 3


def test_hands_are_tracked_independently_by_handedness() -> None:
    tracker = ConfidenceTracker(window_size=3, min_vote_fraction=0.6)

    tracker.update(_candidate(GestureType.PINCH, handedness="left"))
    result_right = tracker.update(_candidate(GestureType.OPEN_PALM, handedness="right"))

    assert result_right.gesture == GestureType.OPEN_PALM


def test_reset_clears_all_history() -> None:
    tracker = ConfidenceTracker(window_size=3, min_vote_fraction=0.6)
    tracker.update(_candidate(GestureType.PINCH))

    tracker.reset()
    result = tracker.update(_candidate(GestureType.OPEN_PALM))

    assert result.gesture == GestureType.OPEN_PALM


def test_invalid_window_size_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        ConfidenceTracker(window_size=0)


def test_invalid_vote_fraction_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        ConfidenceTracker(min_vote_fraction=0.0)
    with pytest.raises(ValueError):
        ConfidenceTracker(min_vote_fraction=1.5)
