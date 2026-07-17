#!/bin/bash
# BIM2BEM student toolkit - GitHub Codespaces launcher.
#
# Usage (run from a terminal inside the Codespace):
#   ./codespace_run.sh                # runs the demo IFC in cases_in/
#   ./codespace_run.sh cases_in/model.ifc
#
# This runs inside the Codespace environment that already contains the
# pipeline toolchain, so students do not need to install Docker locally.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "$#" -gt 1 ]; then
    echo "usage: ./codespace_run.sh [path/to/model.ifc]" >&2
    exit 1
fi

if [ "$#" -eq 1 ]; then
    INPUT_PATH="$1"
else
    if [ -f "$SCRIPT_DIR/cases_in/Demo4_2026-ifc4.ifc" ]; then
        INPUT_PATH="$SCRIPT_DIR/cases_in/Demo4_2026-ifc4.ifc"
    else
        INPUT_PATH="$(find "$SCRIPT_DIR/cases_in" -maxdepth 1 -type f -name '*.ifc' | head -n 1 || true)"
    fi
fi

if [[ "$INPUT_PATH" != /* ]]; then
    INPUT_PATH="$SCRIPT_DIR/$INPUT_PATH"
fi

if [ -z "${INPUT_PATH:-}" ] || [ ! -f "$INPUT_PATH" ]; then
    echo "No IFC file found. Upload a file to cases_in/ or pass a path explicitly." >&2
    exit 1
fi

echo "Using IFC file: $INPUT_PATH"

mkdir -p cases_out
/opt/pipeline/entrypoint.sh "$INPUT_PATH"

shopt -s nullglob
for output_file in /output/*.gbxml /output/*.idf /output/timing.json; do
    if [ -e "$output_file" ]; then
        cp "$output_file" "$SCRIPT_DIR/cases_out/"
    fi
done
shopt -u nullglob

echo "== Done. Results in: cases_out/ =="
