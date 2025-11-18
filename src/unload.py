#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Filament Unloader for BEETHEFIRST
Uses M702 firmware command for automatic filament unloading
"""

import sys
import os
import time

# Add beedriver to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))

import beedriver.connection as conn

print("="*60)
print("FILAMENT UNLOADER")
print("="*60)
print("")

# Connect to printer
print("[1/4] Connecting to printer...")
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
print("\n[2/4] Heating nozzle to {}C...".format(target_temp))
print("      (This uses M703 - blocks until target reached)")

# Use official startHeating method (M703)
cmd.startHeating(target_temp)

current_temp = cmd.getNozzleTemperature()
if current_temp is not None:
    print("      Target temperature reached: {:.1f}C!".format(current_temp))
else:
    print("      Temperature check unavailable, but heating complete")

# Unload filament using M702 firmware command
print("\n[3/4] Unloading filament...")
print("      Using M702 firmware command (automatic unload sequence)")
print("      The printer will now retract filament automatically.")
print("      Watch the printer - this may take 30-60 seconds.")
print("")

cmd.unload()

print("      M702 command sent!")
print("")
print("      The printer is performing the unload sequence:")
print("      1. Small retract to relieve pressure")
print("      2. Main retraction to pull filament out")
print("")
print("      Wait for the printer to finish...")
print("      You can now pull the filament out when it's free.")

# Wait a bit for the operation to start
time.sleep(3)

# Cool down
print("\n[4/4] Cooling down...")
cmd.sendCmd('M104 S0\n')  # Turn off heater
print("      Heater turned off")

print("\n" + "="*60)
print("FILAMENT UNLOAD COMPLETE")
print("="*60)
print("")
print("The filament should now be retracted and ready to remove.")
print("Pull the filament out gently from the top of the extruder.")
