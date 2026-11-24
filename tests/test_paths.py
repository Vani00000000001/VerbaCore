import os
from pathlib import Path
from verbacore.utils.paths import (
    get_data_dir,
    get_models_dir,
    get_uploads_dir,
    get_reports_dir,
    get_recordings_dir,
    get_font_search_paths
)


def test_custom_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VERBACORE_DATA_DIR", str(tmp_path))
    assert get_data_dir() == tmp_path
    assert get_uploads_dir() == tmp_path / "uploads"
    assert get_reports_dir() == tmp_path / "reports"
    assert get_recordings_dir() == tmp_path / "recordings"


def test_custom_models_dir(tmp_path, monkeypatch):
    custom_models = tmp_path / "custom_models"
    monkeypatch.setenv("VERBACORE_MODELS_DIR", str(custom_models))
    assert get_models_dir() == custom_models
    assert custom_models.is_dir()


def test_font_search_returns_list():
    fonts = get_font_search_paths()
    assert isinstance(fonts, list)
    for f in fonts:
        assert isinstance(f, Path)
        assert f.is_file()
