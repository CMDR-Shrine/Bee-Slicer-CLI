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
print("\n[1/5] Connecting to printer...")
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
print("\n[2/5] Ensuring firmware mode...")
mode = cmd.getPrinterMode()
if mode != "Firmware":
    print("      Switching to firmware...")
    cmd.goToFirmware()
    time.sleep(2)
print("      In firmware mode!")

# Step 3: Get target temperature from G-code
print("\n[3/5] Reading G-code for temperature...")
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

# Step 4: Start print (handles heating, transfer, and M33 automatically)
print("\n[4/5] Starting print job...")
print("      Target temperature: {}C (+5C for heating)".format(target_temp))
print("      File: {}".format(os.path.basename(gcode_file)))

result = cmd.printFile(
    filePath=gcode_file,
    printTemperature=target_temp,
    sdFileName=os.path.basename(gcode_file)
)

if not result:
    print("ERROR: Failed to start print!")
    c.close()
    sys.exit(1)

print("      Print job started successfully!")

# Step 5: Monitor transfer and heating progress
print("\n[5/5] Monitoring transfer progress...")

last_transfer_progress = -1

while cmd.isTransferring():
    time.sleep(2)
    progress = cmd.getTransferCompletionState()
    if progress != last_transfer_progress:
        print("      Transfer: {}%".format(progress))
        last_transfer_progress = progress

print("      Transfer complete!")
print("      Printer is now heating and will start printing automatically...")
print("")

# Wait a moment for print to actually start
time.sleep(5)

print("\n" + "="*60)
print("PRINT STARTED!")
print("="*60)
print("The printer has received the file and is printing.")
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
