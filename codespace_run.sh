#!/bin/bash
# BIM2BEM student toolkit - GitHub Codespaces launcher.
#
# Usage (run from a terminal inside the Codespace):
#   ./codespace_run.sh cases_in/model.ifc
#
# Unlike run.sh (which does `docker run` from your own machine), this runs
# directly inside the container the Codespace is already using - no Docker
# commands needed here.
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: ./codespace_run.sh path/to/model.ifc" >&2
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "File not found: $1" >&2
    exit 1
fi

/opt/pipeline/entrypoint.sh "$1"

mkdir -p cases_out
cp /output/*.gbxml /output/*.idf /output/timing.json cases_out/
echo "== Done. Results in: cases_out/ =="
