#!/usr/bin/env python3
"""
VerbaCore Offline Model Pre-Downloader
Downloads faster-whisper ASR weights and Qwen 2.5 1.5B GGUF weights for complete offline usage.
"""
import sys
import argparse
from pathlib import Path

# Add src to sys.path if not installed yet
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from verbacore.utils.paths import get_models_dir
from verbacore.llm.manager import (
    download_gguf_model,
    find_gguf_model,
    DEFAULT_GGUF_REPO,
    DEFAULT_GGUF_FILENAME
)


def install_whisper_models(models: list[str]):
    print("=" * 65)
    print("   1. faster-whisper ASR Models")
    print("=" * 65)
    models_dir = get_models_dir()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[!] faster-whisper is not installed. Run: pip install faster-whisper")
        return

    for m in models:
        print(f"\n[*] Pre-downloading faster-whisper [{m}] into: {models_dir}...")
        try:
            # Instantiating WhisperModel with download_root downloads the weights
            WhisperModel(m, device="cpu", compute_type="int8", download_root=str(models_dir))
            print(f"[OK] faster-whisper [{m}] successfully cached!")
        except Exception as e:
            print(f"[ERROR] Failed downloading [{m}]: {e}")


def install_brain_llm(repo_id: str = DEFAULT_GGUF_REPO, filename: str = DEFAULT_GGUF_FILENAME):
    print("\n" + "=" * 65)
    print("   2. Qwen 2.5 1.5B Brain LLM (llama.cpp GGUF)")
    print("=" * 65)
    existing = find_gguf_model(filename)
    if existing:
        print(f"[OK] GGUF model already present on system at: {existing}")
        return

    print(f"[*] Downloading {filename} from {repo_id}...")
    try:
        path = download_gguf_model(repo_id, filename)
        print(f"[OK] GGUF model successfully downloaded to: {path}")
    except Exception as e:
        print(f"[ERROR] Failed downloading GGUF model: {e}")


def main():
    parser = argparse.ArgumentParser(description="VerbaCore Offline Model Installer")
    parser.add_argument(
        "--whisper",
        nargs="+",
        default=["small"],
        help="Whisper model sizes to download (e.g. tiny base small medium)"
    )
    parser.add_argument(
        "--skip-whisper",
        action="store_true",
        help="Skip downloading faster-whisper models"
    )
    parser.add_argument(
        "--skip-brain",
        action="store_true",
        help="Skip downloading Qwen GGUF model"
    )
    args = parser.parse_args()

    print("=" * 65)
    print("   VerbaCore Offline Model Pre-Installer")
    print(f"   Target Directory: {get_models_dir()}")
    print("=" * 65)

    if not args.skip_whisper:
        install_whisper_models(args.whisper)

    if not args.skip_brain:
        install_brain_llm()

    print("\n" + "=" * 65)
    print("   All requested models installed and ready for offline use!")
    print("=" * 65)


if __name__ == "__main__":
    main()
