#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Standalone BEETHEFIRST Calibration Script
Interactively guides the user through the bed leveling process.
"""

import sys
import os
import time

# Python 2/3 compatibility
if sys.version_info[0] >= 3:
    raw_input = input

# Add beedriver to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'beedriver'))

try:
    import beedriver.connection as conn
except ImportError as e:
    print("ERROR: Failed to import beedriver!")
    print("Error: {}".format(e))
    sys.exit(1)

def get_keypress():
    """Waits for a single keypress from the user."""
    try:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
    except ImportError:
        # Windows or non-Unix fallback
        return raw_input()

def main():
    print("="*60)
    print("BEETHEFIRST CALIBRATION WIZARD")
    print("="*60)
    print("")

    # Step 1: Connect to printer
    print("[1/5] Connecting to printer...")
    c = conn.Conn()
    if not c.connectToFirstPrinter():
        print("ERROR: Failed to connect to printer!")
        sys.exit(1)

    cmd = c.getCommandIntf()
    if cmd is None:
        print("ERROR: Failed to get command interface!")
        sys.exit(1)

    print("      Connected!")

    # Step 2: Ensure Firmware Mode
    print("\n[2/5] Checking printer mode...")
    mode = cmd.getPrinterMode()
    if mode != 'Firmware':
        print("      Switching to Firmware mode...")
        cmd.goToFirmware()
        time.sleep(5)
        if not c.reconnect():
            print("ERROR: Failed to reconnect!")
            sys.exit(1)
        cmd = c.getCommandIntf()
        if cmd is None:
            print("ERROR: Lost connection after firmware switch!")
            sys.exit(1)
    
    # Step 3: Start Calibration (Point A)
    print("\n[3/5] Moving to Point A (Z-Offset Adjustment)...")
    print("      Sending G131 S0...")
    cmd.sendCmd("G131 S0\n")
    
    print("\nAdjust the Nozzle Height using the keyboard:")
    print("  'u' : Up 0.05mm")
    print("  'U' : Up 0.5mm")
    print("  'd' : Down 0.05mm")
    print("  'D' : Down 0.5mm")
    print("  'n' : Next Position")
    print("  'q' : Quit")
    
    while True:
        sys.stdout.write("\nCommand [u/U/d/D/n/q]: ")
        sys.stdout.flush()
        key = get_keypress()
        print(key) 
        
        if key == 'u':
            print("Moving Z Up 0.05mm")
            cmd.sendCmd("G0 Z0.05\n")
        elif key == 'U':
            print("Moving Z Up 0.5mm")
            cmd.sendCmd("G0 Z0.5\n")
        elif key == 'd':
            print("Moving Z Down 0.05mm")
            cmd.sendCmd("G0 Z-0.05\n")
        elif key == 'D':
            print("Moving Z Down 0.5mm")
            cmd.sendCmd("G0 Z-0.5\n")
        elif key == 'n':
            break
        elif key == 'q':
            print("Aborting...")
            cmd.sendCmd("G28\n")
            sys.exit(0)
            
    # Step 4: Point B (Screw 1)
    print("\n[4/5] Moving to Point B (Left Screw)...")
    cmd.sendCmd("G132\n")
    print("      Adjust the LEFT screw until the nozzle just touches the bed.")
    print("      (Use a piece of paper as a gauge)")
    raw_input("      Press ENTER when done...")

    # Step 5: Point C (Screw 2)
    print("\n[5/5] Moving to Point C (Right Screw)...")
    cmd.sendCmd("G132\n")
    print("      Adjust the RIGHT screw until the nozzle just touches the bed.")
    raw_input("      Press ENTER when done...")
    
    # Finish Position
    print("\nMoving to Finish Position...")
    cmd.sendCmd("G132\n")
    
    print("\nCalibration Positions Complete!")
    
    # Optional Test Print
    print("\nDo you want to run the Calibration Test Print?")
    print("This will print a test pattern to verify leveling.")
    
    while True:
        choice = raw_input("Run test print? [y/N]: ").lower()
        if choice == 'y':
            run_test_print(cmd)
            break
        elif choice == 'n' or choice == '':
            cmd.sendCmd("G28\n")
            break

    print("\nDone!")

def run_test_print(cmd):
    print("\n=== STARTING TEST PRINT ===")
    
    # Check for calibration.gcode
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming src/calibrate.py, so up one level is root
    root_dir = os.path.dirname(script_dir)
    gcode_file = os.path.join(root_dir, "gcode", "calibration.gcode")
    
    if not os.path.exists(gcode_file):
        print("ERROR: {} not found!".format(gcode_file))
        return

    # Analyze file for temp
    target_temp = 200
    with open(gcode_file, 'r') as f:
        for line in f:
            if 'M104 S' in line or 'M109 S' in line:
                try:
                    t = int(float(line.split('S')[1].split()[0].split(';')[0]))
                    if t > 150: target_temp = t
                except: pass
    
    print("Target Temp: {}C".format(target_temp))
    
    # Transfer
    print("Transferring file...")
    cmd.transferSDFile(fileName=gcode_file, sdFileName="ABCDE")
    
    # Wait for transfer
    while cmd.isTransferring():
        time.sleep(1)
        
    # Heat
    print("Heating nozzle...")
    cmd.sendCmd('M104 S{}\n'.format(target_temp))
    
    last_temp = 0
    while True:
        curr = cmd.getNozzleTemperature()
        if curr is not None:
            if abs(curr - last_temp) >= 5:
                print("Temp: {:.1f}C / {}C".format(curr, target_temp))
                last_temp = curr
            if curr >= target_temp - 2:
                print("Target reached!")
                break
        time.sleep(2)
        
    # Start Print
    print("Starting Print...")
    cmd.sendCmd('M21\n')
    time.sleep(1)
    cmd.sendCmd('M23 abcde\n')
    time.sleep(1)
    cmd.sendCmd('M33\n')
    
    print("Print started! Monitor progress on printer.")

if __name__ == "__main__":
    main()
