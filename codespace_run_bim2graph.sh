#!/bin/bash
# BIM2BEM student toolkit - BIM2Graph GitHub Codespaces launcher.
#
# Usage (run from a terminal inside the Codespace, after opening it with the
# "bim2graph" dev container configuration):
#   ./codespace_run_bim2graph.sh cases_in/model.ifc
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: ./codespace_run_bim2graph.sh path/to/model.ifc" >&2
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "File not found: $1" >&2
    exit 1
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$HERE/cases_out_bim2graph"
mkdir -p "$OUT_DIR"

python3 "$HERE/bim2graph/run_pipeline.py" "$1" -o "$OUT_DIR"

echo "== Done. Results in: $OUT_DIR =="
