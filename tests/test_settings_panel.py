from gestureos.models import Settings
from gestureos.ui.settings_panel import SettingsPanel


def test_starts_with_first_item_selected() -> None:
    panel = SettingsPanel(Settings())

    assert panel.selected_index == 0


def test_move_selection_wraps_around() -> None:
    panel = SettingsPanel(Settings())
    count = len(panel.items)

    panel.move_selection(-1)

    assert panel.selected_index == count - 1


def test_move_selection_forward() -> None:
    panel = SettingsPanel(Settings())

    panel.move_selection(1)

    assert panel.selected_index == 1


def test_adjust_selected_increases_value() -> None:
    settings = Settings()
    panel = SettingsPanel(settings)
    before = settings.control.cursor_sensitivity

    panel.adjust_selected(1)

    assert settings.control.cursor_sensitivity > before


def test_adjust_selected_decreases_value() -> None:
    settings = Settings()
    panel = SettingsPanel(settings)
    before = settings.control.cursor_sensitivity

    panel.adjust_selected(-1)

    assert settings.control.cursor_sensitivity < before


def test_adjust_selected_clamps_to_maximum() -> None:
    settings = Settings()
    panel = SettingsPanel(settings)

    for _ in range(200):
        panel.adjust_selected(1)

    item = panel.items[panel.selected_index]
    assert item.get(settings) == item.maximum


def test_adjust_selected_clamps_to_minimum() -> None:
    settings = Settings()
    panel = SettingsPanel(settings)

    for _ in range(200):
        panel.adjust_selected(-1)

    item = panel.items[panel.selected_index]
    assert item.get(settings) == item.minimum


def test_adjusting_one_item_does_not_affect_others() -> None:
    settings = Settings()
    panel = SettingsPanel(settings)
    other_before = settings.audio.volume  # a different setting, index != 0

    panel.adjust_selected(1)  # adjusts cursor_sensitivity (index 0)

    assert settings.audio.volume == other_before


def test_display_rows_marks_the_selected_item() -> None:
    panel = SettingsPanel(Settings())

    rows = panel.display_rows()

    assert rows[0].startswith(">")
    for row in rows[1:]:
        assert row.startswith(" ")


def test_display_rows_selection_marker_follows_selection() -> None:
    panel = SettingsPanel(Settings())
    panel.move_selection(1)

    rows = panel.display_rows()

    assert rows[1].startswith(">")
    assert rows[0].startswith(" ")


def test_display_rows_count_matches_items() -> None:
    panel = SettingsPanel(Settings())

    assert len(panel.display_rows()) == len(panel.items)
