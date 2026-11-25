# Contributing to VerbaCore

Thanks for your interest in VerbaCore — the offline, turn-based multilingual speech recognition and audio intelligence engine. We welcome bug reports, feature ideas, documentation improvements, and code contributions.

## Getting Started

### Prerequisites

- Python 3.10 or newer
- `pip` (preferably inside a virtual environment)

### 1. Clone and install

```bash
git clone https://github.com/your-username/verbacore.git
cd verbacore
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"
```

The `.[dev]` extra installs `pytest`, `ruff`, and `mypy` for testing and linting.

### 2. Run the app

**Windows:**
```cmd
launch.bat
```

**Linux / macOS:**
```bash
chmod +x launch.sh
./launch.sh
```

Or directly:
```bash
python -m verbacore.server
```

Open `http://127.0.0.1:7860` in your browser.

## Making Changes

### Code style

- Follow [PEP 8](https://pep8.org/) and keep code Pythonic with type hints where practical.
- Run the linter and type checker before submitting:

```bash
ruff check src tests
ruff format --check src tests
mypy src
```

### Tests

VerbaCore uses `pytest`. Run the full suite from the repo root:

```bash
pytest -v
```

CI runs `ruff check src tests`, `ruff format --check src tests`, `mypy src`, and `pytest -v` on every push and pull request across Ubuntu, Windows, and macOS (Python 3.10–3.12). Please make sure all checks and tests pass locally before opening a PR.

### Configuration secrets

Do **not** commit real API keys. Cloud settings live in a local, gitignored `cloud_config.json` (see `cloud_config.example.json` for the shape). Never add keys to the repo.

## Submitting a Pull Request

1. Fork the repo and create a feature branch from `main`.
2. Make your changes, add or update tests as needed, and run `pytest -v`, `ruff`, and `mypy`.
3. Open a pull request against `main` with a clear description of what changed and why.
4. Keep PRs focused on one concern. Large features are easier to review when split into smaller PRs.

### Commit style

Use concise, imperative commit messages, e.g.:

```
feat: add Portuguese language guardrail
fix: resolve ffmpeg path lookup on Windows
docs: update offline model setup instructions
```

## Project Layout

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
├── tests/            # Automated test suite
└── CONTRIBUTING.md   # this file
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License that covers this project.

## Questions?

Open an issue for bugs, feature requests, or discussion. For quick questions, a GitHub Discussion works well too.

Happy contributing! 🎙️