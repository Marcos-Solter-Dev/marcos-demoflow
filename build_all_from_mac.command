#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

REPO="Marcos-Solter-Dev/marcos-demoflow"
WORKFLOW="build-desktop.yml"
OUT="dist/github"

command -v gh >/dev/null 2>&1 || { echo "Instale: brew install gh"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Execute: gh auth login"; exit 1; }

gh workflow run "$WORKFLOW" --repo "$REPO"
sleep 3
RUN_ID="$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$RUN_ID" --repo "$REPO" --exit-status
rm -rf "$OUT"
mkdir -p "$OUT"
gh run download "$RUN_ID" --repo "$REPO" --dir "$OUT"
echo "Builds baixados para $OUT"
