@echo off
setlocal EnableDelayedExpansion
title VerbaCore (Portable Edition)
cls

echo ======================================================================
echo    VERBACORE [Portable Open-Source Edition]
echo    Offline Speech Recognition and Audio Intelligence
echo ======================================================================
echo.

rem Navigate to repository root
cd /d "%~dp0.."

rem 1. Discover or create virtual environment
echo [1/3] Checking Python virtual environment...
set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    echo [Setup] Creating portable Python virtual environment in .venv...
    python -m venv .venv
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Could not create virtual environment. Ensure Python 3.10+ is installed.
        pause
        exit /b 1
    )
    set "PY_CMD=.venv\Scripts\python.exe"
    echo [Setup] Installing dependencies...
    "%PY_CMD%" -m pip install --upgrade pip
    "%PY_CMD%" -m pip install -e .
)

rem 2. Check Local Brain LLM Status
echo [2/3] Checking Brain LLM status [Ollama / llama-server]...
"%PY_CMD%" -m verbacore.llm.manager

rem 3. Launch Web Server
echo.
echo [3/3] Starting VerbaCore Server at http://127.0.0.1:7860...
start "" "http://127.0.0.1:7860"
"%PY_CMD%" -m verbacore.server

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Server stopped with error code %ERRORLEVEL%
    pause
)
