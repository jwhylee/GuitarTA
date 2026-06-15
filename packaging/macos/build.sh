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

RUNNER_SWIFT="$STAGE_DIR/build/flutter/macos/Runner/MainFlutterWindow.swift"
FLUTTER_BIN="${FLUTTER_BIN:-}"
if [[ -z "$FLUTTER_BIN" ]]; then
  if command -v flutter >/dev/null 2>&1; then
    FLUTTER_BIN="$(command -v flutter)"
  else
    FLUTTER_BIN="$HOME/flutter/3.41.7/bin/flutter"
  fi
fi

python3 - "$RUNNER_SWIFT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
old = """    let windowFrame = self.frame
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)
"""
new = """    self.contentViewController = flutterViewController
    if let screenFrame = NSScreen.main?.visibleFrame {
      self.setFrame(screenFrame, display: true)
    }
"""
if old not in text:
    raise SystemExit(f"Unable to patch initial macOS window frame in {path}")
path.write_text(text.replace(old, new))
PY

(
  cd "$STAGE_DIR/build/flutter"
  "$FLUTTER_BIN" build macos --release
)

rm -rf "$OUTPUT_DIR/GuitarTA.app"
mkdir -p "$OUTPUT_DIR"
cp -R "$STAGE_DIR/build/flutter/build/macos/Build/Products/Release/GuitarTA.app" "$OUTPUT_DIR/"
rm -rf "$STAGE_DIR/build/flutter/build/macos/Build/Products/Release/GuitarTA.app"
