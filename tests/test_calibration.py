from gestureos.ui.calibration import CalibrationStep, CalibrationWizard
from gestureos.vision.features import Point2D


def test_starts_waiting_for_hand() -> None:
    wizard = CalibrationWizard()

    assert wizard.step == CalibrationStep.WAIT_FOR_HAND
    assert wizard.is_done is False


def test_update_with_no_hand_stays_waiting() -> None:
    wizard = CalibrationWizard()

    wizard.update(None)

    assert wizard.step == CalibrationStep.WAIT_FOR_HAND


def test_update_with_hand_advances_to_top_left() -> None:
    wizard = CalibrationWizard()

    wizard.update(Point2D(0.5, 0.5))

    assert wizard.step == CalibrationStep.TOP_LEFT


def test_confirm_before_any_hand_seen_does_nothing() -> None:
    wizard = CalibrationWizard()

    advanced = wizard.confirm()

    assert advanced is False
    assert wizard.step == CalibrationStep.WAIT_FOR_HAND


def test_confirm_at_top_left_captures_and_advances() -> None:
    wizard = CalibrationWizard()
    wizard.update(Point2D(0.2, 0.2))

    advanced = wizard.confirm()

    assert advanced is True
    assert wizard.step == CalibrationStep.BOTTOM_RIGHT


def test_full_flow_produces_a_region_matching_the_captured_corners() -> None:
    wizard = CalibrationWizard(margin=0.0)
    wizard.update(Point2D(0.2, 0.2))
    wizard.confirm()
    wizard.update(Point2D(0.8, 0.9))
    wizard.confirm()

    assert wizard.is_done
    assert wizard.result is not None
    assert wizard.result.x_min == 0.2
    assert wizard.result.x_max == 0.8
    assert wizard.result.y_min == 0.2
    assert wizard.result.y_max == 0.9


def test_margin_shrinks_the_captured_region() -> None:
    wizard = CalibrationWizard(margin=0.05)
    wizard.update(Point2D(0.2, 0.2))
    wizard.confirm()
    wizard.update(Point2D(0.8, 0.8))
    wizard.confirm()

    assert wizard.result is not None
    assert wizard.result.x_min == 0.25
    assert wizard.result.x_max == 0.75


def test_degenerate_capture_falls_back_to_default_region() -> None:
    from gestureos.vision.mapping import ActiveRegion

    wizard = CalibrationWizard(margin=0.0)
    wizard.update(Point2D(0.5, 0.5))
    wizard.confirm()
    wizard.update(Point2D(0.51, 0.51))  # far too close together
    wizard.confirm()

    assert wizard.result == ActiveRegion()


def test_confirm_after_done_does_nothing_further() -> None:
    wizard = CalibrationWizard()
    wizard.update(Point2D(0.2, 0.2))
    wizard.confirm()
    wizard.update(Point2D(0.8, 0.8))
    wizard.confirm()

    advanced = wizard.confirm()

    assert advanced is False
    assert wizard.step == CalibrationStep.DONE


def test_reversed_corners_still_produce_a_valid_region() -> None:
    wizard = CalibrationWizard(margin=0.0)
    wizard.update(Point2D(0.8, 0.8))  # "top-left" captured bottom-right-ish
    wizard.confirm()
    wizard.update(Point2D(0.2, 0.2))  # "bottom-right" captured top-left-ish
    wizard.confirm()

    assert wizard.result is not None
    assert wizard.result.x_min == 0.2
    assert wizard.result.x_max == 0.8


def test_prompt_text_changes_per_step() -> None:
    wizard = CalibrationWizard()
    prompts = [wizard.prompt]

    wizard.update(Point2D(0.5, 0.5))
    prompts.append(wizard.prompt)
    wizard.confirm()
    prompts.append(wizard.prompt)
    wizard.confirm()
    prompts.append(wizard.prompt)

    assert len(set(prompts)) == 4  # every step has distinct guidance
