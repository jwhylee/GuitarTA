#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGE_DIR="$ROOT_DIR/build/package_source_macos"
OUTPUT_DIR="$ROOT_DIR/build/macos"

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '*.egg-info' \
  "$ROOT_DIR/main.py" \
  "$ROOT_DIR/pyproject.toml" \
  "$ROOT_DIR/setup.py" \
  "$ROOT_DIR/src" \
  "$ROOT_DIR/assets" \
  "$STAGE_DIR/"

"$ROOT_DIR/.venv/bin/flet" build macos "$STAGE_DIR" \
  --output "$OUTPUT_DIR" \
  --arch arm64 \
  --artifact GuitarTA \
  --product GuitarTA \
  --bundle-id com.guitarta.app \
  --splash-color "#080706" \
  --splash-dark-color "#080706" \
  --info-plist NSQuitAlwaysKeepsWindows=false \
  --clear-cache \
  --yes
