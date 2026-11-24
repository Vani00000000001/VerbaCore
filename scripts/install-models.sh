#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

if [ -f ".venv/bin/python" ]; then
    PY_CMD=".venv/bin/python"
else
    PY_CMD="python3"
fi

echo "======================================================================"
echo "   VerbaCore Offline Model Pre-Installer [Linux/macOS]"
echo "======================================================================"
echo ""

"$PY_CMD" scripts/install-models.py "$@"
