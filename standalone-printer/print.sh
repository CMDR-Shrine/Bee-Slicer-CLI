#!/bin/bash
#
# BEETHEFIRST Standalone Printer Script
# No Docker required - uses Miniconda Python 2.7 environment
#
# Usage: ./print.sh <gcode_file>
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="beethefirst"
MINICONDA_DIR="$HOME/.config/miniconda3"

# Check if gcode file provided
if [ -z "$1" ]; then
    echo "Usage: $0 <gcode_file>"
    echo ""
    echo "Example:"
    echo "  $0 /path/to/your/print.gcode"
    exit 1
fi

GCODE_FILE="$1"

if [ ! -f "$GCODE_FILE" ]; then
    echo "ERROR: File not found: $GCODE_FILE"
    exit 1
fi

echo "============================================================"
echo "BEETHEFIRST STANDALONE PRINTER"
echo "============================================================"
echo "G-code file: $(basename "$GCODE_FILE")"
echo "============================================================"
echo ""

# Check for processes using the printer
echo "[0/2] Checking for conflicting processes..."
CONFLICTING_PROCS=$(ps aux | grep -E "(beeweb|beesoft|simple_print|gcode_sender)" | grep -v grep | grep -v "$$" || true)

if [ -n "$CONFLICTING_PROCS" ]; then
    echo ""
    echo "WARNING: Found processes that may be using the printer:"
    echo "$CONFLICTING_PROCS" | awk '{printf "  [PID %s] %s\n", $2, $11}'
    echo ""

    # Check if Docker container is running
    DOCKER_RUNNING=$(docker ps --filter "name=beeweb-server" --format "{{.Names}}" 2>/dev/null || true)
    if [ -n "$DOCKER_RUNNING" ]; then
        echo "  Docker container 'beeweb-server' is running"
    fi

    echo ""
    read -p "Kill these processes and continue? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping conflicting processes..."

        # Stop Docker container if running
        if [ -n "$DOCKER_RUNNING" ]; then
            echo "  Stopping beeweb-server container..."
            docker stop beeweb-server >/dev/null 2>&1 || true
        fi

        # Kill other processes
        echo "$CONFLICTING_PROCS" | awk '{print $2}' | while read pid; do
            if [ -n "$pid" ]; then
                echo "  Killing PID $pid..."
                kill "$pid" 2>/dev/null || true
            fi
        done

        # Wait a moment for processes to die
        sleep 2

        # Check if anything is still using the USB device
        USB_USERS=$(sudo lsof /dev/bus/usb/001/* 2>/dev/null | grep -v "^COMMAND" || true)
        if [ -n "$USB_USERS" ]; then
            echo ""
            echo "WARNING: USB device still in use:"
            echo "$USB_USERS"
            echo ""
            read -p "Force kill remaining processes? [y/N] " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                sudo lsof /dev/bus/usb/001/* 2>/dev/null | grep -v "^COMMAND" | awk '{print $2}' | while read pid; do
                    if [ -n "$pid" ]; then
                        echo "  Force killing PID $pid..."
                        sudo kill -9 "$pid" 2>/dev/null || true
                    fi
                done
                sleep 1
            else
                echo "Aborted. Please manually stop processes using the printer."
                exit 1
            fi
        fi

        echo "Processes stopped. Continuing..."
        echo ""
    else
        echo "Aborted. Please manually stop processes using the printer."
        exit 1
    fi
else
    echo "      No conflicting processes found."
fi

# Check if miniconda is installed
if [ ! -d "$MINICONDA_DIR" ]; then
    echo "ERROR: Miniconda not found at $MINICONDA_DIR"
    echo "Please install Miniconda first or update MINICONDA_DIR in this script"
    exit 1
fi

# Initialize conda
source "$MINICONDA_DIR/etc/profile.d/conda.sh"

# Check if environment exists
if ! conda env list | grep -q "^$ENV_NAME "; then
    echo "[SETUP] Creating Python 2.7 environment '$ENV_NAME'..."
    conda create -y -n "$ENV_NAME" python=2.7

    echo "[SETUP] Installing dependencies..."
    conda activate "$ENV_NAME"
    pip install pyusb==1.0.2 pyserial==2.7
    conda deactivate

    echo "[SETUP] Environment created successfully!"
fi

# Activate environment
echo "[1/3] Activating Python 2.7 environment..."
conda activate "$ENV_NAME"

# Check Python version
PYTHON_VERSION=$(python --version 2>&1)
echo "      Python: $PYTHON_VERSION"

# Install missing dependencies if needed
if ! python -c "import serial" 2>/dev/null; then
    echo "      Installing pyserial..."
    pip install -q pyserial==2.7
fi

# Run the print script
echo "[2/3] Connecting to printer..."
echo ""

python "$SCRIPT_DIR/print.py" "$GCODE_FILE"

# Deactivate environment
conda deactivate

echo ""
echo "Done!"
