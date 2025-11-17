#!/usr/bin/env python2
# Test using the printFile() API method directly

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))
import beedriver.connection as conn

if len(sys.argv) < 2:
    print("Usage: python2 test_print_with_api.py <gcode_file>")
    sys.exit(1)

gcode_file = sys.argv[1]

if not os.path.exists(gcode_file):
    print("ERROR: File not found:", gcode_file)
    sys.exit(1)

# Connect
c = conn.Conn()
printers = c.getPrinterList()
if not printers:
    print("No printer found")
    sys.exit(1)

c.connectToPrinter(printers[0])
time.sleep(1)
cmd = c.getCommandIntf()

print("="*60)
print("Testing printFile() API (with header)")
print("="*60)

# Clear shutdown if needed
status = cmd.getStatus()
if status == 'Shutdown':
    print("Clearing shutdown flag...")
    cmd.clearShutdownFlag()
    time.sleep(2)

# Get target temp from gcode
target_temp = 200
with open(gcode_file, 'r') as f:
    for line in f:
        if line.startswith('M104') or line.startswith('M109'):
            if ' S' in line:
                try:
                    temp_str = line.split(' S')[1].split()[0].split(';')[0]
                    target_temp = int(float(temp_str))
                    break
                except:
                    pass

print("Target temperature:", target_temp)
print("File:", os.path.basename(gcode_file))
print("")

# Use printFile() API - this sends the header!
print("Starting printFile()...")
result = cmd.printFile(
    filePath=gcode_file,
    printTemperature=target_temp,
    sdFileName=os.path.basename(gcode_file)
)

if not result:
    print("ERROR: printFile() returned False")
    c.close()
    sys.exit(1)

print("printFile() started successfully!")
print("")

# Wait for transfer
print("Waiting for transfer...")
while cmd.isTransferring():
    progress = cmd.getTransferCompletionState()
    if progress:
        print("  Transfer: {}%".format(progress))
    time.sleep(2)

print("Transfer complete!")
print("")

# Check if heating
if cmd.isHeating():
    print("Printer is heating...")
    while cmd.isHeating():
        temp = cmd.getNozzleTemperature()
        if temp:
            print("  Temp: {:.1f}C".format(temp))
        time.sleep(2)

print("")
print("Checking print status...")
time.sleep(5)

status = cmd.getStatus()
is_printing = cmd.isPrinting()

print("Status:", status)
print("Is Printing:", is_printing)

if is_printing:
    print("\n" + "="*60)
    print("SUCCESS! Print started!")
    print("="*60)
else:
    print("\nWARNING: Not printing!")

c.close()
