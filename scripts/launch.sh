#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "======================================================================"
echo "   VERBACORE [Portable Open-Source Edition]"
echo "   Offline Speech Recognition and Audio Intelligence"
echo "======================================================================"
echo ""

echo "[1/3] Checking Python virtual environment..."
if [ ! -f ".venv/bin/python" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo "[ERROR] python3 was not found on PATH. Ensure Python 3.10+ is installed." >&2
        exit 1
    fi
    echo "[Setup] Creating portable Python virtual environment in .venv..."
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -e .
fi

echo "[2/3] Checking Brain LLM status [Ollama / llama-server]..."
.venv/bin/python -m verbacore.llm.manager || true

echo ""
echo "[3/3] Starting VerbaCore Server at http://127.0.0.1:7860..."
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:7860" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:7860" >/dev/null 2>&1 &
fi

exec .venv/bin/python -m verbacore.server
