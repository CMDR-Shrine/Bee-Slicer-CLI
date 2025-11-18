#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Passive Print Monitor for BEETHEFIRST
Displays print progress without interfering with the printer
"""

import sys
import os
import time
import re

# Add beedriver to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))

import beedriver.connection as conn

print("="*60)
print("BEETHEFIRST PRINT MONITOR")
print("="*60)
print("")
print("This is a passive monitor - it won't interfere with printing.")
print("Press Ctrl+C to exit.")
print("")

# Connect to printer
print("Connecting to printer...")
try:
    c = conn.Conn()
    c.connectToFirstPrinter()
    cmd = c.getCommandIntf()
    print("Connected!")
except Exception as e:
    print("ERROR: Failed to connect to printer")
    print("{}".format(e))
    sys.exit(1)

print("")
print("="*60)
print("")

def format_time(seconds):
    """Format seconds into human-readable time"""
    if seconds < 0:
        return "Unknown"
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    secs = int(seconds % 60)

    if hours > 0:
        return "{}h {}m {}s".format(hours, minutes, secs)
    elif minutes > 0:
        return "{}m {}s".format(minutes, secs)
    else:
        return "{}s".format(secs)

try:
    last_status = None

    while True:
        # Query print session variables with M32
        # Returns: A<estimated> B<elapsed> C<totalLines> D<currentLine>
        response = cmd.sendCmd('M32\n')

        # Query printer status with M625
        status_response = cmd.sendCmd('M625\n')

        # Get temperature
        temp = cmd.getNozzleTemperature()

        # Parse M32 response
        estimated_time = None
        elapsed_time = None
        total_lines = None
        current_line = None

        if response and response.strip():
            # Parse response like "A123 B456 C789 D100"
            match_a = re.search(r'A(\d+)', response)
            match_b = re.search(r'B(\d+)', response)
            match_c = re.search(r'C(\d+)', response)
            match_d = re.search(r'D(\d+)', response)

            if match_a:
                estimated_time = int(match_a.group(1))
            if match_b:
                elapsed_time = int(match_b.group(1)) / 1000.0  # Convert ms to seconds
            if match_c:
                total_lines = int(match_c.group(1))
            if match_d:
                current_line = int(match_d.group(1))

        # Check if printer is in printing state (s:5)
        is_printing = status_response and 's:5' in status_response

        # Calculate progress percentage
        progress = 0.0
        if total_lines and current_line and total_lines > 0:
            progress = (float(current_line) / float(total_lines)) * 100.0

        # Build status string
        status_parts = []

        if is_printing:
            status_parts.append("PRINTING")
        else:
            status_parts.append("IDLE/READY")

        if temp is not None:
            status_parts.append("Temp: {:.1f}C".format(temp))

        if total_lines and current_line:
            status_parts.append("Progress: {:.1f}%".format(progress))
            status_parts.append("Lines: {}/{}".format(current_line, total_lines))

        if elapsed_time is not None:
            status_parts.append("Elapsed: {}".format(format_time(elapsed_time)))

        if estimated_time is not None and is_printing:
            time_remaining = estimated_time * 60 - elapsed_time  # estimated in minutes
            if time_remaining > 0:
                status_parts.append("Remaining: ~{}".format(format_time(time_remaining)))

        current_status = " | ".join(status_parts)

        # Only print if status changed
        if current_status != last_status:
            print(current_status)
            last_status = current_status

        # Wait 5 seconds before next poll
        time.sleep(5)

except KeyboardInterrupt:
    print("")
    print("")
    print("="*60)
    print("Monitor stopped by user")
    print("="*60)
    sys.exit(0)
except Exception as e:
    print("")
    print("ERROR: {}".format(e))
    sys.exit(1)
