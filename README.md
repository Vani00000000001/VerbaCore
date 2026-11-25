# VerbaCore

Offline, Turn-Based Multilingual Speech Recognition & Audio Intelligence Engine.

VerbaCore runs 100% locally on your machine with zero cloud dependency required, providing speech-to-text, speaker diarization, anti-hallucination guardrails, and executive document generation.

---

## Features

- **Local-First ASR**: Powered by `faster-whisper` (CTranslate2 int8 quantized models) for fast, lightweight CPU & GPU transcription.
- **Multilingual & Bilingual Code-Switching**: Dynamic turn-level switching optimized for mixed language conversations (e.g. Tanglish, Hinglish).
- **Anti-Hallucination & Repetition Guardrails**: Automated detection and removal of Whisper autoregressive looping, silence artifacts, and prompt hallucinations.
- **Local Brain LLM Intelligence**: Connects to Ollama or local GGUF models (`qwen2.5:1.5b`) for speaker diarization, executive summaries, key takeaways, and action items.
- **Optional Cloud Fallback**: Free-tier cloud fallback via Google Gemini Flash or Groq Whisper Large V3 for low-resource or degraded audio.
- **Multi-Format Export**: One-click generation of verbatim transcripts and executive summaries in PDF, Word (`.docx`), TXT, and SubRip (`.srt`) subtitle formats.
- **Fully Cross-Platform**: Native support and paths on Windows, macOS, and Linux.

---

## Quickstart

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/verbacore.git
cd verbacore
pip install -e .
```

### 2. Launching

**On Windows:**
```cmd
launch.bat
```

**On Linux / macOS:**
```bash
chmod +x launch.sh
./launch.sh
```

Or run directly with Python:
```bash
python -m verbacore.server
```

Open your browser at `http://127.0.0.1:7860`.

---

## Architecture

```
verbacore/
├── src/verbacore/
│   ├── asr/          # faster-whisper turn engine and guardrails
│   ├── llm/          # Local Ollama Brain LLM & cloud fallback
│   ├── reports/      # PDF, DOCX, TXT, and SRT generators
│   ├── recordings/   # Chunked browser recording manager
│   ├── utils/        # Cross-platform paths and FFmpeg helpers
│   ├── config.py     # Application configuration
│   └── server.py     # FastAPI server and endpoints
├── static/           # Responsive dark-mode web application
└── tests/            # Automated test suite
```

---

## Models & Offline Setup

VerbaCore is designed to work completely offline out-of-the-box without requiring any cloud API keys:

1. **Speech Recognition (ASR)**:
   - VerbaCore uses `faster-whisper` (CTranslate2 int8 models).
   - Upon first transcription, VerbaCore will automatically download the requested model (e.g. `small`, `medium`) into your local models directory.

2. **Brain LLM (Diarization & Executive Summary)**:
   - If **Ollama** is running locally (`ollama run qwen2.5:1.5b`), VerbaCore connects to it automatically on port 11434.
   - If Ollama is **not** installed or running, VerbaCore automatically downloads `qwen2.5-1.5b-instruct-q4_k_m.gguf` (~0.98 GB) from Hugging Face and launches it locally using `llama.cpp` (`llama-server`) on port 8080!

3. **Pre-downloading All Models for Offline Deployments**:
   To pre-fetch all model weights before going into an offline environment:

   ```bash
   # On Windows
   scripts\install-models.bat

   # On Linux / macOS
   ./scripts/install-models.sh
   ```

---

## Cloud Fallback (Optional)

Cloud transcription is **100% optional**. You do not need any API key to use VerbaCore.

If you wish to enable cloud fallback for difficult audio recordings:
- Open the web UI at `http://127.0.0.1:7860`.
- Click **Cloud Fallback** in the top navigation bar.
- Enter your **Google Gemini** or **Groq** API key and save.
- Settings are saved locally in your private `cloud_config.json` (gitignored).

---

## Configuration

Configuration can be set via environment variables or a local `cloud_config.json`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VERBACORE_HOST` | `127.0.0.1` | Server host address |
| `VERBACORE_PORT` | `7860` | Server listening port |
| `VERBACORE_DATA_DIR` | Auto OS path | Directory for recordings and reports |
| `VERBACORE_MODELS_DIR`| `$DATA_DIR/models` | Local Whisper & GGUF model weights directory |
| `VERBACORE_LLM_URL` | `http://127.0.0.1:11434` | Ollama or llama-server base URL |
| `VERBACORE_LLAMA_SERVER` | None | Custom path to `llama-server` binary |
| `VERBACORE_GGUF_MODEL` | None | Custom path to local GGUF model weights |
| `GEMINI_API_KEY` | None | Optional Google Gemini fallback key |
| `GROQ_API_KEY` | None | Optional Groq fallback key |

---

## Running Local Brain LLM Manually

VerbaCore connects automatically to Ollama or starts llama-server, but you can also run them manually:

```bash
# Option A: Ollama
ollama run qwen2.5:1.5b

# Option B: llama.cpp server
llama-server -m models/qwen2.5-1.5b-instruct-q4_k_m.gguf --port 8080 -c 4096 --threads 4
```

---

## License

This project is licensed under the MIT License (see `pyproject.toml`).
