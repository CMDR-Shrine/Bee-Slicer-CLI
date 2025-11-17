#!/usr/bin/env python2
# Test version: Try M23 + M24 instead of M33

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'beedriver'))
import beedriver.connection as conn
import time

if len(sys.argv) < 2:
    print("Usage: python2 print_test_m23m24.py <SD_FILENAME>")
    print("Example: python2 print_test_m23m24.py FINAGC")
    sys.exit(1)

sd_filename = sys.argv[1].upper()

c = conn.Conn()
printers = c.getPrinterList()
if not printers:
    print("No printer found")
    sys.exit(1)

c.connectToPrinter(printers[0])
time.sleep(1)
cmd = c.getCommandIntf()

print("="*60)
print("Testing M23 + M24 method (Standard Marlin)")
print("="*60)
print("")

# Make sure we're ready
print("Current status:", cmd.getStatus())
print("Files on SD:", cmd.getFileList())
print("")

# Method 1: Try M33 first (baseline)
print("[Test 1] Sending M33 {}...".format(sd_filename))
resp = cmd.sendCmd('M33 {}\n'.format(sd_filename))
print("  Response:", repr(resp))
time.sleep(3)
status = cmd.getStatus()
print("  Status after 3s:", status)
print("  Is Printing:", cmd.isPrinting())
print("")

if not cmd.isPrinting():
    print("[Test 2] M33 didn't work. Trying M23 + M24...")
    
    # Open file with M23
    print("  Sending M23 {}...".format(sd_filename))
    resp = cmd.sendCmd('M23 {}\n'.format(sd_filename))
    print("  Response:", repr(resp))
    time.sleep(1)
    
    # Start print with M24
    print("  Sending M24...")
    resp = cmd.sendCmd('M24\n')
    print("  Response:", repr(resp))
    time.sleep(3)
    
    status = cmd.getStatus()
    print("  Status after 3s:", status)
    print("  Is Printing:", cmd.isPrinting())
    print("")

if not cmd.isPrinting():
    print("[Test 3] M23+M24 didn't work either. Trying initSD + M33...")
    cmd.initSD()
    time.sleep(1)
    resp = cmd.sendCmd('M33 {}\n'.format(sd_filename))
    print("  Response:", repr(resp))
    time.sleep(3)
    status = cmd.getStatus()
    print("  Status:", status)
    print("  Is Printing:", cmd.isPrinting())

c.close()
