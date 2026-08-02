#!/bin/bash
# Builds Aether-x86_64.AppImage from the current source tree.
#
# What this does NOT do: bundle Ollama (a real system service, several
# GB of model weights — see AppRun's comments) or bundle Prudhvi's real
# dev database (a fresh, schema-only DB is generated instead — see the
# seed-DB step below and STATUS.md for why the baseline migration needed
# a fix before this could even work).
#
# Usage: ./packaging/appimage/build.sh
# Output: ./Aether-x86_64.AppImage in the repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="$(mktemp -d)"
APPDIR="$BUILD_DIR/Aether.AppDir"

echo "==> Building in $BUILD_DIR"
trap 'rm -rf "$BUILD_DIR"' EXIT

# ---- 1. frontend production build ----
echo "==> Building frontend (npm run build)..."
(cd "$REPO_ROOT/frontend" && npm run build --silent)

# ---- 2. AppDir skeleton ----
mkdir -p "$APPDIR/usr/backend" "$APPDIR/usr/frontend-build"

# ---- 3. copy backend source, excluding dev-only artifacts ----
echo "==> Copying backend source..."
rsync -a \
    --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='aether.db' --exclude='.pytest_cache' \
    "$REPO_ROOT/backend/" "$APPDIR/usr/backend/"
find "$APPDIR/usr/backend" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# ---- 4. copy frontend build ----
echo "==> Copying frontend build..."
rsync -a "$REPO_ROOT/frontend/build/" "$APPDIR/usr/frontend-build/"

# ---- 5. fresh, self-contained venv ----
# --copies (not symlinks) + requirements.txt pinned versions — see
# requirements.txt's own history for why this file exists at all
# (it didn't, until this same session — the dev venv had been built ad
# hoc with no reproducible record).
echo "==> Building venv..."
(cd "$APPDIR/usr/backend" && \
    python3 -m venv --copies .venv && \
    .venv/bin/pip install --quiet --upgrade pip && \
    .venv/bin/pip install --quiet -r requirements.txt)

# ---- 6. schema-only seed DB ----
# Requires the cb702a809575 baseline-migration fix (see STATUS.md,
# found live while first building this) — before that fix, alembic
# upgrade head against a genuinely empty DB crashed partway through.
echo "==> Generating seed database..."
(cd "$APPDIR/usr/backend" && .venv/bin/alembic upgrade head)
mv "$APPDIR/usr/backend/aether.db" "$APPDIR/usr/seed.db"

# ---- 7. AppRun / desktop file / icon ----
cp "$REPO_ROOT/packaging/appimage/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp "$REPO_ROOT/packaging/appimage/Aether.desktop" "$APPDIR/Aether.desktop"
if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w 256 -h 256 "$REPO_ROOT/packaging/appimage/aether-icon.svg" -o "$APPDIR/aether.png"
else
    echo "WARNING: rsvg-convert not found — AppImage will build without an icon."
fi

# ---- 8. appimagetool (cached under packaging/appimage/.cache, gitignored) ----
CACHE_DIR="$REPO_ROOT/packaging/appimage/.cache"
mkdir -p "$CACHE_DIR"
if [ ! -x "$CACHE_DIR/appimagetool.AppImage" ]; then
    echo "==> Downloading appimagetool..."
    curl -sL -o "$CACHE_DIR/appimagetool.AppImage" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$CACHE_DIR/appimagetool.AppImage"
fi

echo "==> Packaging..."
rm -f "$REPO_ROOT/Aether-x86_64.AppImage"
ARCH=x86_64 "$CACHE_DIR/appimagetool.AppImage" \
    "$APPDIR" "$REPO_ROOT/Aether-x86_64.AppImage"

echo "==> Done: $REPO_ROOT/Aether-x86_64.AppImage"
