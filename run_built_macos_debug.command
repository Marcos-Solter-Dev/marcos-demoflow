#!/bin/bash
set -e
cd "$(dirname "$0")"

APP_EXEC='dist/Marcos DemoFlow.app/Contents/MacOS/Marcos DemoFlow'

if [ ! -x "$APP_EXEC" ]; then
  echo "O .app ainda não foi gerado."
  echo "Execute primeiro: ./build_macos.command"
  exit 1
fi

echo "Abrindo o executável interno para mostrar erros no Terminal..."
echo
"$APP_EXEC"
