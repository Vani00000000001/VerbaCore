import pytest
from pathlib import Path
from verbacore.llm.manager import (
    is_endpoint_alive,
    check_ollama_status,
    check_llama_server_status,
    find_llama_server,
    find_gguf_model,
    ensure_brain_llm_active
)


def test_is_endpoint_alive_invalid():
    assert not is_endpoint_alive("http://127.0.0.1:59999/does_not_exist", timeout=0.2)


def test_check_ollama_status():
    status = check_ollama_status("http://127.0.0.1:59999")
    assert isinstance(status, dict)
    assert "running" in status
    assert "models" in status


def test_check_llama_server_status():
    status = check_llama_server_status()
    assert isinstance(status, dict)
    assert "running" in status
    assert "loaded_model" in status


def test_find_llama_server():
    server = find_llama_server()
    if server:
        assert isinstance(server, Path)
        assert server.is_file()


def test_find_gguf_model():
    model = find_gguf_model()
    if model:
        assert isinstance(model, Path)
        assert model.is_file()


def test_ensure_brain_llm_active():
    res = ensure_brain_llm_active()
    assert isinstance(res, dict)
    assert "active" in res
    assert "provider" in res
