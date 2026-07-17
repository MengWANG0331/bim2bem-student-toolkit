#!/bin/bash
# BIM2BEM student toolkit - BIM2Graph launcher (Mac/Linux).
# IFC -> Brick/BOT/FSO knowledge graph -> simplified topology views.
#
# Usage:
#   ./run_bim2graph.sh path/to/model.ifc
#
# Requires Python 3.11+ (no Docker needed - this tool is plain Python and its
# source is not hidden, see bim2graph/ in this repo for the real code). First
# run creates a local virtual environment and installs dependencies; later
# runs reuse it.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/bim2graph/.venv"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11+ was not found. Install it from https://www.python.org/downloads/ and try again." >&2
    exit 1
fi

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <path-to-model.ifc>" >&2
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "File not found: $1" >&2
    exit 1
fi

if [ ! -x "$VENV/bin/python" ]; then
    echo "== First run: setting up a local Python environment, this can take a few minutes =="
    python3 -m venv "$VENV"
    "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV/bin/python" -m pip install -r "$HERE/bim2graph/requirements.txt"
fi

OUT_DIR="$HERE/cases_out_bim2graph"
mkdir -p "$OUT_DIR"

echo "== Running BIM2Graph on $(basename "$1") =="
"$VENV/bin/python" "$HERE/bim2graph/run_pipeline.py" "$1" -o "$OUT_DIR"

echo "== Done. Results in: $OUT_DIR =="
