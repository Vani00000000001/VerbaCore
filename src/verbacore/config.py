import os
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from verbacore.utils.paths import get_data_dir, get_project_root


class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7860
    
    # LLM Settings
    brain_llm_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Ollama or llama-server base endpoint"
    )
    brain_llm_model: str = "qwen2.5:1.5b"
    llama_server_path: Optional[str] = None
    gguf_model_path: Optional[str] = None
    
    # ASR Settings
    default_whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_threads: int = 4
    
    # Limits
    max_upload_bytes: int = 100 * 1024 * 1024
    max_recording_bytes: int = 2 * 1024 * 1024 * 1024
    max_chunk_bytes: int = 16 * 1024 * 1024
    cloud_chunk_seconds: int = 600
    
    # Cloud API Keys
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    auto_fallback: bool = True
    preferred_cloud: str = "gemini"


def load_config() -> AppConfig:
    """Load configuration from environment, cloud_config.json, or defaults."""
    cfg = AppConfig()

    # Search paths for cloud_config.json
    candidates = [
        get_data_dir() / "cloud_config.json",
        get_project_root() / "cloud_config.json",
        Path.cwd() / "cloud_config.json",
    ]

    for p in candidates:
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if "gemini_api_key" in data and data["gemini_api_key"]:
                    cfg.gemini_api_key = data["gemini_api_key"]
                if "groq_api_key" in data and data["groq_api_key"]:
                    cfg.groq_api_key = data["groq_api_key"]
                if "auto_fallback" in data:
                    cfg.auto_fallback = bool(data["auto_fallback"])
                if "preferred_cloud" in data:
                    cfg.preferred_cloud = str(data["preferred_cloud"])
                if "llama_server_path" in data and data["llama_server_path"]:
                    cfg.llama_server_path = str(data["llama_server_path"])
                if "gguf_model_path" in data and data["gguf_model_path"]:
                    cfg.gguf_model_path = str(data["gguf_model_path"])
                break
            except Exception:
                pass

    # Environment variables override
    if key := os.environ.get("GEMINI_API_KEY"):
        cfg.gemini_api_key = key
    if key := os.environ.get("GROQ_API_KEY"):
        cfg.groq_api_key = key
    if server := os.environ.get("VERBACORE_LLAMA_SERVER"):
        cfg.llama_server_path = server
    if model := os.environ.get("VERBACORE_GGUF_MODEL"):
        cfg.gguf_model_path = model
    if host := os.environ.get("VERBACORE_HOST"):
        cfg.host = host
    if port := os.environ.get("VERBACORE_PORT"):
        try:
            cfg.port = int(port)
        except ValueError:
            pass
    if llm_url := os.environ.get("VERBACORE_LLM_URL"):
        cfg.brain_llm_url = llm_url

    return cfg
