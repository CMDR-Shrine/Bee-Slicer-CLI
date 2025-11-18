#!/bin/bash
#
# BEETHEFIRST Standalone Printer CLI
# No Docker required - uses Miniconda Python 2.7 environment (x86_64)
# or system Python 2.7 + virtualenv (ARM64/Raspberry Pi)
#
# Usage: ./print.sh [gcode_file]
#        ./print.sh              (shows menu)
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="beethefirst"
MINICONDA_DIR="$HOME/.config/miniconda3"
VENV_DIR="$SCRIPT_DIR/.venv_py27"

# Detect architecture
ARCH=$(uname -m)

# Show menu if no arguments provided
if [ -z "$1" ]; then
    echo "============================================================"
    echo "BEETHEFIRST STANDALONE PRINTER CLI"
    echo "============================================================"
    echo ""
    echo "Select an option:"
    echo "  1) Print from G-code file"
    echo "  2) Load filament (heat + extrude)"
    echo "  3) Unload filament (heat + retract)"
    echo "  4) Exit"
    echo ""
    read -p "Choice [1-4]: " CHOICE
    echo ""

    case $CHOICE in
        1)
            read -p "Enter G-code file path: " GCODE_FILE
            if [ -z "$GCODE_FILE" ]; then
                echo "ERROR: No file specified"
                exit 1
            fi
            if [ ! -f "$GCODE_FILE" ]; then
                echo "ERROR: File not found: $GCODE_FILE"
                exit 1
            fi
            MODE="print"
            ;;
        2)
            MODE="load"
            ;;
        3)
            MODE="unload"
            ;;
        4|q|Q)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid choice"
            exit 1
            ;;
    esac
else
    # Direct usage: ./print.sh <gcode_file>
    GCODE_FILE="$1"
    if [ ! -f "$GCODE_FILE" ]; then
        echo "ERROR: File not found: $GCODE_FILE"
        exit 1
    fi
    MODE="print"
fi

echo "============================================================"
if [ "$MODE" = "print" ]; then
    echo "BEETHEFIRST STANDALONE PRINTER"
    echo "============================================================"
    echo "G-code file: $(basename "$GCODE_FILE")"
elif [ "$MODE" = "load" ]; then
    echo "FILAMENT LOADER"
elif [ "$MODE" = "unload" ]; then
    echo "FILAMENT UNLOADER"
fi
echo "Architecture: $ARCH"
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

        echo "Processes stopped. Continuing..."
        echo ""
    else
        echo "Aborted. Please manually stop processes using the printer."
        exit 1
    fi
else
    echo "      No conflicting processes found."
fi

# ARM64 (Raspberry Pi) - use system Python 2.7 with virtualenv
if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    echo "[1/3] Using system Python 2.7 (ARM64 platform)..."

    # Check if Python 2.7 is installed
    if ! command -v python2.7 &> /dev/null; then
        echo "ERROR: Python 2.7 not found!"
        echo ""
        echo "Install it with:"
        echo "  sudo apt update"
        echo "  sudo apt install -y python2.7 python-pip-whl python-setuptools-whl"
        echo ""
        exit 1
    fi

    # Check if virtualenv is available
    if ! python2.7 -m virtualenv --version &> /dev/null 2>&1; then
        echo "ERROR: virtualenv not found for Python 2.7!"
        echo ""
        echo "Install it with:"
        echo "  sudo apt install -y python-virtualenv"
        echo ""
        echo "Or via pip (if not in a virtualenv):"
        echo "  pip2 install virtualenv"
        echo ""
        exit 1
    fi

    # Create virtualenv if it doesn't exist
    if [ ! -d "$VENV_DIR" ]; then
        echo "[SETUP] Creating Python 2.7 virtualenv..."
        python2.7 -m virtualenv "$VENV_DIR"

        echo "[SETUP] Installing dependencies..."
        source "$VENV_DIR/bin/activate"
        pip install pyusb==1.0.2 pyserial==2.7
        deactivate

        echo "[SETUP] Virtualenv created successfully!"
    fi

    # Activate virtualenv
    source "$VENV_DIR/bin/activate"

    PYTHON_VERSION=$(python --version 2>&1)
    echo "      Python: $PYTHON_VERSION"

    # Install missing dependencies if needed
    if ! python -c "import serial" 2>/dev/null; then
        echo "      Installing pyserial..."
        pip install -q pyserial==2.7
    fi

    if ! python -c "import usb" 2>/dev/null; then
        echo "      Installing pyusb..."
        pip install -q pyusb==1.0.2
    fi

# x86_64 - use Miniconda as before
else
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
fi

# Run the appropriate script based on mode
echo "[2/3] Running $MODE script..."
echo ""

case $MODE in
    print)
        python "$SCRIPT_DIR/print.py" "$GCODE_FILE"
        ;;
    load)
        python "$SCRIPT_DIR/load.py"
        ;;
    unload)
        python "$SCRIPT_DIR/unload.py"
        ;;
esac

# Deactivate environment
if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    deactivate
else
    conda deactivate
fi

echo ""
echo "Done!"
