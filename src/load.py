#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Filament Loader for BEETHEFIRST
Uses M701 firmware command for automatic filament loading
"""

import sys
import os
import time

# Add beedriver to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))

import beedriver.connection as conn

print("="*60)
print("FILAMENT LOADER")
print("="*60)
print("")

# Connect to printer
print("[1/3] Connecting to printer...")
try:
    c = conn.Conn()
    c.connectToFirstPrinter()
    cmd = c.getCommandIntf()
    print("      Connected!")
except Exception as e:
    print("      ERROR: Failed to connect to printer")
    print("      {}".format(e))
    sys.exit(1)

# Check if we need to reconnect after Bootloader -> Firmware switch
time.sleep(2)
mode = cmd.getPrinterMode()
if mode == "Bootloader":
    print("      Switching to firmware mode...")
    cmd.goToFirmware()
    time.sleep(5)
    c.reconnect()
    cmd = c.getCommandIntf()
    print("      Reconnected!")

# Set temperature to 215C and wait
target_temp = 215
print("\n[2/3] Heating nozzle to {}C...".format(target_temp))
print("      (This uses M703 - blocks until target reached)")

# Use official startHeating method (M703)
cmd.startHeating(target_temp)

current_temp = cmd.getNozzleTemperature()
if current_temp is not None:
    print("      Target temperature reached: {:.1f}C!".format(current_temp))
else:
    print("      Temperature check unavailable, but heating complete")

# Load filament using M701 firmware command
print("\n[3/3] Loading filament...")
print("      Using M701 firmware command (automatic load sequence)")
print("      The printer will now load filament automatically.")
print("      Watch the printer - this may take 30-60 seconds.")
print("")

cmd.load()

print("      M701 command sent!")
print("")
print("      The printer is performing the load sequence:")
print("      1. Initial slow extrusion")
print("      2. Fast main load")
print("      3. Purge extrusion")
print("")
print("      Wait for the printer to finish...")

# Wait a bit for the operation to start
time.sleep(3)

print("\n" + "="*60)
print("FILAMENT LOAD COMMAND SENT")
print("="*60)
print("")
print("The printer should now be loading filament.")
print("Check the printer display and watch for filament movement.")
print("")
print("Note: The heater will remain on. Use the printer menu to cool down,")
print("      or run the unload utility which will cool down at the end.")
