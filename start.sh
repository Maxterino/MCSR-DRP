#!/bin/bash
echo ""
echo " ============================================"
echo "  MCSR Discord Rich Presence Tracker"
echo " ============================================"
echo ""

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Install it from https://python.org or via your package manager."
    exit 1
fi

# Install dependencies
echo "Checking dependencies..."
pip3 install -q pypresence watchdog requests

echo ""
echo "Starting tracker... (Press Ctrl+C to stop)"
echo ""
python3 main.py "$@"
