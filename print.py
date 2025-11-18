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
        # Only accept temps > 150C (ignore M104 S0 which turns off heater)
        if line.startswith('M104') or line.startswith('M109'):
            if ' S' in line:
                try:
                    temp_str = line.split(' S')[1].split()[0].split(';')[0]
                    temp = int(float(temp_str))
                    if temp > 150:  # Ignore heater-off commands
                        target_temp = temp
                        print("      Found temperature: {}C".format(target_temp))
                except:
                    pass

print("      G-code lines: {}".format(gcode_line_count))
print("      Target temperature: {}C".format(target_temp))

# Step 4: Transfer file to SD card
print("\n[4/7] Transferring file to SD card...")
basename = os.path.basename(gcode_file)
print("      File: {}".format(basename))

# Always use "ABCDE" as the SD filename (matches official BeeSlicer)
# This prevents file accumulation - each print overwrites the previous one
print("      SD filename: ABCDE (fixed, prevents file accumulation)")

cmd.transferSDFile(fileName=gcode_file, sdFileName="ABCDE")

# Step 5: Monitor transfer progress
print("\n[5/7] Monitoring transfer...")
last_progress = -1
while cmd.isTransferring():
    progress = cmd.getTransferCompletionState()
    if progress is not None and progress != last_progress:
        # Convert to float if it's a string
        try:
            progress_num = float(progress)
            print("      Transfer: {:.2f}%".format(progress_num))
            last_progress = progress
        except (ValueError, TypeError):
            pass
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

# Use "abcde" as the SD filename (lowercase for M23 command)
# This matches what we transferred as "ABCDE" (firmware converts to lowercase)
sd_filename_lower = "abcde"
print("      SD filename: {}".format(sd_filename_lower))

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
    print("      ERROR: M23 failed to select file!")
    sys.exit(1)

# Start autonomous SD printing with M33 (BEETHEFIRST custom command)
# Based on official BeeSlicer software - just "M33" alone, no filename!
# NOTE: Official software does NOT send G28 before print - printer homes from G-code
time.sleep(1)
print("      Sending M33 (Start autonomous SD print)...")
response = cmd.sendCmd('M33\n')
print("      M33: {}".format(response.strip() if response else 'No response'))

# Wait for print to initialize and check status using M32 (official method)
print("      Waiting 5 seconds for print to initialize...")
time.sleep(5)

print("      Checking print status with M32 (print session variables)...")
print("      M32 returns: A<estimated> B<elapsed> C<totalLines> D<currentLine>")
print("")

is_printing = False
for i in range(6):  # Check 6 times over 30 seconds
    # M32 returns print session variables - official BeeSlicer method
    response = cmd.sendCmd('M32\n')
    response_str = response.strip() if response else 'No response'
    print("      M32: {}".format(response_str))

    # Check if we're getting print progress data (indicates printing)
    if response and ('A' in response or 'B' in response or 'D' in response):
        is_printing = True
        print("      ✓ Print session active!")
        break

    # Also check M625 status
    status_response = cmd.sendCmd('M625\n')
    print("      M625: {}".format(status_response.strip() if status_response else 'No response'))

    # s:5 means printing state
    if status_response and 's:5' in status_response:
        is_printing = True
        print("      ✓ Printer status: s:5 (Printing)")
        break

    if i < 5:  # Don't sleep on last iteration
        print("      Waiting... ({}/{})".format(i+1, 6))
        time.sleep(5)

if not is_printing:
    print("\n      ⚠ WARNING: Print status unclear after 30 seconds")
    print("      The print may still start successfully.")
    print("      Check the printer display to verify.")

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
