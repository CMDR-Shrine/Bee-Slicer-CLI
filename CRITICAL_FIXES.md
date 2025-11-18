# CRITICAL DISCOVERIES & FIXES

## 🎯 THE KEY BREAKTHROUGH: M33 vs M24

**BEETHEFIRST DOES NOT IMPLEMENT M24!**

The firmware uses **M33** to start SD prints, NOT M24 (standard Marlin).
- Standard Marlin: M24 = Start SD print
- BEETHEFIRST: M24 doesn't exist, returns "Bad M-code 24"
- BEETHEFIRST: **M33 = Start SD print** (custom command)

Source: beethefirst-firmware repository, `gcode_process.c` lines 1338-1363

## 🔥 CRITICAL PRINT WORKFLOW

```gcode
M21           # Initialize SD card
M23 abcde     # Select file (LOWERCASE!)
M33           # Start print (NO filename parameter!)
```

**IMPORTANT:**
1. NO G28 homing before print! (Official BeeSlicer doesn't send it)
2. Use bare `M33` without filename after M23
3. Monitor with `M32` to check progress

## 💾 SD CARD FILE ACCUMULATION FIX

**Always use "ABCDE" as SD filename** (like official BeeSlicer)
- Each print overwrites the previous one
- No file accumulation on SD card
- Prevents SD card from filling up

Code: `cmd.transferSDFile(fileName=gcode_file, sdFileName="ABCDE")`

## 🔧 FILAMENT LOAD/UNLOAD FIX

**DO NOT use manual G-code!** Use firmware commands:

### Load Filament:
```python
cmd.startHeating(215)  # M703 S215 - blocks until heated
cmd.load()             # M701 - automatic load sequence
```

### Unload Filament:
```python
cmd.startHeating(215)  # M703 S215 - blocks until heated
cmd.unload()           # M702 - automatic unload sequence
cmd.sendCmd('M104 S0\n')  # Turn off heater
```

**Why this works:**
- M701/M702 are firmware macros that handle everything
- Multi-stage extrusion/retraction
- Official BeeSlicer uses these exact commands

Source: `src/beedriver/commands.py` lines 768-798

## 📊 PRINT MONITORING

Use **M32** to query print progress (official method):
```python
response = cmd.sendCmd('M32\n')
# Returns: A<estimated> B<elapsed> C<totalLines> D<currentLine>
# Example: "A123 B456000 C789 D100"
```

Check print status with **M625**:
- `s:5` = Printing
- `s:3` = Ready/Idle

## 🔤 LOWERCASE FILENAME REQUIREMENT

**The firmware converts filenames to lowercase in M23!**
- SD card stores: `ABCDE` (uppercase)
- M23 requires: `abcde` (lowercase)
- Failure to use lowercase: "error opening file"

Code location: `cardreader.cpp` in `openAndPrintFile()`:
```c
for (char *c = &cmd[4]; *c; c++) *c = tolower(*c);
```

## 🏗️ PROJECT STRUCTURE

```
Bee-Slicer-CLI/
├── print.sh              # Main CLI wrapper
├── config/               # Configuration
│   └── 99-beeverycreative.rules
├── src/                  # All Python code
│   ├── print.py         # Print from G-code
│   ├── load.py          # Load filament (M701)
│   ├── unload.py        # Unload filament (M702)
│   ├── monitor.py       # Passive print monitor (NEW!)
│   └── beedriver/       # USB driver library
├── API.md
└── README.md
```

## 🖥️ CLI MENU

```
1) Print from G-code file
2) Load filament (heat + extrude)
3) Unload filament (heat + retract)
4) Monitor print progress (passive)    ← NEW!
5) Exit
```

## 🔍 MONITOR UTILITY FEATURES

**src/monitor.py** - Passive monitoring without interference:
- Polls M32 every 5 seconds for progress
- Shows: Status, Temperature, Progress %, Lines, Elapsed/Remaining time
- No mode changes, no interference with printing
- Press Ctrl+C to exit

Perfect for checking print status remotely!

## 🔑 KEY FIRMWARE COMMANDS

### Print Commands:
- **M21** - Initialize SD card
- **M23 <file>** - Select SD file (lowercase!)
- **M33** - Start SD print (BEETHEFIRST custom)
- **M32** - Query print session variables
- **M625** - Check printer status

### Filament Commands:
- **M703 S<temp>** - Start heating and wait
- **M704** - Cancel heating
- **M701** - Load filament (automatic)
- **M702** - Unload filament (automatic)

### NOT IMPLEMENTED:
- **M24** - Does NOT exist in BEETHEFIRST firmware!

## 🏁 COMPLETE WORKING PRINT SCRIPT

See `src/print.py` for full implementation:

1. Connect to printer
2. Read G-code temperature (M104/M109 lines)
3. Transfer to SD as "ABCDE"
4. Heat nozzle with M703
5. M21 (init SD)
6. M23 abcde (select file - lowercase!)
7. M33 (start print - no params!)
8. M32 (monitor progress)

## 🚀 RASPBERRY PI SUPPORT

Added ARM64/aarch64 support:
- x86_64: Uses Miniconda Python 2.7
- ARM64: Uses system Python 2.7 + virtualenv
- Auto-detects architecture with `uname -m`
- Fixed USB langid errors on Raspberry Pi

## 📝 COMMIT HISTORY

All commits are saved locally in branch `feature/complete-cli-with-monitor`:

1. fcc37b9 - Add passive print monitor utility
2. ad11b4c - Use firmware M701/M702 commands for filament load/unload
3. b50f1b9 - Clean up repository and update documentation
4. 6bd50a6 - Reorganize project structure and fix import errors
5. caf3689 - Add CLI menu and filament load/unload tools
6. e13aa84 - Fix print start sequence based on official BeeSlicer software
7. 13bb1f1 - Add G28 homing command before starting SD print
8. 4e02d8f - Use M33 instead of M24 to start SD prints
9. aef3068 - Fix temperature detection and transfer progress format
10. dbee462 - Fix reconnection after switching from Bootloader to Firmware mode

## 🔧 MANUAL PUSH COMMAND

When git server recovers:
```bash
cd ~/Bee-Slicer-CLI
git push -u origin feature/complete-cli-with-monitor
```

## 🎉 EVERYTHING WORKS NOW!

✅ Printing from G-code files (M33 workflow)
✅ Filament loading (M701)
✅ Filament unloading (M702)
✅ Print monitoring (M32/M625)
✅ No SD card file accumulation (ABCDE)
✅ Raspberry Pi support
✅ Clean CLI interface

---

**Bottom line:** The script is COMPLETE and WORKING. All code is saved locally.
Just push when git recovers!
