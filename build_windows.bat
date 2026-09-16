@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   Marcos DemoFlow - Build Windows EXE
echo ============================================
echo.

if not exist ".venv-build\Scripts\python.exe" (
    echo [1/5] Criando ambiente de build...
    py -3 -m venv .venv-build 2>nul
    if errorlevel 1 (
        python -m venv .venv-build
        if errorlevel 1 goto :error
    )
) else (
    echo [1/5] Ambiente de build ja existe.
)

call ".venv-build\Scripts\activate.bat"

echo [2/5] Atualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/5] Instalando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python -m pip install pyinstaller
if errorlevel 1 goto :error

echo [4/5] Limpando build anterior...
if exist build rmdir /s /q build
if exist "dist\Marcos DemoFlow.exe" del /q "dist\Marcos DemoFlow.exe"
if exist "Marcos DemoFlow.spec" del /q "Marcos DemoFlow.spec"

echo [5/5] Criando EXE...
pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "Marcos DemoFlow" ^
  --icon "assets\app_icon.ico" ^
  --add-data "assets;assets" ^
  --collect-submodules pyautogui ^
  --collect-submodules mss ^
  app.py

if errorlevel 1 goto :error

echo.
echo ============================================
echo BUILD CONCLUIDO
echo Arquivo:
echo   dist\Marcos DemoFlow.exe
echo ============================================
echo.
pause
exit /b 0

:error
echo.
echo ============================================
echo ERRO AO CRIAR O EXE
echo Verifique as mensagens acima.
echo ============================================
echo.
pause
exit /b 1
