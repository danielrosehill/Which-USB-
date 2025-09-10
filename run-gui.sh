#!/bin/bash

# Which USB? - GUI Launcher
# Runs the GUI version with proper virtual environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Virtual environment not found. Running setup..."
    cd "$SCRIPT_DIR"
    
    # Create virtual environment
    if command -v uv &> /dev/null; then
        uv venv venv
        source venv/bin/activate
        uv pip install -r requirements.txt
    else
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
else
    # Activate existing environment
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Check for root privileges warning
if [ "$EUID" -ne 0 ]; then
    echo "Note: Running without root privileges."
    echo "Some USB devices might not be visible."
    echo "For complete results, run: sudo $0"
    echo ""
fi

# Check if we have a display
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    echo "No display detected. GUI requires a graphical environment."
    echo "Use the command-line version instead: ./which-usb"
    exit 1
fi

# Launch the GUI
cd "$SCRIPT_DIR"
python which-usb-gui.py
