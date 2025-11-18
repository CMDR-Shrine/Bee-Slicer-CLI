#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Filament Unloader for BEETHEFIRST
Heats nozzle, retracts filament, then cools down
"""

import sys
import os
import time

# Add beedriver to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))

from beedriver import connection as conn
from beedriver import command as comm

print("="*60)
print("FILAMENT UNLOADER")
print("="*60)
print("")

# Connect to printer
print("[1/4] Connecting to printer...")
try:
    c = conn.Conn()
    c.connectToFirstPrinter()
    cmd = comm.Command(c)
    print("      Connected!")
except Exception as e:
    print("      ERROR: Failed to connect to printer")
    print("      {}".format(e))
    sys.exit(1)

# Check if we need to reconnect after Bootloader -> Firmware switch
time.sleep(2)
if hasattr(c, 'reconnect'):
    print("      Reconnecting after mode switch...")
    time.sleep(5)
    c.reconnect()
    cmd = comm.Command(c)

# Set temperature to 215C
target_temp = 215
print("\n[2/4] Heating nozzle to {}C...".format(target_temp))
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

# Retract 50mm of filament
print("\n[3/4] Retracting filament...")
print("      Press Ctrl+C to stop")
print("")

try:
    retract_amount = 5  # mm per command
    retract_speed = 100  # mm/min

    for i in range(10):  # 10 x 5mm = 50mm total
        print("      Retracting... {}/50mm".format((i+1) * retract_amount))
        cmd.sendCmd('G91\n')  # Relative positioning
        cmd.sendCmd('G1 E-{} F{}\n'.format(retract_amount, retract_speed))
        cmd.sendCmd('G90\n')  # Absolute positioning
        time.sleep(1)

    print("      Retraction complete!")

except KeyboardInterrupt:
    print("\n      Retraction stopped by user")

# Cool down
print("\n[4/4] Cooling down...")
cmd.sendCmd('M104 S0\n')  # Turn off heater
print("      Heater turned off")

print("\n" + "="*60)
print("FILAMENT UNLOAD COMPLETE")
print("="*60)
