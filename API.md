# BEETHEFIRST+ Printer API Reference

Complete API documentation for BEETHEFIRST and BEETHEFIRST+ 3D printers using the beedriver library.

## Table of Contents

- [Connection Management](#connection-management)
- [Printer Control](#printer-control)
- [Temperature Management](#temperature-management)
- [File Transfer & Printing](#file-transfer--printing)
- [Movement & Positioning](#movement--positioning)
- [Calibration](#calibration)
- [Filament Operations](#filament-operations)
- [Status & Monitoring](#status--monitoring)
- [Firmware Management](#firmware-management)
- [Low-Level Commands](#low-level-commands)

---

## Connection Management

### `isConnected()`
Returns the connection state.

**Returns:** `bool` - True if connected, False otherwise

**Example:**
```python
if cmd.isConnected():
    print("Printer is connected")
```

---

## Printer Control

### `goToFirmware()`
Resets printer to firmware mode.

**Returns:** `bool` - True if successful

**Example:**
```python
cmd.goToFirmware()
```

### `goToBootloader()`
Resets printer to bootloader mode (for firmware updates).

**Returns:** `bool` - True if successful

**Example:**
```python
cmd.goToBootloader()
```

### `getPrinterMode()`
Returns current printer mode.

**Returns:** `str` - "Firmware" or "Bootloader"

**Example:**
```python
mode = cmd.getPrinterMode()
print("Printer mode:", mode)
```

### `getStatus()`
Returns current printer status.

**Returns:** `str` - Printer status string

**Example:**
```python
status = cmd.getStatus()
print("Status:", status)
```

### `beep()`
Triggers a 2-second beep on the printer.

**Example:**
```python
cmd.beep()
```

### `cleanBuffer()`
Cleans the communication buffer.

**Example:**
```python
cmd.cleanBuffer()
```

---

## Temperature Management

### `getNozzleTemperature()`
Returns current nozzle temperature.

**Returns:** `float` - Temperature in Celsius

**Example:**
```python
temp = cmd.getNozzleTemperature()
print("Nozzle temp: {:.1f}C".format(temp))
```

### `setNozzleTemperature(temperature)`
Sets nozzle target temperature.

**Parameters:**
- `temperature` (int/float): Target temperature in Celsius

**Example:**
```python
cmd.setNozzleTemperature(200)
```

### `getTargetTemperature()`
Returns the target nozzle temperature.

**Returns:** `float` - Target temperature in Celsius

**Example:**
```python
target = cmd.getTargetTemperature()
```

### `getTemperatures()`
Returns all printer temperatures as a dictionary.

**Returns:** `dict` - Dictionary with temperature values
- `'Nozzle'`: Nozzle temperature (float)
- `'Bed'`: Bed temperature (float, if available)
- `'Electronics'`: Electronics temperature (float)

**Example:**
```python
temps = cmd.getTemperatures()
print("Nozzle: {}C".format(temps['Nozzle']))
print("Electronics: {}C".format(temps.get('Electronics', 'N/A')))
```

### `getElectronicsTemperature()`
Returns printer electronics temperature.

**Returns:** `float` - Temperature in Celsius

### `getExtruderBlockTemperature()`
Returns extruder block temperature.

**Returns:** `float` - Temperature in Celsius

### `startHeating(temperature, extruder=0)`
Starts heating procedure to specified temperature.

**Parameters:**
- `temperature` (int/float): Target temperature in Celsius
- `extruder` (int, optional): Extruder number (default: 0)

**Example:**
```python
cmd.startHeating(200)
```

### `getHeatingProgress()`
Returns the current heating state progress.

**Returns:** `float` - Progress percentage (0-100)

### `cancelHeating()`
Cancels ongoing heating operation.

**Example:**
```python
cmd.cancelHeating()
```

---

## File Transfer & Printing

### `printFile(filePath, printTemperature=200, estimatedPrintTime=None, gcodeLines=None, sdFileName=None)`
Transfers a file to the printer and starts printing (all-in-one method).

**Parameters:**
- `filePath` (str): Complete path to the gcode file
- `printTemperature` (int, optional): Target temperature for the filament (default: 200)
- `estimatedPrintTime` (int, optional): Estimated print time in seconds
- `gcodeLines` (int, optional): Number of gcode lines
- `sdFileName` (str, optional): Name for the file on SD card (max 8 chars)

**Returns:** `bool` - True if print starts successfully

**Example:**
```python
result = cmd.printFile(
    filePath="/path/to/print.gcode",
    printTemperature=205,
    sdFileName="MYPRINT"
)
```

### `transferSDFile(fileName, sdFileName=None)`
Transfers a G-code file to printer's internal SD card memory.

**Parameters:**
- `fileName` (str): Complete path to the gcode file
- `sdFileName` (str, optional): Name for the file on SD card (max 8 chars, no special chars)

**Example:**
```python
cmd.transferSDFile(
    fileName="/path/to/print.gcode",
    sdFileName="PRINT001"
)
```

### `startSDPrint(sdFileName)`
Starts printing a file already on the SD card.

**Parameters:**
- `sdFileName` (str): Name of the file on SD card

**Example:**
```python
cmd.startSDPrint("PRINT001")
```

### `repeatLastPrint(printTemperature=200)`
Repeats the last printed file.

**Parameters:**
- `printTemperature` (int, optional): Target temperature (default: 200)

**Returns:** `bool` - True if print starts successfully

**Example:**
```python
cmd.repeatLastPrint(printTemperature=205)
```

### `cancelPrint()`
Cancels current print and homes the printer axes.

**Example:**
```python
cmd.cancelPrint()
```

### `pausePrint()`
Initiates pause process for current print.

**Example:**
```python
cmd.pausePrint()
```

### `resumePrint()`
Resumes print from pause or shutdown.

**Example:**
```python
cmd.resumePrint()
```

---

## Movement & Positioning

### `home()`
Homes all axes (X, Y, Z).

**Example:**
```python
cmd.home()
```

### `homeXY()`
Homes X and Y axes only.

**Example:**
```python
cmd.homeXY()
```

### `homeZ()`
Homes Z axis only.

**Example:**
```python
cmd.homeZ()
```

### `move(x=None, y=None, z=None, e=None, f=None, wait=True)`
Performs relative movement.

**Parameters:**
- `x` (float, optional): X-axis movement in mm
- `y` (float, optional): Y-axis movement in mm
- `z` (float, optional): Z-axis movement in mm
- `e` (float, optional): Extruder movement in mm
- `f` (float, optional): Feed rate in mm/min
- `wait` (bool, optional): Wait for movement to complete (default: True)

**Example:**
```python
# Move 10mm on X, 20mm on Y
cmd.move(x=10, y=20, f=3000)

# Extrude 5mm of filament
cmd.move(e=5, f=100)
```

### `goToHeatPos()`
Moves the printer to the heating position coordinates.

**Example:**
```python
cmd.goToHeatPos()
```

### `goToRestPos()`
Moves the printer to the rest position.

**Example:**
```python
cmd.goToRestPos()
```

---

## Calibration

### `startCalibration()`
Starts the bed leveling calibration procedure.

**Example:**
```python
cmd.startCalibration()
```

### `cancelCalibration()`
Cancels the ongoing calibration procedure.

**Example:**
```python
cmd.cancelCalibration()
```

### `goToNextCalibrationPoint()`
Moves to the next calibration point during calibration.

**Example:**
```python
cmd.goToNextCalibrationPoint()
```

---

## Filament Operations

### `load()`
Performs load filament operation.

**Example:**
```python
cmd.load()
```

### `unload()`
Performs unload filament operation.

**Example:**
```python
cmd.unload()
```

### `setFilamentString(filamentString)`
Sets the filament identification string.

**Parameters:**
- `filamentString` (str): Filament identifier

**Example:**
```python
cmd.setFilamentString("PLA-RED-1.75")
```

### `getFilamentString()`
Returns the current filament string.

**Returns:** `str` - Filament identifier

**Example:**
```python
filament = cmd.getFilamentString()
print("Current filament:", filament)
```

---

## Status & Monitoring

### `isPrinting()`
Returns True if printer is currently printing.

**Returns:** `bool`

**Example:**
```python
if cmd.isPrinting():
    print("Print in progress")
```

### `isHeating()`
Returns True if heating is in progress.

**Returns:** `bool`

**Example:**
```python
if cmd.isHeating():
    print("Heating...")
```

### `isTransferring()`
Returns True if a file transfer is in progress.

**Returns:** `bool`

**Example:**
```python
while cmd.isTransferring():
    print("Transferring...")
    time.sleep(2)
```

### `isPaused()`
Returns True if the printer is in pause state.

**Returns:** `bool`

### `isResuming()`
Returns True if the printer is resuming from pause.

**Returns:** `bool`

### `isPreparingOrPrinting()`
Returns True if printer is heating/transferring (preparing) or printing.

**Returns:** `bool`

### `isBusy()`
Returns True if printer is heating/transferring/printing or moving.

**Returns:** `bool`

**Example:**
```python
if not cmd.isBusy():
    print("Printer is idle")
```

### `getPrintVariables()`
Returns list with print variables (progress, time remaining, etc.).

**Returns:** `list` - Print status variables

### `getCurrentPrintFilename()`
Returns the name of the file currently being printed.

**Returns:** `str` - Filename

**Example:**
```python
filename = cmd.getCurrentPrintFilename()
print("Printing:", filename)
```

### `getTransferState()`
Returns the transfer progress if any transfer is running.

**Returns:** Transfer state information

### `getTransferCompletionState()`
Returns current transfer completion percentage.

**Returns:** `float` - Percentage (0-100)

**Example:**
```python
progress = cmd.getTransferCompletionState()
print("Transfer: {}%".format(progress))
```

### `startPrintStatusMonitor()`
Starts the print status monitor thread for continuous status updates.

**Example:**
```python
cmd.startPrintStatusMonitor()
```

---

## SD Card Management

### `initSD()`
Initializes the SD card.

**Example:**
```python
cmd.initSD()
```

### `getFileList()`
Returns list of G-code files stored in printer's memory.

**Returns:** `list` - List of filenames

**Example:**
```python
files = cmd.getFileList()
for f in files:
    print("File:", f)
```

### `createFile(fileName)`
Creates a file in the SD card root directory.

**Parameters:**
- `fileName` (str): Name of file to create

### `openFile(fileName)`
Opens a file in the SD card root directory.

**Parameters:**
- `fileName` (str): Name of file to open

### `cancelTransfer()`
Cancels current file transfer.

**Example:**
```python
cmd.cancelTransfer()
```

---

## Firmware Management

### `getFirmwareVersion()`
Returns firmware version string.

**Returns:** `str` - Firmware version

**Example:**
```python
version = cmd.getFirmwareVersion()
print("Firmware:", version)
```

### `setFirmwareString(firmwareString)`
Sets new bootloader firmware string.

**Parameters:**
- `firmwareString` (str): Firmware identifier

### `flashFirmware(fileName, firmwareString)`
Flashes new firmware to the printer.

**Parameters:**
- `fileName` (str): Path to firmware file
- `firmwareString` (str): Firmware identifier

**Warning:** Use with caution! Can brick your printer if done incorrectly.

---

## Printer Configuration

### `setBlowerSpeed(speed)`
Sets cooling fan/blower speed.

**Parameters:**
- `speed` (int): Speed value (0-255)

**Example:**
```python
cmd.setBlowerSpeed(128)  # 50% speed
```

### `setSerialNumber(serialNumber)`
Defines printer serial number.

**Parameters:**
- `serialNumber` (str): Serial number string

### `getExtruderStepsMM()`
Returns extruder steps per mm calibration value.

**Returns:** `float` - Steps per mm

### `setExtruderStepsMM(steps)`
Defines extruder steps per mm calibration value.

**Parameters:**
- `steps` (float): Steps per mm

**Example:**
```python
cmd.setExtruderStepsMM(95.5)
```

### `resetPrinterConfig()`
Resets printer configuration to factory settings.

**Warning:** This will erase all calibration data!

**Example:**
```python
cmd.resetPrinterConfig()
```

---

## Shutdown Management

### `enterShutdown()`
Pauses print and sets printer in shutdown mode (for power loss recovery).

**Example:**
```python
cmd.enterShutdown()
```

### `clearShutdownFlag()`
Clears shutdown flag after recovery.

**Example:**
```python
cmd.clearShutdownFlag()
```

---

## Low-Level Commands

### `sendCmd(command, wait=True, timeout=10)`
Sends a raw G-code command to the printer.

**Parameters:**
- `command` (str): G-code command to send (should end with `\n`)
- `wait` (bool, optional): Wait for response (default: True)
- `timeout` (int, optional): Timeout in seconds (default: 10)

**Returns:** `str` - Printer response

**Example:**
```python
# Send M105 (get temperature)
response = cmd.sendCmd("M105\n")
print(response)

# Send M33 (start SD print)
response = cmd.sendCmd("M33 MYPRINT\n")
```

---

## BEETHEFIRST-Specific G-code Commands

The BEETHEFIRST firmware is based on Marlin 1.1.x and supports standard Marlin commands.

### M23 / M24 - SD Card Printing

**CRITICAL:** The BEETHEFIRST firmware converts filenames to **lowercase** when using M23!

**M23 - Select SD File:**
```gcode
M23 myprint    # Use lowercase filename!
```

**M24 - Start/Resume SD Print:**
```gcode
M24
```

**Example workflow:**
```python
# Files on SD card are stored as UPPERCASE (e.g., "MYPRINT")
# But you MUST send lowercase to M23!
cmd.sendCmd('M23 myprint\n')  # lowercase!
cmd.sendCmd('M24\n')
```

### M33 - Get Long Filename
**Note:** M33 is NOT a print command! It retrieves the long filename for a given path.

**Format:** `M33 <filename>`

**Example:**
```gcode
M33 PRINT~1
```

This returns the full filename if the filesystem uses 8.3 naming.

---

## Common Usage Patterns

### Basic Print Workflow

```python
import beedriver.connection as conn
import time

# Connect
c = conn.Conn()
printers = c.getPrinterList()
c.connectToPrinter(printers[0])
cmd = c.getCommandIntf()

# Ensure firmware mode
if cmd.getPrinterMode() != "Firmware":
    cmd.goToFirmware()
    time.sleep(2)

# Method 1: All-in-one (recommended)
cmd.printFile(
    filePath="/path/to/print.gcode",
    printTemperature=200,
    sdFileName="MYPRINT"
)

# Method 2: Manual control
# Transfer file
cmd.transferSDFile("/path/to/print.gcode", "MYPRINT")
while cmd.isTransferring():
    time.sleep(2)

# Start heating
cmd.startHeating(200)
while cmd.isHeating():
    time.sleep(1)

# Start print
cmd.sendCmd("M33 MYPRINT\n")

# Monitor
while cmd.isPrinting():
    temps = cmd.getTemperatures()
    print("Nozzle: {}C".format(temps['Nozzle']))
    time.sleep(10)

# Cleanup
c.close()
```

### Temperature Monitoring

```python
while True:
    temps = cmd.getTemperatures()
    target = cmd.getTargetTemperature()

    print("Nozzle: {:.1f}C / Target: {:.1f}C".format(
        temps['Nozzle'], target
    ))

    if cmd.isPrinting():
        filename = cmd.getCurrentPrintFilename()
        print("Printing:", filename)

    time.sleep(5)
```

### Safe File Transfer with Progress

```python
cmd.transferSDFile("/path/to/large_file.gcode", "BIGPRINT")

while cmd.isTransferring():
    progress = cmd.getTransferCompletionState()
    print("Transfer: {}%".format(progress))
    time.sleep(2)

print("Transfer complete!")
```

---

## Notes

- **Filename limitations:** SD card filenames must be max 8 characters, no special characters, and cannot start with a digit.
- **Thread safety:** The beedriver library uses threading internally. File transfers and heating operations run in background threads.
- **Connection persistence:** Keep the connection object alive during prints! Closing the connection will stop background operations.
- **M33 vs M23/M24:** BEETHEFIRST firmware uses `M33 <filename>` instead of the standard Marlin `M23` (select file) + `M24` (start print) commands.

---

## Source Files

All API documentation is extracted from:
- `beedriver/commands.py` - Main command interface
- `beedriver/connection.py` - Connection management
- `beedriver/transferThread.py` - File transfer operations

---

*Last updated: 2025-11-15*
