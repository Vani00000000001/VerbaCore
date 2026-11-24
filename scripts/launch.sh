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
    echo "[Setup] Creating portable Python virtual environment in .venv..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e .
fi

echo "[2/3] Checking Brain LLM status [Ollama / llama-server]..."
.venv/bin/python -m verbacore.llm.manager || true

echo ""
echo "[3/3] Starting VerbaCore Server at http://127.0.0.1:7860..."
if which xdg-open > /dev/null; then
    xdg-open "http://127.0.0.1:7860" &
elif which open > /dev/null; then
    open "http://127.0.0.1:7860" &
fi

.venv/bin/python -m verbacore.server
