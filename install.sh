#!/bin/bash

echo "========================================"
echo "   LoL Voice Controller - Installer"
echo "========================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8+ first"
    exit 1
fi

echo "Starting setup..."
python3 setup.py

if [ $? -ne 0 ]; then
    echo
    echo "Setup failed!"
    exit 1
fi

echo
echo "Installation complete!"
echo "You can now run the application using:"
echo "  - ./launch.sh (default mode)"
echo "  - ./launch_gui.sh (GUI mode)" 
echo "  - ./launch_cli.sh (CLI mode)"
echo