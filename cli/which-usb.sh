#!/bin/bash

# Which USB? - Shell Wrapper
# Simple wrapper script to run the which-usb Python tool

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/which-usb"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found in PATH"
    echo "Please install Python 3 to use this tool"
    exit 1
fi

# Check if lsusb is available
if ! command -v lsusb &> /dev/null; then
    echo "Error: lsusb command is required but not found"
    echo "Please install usbutils package (e.g., 'sudo apt install usbutils')"
    exit 1
fi

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: which-usb Python script not found at $PYTHON_SCRIPT"
    exit 1
fi

# Make sure the Python script is executable
if [ ! -x "$PYTHON_SCRIPT" ]; then
    chmod +x "$PYTHON_SCRIPT"
fi

# Run the Python script with all passed arguments
exec python3 "$PYTHON_SCRIPT" "$@"
