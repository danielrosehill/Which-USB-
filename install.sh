#!/bin/bash

# Which USB? - GUI Installation Script
# Installs the Which USB? GUI application for system-wide access

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/usr/local/bin"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/pixmaps"
APP_NAME="which-usb-gui"

echo "=== Which USB? GUI Installation ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script needs to be run as root (use sudo)"
    echo "Usage: sudo ./install.sh"
    exit 1
fi

# Check dependencies
echo "Checking dependencies..."

if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    echo "Install with: apt install python3"
    exit 1
fi

if ! command -v lsusb &> /dev/null; then
    echo "Error: lsusb is required but not found"
    echo "Install with: apt install usbutils"
    exit 1
fi

# Check for PySide6
if ! python3 -c "import PySide6" &> /dev/null; then
    echo "Error: PySide6 is required but not found"
    echo "Install with: pip install PySide6"
    exit 1
fi

echo "✓ Dependencies satisfied"

# Install Python requirements
echo "Installing Python dependencies..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip3 install -r "$SCRIPT_DIR/requirements.txt"
fi

# Copy main application
echo "Installing GUI application..."
cp "$SCRIPT_DIR/which-usb-gui.py" "$INSTALL_DIR/$APP_NAME"
chmod +x "$INSTALL_DIR/$APP_NAME"

# Copy run script
cp "$SCRIPT_DIR/run-gui.sh" "$INSTALL_DIR/which-usb-gui.sh"
chmod +x "$INSTALL_DIR/which-usb-gui.sh"

# Create desktop entry
echo "Creating desktop entry..."
cat > "$DESKTOP_DIR/which-usb-gui.desktop" << EOF
[Desktop Entry]
Name=Which USB?
Comment=Identify USB devices by connection/disconnection
Exec=$INSTALL_DIR/$APP_NAME
Icon=usb
Terminal=false
Type=Application
Categories=System;Utility;
Keywords=USB;device;identification;hardware;
EOF

echo "✓ Installation complete!"
echo ""
echo "You can now run the GUI application using:"
echo "  which-usb-gui"
echo "  which-usb-gui.sh"
echo "  Or find it in your applications menu as 'Which USB?'"
echo ""
echo "For best results detecting all USB devices, run with sudo:"
echo "  sudo which-usb-gui"
