@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Execute setup_windows.bat primeiro.
  pause
  exit /b 1
)
.venv\Scripts\python.exe app.py
if errorlevel 1 pause
