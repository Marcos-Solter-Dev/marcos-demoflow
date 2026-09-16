#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

is_good_python() {
  local p="$1"
  if [[ "$p" == */* ]]; then
    [ -x "$p" ] || return 1
  else
    command -v "$p" >/dev/null 2>&1 || return 1
  fi
  "$p" - <<'PYCHECK' >/dev/null 2>&1
import sys, tkinter as tk
raise SystemExit(0 if sys.version_info >= (3, 11) and tk.TkVersion >= 8.6 else 1)
PYCHECK
}

CANDIDATES=()
if [ -n "${PYTHON_BIN:-}" ]; then CANDIDATES+=("$PYTHON_BIN"); fi
CANDIDATES+=(
  "/opt/homebrew/bin/python3.12"
  "/usr/local/bin/python3.12"
  "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
  "python3.12"
  "python3"
)

PY=""
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
  cat <<'MSG'

Não encontrei um Python com Tk moderno (Tk 8.6+).
O Python/Tk do próprio macOS pode abrir o DemoFlow como uma janela preta.

Com Homebrew, rode:
  brew install python@3.12 python-tk@3.12
  rm -rf .venv
  PYTHON_BIN="$(brew --prefix python@3.12)/bin/python3.12" ./setup_macos.sh

Ou instale Python 3.12 pelo instalador oficial do Python e execute novamente.
MSG
  exit 2
fi

echo "Usando: $PY"
"$PY" - <<'PYINFO'
import sys, tkinter as tk
print(f"Python {sys.version.split()[0]} | Tk {tk.TkVersion} | Tcl {tk.TclVersion}")
PYINFO

if [ -d .venv ]; then
  if ! .venv/bin/python - <<'PYCHECK2' >/dev/null 2>&1
import sys, tkinter as tk
raise SystemExit(0 if sys.version_info >= (3,11) and tk.TkVersion >= 8.6 else 1)
PYCHECK2
  then
    echo "A venv atual usa Tk antigo; recriando..."
    rm -rf .venv
  fi
fi

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Instalação concluída. Rode: ./run_macos.sh"
