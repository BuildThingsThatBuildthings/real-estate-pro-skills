#!/bin/bash
# Content Foundry — Remotion render driver.
# Usage: render_video.sh <props.json> <out.mp4> [composition-id]
# Runs from anywhere; always executes inside the engine directory.
set -euo pipefail

PROPS="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT="$2"
COMP="${3:-Walkthrough}"
shift 3 || shift $#          # remaining args pass straight to remotion render
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../engines/remotion" && pwd)"

mkdir -p "$(dirname "$OUT")"
cd "$ENGINE_DIR"
exec npx remotion render src/index.ts "$COMP" "$OUT" --props="$PROPS" "$@"
