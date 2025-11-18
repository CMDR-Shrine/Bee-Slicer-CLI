# BEETHEFIRST Standalone Printer

Standalone Python script to print G-code files on BEETHEFIRST/BEETHEFIRST+ printers directly from PrusaSlicer.

**No Docker required** - uses Miniconda Python 2.7 environment.

## Quick Start

```bash
./print.sh /path/to/your/print.gcode
```

The first run will automatically:
1. Download and install Miniconda2 (if not already installed)
2. Create a Python 2.7 environment with required dependencies
3. Print your G-code file

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
sudo cp 99-beeverycreative.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Verify printer is detected:

```bash
lsusb | grep BEEVERYCREATIVE
```

## How It Works

1. **Connects** to your BEETHEFIRST printer via USB
2. **Reads** the target temperature from your G-code (M104/M109 commands)
3. **Transfers** the G-code file to printer's internal SD card
4. **Heats** the nozzle to target temperature
5. **Starts** the print using M23/M24 commands (standard Marlin)
6. **Monitors** print progress and temperature

## Features

✅ **No Docker** - runs natively with Miniconda
✅ **Auto-setup** - first run installs everything automatically
✅ **PrusaSlicer compatible** - works with standard G-code output
✅ **M23/M24 print commands** - uses standard Marlin SD card commands
✅ **Smart heating** - extracts temperature from your G-code
✅ **Progress monitoring** - shows real-time temperature and status
✅ **Safe file naming** - automatically creates SD-card compatible names (lowercase!)

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

### What's Included

- `print.sh` - Shell wrapper that manages the Python environment
- `print.py` - Main print script
- `beedriver/` - USB printer communication library (extracted from BEEweb)

### Dependencies

Automatically installed by `print.sh`:
- Python 2.7 (via Miniconda2)
- pyusb==1.0.2
- pyserial==2.7

### Print Process

```
1. Connect to printer
2. Switch to firmware mode (if needed)
3. Analyze G-code file (read temperature, count lines)
4. Transfer file to SD card
5. Heat nozzle (M104 command)
6. Initialize SD card (M21)
7. Select file with M23 <lowercase_filename>
8. Start print with M24
9. Monitor temperature and print status
```

### Critical: Lowercase Filenames

**The BEETHEFIRST firmware converts filenames to lowercase when using M23!**

Files on SD card are stored as **UPPERCASE** (e.g., `MYPRINT`), but you **MUST** send **lowercase** to M23:

```gcode
M23 myprint    # Correct! (lowercase)
M23 MYPRINT    # Wrong! (will get "error opening file")
```

The script handles this automatically.

### M23/M24 Commands

The BEETHEFIRST firmware uses standard Marlin SD card commands:

- **M23 <filename>** - Select SD file (must be lowercase!)
- **M24** - Start/Resume SD print

Example:
```gcode
M23 myprint    ; Select file (lowercase!)
M24            ; Start printing
```

**Note:** M33 is NOT a print command! M33 is "Get Long Filename" and only retrieves filename information.

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
4. Verify M23 command was sent with lowercase filename (shown in output)
5. Check for "error opening file" - this means filename case mismatch
6. Ensure M24 command was sent after M23 succeeds

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
