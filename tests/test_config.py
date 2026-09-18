from pathlib import Path

from gestureos.config import Config
from gestureos.models import ControlSettings, Settings, Theme


def test_defaults_when_no_file_exists(tmp_path: Path) -> None:
    config = Config(path=tmp_path / "settings.json")

    settings = config.load()

    assert settings.active_profile == "default"
    assert settings.ui.theme == Theme.DARK


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    config = Config(path=tmp_path / "settings.json")
    config.load()
    config.settings.active_profile = "media"
    config.settings.control.cursor_sensitivity = 2.5
    config.settings.ui.theme = Theme.NEON

    config.save()

    reloaded = Config(path=tmp_path / "settings.json")
    settings = reloaded.load()

    assert settings.active_profile == "media"
    assert settings.control.cursor_sensitivity == 2.5
    assert settings.ui.theme == Theme.NEON


def test_corrupted_settings_file_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not valid json", encoding="utf-8")
    config = Config(path=path)

    settings = config.load()

    assert settings == Settings()


def test_non_object_json_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    config = Config(path=path)

    settings = config.load()

    assert settings == Settings()


def test_partial_settings_file_fills_in_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"active_profile": "presentation"}', encoding="utf-8")
    config = Config(path=path)

    settings = config.load()

    assert settings.active_profile == "presentation"
    assert settings.vision.camera_index == 0  # default filled in


def test_out_of_range_values_are_clamped_on_validate() -> None:
    control = ControlSettings(cursor_sensitivity=999.0, smoothing=-5.0)

    control.validate()

    assert control.cursor_sensitivity == 5.0
    assert control.smoothing == 0.0


def test_invalid_theme_string_falls_back_to_dark(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"ui": {"theme": "not_a_real_theme"}}', encoding="utf-8")
    config = Config(path=path)

    settings = config.load()

    assert settings.ui.theme == Theme.DARK
