#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Direct USB Line-by-Line Printer Script
Sends G-code directly over USB without using SD card

WARNING: This is slower and requires keeping the connection open!
But if SD card printing doesn't work, this is the fallback.

Usage:
    python2 print_direct.py <gcode_file>
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
    print("Usage: python2 print_direct.py <gcode_file>")
    sys.exit(1)

gcode_file = sys.argv[1]
if not os.path.exists(gcode_file):
    print("ERROR: File not found: {}".format(gcode_file))
    sys.exit(1)

print("="*60)
print("DIRECT USB PRINTING (Line-by-Line)")
print("="*60)
print("File: {}".format(gcode_file))
print("")

# Step 1: Connect to printer
print("[1/6] Connecting to printer...")
c = conn.getBeeConnection()
if not c.connect():
    print("ERROR: Failed to connect to printer!")
    sys.exit(1)

cmd = c.getCommandIntf()
print("      Connected!")

# Step 2: Check firmware mode
print("\n[2/6] Checking printer mode...")
mode = cmd.getPrinterMode()
print("      Mode: {}".format(mode))

if mode != 'Firmware':
    print("      Going to firmware mode...")
    cmd.goToFirmware()
    time.sleep(2)

status = cmd.getStatus()
print("      Status: {}".format(status))

# Step 3: Analyze G-code file
print("\n[3/6] Analyzing G-code file...")
target_temp = 200  # default
gcode_lines = []
total_lines = 0

with open(gcode_file, 'r') as f:
    for line in f:
        line = line.strip()
        total_lines += 1

        # Skip empty lines and comments
        if not line or line.startswith(';'):
            continue

        # Remove inline comments
        if ';' in line:
            line = line.split(';')[0].strip()

        if not line:
            continue

        gcode_lines.append(line)

        # Extract temperature from M104/M109 commands
        if line.startswith('M104') or line.startswith('M109'):
            if ' S' in line:
                try:
                    temp_str = line.split(' S')[1].split()[0]
                    temp = int(float(temp_str))
                    if temp > 150:  # Ignore M104 S0 (turn off)
                        target_temp = temp
                        print("      Found temperature: {}C".format(target_temp))
                except:
                    pass

print("      Total lines in file: {}".format(total_lines))
print("      G-code commands to send: {}".format(len(gcode_lines)))
print("      Target temperature: {}C".format(target_temp))

# Step 4: Home printer
print("\n[4/6] Homing printer...")
cmd.home()
print("      Homing complete!")

# Step 5: Heat nozzle
print("\n[5/6] Heating nozzle to {}C...".format(target_temp))
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

# Step 6: Send G-code line by line
print("\n[6/6] Sending G-code commands...")
print("      This will take a while - sending {} commands".format(len(gcode_lines)))
print("")

sent_count = 0
error_count = 0
start_time = time.time()

try:
    for i, line in enumerate(gcode_lines):
        # Add newline if not present
        if not line.endswith('\n'):
            line = line + '\n'

        # Send command and wait for response
        try:
            response = cmd.sendCmd(line)
            sent_count += 1

            # Check for errors in response
            if response and ('error' in response.lower() or 'bad' in response.lower()):
                error_count += 1
                print("      ERROR on line {}: {}".format(i+1, response.strip()))

            # Show progress every 100 lines
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                lines_per_sec = sent_count / elapsed if elapsed > 0 else 0
                remaining = (len(gcode_lines) - sent_count) / lines_per_sec if lines_per_sec > 0 else 0
                print("      Progress: {}/{} ({:.1f}%) - {:.1f} lines/sec - ETA: {:.0f}s".format(
                    sent_count, len(gcode_lines),
                    100.0 * sent_count / len(gcode_lines),
                    lines_per_sec,
                    remaining
                ))

            # Small delay to avoid overwhelming the printer
            # time.sleep(0.01)  # 10ms delay - commented out to go faster

        except KeyboardInterrupt:
            print("\n\n      INTERRUPTED BY USER!")
            raise
        except Exception as e:
            error_count += 1
            print("      Exception on line {}: {}".format(i+1, str(e)))

except KeyboardInterrupt:
    print("\n")
    print("="*60)
    print("PRINT INTERRUPTED!")
    print("="*60)
    print("Sent {}/{} commands ({:.1f}%)".format(
        sent_count, len(gcode_lines),
        100.0 * sent_count / len(gcode_lines)
    ))
    print("Errors: {}".format(error_count))

    # Try to stop any movement
    print("\nStopping printer...")
    try:
        cmd.sendCmd('M108\n')  # Break and continue
        cmd.sendCmd('M112\n')  # Emergency stop
    except:
        pass

    c.close()
    sys.exit(1)

elapsed = time.time() - start_time

print("")
print("="*60)
print("PRINT COMPLETE!")
print("="*60)
print("Commands sent: {}/{}".format(sent_count, len(gcode_lines)))
print("Errors: {}".format(error_count))
print("Time elapsed: {:.1f} seconds ({:.1f} minutes)".format(elapsed, elapsed/60))
print("Average speed: {:.1f} commands/second".format(sent_count / elapsed if elapsed > 0 else 0))
print("")

# Cool down
print("Cooling down...")
cmd.sendCmd('M104 S0\n')  # Turn off heater

print("Closing connection...")
c.close()

print("\nDone!")
