#!/bin/bash
# BIM2BEM student toolkit - Mac/Linux launcher.
#
# Usage:
#   ./run.sh path/to/model.ifc
#
# Requires Docker Desktop (or Docker Engine) installed and running.
# First run will download the pipeline image (a few hundred MB); later
# runs reuse the cached image.
set -euo pipefail

IMAGE="ghcr.io/mengwang0331/bim2bem-cbip:latest"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker was not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and try again." >&2
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

IFC_DIR="$(cd "$(dirname "$1")" && pwd)"
IFC_NAME="$(basename "$1")"
OUT_DIR="$(cd "$(dirname "$0")" && pwd)/cases_out"
mkdir -p "$OUT_DIR"

echo "== Pulling pipeline image (skipped if already up to date) =="
docker pull "$IMAGE"

echo "== Running pipeline on $IFC_NAME =="
docker run --rm \
    -v "$IFC_DIR":/input:ro \
    -v "$OUT_DIR":/output \
    "$IMAGE" "/input/$IFC_NAME"

echo "== Done. Results in: $OUT_DIR =="
