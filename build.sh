#!/bin/bash

# Which USB? - Build Script
# Creates a standalone executable using PyInstaller

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="which-usb-gui"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"

echo "=== Which USB? Build Script ==="

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✓ Using virtual environment: $VIRTUAL_ENV"
else
    echo "❌ Error: Virtual environment required"
    echo "Please activate your virtual environment first:"
    echo "  source .venv/bin/activate"
    echo "  ./build.sh"
    exit 1
fi

# Check dependencies
echo "Checking build dependencies..."

if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "Installing PyInstaller..."
    if command -v uv &> /dev/null; then
        uv pip install pyinstaller
    else
        python3 -m pip install pyinstaller
    fi
fi

if ! python3 -c "import PyQt6" &> /dev/null; then
    echo "Installing PyQt6..."
    if command -v uv &> /dev/null; then
        uv pip install PyQt6
    else
        python3 -m pip install PyQt6
    fi
fi

echo "✓ Build dependencies satisfied"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$DIST_DIR"
rm -rf "$BUILD_DIR"
rm -f "$SCRIPT_DIR/*.spec"

# Build executable
echo "Building executable..."
python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name "$APP_NAME" \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "$SCRIPT_DIR" \
    --add-data "images:images" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtWidgets" \
    --hidden-import "PyQt6.QtGui" \
    --hidden-import "PyQt6.QtNetwork" \
    "$SCRIPT_DIR/which-usb-gui.py"

# Clean up build artifacts
echo "Cleaning up build artifacts..."
rm -rf "$BUILD_DIR"
rm -f "$SCRIPT_DIR/*.spec"

# Make executable
chmod +x "$DIST_DIR/$APP_NAME"

echo "✓ Build complete!"
echo ""
echo "Executable created at: $DIST_DIR/$APP_NAME"
echo "File size: $(du -h "$DIST_DIR/$APP_NAME" | cut -f1)"
echo ""
echo "To run the executable:"
echo "  ./dist/$APP_NAME"
echo ""
echo "To install system-wide:"
echo "  sudo cp ./dist/$APP_NAME /usr/local/bin/"
