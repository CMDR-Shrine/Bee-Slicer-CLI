#!/bin/bash
# Test different methods to start printing

echo "Testing different print start methods..."
echo ""
echo "Make sure you have a file on the SD card first!"
echo "Run ./print.sh your-file.gcode and let it complete transfer and heating"
echo ""
echo "Then we'll test different M-codes to start the print:"
echo ""
echo "Method 1: M33 FILENAME (BEETHEFIRST custom)"
echo "Method 2: M23 FILENAME + M24 (Standard Marlin)"
echo "Method 3: Use startSDPrint() API"
echo "Method 4: M33 without homing first"
echo ""
echo "Press Enter to continue..."
read

# You'll need to manually test these after your file is transferred and heated
