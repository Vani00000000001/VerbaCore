import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from verbacore.config import AppConfig
from verbacore.utils.paths import get_data_dir, get_models_dir

DEFAULT_GGUF_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
DEFAULT_GGUF_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEFAULT_LLAMA_PORT = 8080
DEFAULT_OLLAMA_PORT = 11434

_LLAMA_PROCESS: subprocess.Popen | None = None


def is_endpoint_alive(url: str, timeout: float = 2.0) -> bool:
    """Return True if an HTTP endpoint responds with a 2xx status code."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VerbaCore-Probe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return 200 <= res.status < 300
    except Exception:
        return False


def check_ollama_status(
    base_url: str = f"http://127.0.0.1:{DEFAULT_OLLAMA_PORT}",
) -> dict[str, Any]:
    """Check if Ollama service is reachable and retrieve list of available models."""
    norm_url = base_url.rstrip("/")
    tags_url = f"{norm_url}/api/tags"
    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "VerbaCore/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as res:
            if 200 <= res.status < 300:
                data = json.loads(res.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return {
                    "running": True,
                    "url": norm_url,
                    "models": models,
                    "has_qwen": any("qwen2.5" in m.lower() for m in models),
                }
    except Exception:
        pass
    return {"running": False, "url": norm_url, "models": [], "has_qwen": False}


def check_llama_server_status(
    base_url: str = f"http://127.0.0.1:{DEFAULT_LLAMA_PORT}",
) -> dict[str, Any]:
    """Check if llama-server is healthy and which model is loaded."""
    norm_url = base_url.rstrip("/")
    health_url = f"{norm_url}/health"
    try:
        req = urllib.request.Request(health_url, headers={"User-Agent": "VerbaCore/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as res:
            if 200 <= res.status < 300:
                models_url = f"{norm_url}/v1/models"
                loaded_model = "unknown"
                try:
                    m_req = urllib.request.Request(
                        models_url, headers={"User-Agent": "VerbaCore/1.0"}
                    )
                    with urllib.request.urlopen(m_req, timeout=2.0) as m_res:
                        m_data = json.loads(m_res.read().decode("utf-8"))
                        if m_data.get("data") and len(m_data["data"]) > 0:
                            loaded_model = m_data["data"][0].get("id", "llama-model")
                except Exception:
                    pass
                return {"running": True, "url": norm_url, "loaded_model": loaded_model}
    except Exception:
        pass
    return {"running": False, "url": norm_url, "loaded_model": None}


def find_llama_server(config: AppConfig | None = None) -> Path | None:
    """
    Search for a local llama-server executable across configured path, PATH,
    and application directories.
    """
    from verbacore.config import load_config

    cfg = config or load_config()

    # 1. Configured or environment path
    if cfg.llama_server_path:
        p = Path(cfg.llama_server_path).resolve()
        if p.is_file():
            return p

    exe_name = "llama-server.exe" if platform.system() == "Windows" else "llama-server"

    # 2. System PATH
    which_path = shutil.which(exe_name) or shutil.which("llama-server")
    if which_path:
        return Path(which_path).resolve()

    # 3. Dedicated bin subdirectories in application storage
    candidates = [
        get_models_dir() / "bin" / exe_name,
        get_data_dir() / "bin" / exe_name,
        Path.home() / "llama.cpp" / "build" / "bin" / "Release" / exe_name,
        Path.home() / ".local" / "bin" / exe_name,
    ]

    for c in candidates:
        if c.is_file():
            return c

    return None


def find_gguf_model(
    filename: str = DEFAULT_GGUF_FILENAME, config: AppConfig | None = None
) -> Path | None:
    """
    Locate an existing GGUF model file on disk.
    """
    from verbacore.config import load_config

    cfg = config or load_config()

    # 1. Configured or environment path
    if cfg.gguf_model_path:
        p = Path(cfg.gguf_model_path).resolve()
        if p.is_file():
            return p

    candidates = [
        get_models_dir() / filename,
        get_models_dir() / "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        get_models_dir() / "qwen2.5-1.5b.gguf",
    ]

    for c in candidates:
        if c.is_file():
            return c

    return None

    return None


def download_gguf_model(
    repo_id: str = DEFAULT_GGUF_REPO, filename: str = DEFAULT_GGUF_FILENAME
) -> Path:
    """
    Download Qwen 2.5 1.5B GGUF model weights from Hugging Face Hub directly into models directory.
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise RuntimeError(
            "huggingface_hub is required to download model weights. "
            "Please run: pip install huggingface_hub"
        )

    target_dir = get_models_dir()
    print(f"[Model Manager] Downloading {filename} from Hugging Face ({repo_id})...")
    print(f"[Model Manager] Destination directory: {target_dir}")

    downloaded = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(target_dir),
    )
    return Path(downloaded)


