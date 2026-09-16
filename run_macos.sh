#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Execute ./setup_macos.sh primeiro."
  exit 1
fi

if ! .venv/bin/python - <<'PYCHECK' >/dev/null 2>&1
import tkinter as tk
raise SystemExit(0 if tk.TkVersion >= 8.6 else 1)
PYCHECK
then
  cat <<'MSG'
A .venv ainda está usando o Tk antigo do macOS.
Apague a venv e rode ./setup_macos.sh novamente usando Python 3.12 moderno.
MSG
  exit 2
fi

export TK_SILENCE_DEPRECATION=1
exec .venv/bin/python app.py
