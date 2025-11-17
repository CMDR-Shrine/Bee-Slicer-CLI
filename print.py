#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Standalone BEETHEFIRST Printer Script
No Docker required - uses local Python 2.7 environment

This script uses FileTransferThread with transferType='print':
- Generates M31 header with print metadata (time estimate, line count)
- Transfers file to SD card with M31 header
- Background thread automatically heats nozzle
- Background thread sends M33 to start print after heating completes

This puts the printer into SD_Print mode (status S:5) for autonomous printing.

Usage:
    python2 print.py <gcode_file>
"""

import sys
import os
import time
import re

# Add beedriver to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))

try:
    import beedriver.connection as conn
    import beedriver.transferThread as transferThread
    import beedriver.commands as BeeCmd
except ImportError as e:
    print("ERROR: Failed to import beedriver!")
    print("Error: {}".format(e))
    print("\nMake sure you run this via the print.sh wrapper script!")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python2 print.py <gcode_file>")
    sys.exit(1)

gcode_file = sys.argv[1]

if not os.path.exists(gcode_file):
    print("ERROR: File not found: {}".format(gcode_file))
    sys.exit(1)

print("="*60)
print("File: {}".format(os.path.basename(gcode_file)))
print("="*60)

# Step 1: Connect
print("\n[1/7] Connecting to printer...")
c = conn.Conn()
printers = c.getPrinterList()

if not printers:
    print("ERROR: No printer found!")
    print("\nTroubleshooting:")
    print("  1. Is printer powered on and connected via USB?")
    print("  2. Run: lsusb | grep BEEVERYCREATIVE")
    print("  3. Check USB permissions (see main README.md)")
    sys.exit(1)

c.connectToPrinter(printers[0])
time.sleep(1)

if not c.isConnected():
    print("ERROR: Connection failed!")
    print("\nTroubleshooting:")
    print("  1. Make sure no other software is using the printer")
    print("  2. Check: ps aux | grep -i bee")
    sys.exit(1)

cmd = c.getCommandIntf()
print("      Connected to: {}".format(printers[0].get('Product', 'Unknown')))
print("      Serial: {}".format(printers[0].get('Serial Number', 'Unknown')))

# Step 2: Firmware mode
print("\n[2/7] Ensuring firmware mode...")
mode = cmd.getPrinterMode()
if mode != "Firmware":
    print("      Switching to firmware...")
    cmd.goToFirmware()
    time.sleep(2)

# Clear any shutdown flag from previous print
status = cmd.getStatus()
if status == 'Shutdown':
    print("      Printer in Shutdown mode, clearing flag...")
    cmd.clearShutdownFlag()
    time.sleep(2)
    status = cmd.getStatus()
    print("      New status: {}".format(status))

print("      In firmware mode!")

# Step 3: Analyze G-code file
print("\n[3/7] Analyzing G-code file...")
target_temp = 200  # default
gcode_line_count = 0
estimated_time_seconds = 0  # Will be rough estimate

with open(gcode_file, 'r') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith(';'):
            continue  # Skip empty lines and comments

        gcode_line_count += 1

        # Extract temperature from M104/M109 commands
        if line.startswith('M104') or line.startswith('M109'):
            if ' S' in line:
                try:
                    temp_str = line.split(' S')[1].split()[0].split(';')[0]
                    target_temp = int(float(temp_str))
                    print("      Found temperature: {}C".format(target_temp))
                except:
                    pass

print("      G-code lines: {}".format(gcode_line_count))

# Rough time estimate: ~0.1 seconds per line (very approximate)
estimated_time_seconds = int(gcode_line_count * 0.1)
estimated_minutes = estimated_time_seconds / 60
print("      Estimated time: {} minutes (rough)".format(estimated_minutes))

# Sanity check temperature
if target_temp < 150:
    print("      WARNING: No heating commands found in G-code!")
    print("      Using default temperature: 200C")
    target_temp = 200

# Step 4: Transfer file to SD card WITH M31 header
print("\n[4/7] Transferring file to SD card with metadata...")
basename = os.path.basename(gcode_file)
print("      File: {}".format(basename))

# Show what the filename will become after sanitization
sanitized_preview = re.sub('[\W_]+', '', basename)
if len(sanitized_preview) > 8:
    sanitized_preview = sanitized_preview[:7]
if sanitized_preview and sanitized_preview[0].isdigit():
    sanitized_preview = 'a' + sanitized_preview[1:7]
print("      Expected SD name: {} (uppercase)".format(sanitized_preview.upper()))

# Generate M31 header with print metadata (like printFile API does)
print("      Generating M31 metadata header...")
m31_header = BeeCmd.BeeCmd.generatePrintInfoHeader(
    gcode_file,
    estimated_time_seconds,
    gcode_line_count
)
if m31_header:
    print("      Header: {}".format(m31_header.strip().replace('\n', ' | ')))

# Create FileTransferThread directly with M31 header and 'print' type
# transferType='print' makes it call waitForHeatingAndPrint() which sends M33!
cmd._transfThread = transferThread.FileTransferThread(
    cmd._beeCon,
    gcode_file,
    'print',  # CRITICAL: 'print' not 'gcode' - this triggers M33 after transfer!
    basename,
    target_temp,  # Pass temperature so it waits for heating then sends M33
    m31_header  # M31 header for print metadata
)
cmd._transfThread.start()
print("      Transfer thread started - will auto-heat and start print!")

# Step 5: Monitor transfer progress
print("\n[5/7] Monitoring transfer...")

last_transfer_progress = -1

while cmd.isTransferring():
    time.sleep(2)
    progress = cmd.getTransferCompletionState()
    if progress is not None and progress != last_transfer_progress:
        print("      Transfer: {}%".format(progress))
        last_transfer_progress = progress

print("      Transfer complete!")
# Wait a moment for SD card to finish writing and closing
time.sleep(2)

# Check what files are on SD card
print("      Checking SD card files...")
file_list = cmd.getFileList()
if file_list and 'FileNames' in file_list:
    print("      Files on SD card: {}".format(file_list['FileNames']))
    print("      Total files: {}".format(len(file_list['FileNames'])))
else:
    print("      Could not read SD card file list")

# Step 6 & 7: Transfer thread will auto-heat and start print
print("\n[6/7] Transfer thread is now heating and starting print...")
print("      The thread will:")
print("      1. Heat to {}C".format(target_temp))
print("      2. Wait for target temperature")
print("      3. Send M33 command to start print")

# Wait for heating and print to start - check status over time
print("\n[7/7] Waiting for heating and print to start...")
print("      (This may take several minutes to heat up)")
is_printing = False
status = "Unknown"
last_temp = 0

# Check every 10 seconds for up to 5 minutes
for i in range(30):  # 30 checks * 10 seconds = 5 minutes max
    time.sleep(10)

    # Get current status
    is_printing = cmd.isPrinting()
    status = cmd.getStatus()
    current_temp = cmd.getNozzleTemperature()

    if current_temp is not None and current_temp != last_temp:
        print("      Check {}/30: Temp={:.1f}C, Status={}, Printing={}".format(
            i+1, current_temp, status, is_printing))
        last_temp = current_temp
    else:
        print("      Check {}/30: Status={}, Printing={}".format(i+1, status, is_printing))

    if is_printing:
        print("      Print started successfully!")
        break

if not is_printing:
    print("      WARNING: Printer status shows not printing after 5 minutes!")
    print("      Final status: {}".format(status))
    if status == 'Shutdown':
        print("      Printer in Shutdown mode - this is unexpected!")
    print("      Check printer display for error messages")

print("\n" + "="*60)
print("PRINT STARTED!" if is_printing else "WAITING FOR PRINT...")
print("="*60)
print("")
print("Monitoring status (Ctrl+C to exit)...")
print("="*60 + "\n")

# Simple monitoring loop
try:
    while True:
        time.sleep(5)
        try:
            temps = cmd.getTemperatures()
            nozzle = temps.get('Nozzle', 'N/A')
            status = cmd.getStatus()
            is_printing = cmd.isPrinting()

            print("[{}] Temp: {}C | Status: {} | Printing: {}".format(
                time.strftime("%H:%M:%S"), nozzle, status, is_printing))

            # Exit if print finished and cooled down
            if not is_printing and isinstance(nozzle, float) and nozzle < 50:
                print("\nPrint finished!")
                break

        except Exception as e:
            print("Error: {}".format(e))

except KeyboardInterrupt:
    print("\n\nExiting... (print continues on printer)")

# Cleanup
c.close()
print("Disconnected")
