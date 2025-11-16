#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Standalone BEETHEFIRST Printer Script
No Docker required - uses local Python 2.7 environment

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

# Step 3: Get target temperature from G-code
print("\n[3/7] Reading G-code for temperature...")
target_temp = 200  # default
with open(gcode_file, 'r') as f:
    for line in f:
        if line.startswith('M104') or line.startswith('M109'):
            # Extract S parameter
            if ' S' in line:
                try:
                    temp_str = line.split(' S')[1].split()[0].split(';')[0]
                    target_temp = int(float(temp_str))
                    print("      Found temperature: {}C".format(target_temp))
                    break
                except:
                    pass

# Step 4: Transfer file to SD card
print("\n[4/7] Transferring file to SD card...")
basename = os.path.basename(gcode_file)
print("      File: {}".format(basename))

# Show what the filename will become after sanitization
sanitized_preview = re.sub('[\W_]+', '', basename)
if len(sanitized_preview) > 8:
    sanitized_preview = sanitized_preview[:7]
if sanitized_preview and sanitized_preview[0].isdigit():
    sanitized_preview = 'a' + sanitized_preview[1:7]
print("      Expected SD name: {} (uppercase)".format(sanitized_preview.upper()))

cmd.transferSDFile(fileName=gcode_file, sdFileName=basename)

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

# Wait a moment for SD card to finish writing
time.sleep(2)

# Check what files are on SD card
print("      Checking SD card files...")
file_list = cmd.getFileList()
if file_list and 'FileNames' in file_list:
    print("      Files on SD card: {}".format(file_list['FileNames']))
    print("      Total files: {}".format(len(file_list['FileNames'])))
else:
    print("      Could not read SD card file list")

# Step 6: Heat nozzle
print("\n[6/7] Heating nozzle to {}C...".format(target_temp))
cmd.setNozzleTemperature(target_temp)

# Wait for temperature with timeout
max_wait = 300  # 5 minutes
start_time = time.time()
last_reported_temp = -999

while time.time() - start_time < max_wait:
    current_temp = cmd.getNozzleTemperature()

    if current_temp is not None:
        # Report temperature every 5 degrees change
        if abs(current_temp - last_reported_temp) >= 5:
            print("      Current: {:.1f}C / Target: {}C".format(current_temp, target_temp))
            last_reported_temp = current_temp

        # Check if target reached
        if current_temp >= target_temp - 2:  # Within 2 degrees
            print("      Target temperature reached: {:.1f}C!".format(current_temp))
            break

    time.sleep(2)

# Step 7: Start print
print("\n[7/7] Starting print...")

# Calculate expected SD filename (match transferThread.py logic exactly)
sd_filename = re.sub('[\W_]+', '', basename)  # Remove special chars (dots, spaces, etc)
if len(sd_filename) > 8:
    sd_filename = sd_filename[:7]  # Truncate to 7 chars like transferThread does
if sd_filename and sd_filename[0].isdigit():
    sd_filename = 'a' + sd_filename[1:7]

print("      Expected SD filename: {}".format(sd_filename))

# Find matching file on SD card
matched_file = None
if file_list and 'FileNames' in file_list:
    sd_filename_upper = sd_filename.upper()

    # First try exact match
    if sd_filename_upper in file_list['FileNames']:
        matched_file = sd_filename_upper
        print("      Exact match found: {}".format(matched_file))
    else:
        # Try to find a file that starts with our expected name
        # This handles cases where the SD card truncated the filename further
        for f in file_list['FileNames']:
            if f.startswith(sd_filename_upper[:6]):  # Match first 6 chars
                matched_file = f
                print("      Partial match found: {} (expected: {})".format(f, sd_filename_upper))
                break

        if not matched_file:
            print("      WARNING: No matching file found on SD card!")
            print("      Expected: {}".format(sd_filename_upper))
            print("      Available: {}".format(file_list['FileNames']))
            print("      Using expected name anyway...")
            matched_file = sd_filename_upper

if matched_file:
    sd_filename = matched_file
else:
    sd_filename = sd_filename.upper()

print("      Using SD filename: {}".format(sd_filename))

# Start print using M33 command
result = cmd.startSDPrint(sd_filename)

if not result:
    print("      WARNING: M33 command may have failed")

# Give printer a moment to start
print("      Waiting for print to start...")
time.sleep(3)

# Verify print started
is_printing = cmd.isPrinting()
status = cmd.getStatus()
if is_printing:
    print("      Print started successfully!")
else:
    print("      WARNING: Printer status shows not printing!")
    print("      Printer status: {}".format(status))
    if status == 'Shutdown':
        print("      Printer still in Shutdown mode - this is unexpected!")
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
