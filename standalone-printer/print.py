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
print("\n[3/9] Connecting to printer...")
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
print("\n[4/9] Ensuring firmware mode...")
mode = cmd.getPrinterMode()
if mode != "Firmware":
    print("      Switching to firmware...")
    cmd.goToFirmware()
    time.sleep(2)
print("      In firmware mode!")

# Step 3: Get target temperature from G-code
print("\n[5/9] Reading G-code for temperature...")
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

# Step 4: Start heating
heat_temp = target_temp + 5  # Heat 5 degrees above target
print("\n[6/9] Starting heating to {}C...".format(heat_temp))
response = cmd.sendCmd("M104 S{}\n".format(heat_temp))
print("      M104 response: {}".format(response.strip()))
print("      Waiting for temperature...")

# Wait for temperature
current_temp = 0
for i in range(300):  # 5 minutes max
    time.sleep(1)
    current_temp = cmd.getNozzleTemperature()
    if i % 5 == 0:  # Print every 5 seconds
        print("      Current: {:.1f}C / Target: {}C".format(current_temp, heat_temp))

    if current_temp >= heat_temp:  # Reached target
        print("      Temperature reached: {:.1f}C!".format(current_temp))
        break

if current_temp < heat_temp:
    print("      WARNING: Only reached {:.1f}C after timeout, continuing anyway...".format(current_temp))

# Step 5: Transfer file
print("\n[7/9] Transferring file...")
basename = os.path.basename(gcode_file)
# Create SD-card safe filename (max 8 chars, no special chars, can't start with digit)
sd_name = basename[:8].replace('.', '').replace(' ', '').replace('-', '').replace('_', '')
if not sd_name:
    sd_name = "PRINT"
elif sd_name[0].isdigit():
    sd_name = 'P' + sd_name[1:8]

print("      SD name: {}".format(sd_name))

cmd.transferSDFile(fileName=gcode_file, sdFileName=sd_name)

# Wait for transfer
print("      Waiting for transfer to complete...")
max_wait = 300
elapsed = 0
while elapsed < max_wait:
    if cmd.isTransferring():
        time.sleep(2)
        elapsed += 2
        if elapsed % 10 == 0:
            print("      Still transferring... ({}s)".format(elapsed))
    else:
        break

if cmd.isTransferring():
    print("      WARNING: Transfer still in progress after timeout!")
else:
    print("      Transfer complete!")

# Extra safety: wait a bit more for SD card to finish writing
print("      Waiting for SD card to be ready...")
time.sleep(3)

# Step 6: Start print with M33 (BEETHEFIRST-specific print command)
print("\n[8/9] Starting print with M33 command...")
print("      SD filename: {}".format(sd_name))
print("      Sending M33 to start print...")
response = cmd.sendCmd("M33 {}\n".format(sd_name))
print("      M33 response: {}".format(response.strip()))

# Give printer time to process M33 command
time.sleep(2)

print("\n" + "="*60)
print("[9/9] PRINT STARTED!")
print("="*60)
print("The G-code file is now executing on the printer.")
print("Your G-code's M104/M109 commands will heat the nozzle.")
print("Watch the printer display!")
print("")
print("Monitoring temperature (Ctrl+C to exit)...")
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
