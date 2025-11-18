# BEETHEFIRST Standalone Printer CLI

Standalone CLI tool to print G-code files and manage filament on BEETHEFIRST/BEETHEFIRST+ printers.

**No Docker required** - uses Python 2.7 (Miniconda on x86_64, virtualenv on ARM64/Raspberry Pi).

## Quick Start

**Interactive Menu:**
```bash
./print.sh
```

**Direct Print:**
```bash
./print.sh /path/to/your/print.gcode
```

## Features

1. **Print from G-code file** - Transfer and print directly to SD card
2. **Load filament** - Heat nozzle to 215°C and extrude 50mm
3. **Unload filament** - Heat nozzle to 215°C and retract 50mm

The first run will automatically:
1. Set up Python 2.7 environment with required dependencies
2. Connect to your printer
3. Run the selected operation

Subsequent runs are instant!

## Requirements

- BEETHEFIRST or BEETHEFIRST+ printer connected via USB
- Linux (tested on Arch Linux)
- USB permissions configured (see below)
- Internet connection (first run only, to download Miniconda)

## USB Permissions Setup

Your user must be in the `uucp` group (Arch) or `dialout` group (Ubuntu/Debian):

```bash
# Arch Linux
sudo usermod -a -G uucp $USER

# Ubuntu/Debian
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
```

Install udev rules:

```bash
sudo cp config/99-beeverycreative.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Verify printer is detected:

```bash
lsusb | grep BEEVERYCREATIVE
```

## Project Structure

```
Bee-Slicer-CLI/
├── print.sh              # Main CLI wrapper (run this!)
├── config/               # Configuration files
│   └── 99-beeverycreative.rules  # udev rules for USB permissions
├── src/                  # Python source code
│   ├── print.py          # Print G-code files
│   ├── load.py           # Load filament utility
│   ├── unload.py         # Unload filament utility
│   └── beedriver/        # USB printer driver library
├── API.md                # beedriver API documentation
└── README.md             # This file
```

## How It Works

**Print workflow:**
1. Connects to BEETHEFIRST printer via USB
2. Reads target temperature from G-code (M104/M109 commands)
3. Transfers file to SD card as "ABCDE" (prevents file accumulation)
4. Heats nozzle to target temperature
5. Starts print using M23 + M33 commands (BEETHEFIRST-specific)
6. Monitors print status with M32 command

**Note:** Uses fixed filename "ABCDE" (like official BeeSlicer) to prevent SD card file accumulation.

## Usage Examples

```bash
# Basic usage
./print.sh my_print.gcode

# With full path
./print.sh ~/Documents/3D_Prints/benchy.gcode

# From PrusaSlicer export location
./print.sh ~/Downloads/calibration_cube.gcode
```

## Technical Details

### Platform Support

- **x86_64**: Uses Miniconda Python 2.7
- **ARM64/aarch64 (Raspberry Pi)**: Uses system Python 2.7 + virtualenv

### Dependencies

Automatically installed by `print.sh`:
- Python 2.7
- pyusb==1.0.2
- pyserial==2.7

### Print Process

```
1. Connect to printer via USB
2. Switch to firmware mode (if needed)
3. Analyze G-code file (read temperature, count lines)
4. Transfer file to SD card as "ABCDE"
5. Heat nozzle (M104 command)
6. Initialize SD card (M21)
7. Select file with M23 abcde (lowercase!)
8. Start print with M33 (BEETHEFIRST custom command)
9. Monitor print status with M32
```

### BEETHEFIRST-Specific Commands

**M33 vs M24:** BEETHEFIRST firmware does NOT implement M24 (standard Marlin). Instead it uses:

- **M21** - Initialize SD card
- **M23 <filename>** - Select SD file (must be lowercase!)
- **M33** - Start SD print (BEETHEFIRST custom - replaces M24)
- **M32** - Query print session variables (progress monitoring)

Example workflow:
```gcode
M21           ; Initialize SD
M23 abcde     ; Select file (lowercase!)
M33           ; Start print (BEETHEFIRST custom command)
```

**Important:** In standard Marlin, M33 means "Get Long Filename", but BEETHEFIRST repurposed it to start SD prints.

## Troubleshooting

### "No printer found"

1. Check USB connection: `lsusb | grep BEEVERYCREATIVE`
2. Check USB permissions: `ls -l /dev/bus/usb/001/*`
3. Make sure you're in the `uucp` or `dialout` group
4. Try unplugging and replugging the USB cable

### "Resource busy"

Another program is using the printer:

```bash
# Check what's using the printer
sudo lsof /dev/bus/usb/001/* 2>/dev/null

# Stop BEEweb if running
docker stop beeweb-server
```

### Print doesn't start

1. Make sure your G-code has M104/M109 heating commands
2. Check that the file transferred successfully (100% in output)
3. Wait for the heating phase to complete
4. Verify M23 returned "File opened: ABCDE" message
5. Check M33 response - should return "ok" without errors
6. Monitor M32 output - should show print session variables (A, B, C, D values)

### "Command not found: conda"

The script will automatically install Miniconda2 on first run. If you see this error, delete `~/miniconda2` and try again.

## Comparison with Docker Version

| Feature | Docker | Standalone |
|---------|--------|-----------|
| Setup complexity | High | Low (automatic) |
| First run time | 5-10 min (build) | 2-3 min (download) |
| Subsequent runs | Instant | Instant |
| Disk space | ~500MB | ~300MB |
| Dependencies | Docker | wget |
| Updates | Rebuild image | Update scripts |

## Future Plans

This standalone version will eventually replace the Docker setup entirely, making this repo Docker-free and much simpler to use!

## Credits

Based on the BEEweb project and beedriver library from Beeverycreative.

## License

See main repository LICENSE file.
