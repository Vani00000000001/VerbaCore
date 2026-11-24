@echo off
setlocal
title VerbaCore Model Installer
cls

cd /d "%~dp0.."

set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

echo ======================================================================
echo    VerbaCore Offline Model Pre-Installer [Windows]
echo ======================================================================
echo.

"%PY_CMD%" scripts\install-models.py %*

echo.
pause
