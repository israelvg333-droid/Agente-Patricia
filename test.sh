#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif [[ -x ".venv/Scripts/python.exe" ]]; then
  PYTHON=".venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "Error: no se encontro Python en .venv ni en PATH." >&2
  exit 127
fi

if ! "$PYTHON" -c "import pytest" >/dev/null 2>&1; then
  echo "Error: pytest no esta instalado para $PYTHON." >&2
  echo "Instalalo con: $PYTHON -m pip install pytest" >&2
  exit 1
fi

echo "Ejecutando pruebas con $PYTHON..."
if [[ $# -eq 0 ]]; then
  "$PYTHON" -m pytest tests/ -v
else
  "$PYTHON" -m pytest "$@"
fi
