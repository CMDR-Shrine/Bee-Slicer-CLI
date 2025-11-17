#!/usr/bin/env python2
# Quick debug script to check printer state

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))

import beedriver.connection as conn
import time

c = conn.Conn()
printers = c.getPrinterList()
if not printers:
    print("No printer found")
    sys.exit(1)

c.connectToPrinter(printers[0])
time.sleep(1)
cmd = c.getCommandIntf()

print("="*60)
print("PRINTER DEBUG INFO")
print("="*60)

# Check current state
print("\n1. Printer Mode:", cmd.getPrinterMode())
print("2. Printer Status:", cmd.getStatus())
print("3. Is Printing:", cmd.isPrinting())
print("4. Is Busy:", cmd.isBusy())
print("5. Is Heating:", cmd.isHeating())
print("6. Is Transferring:", cmd.isTransferring())
print("7. Is Paused:", cmd.isPaused())
print("8. Is Shutdown:", cmd.isShutdown())

# Check temperatures
temps = cmd.getTemperatures()
print("\n9. Temperatures:", temps)
print("10. Nozzle Temp:", cmd.getNozzleTemperature())
print("11. Target Temp:", cmd.getTargetTemperature())

# Get file list
print("\n12. Files on SD card:")
files = cmd.getFileList()
if files and 'FileNames' in files:
    for f in files['FileNames']:
        print("    -", f)

# Send raw M625 to see status
print("\n13. Raw M625 response:")
resp = cmd.sendCmd("M625\n")
print("   ", repr(resp))

# Try sending M33 to a known file
if files and 'FileNames' in files and len(files['FileNames']) > 0:
    test_file = files['FileNames'][-1]  # Last file
    print("\n14. Testing M33 with file:", test_file)
    resp = cmd.sendCmd('M33 {}\n'.format(test_file))
    print("    Response:", repr(resp))
    time.sleep(2)
    print("    Status after M33:", cmd.getStatus())
    print("    Is Printing:", cmd.isPrinting())

c.close()
