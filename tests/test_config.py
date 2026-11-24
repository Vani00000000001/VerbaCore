from verbacore.config import load_config, AppConfig


def test_default_config():
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.port == 7860
    assert cfg.brain_llm_model == "qwen2.5:1.5b"


def test_env_override(monkeypatch):
    monkeypatch.setenv("VERBACORE_PORT", "8888")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    cfg = load_config()
    assert cfg.port == 8888
    assert cfg.gemini_api_key == "test_gemini_key"