def ensure_gguf_model(
    repo_id: str = DEFAULT_GGUF_REPO,
    filename: str = DEFAULT_GGUF_FILENAME,
    auto_download: bool = True,
) -> Path | None:
    """
    Ensure the GGUF model exists locally, downloading it if absent and auto_download is enabled.
    """
    existing = find_gguf_model(filename)
    if existing:
        return existing

    if auto_download:
        return download_gguf_model(repo_id, filename)
    return None


def start_llama_server(
    server_bin: Path | None = None,
    model_path: Path | None = None,
    port: int = DEFAULT_LLAMA_PORT,
    threads: int = 4,
) -> bool:
    """
    Launch llama-server in the background serving the specified GGUF model.
    """
    global _LLAMA_PROCESS

    # If already running and healthy, nothing to do
    status = check_llama_server_status(f"http://127.0.0.1:{port}")
    if status["running"]:
        return True

    if not server_bin:
        server_bin = find_llama_server()
    if not server_bin or not server_bin.is_file():
        print("[Model Manager] llama-server binary not found.")
        return False

    if not model_path:
        model_path = ensure_gguf_model(auto_download=True)
    if not model_path or not model_path.is_file():
        print("[Model Manager] GGUF model weights not found or could not be downloaded.")
        return False

    print(f"[Model Manager] Starting llama-server on port {port}...")
    print(f"               Binary: {server_bin}")
    print(f"               Model:  {model_path}")

    cmd = [
        str(server_bin),
        "-m",
        str(model_path),
        "--port",
        str(port),
        "-c",
        "4096",
        "--threads",
        str(threads),
    ]

    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if platform.system() == "Windows":
        kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
        ) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

    try:
        _LLAMA_PROCESS = subprocess.Popen(cmd, **kwargs)
        # Poll health for up to 10 seconds
        for _ in range(20):
            time.sleep(0.5)
            if check_llama_server_status(f"http://127.0.0.1:{port}")["running"]:
                print(f"[Model Manager] llama-server is healthy and ready on port {port}!")
                return True
        print("[Model Manager] llama-server started but health check timed out.")
        return False
    except Exception as e:
        print(f"[Model Manager] Failed to launch llama-server: {e}")
        return False


def ensure_brain_llm_active(config: AppConfig | None = None) -> dict[str, Any]:
    """
    Orchestrate Brain LLM readiness:
    1. Check if Ollama is active.
    2. Check if llama-server is active.
    3. If neither, attempt to launch llama-server (downloading GGUF weights if needed).
    """
    # 1. Check Ollama
    ollama_status = check_ollama_status()
    if ollama_status["running"]:
        return {
            "active": True,
            "provider": "ollama",
            "url": f"http://127.0.0.1:{DEFAULT_OLLAMA_PORT}",
            "model": config.brain_llm_model if config else "qwen2.5:1.5b",
        }

    # 2. Check llama-server
    llama_status = check_llama_server_status()
    if llama_status["running"]:
        return {
            "active": True,
            "provider": "llama_server",
            "url": f"http://127.0.0.1:{DEFAULT_LLAMA_PORT}",
            "model": llama_status.get("loaded_model") or "qwen2.5:1.5b",
        }

    # 3. Attempt to launch llama-server
    print("[Model Manager] Neither Ollama nor llama-server is active. Attempting auto-start...")
    started = start_llama_server()
    if started:
        return {
            "active": True,
            "provider": "llama_server",
            "url": f"http://127.0.0.1:{DEFAULT_LLAMA_PORT}",
            "model": "qwen2.5-1.5b",
        }

    return {"active": False, "provider": "none", "url": None, "model": None}


def main():
    """CLI utility to probe, download, or launch local Brain LLM."""
    print("=" * 65)
    print("   VerbaCore Brain LLM & Model Manager")
    print("=" * 65)
    print()

    ollama = check_ollama_status()
    llama = check_llama_server_status()
    bin_path = find_llama_server()
    model_path = find_gguf_model()

    print(f"Ollama Service:       {'ONLINE' if ollama['running'] else 'OFFLINE'} ({ollama['url']})")
    if ollama["running"]:
        print(f"  Available models:   {', '.join(ollama['models']) or 'None'}")
    print(f"llama-server Service: {'ONLINE' if llama['running'] else 'OFFLINE'} ({llama['url']})")
    if llama["running"]:
        print(f"  Loaded model:       {llama['loaded_model']}")
    print(f"llama-server Binary:  {bin_path if bin_path else 'Not found on system'}")
    print(f"Qwen 1.5B GGUF Model: {model_path if model_path else 'Not found locally'}")
    print()

    if "--download" in sys.argv:
        if not model_path:
            download_gguf_model()
        else:
            print(f"[Model Manager] GGUF model already present at: {model_path}")

    if "--start" in sys.argv:
        ensure_brain_llm_active()


if __name__ == "__main__":
    main()
