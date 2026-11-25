import pytest


@pytest.fixture(autouse=True)
def isolate_verbacore_storage(tmp_path, monkeypatch):
    """Redirect VerbaCore data and model directories to pytest tmp_path so tests never write to C:."""
    data_dir = tmp_path / "verbacore_data"
    models_dir = tmp_path / "verbacore_models"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VERBACORE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("VERBACORE_MODELS_DIR", str(models_dir))
