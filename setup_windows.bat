@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (
  echo Python nao encontrado. Instale Python 3.11 ou 3.12 e marque Add Python to PATH.
  pause
  exit /b 1
)
if not exist .venv (
  python -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Houve um erro instalando as dependencias.
  pause
  exit /b 1
)
echo.
echo Instalacao concluida. Use run_windows.bat para abrir o DemoFlow.
pause
