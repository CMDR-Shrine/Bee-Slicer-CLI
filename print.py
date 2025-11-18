#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Standalone BEETHEFIRST Printer Script
No Docker required - uses local Python 2.7 environment

Key discovery: The BEETHEFIRST firmware converts filenames to LOWERCASE
when using M23! So we must send lowercase filenames.

Workflow:
1. Transfer G-code file to SD card
2. Heat nozzle to target temperature
3. Send M23 with LOWERCASE filename to select file
4. Send M24 to start printing

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

# Check args
if len(sys.argv) < 2:
    print("Usage: python2 print.py <gcode_file>")
    sys.exit(1)

gcode_file = sys.argv[1]
if not os.path.exists(gcode_file):
    print("ERROR: File not found: {}".format(gcode_file))
    sys.exit(1)

print("="*60)
print("BEETHEFIRST STANDALONE PRINTER")
print("="*60)
print("File: {}".format(gcode_file))
print("")

# Step 1: Connect to printer
print("[1/7] Connecting to printer...")
c = conn.Conn()
if not c.connectToFirstPrinter():
    print("ERROR: Failed to connect to printer!")
    sys.exit(1)

cmd = c.getCommandIntf()
if cmd is None:
    print("ERROR: Failed to get command interface!")
    print("This usually means USB permission issues.")
    print("")
    print("Fix with:")
    print("  sudo usermod -a -G dialout $USER")
    print("  (then log out and back in)")
    print("")
    print("Or run with sudo:")
    print("  sudo ./print.sh gcode/case.gcode")
    sys.exit(1)

print("      Connected!")

# Step 2: Check firmware mode
print("\n[2/7] Checking printer mode...")
mode = cmd.getPrinterMode()
print("      Mode: {}".format(mode))

if mode != 'Firmware':
    print("      Going to firmware mode...")
    cmd.goToFirmware()

    # Wait for device to reset and re-enumerate
    print("      Waiting for device to reset...")
    time.sleep(5)

    # Reconnect to the printer
    print("      Reconnecting...")
    if not c.reconnect():
        print("ERROR: Failed to reconnect after firmware switch!")
        sys.exit(1)

    # Get new command interface
    cmd = c.getCommandIntf()
    if cmd is None:
        print("ERROR: Failed to get command interface after reconnect!")
        sys.exit(1)

    print("      Reconnected successfully!")
    mode = cmd.getPrinterMode()
    print("      New mode: {}".format(mode))

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

# Sanity check temperature
if target_temp < 150:
    print("      WARNING: No heating commands found in G-code!")
    print("      Using default temperature: 200C")
    target_temp = 200

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
last_progress = -1
while cmd.isTransferring():
    progress = cmd.getTransferCompletionState()
    if progress is not None and progress != last_progress:
        print("      Transfer: {:.2f}%".format(progress))
        last_progress = progress
    time.sleep(1)

print("      Transfer complete!")

# Step 6: Heat nozzle
print("\n[6/7] Heating nozzle to {}C...".format(target_temp))
cmd.sendCmd('M104 S{}\n'.format(target_temp))

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
sd_filename = re.sub('[\W_]+', '', basename)  # Remove special chars
if len(sd_filename) > 8:
    sd_filename = sd_filename[:7]  # Truncate to 7 chars
if sd_filename and sd_filename[0].isdigit():
    sd_filename = 'a' + sd_filename[1:7]

# CRITICAL: Use LOWERCASE for M23 command!
# The BEETHEFIRST firmware converts filenames to lowercase internally
sd_filename_lower = sd_filename.lower()

print("      SD filename (lowercase): {}".format(sd_filename_lower))

# Initialize SD card
print("      Sending M21 (Init SD card)...")
response = cmd.sendCmd('M21\n')
print("      M21: {}".format(response.strip() if response else 'No response'))
time.sleep(1)

# Select file with M23 (LOWERCASE filename!)
print("      Sending M23 {} (Select SD file)...".format(sd_filename_lower))
response = cmd.sendCmd('M23 {}\n'.format(sd_filename_lower))
print("      M23: {}".format(response.strip() if response else 'No response'))

if 'error' in response.lower():
    print("      ERROR: M23 failed! Trying M32 with !filename# syntax...")
    # Try M32 as fallback
    response = cmd.sendCmd('M32 !{}\n'.format(sd_filename_lower))
    print("      M32: {}".format(response.strip() if response else 'No response'))
else:
    # M23 worked, now send M24
    time.sleep(1)
    print("      Sending M24 (Start SD print)...")
    response = cmd.sendCmd('M24\n')
    print("      M24: {}".format(response.strip() if response else 'No response'))

# Wait for print to start
print("      Waiting for print to start (checking for 30 seconds)...")
is_printing = False
status = "Unknown"

for i in range(6):  # Check 6 times over 30 seconds
    time.sleep(5)
    is_printing = cmd.isPrinting()
    status = cmd.getStatus()
    print("      Check {}/6: Status={}, Printing={}".format(i+1, status, is_printing))

    if is_printing:
        print("      Print started successfully!")
        break

if not is_printing:
    print("      WARNING: Printer status shows not printing after 30 seconds!")
    print("      Final status: {}".format(status))
    print("      Check printer display for error messages")

print("\n" + "="*60)
print("PRINT STARTED!" if is_printing else "WAITING FOR PRINT...")
print("="*60)

# Monitor print status
print("\nMonitoring status (Ctrl+C to exit)...")
print("="*60)
print("")

try:
    while True:
        time.sleep(7)

        try:
            temps = cmd.getTemperatures()
            nozzle = temps.get('Nozzle', 'N/A')
            status = cmd.getStatus()
            is_printing = cmd.isPrinting()

            print("[{}] Temp: {}C | Status: {} | Printing: {}".format(
                time.strftime("%H:%M:%S"), nozzle, status, is_printing))

            if status == 'Shutdown' or not is_printing:
                print("\nPrint completed or stopped.")
                break

        except Exception as e:
            print("Error reading status: {}".format(e))
            break

except KeyboardInterrupt:
    print("\n\nMonitoring stopped by user.")

print("\nClosing connection...")
c.close()
print("Done!")
