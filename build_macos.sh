#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo
echo "============================================"
echo "  Marcos DemoFlow - Build macOS .app"
echo "============================================"
echo

is_good_python() {
  local p="$1"

  if [[ "$p" == */* ]]; then
    [ -x "$p" ] || return 1
  else
    command -v "$p" >/dev/null 2>&1 || return 1
  fi

  "$p" - <<'PYCHECK' >/dev/null 2>&1
import sys
import tkinter as tk
from tkinter import ttk

if sys.version_info < (3, 11) or tk.TkVersion < 8.6:
    raise SystemExit(1)

root = tk.Tk()
root.withdraw()
themes = set(ttk.Style(root).theme_names())
root.destroy()

raise SystemExit(0 if themes.intersection({"clam", "alt", "classic"}) else 1)
PYCHECK
}

CANDIDATES=()
if [ -n "${PYTHON_BIN:-}" ]; then
  CANDIDATES+=("$PYTHON_BIN")
fi

CANDIDATES+=(
  "/opt/homebrew/bin/python3.12"
  "/usr/local/bin/python3.12"
  "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
  "/opt/homebrew/bin/python3.13"
  "/usr/local/bin/python3.13"
  "python3.12"
  "python3.13"
  "python3"
)

PY=""

echo "[1/7] Procurando Python/Tk compatível..."
for candidate in "${CANDIDATES[@]}"; do
  if is_good_python "$candidate"; then
    if [[ "$candidate" == */* ]]; then
      PY="$candidate"
    else
      PY="$(command -v "$candidate")"
    fi
    break
  fi
done

if [ -z "$PY" ]; then
  echo
  echo "ERRO: não encontrei Python com Tk moderno e tema ttk compatível."
  echo
  echo "Instale no Mac com:"
  echo "  brew install python@3.12 python-tk@3.12"
  echo
  echo "Depois execute novamente:"
  echo "  ./build_macos.command"
  echo
  exit 2
fi

echo "Python escolhido:"
echo "  $PY"
"$PY" - <<'PYINFO'
import sys
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.withdraw()
themes = ttk.Style(root).theme_names()
root.destroy()

print(f"  Python {sys.version.split()[0]}")
print(f"  Tk {tk.TkVersion} / Tcl {tk.TclVersion}")
print(f"  Temas ttk: {', '.join(themes)}")
PYINFO

export TK_SILENCE_DEPRECATION=1

echo "[2/7] Validando ambiente de build..."
RECREATE=0

if [ ! -x ".venv-build/bin/python" ]; then
  RECREATE=1
else
  if ! .venv-build/bin/python - <<'VENVTEST' >/dev/null 2>&1
import sys
import tkinter as tk
from tkinter import ttk

if sys.version_info < (3, 11) or tk.TkVersion < 8.6:
    raise SystemExit(1)

root = tk.Tk()
root.withdraw()
themes = set(ttk.Style(root).theme_names())
root.destroy()
raise SystemExit(0 if themes.intersection({"clam", "alt", "classic"}) else 1)
VENVTEST
  then
    RECREATE=1
  fi
fi

if [ "$RECREATE" -eq 1 ]; then
  echo "A .venv-build antiga não é adequada; recriando..."
  rm -rf .venv-build
  "$PY" -m venv .venv-build
else
  echo "A .venv-build atual é compatível."
fi

source .venv-build/bin/activate

echo "[3/7] Conferindo Python/Tk do ambiente..."
python - <<'PYINFO2'
import sys
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.withdraw()
style = ttk.Style(root)
themes = style.theme_names()
root.destroy()

print(f"  Executável: {sys.executable}")
print(f"  Python: {sys.version.split()[0]}")
print(f"  Tk: {tk.TkVersion}")
print(f"  Temas: {', '.join(themes)}")
assert tk.TkVersion >= 8.6
assert set(themes).intersection({"clam", "alt", "classic"})
PYINFO2

echo "[4/7] Instalando dependências..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install --upgrade pyinstaller pillow

echo "[5/7] Criando ícone .icns..."
ICONSET="assets/MarcosDemoFlow.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

python - <<'PY'
from pathlib import Path
from PIL import Image

src = Path("assets/app_icon.png")
img = Image.open(src).convert("RGBA")

sizes = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

out = Path("assets/MarcosDemoFlow.iconset")
for size, name in sizes:
    img.resize((size, size), Image.Resampling.LANCZOS).save(out / name)
PY

iconutil -c icns "$ICONSET" -o "assets/app_icon.icns"
rm -rf "$ICONSET"

echo "[6/7] Limpando build anterior..."
rm -rf build
rm -rf "dist/Marcos DemoFlow.app"
rm -f "Marcos DemoFlow.spec"

echo "[7/7] Criando aplicativo macOS..."
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Marcos DemoFlow" \
  --osx-bundle-identifier "com.marcosdev.demoflow" \
  --icon "assets/app_icon.icns" \
  --add-data "assets:assets" \
  --collect-submodules Quartz \
  --collect-submodules pyautogui \
  --collect-submodules mss \
  app.py

APP_EXEC="dist/Marcos DemoFlow.app/Contents/MacOS/Marcos DemoFlow"

if [ ! -x "$APP_EXEC" ]; then
  echo
  echo "ERRO: o executável do .app não foi criado."
  exit 3
fi

echo
echo "============================================"
echo "BUILD CONCLUÍDO"
echo "============================================"
echo
echo "Aplicativo:"
echo '  dist/Marcos DemoFlow.app'
echo
echo "Abra normalmente com:"
echo '  open "dist/Marcos DemoFlow.app"'
echo
echo "Se precisar ver erros no Terminal:"
echo '  "dist/Marcos DemoFlow.app/Contents/MacOS/Marcos DemoFlow"'
echo
read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
echo
