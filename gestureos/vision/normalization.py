"""
Normalization (Section 9).

    "Normalize geometry relative to hand scale, such as palm width...
     This prevents gesture thresholds from depending heavily on how
     close the hand is to the camera."

Takes the raw, image-space features from ``features.py`` and rescales
the distance-based ones (pinch distance, velocity magnitude) by the
hand's own palm width, so a threshold like "pinch closer than 0.06"
means the same thing whether the user is close to or far from the
camera.
"""

from __future__ import annotations

from dataclasses import replace

from gestureos.vision.features import FrameFeatures, HandFeatures, Point2D

_MIN_PALM_WIDTH = 1e-6  # guards against division by ~0 for degenerate landmarks


def normalize_hand_features(features: HandFeatures) -> HandFeatures:
    if not features.hand_present:
        return features
    if features.palm_width is None or features.palm_width < _MIN_PALM_WIDTH:
        return features

    scale = features.palm_width
    new_pinch = (
        features.pinch_distance / scale if features.pinch_distance is not None else None
    )
    new_velocity = (
        Point2D(features.velocity.x / scale, features.velocity.y / scale)
        if features.velocity is not None
        else None
    )
    return replace(features, pinch_distance=new_pinch, velocity=new_velocity)


def normalize_frame_features(frame: FrameFeatures) -> FrameFeatures:
    normalized_hands = tuple(normalize_hand_features(hand) for hand in frame.hands)
    return replace(frame, hands=normalized_hands)
