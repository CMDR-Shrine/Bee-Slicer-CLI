#!/usr/bin/env python

import os
import threading
import time
from beedriver import logger, printStatusThread
from beedriver import transferThread
import platform
import re

# Copyright (c) 2015 BEEVC - Electronic Systems This file is part of BEESOFT
# software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version. BEESOFT is
# distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details. You
# should have received a copy of the GNU General Public License along with
# BEESOFT. If not, see <http://www.gnu.org/licenses/>.

__author__ = "BVC Electronic Systems"
__license__ = ""


class BeeCmd:
    r"""
    BeeCmd Class

    This class exports some methods with predefined commands to control
    BEEVERYCREATIVE 3D printers

    __init__(conn)                                            Inits current class
    goToFirmware()                                            Resets Printer in firmware mode
    goToBootloader()                                          Resets Printer in bootloader mode
    getPrinterMode()                                          Return printer mode
    cleanBuffer()                                             Cleans communication buffer
    isConnected()                                             Returns the connection state
    getStatus()                                               Return printer status
    beep()                                                    2s Beep
    home()                                                    Home all axis
    homeXY()                                                  Home X and Y axis
    homeZ()                                                   Home Z axis
    move(x, y, z, e, f, wait)                                 Relative move
    startCalibration()                                        Starts the calibration procedure
    cancelCalibration()                                       Cancels the calibration procedure.
    goToNextCalibrationPoint()                                Moves to next calibration point.
    getNozzleTemperature()                                    Returns current nozzle temperature
    setNozzleTemperature(t)                                   Sets nozzle target temperature
    getTargetTemperature()                                    Return the target temperature                                        
    load()                                                    Performs load filament operation
    unload()                                                  Performs unload operation
    startHeating(t,extruder)                                  Starts Heating procedure
    getHeatingProgress()                                         Returns the current heating state progress
    getTransferState()                                        Returns the transfer progress, if any is running
    cancelHeating()                                           Cancels Heating
    goToHeatPos()                                             Moves the printer to the heating coordinates
    goToRestPos()                                             Moves the printer to the rest position
    setFilamentString(filStr)                                 Sets filament string
    getFilamentString()                                       Returns filament string
    printFile(filePath, printTemperature, sdFileName)         Transfers a file to the printer and starts printing
    repeatLastPrint(printTemperature)                         Repeats last printed file
    initSD()                                                  Inits SD card
    getFileList()                                             Returns list with GCode files stored in the printers memory
    createFile(fileName)                                      Creates a file in the SD card root directory
    openFile(fileName)                                        Opens file in the sd card root dir
    startSDPrint(sdFileName)                                  Starts printing selected file
    cancelPrint()                                             Cancels current print and home the printer axis
    getPrintVariables()                                       Returns List with Print Variables:
    setBlowerSpeed(speed)                                     Sets Blower Speed
    setFirmwareString(fwStr)                                  Sets new bootloader firmware String
    flashFirmware(fileName, firmwareString)                   Flash New Firmware
    transferSDFile(fileName, sdFileName)                      Transfers GCode file to printer internal memory
    getTransferCompletionState()                              Returns current transfer completion percentage 
    cancelTransfer()                                          Cancels Current Transfer 
    getFirmwareVersion()                                      Returns Firmware Version String
    pausePrint()                                              Initiates pause process
    resumePrint()                                             Resume print from pause/shutdown
    enterShutdown()                                           Pauses print and sets printer in shutdown
    clearShutdownFlag()                                       Clears shutdown Flag
    sendCmd(cmd, wait, timeout)                               Sends command to printer
    startPrintStatusMonitor()                                 Starts the print status monitor thread
    isHeating()                                               Returns True if heating is still in progress
    isTransferring()                                          Returns True if a file is being transfer
    isPaused()                                                Returns True if the printer is in Pause state
    isResuming()                                              Returns True if the printer is in Resuming state
    isPreparingOrPrinting()                                   Returns True if the printer is either heating/transferring (preparing to print) or printing
    isBusy()                                                  Returns True if the printer is either heating/transferring/printing or moving
    setSerialNumber()                                         Defines printer serial number
    getTemperatures()                                         Returns printer temperatures dict
    getElectronicsTemperature()                               Returns printer electronics temperature
    getExtruderBlockTemperature()                             Returns extruder block temperature
    getCurrentPrintFilename()                                 Returns the name of the file currently being printed
    getExtruderStepsMM()                                      Returns Extruder steps per mm
    setExtruderStepsMM()                                      Defines Extruder Steps per mm
    resetPrinterConfig()                                      Restes printer config to factory settings
    """

    MESSAGE_SIZE = 512
    BLOCK_SIZE = 64

    # *************************************************************************
    #                            __init__ Method
    # *************************************************************************
    def __init__(self, conn):
        r"""
        __init__ Method

        arguments:
            conn - Connection object

        Initializes this class

        """

        self._beeCon = conn
        self._connected = self._beeCon.isConnected()
        self._transfThread = None
        self._printStatusThread = None

        self._calibrationState = 0
        self._setPointTemperature = 0

        self._pausing = False
        self._paused = False
        self._shutdown = False
        self._resuming = False

        self._inBootloader = False
        self._inFirmware = False

        self._commandLock = threading.Lock()

        self._printStatus = {}
        self._currentNozzleTemperature = 0

        return
    
    # *************************************************************************
    #                            goToFirmware Method
    # *************************************************************************
    def goToFirmware(self):
        r"""
        goToFirmware method

        Resets the printer to firmware
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        if self._beeCon.transferring:
            logger.info('File transfer in progress... Can not change to Firmware\n')
            return None

        logger.info('Changing to Firmware...\n')

        mode = self.getPrinterMode()

        if mode == 'Firmware':
            logger.info('Printer Already in Firmware\n')
            return False

        with self._commandLock:
            self._beeCon.sendCmd('M630\n')
            self._beeCon.reconnect()

        mode = self.getPrinterMode()

        return mode

    # *************************************************************************
    #                            goToBootloader Method
    # *************************************************************************
    def goToBootloader(self):
        r"""
        goToBootloader method

        Resets the printer to Bootloader
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        if self._beeCon.transferring:
            logger.info('File transfer in progress... Can not change to Bootloader\n')
            return None

        logger.info('Changing to Bootloader...\n')

        mode = self.getPrinterMode()

        if mode == 'Bootloader':
            logger.info('Printer Already in Bootloader\n')
            return False

        with self._commandLock:
            self._beeCon.sendCmd('M609\n')
            self._beeCon.reconnect()

        mode = self.getPrinterMode()

        return mode
    
    # *************************************************************************
    #                            getPrinterMode Method
    # *************************************************************************
    def getPrinterMode(self):
        r"""
        getPrinterMode method

        Returns a string with the current printer mode (Bootloader/Firmware).
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            resp = self._beeCon.sendCmd("M625\n")

            if 'Bad M-code 625' in resp:   # printer in bootloader mode
                self._inBootloader = True
                self._inFirmware = False
                return "Bootloader"
            elif 'ok Q' in resp:
                self._inBootloader = False
                self._inFirmware = True
                return "Firmware"
            else:
                return None
        
    # *************************************************************************
    #                            cleanBuffer Method
    # *************************************************************************
    def cleanBuffer(self):
        r"""
        cleanBuffer method

        Cleans communication buffer and establishes communications
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            logger.debug("Cleaning")
            cleanStr = 'M625;' + 'a'*(self.MESSAGE_SIZE-6) + '\n'

            self._beeCon.write(cleanStr, 50)

            tries = self.BLOCK_SIZE + 1

            resp = self._beeCon.read()
            acc_resp = ""

            while "ok" not in acc_resp.lower() and tries > 0:
                try:
                    self._beeCon.write(cleanStr)

                    resp = self._beeCon.read()

                    acc_resp += resp
                    #print(resp)
                    tries -= 1
                except Exception as ex:
                    logger.error("Read timeout %s", str(ex))
                    tries = 0

            #print(resp)

            return tries

    # *************************************************************************
    #                            isConnected Method
    # *************************************************************************
    def isConnected(self):
        r"""
        isConnected method

        return the sate of the connection:
            connected = True
            disconnected = False
        """
        return self._connected

    # *************************************************************************
    #                            isPrinting Method
    # *************************************************************************
    def isPrinting(self):
        r"""
        isPrinting method

        return True if the printer is in printing mode or False if not
        """
        if self.isTransferring():
            return False

        status = self.getStatus()
        if status is not None and status == 'SD_Print':
            return True

        return False

    # *************************************************************************
    #                            isBusy Method
    # *************************************************************************
    def isBusy(self):
        r"""
        isBusy method

        return True if the printer is either heating/transferring/printing or moving
        """
        if self.isTransferring() or self.isHeating():
            return True

        status = self.getStatus()
        if status is not None and (status == 'SD_Print' or status == 'Moving'):
            return True

        return False

    # *************************************************************************
    #                            isPreparingOrPrinting Method
    # *************************************************************************
    def isPreparingOrPrinting(self):
        r"""
        isPreparingOrPrinting method

        return True if the printer is either heating/transferring
        (preparing to print) or printing
        """
        if self.isTransferring() or self.isHeating():
            return True

        status = self.getStatus()
        if status is not None and status == 'SD_Print':
            return True

        return False

    # *************************************************************************
    #                            isReady Method
    # *************************************************************************
    def isReady(self):
        r"""
        isReady method

        return True if the printer is Ready or False if not
        """
        if self.isTransferring():
            return False

        status = self.getStatus()
        if status is not None and status == 'Ready':
            return True

        return False

    # *************************************************************************
    #                            isPaused Method
    # *************************************************************************
    def isPaused(self):
        r"""
        isPaused method

        return True if the printer is in Pause state or False if not
        """
        if self.isTransferring():
            return False

        status = self.getStatus()
        if status is not None and status == 'Pause':
            return True

        return False

    # *************************************************************************
    #                            isResuming Method
    # *************************************************************************
    def isResuming(self):
        r"""
        isResuming method

        return True if the printer is in Resuming state or False if not
        """
        if self._beeCon.dummyPlugConnected():
            time.sleep(3)
            return False

        self.getStatus()  # updates the status
        if self._resuming:
            return True

        return False

    # *************************************************************************
    #                            isShutdown Method
    # *************************************************************************
    def isShutdown(self):
        r"""
        isShutdown method

        return True if the printer is in Shutdown mode or False if not
        """
        if self.isTransferring():
            return False

        status = self.getStatus()
        if status is not None and status == 'Shutdown':
            return True

        return False

    # *************************************************************************
    #                            getStatus Method
    # *************************************************************************
    def getStatus(self):
        r"""
        getStatus method

        returns the current status of the printer
        """
        mode = self.getPrinterMode()

        # In dummy printer mode sets mode to firmware
        if mode is None and self._beeCon.dummyPlugConnected():
            mode = 'Firmware'

        if mode == 'Bootloader':
            logger.info('Printer in Bootloader mode')
            return 'Bootloader'
        if mode is None or (mode != 'Firmware' and mode != 'Bootloader'):
            logger.debug('GetStatus: can only get status in firmware')
            return None

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        resp = ''
        status = ''
        done = False

        with self._commandLock:
            while not done:

                while 's:' not in resp.lower():
                    resp += self._beeCon.sendCmd("M625\n")
                    time.sleep(1)

                if 'pause' in resp.lower():
                    status = 'Pause'
                    self._paused = True
                    done = True
                elif 'shutdown' in resp.lower():
                    status = 'Shutdown'
                    self._shutdown = True
                    done = True

                elif 's:3' in resp.lower():
                    status = 'Ready'
                    done = True
                elif 's:4' in resp.lower():
                    status = 'Moving'
                    done = True
                elif 's:5' in resp.lower():
                    status = 'SD_Print'
                    done = True
                    self._resuming = False
                elif 's:6' in resp.lower():
                    status = 'Transfer'
                    done = True
                elif 's:7' in resp.lower() or 'pause' in resp.lower():
                    status = 'Pause'
                    self._paused = True
                    done = True
                elif 's:9' in resp.lower() or 'shutdown' in resp.lower():
                    status = 'Shutdown'
                    self._shutdown = True
                    done = True

            return status

    # *************************************************************************
    #                            beep Method
    # *************************************************************************
    def beep(self):
        r"""
        beep method

        performs a beep with 2 seconds duration
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd("M300 P2000\n")

            return

    # *************************************************************************
    #                            home Method
    # *************************************************************************
    def home(self):
        r"""
        home method

        homes all axis
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd("G28\n", "3")

            return

    # *************************************************************************
    #                            homeXY Method
    # *************************************************************************
    def homeXY(self):
        r"""
        homeXY method

        home axis X and Y
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd("G28 X0 Y0\n", "3")

            return

    # *************************************************************************
    #                            homeZ Method
    # *************************************************************************
    def homeZ(self):
        r"""
        homeZ method

        homes Z axis
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd("G28 Z0\n", "3")

            return

    # *************************************************************************
    #                            move Method
    # *************************************************************************
    def move(self, x=None, y=None, z=None, e=None, f=None, wait=None):
        r"""
        move method

        performs a relative move at a given feedrate current

        arguments:
        x - X axis displacement
        y - Y axis displacement
        z - Z axis displacement
        e - E extruder displacement

        f - feedrate

        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd("G91\n")

            newX = 0
            newY = 0
            newZ = 0
            newE = 0

            if x is not None:
                newX = newX + x
            if y is not None:
                newY = newY + y
            if z is not None:
                newZ = newZ + z
            if e is not None:
                newE = newE + e

            if f is not None:
                newF = float(f)
                commandStr = "G1 X" + str(newX) + " Y" + str(newY) \
                             + " Z" + str(newZ) + " E" + str(newE) + " F" + str(newF) + "\n"
            else:
                commandStr = "G1 X" + str(newX) + " Y" + str(newY) \
                             + " Z" + str(newZ) + " E" + str(newE) + "\n"

            if wait is not None:
                self._beeCon.sendCmd(commandStr, wait)
            else:
                self._beeCon.sendCmd(commandStr)
                
            self._beeCon.sendCmd("G90\n")

            return
    
    # *************************************************************************
    #                     startCalibration Method
    # *************************************************************************
    def startCalibration(self, startZ=2.0, repeat=False):
        r"""
        startCalibration method

        Starts the calibration procedure. If a calibration repeat is asked the startZ heigh is used.
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._calibrationState = 0

            if repeat:
                cmdStr = 'G131 Z%.2f' % startZ
            else:
                cmdStr = 'G131'

            self._beeCon.sendCmd(cmdStr)

            return True
    
    # *************************************************************************
    #                     cancelCalibration Method
    # *************************************************************************
    def cancelCalibration(self):
        r"""
        cancelCalibration method

        Cancels the calibration procedure.
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        self.home()

        return
    
    # *************************************************************************
    #                     goToNextCalibrationPoint Method
    # *************************************************************************
    def goToNextCalibrationPoint(self):
        r"""
        goToNextCalibrationPoint method

        Moves to next calibration point.
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd('G132\n')

            return
    
    # *************************************************************************
    #                     getNozzleTemperature Method
    # *************************************************************************
    def getNozzleTemperature(self):
        r"""
        getNozzleTemperature method

        reads current nozzle temperature

        returns:
            nozzle temperature
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            # get Temperature
            resp = self._beeCon.sendCmd("M105\n", "ok", 2)
            try:
                splits = resp.split(" ")
                tPos = splits[0].find("T:")
                self._currentNozzleTemperature = float(splits[0][tPos+2:])

            except ValueError as ve:
                # if for some reason the temperature value could not be parsed as float,
                #  returns the previous/current value
                return self._currentNozzleTemperature
            except Exception as ex:
                logger.error("Error getting nozzle temperature: %s", str(ex))

            return self._currentNozzleTemperature

    # *************************************************************************
    #                        setNozzleTemperature Method
    # *************************************************************************
    def setNozzleTemperature(self, t):
        r"""
        setNozzleTemperature method

        Sets nozzle target temperature

        Arguments:
            t - nozzle temperature
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            commandStr = "M104 S" + str(t) + "\n"

            # set Temperature
            self._beeCon.sendCmd(commandStr)

            return

    # *************************************************************************
    #                        getTargetTemperature Method
    # *************************************************************************
    def getTargetTemperature(self):
        r"""
        getTargetTemperature method

        Gets nozzle target temperature

        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        if self._beeCon.dummyPlugConnected():
            return 200.0

        with self._commandLock:
            # get Target Temperature
            resp = self._beeCon.sendCmd("M1029 \n", 'ok', 2)

            try:
                splits = resp.split(" ")
                tStr = splits[0]
                t = float(tStr[tStr.find("/") + 1:tStr.find("(")])
                return t
            except Exception as ex:
                logger.error("Error getting target temperature: %s", str(ex))

            return 0

    # *************************************************************************
    #                            load Method
    # *************************************************************************
    def load(self):
        r"""
        load method

        performs load filament operation
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd("M701\n", "3")
            return

    # *************************************************************************
    #                            unload Method
    # *************************************************************************
    def unload(self):
        r"""
        unload method

        performs unload operation
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd("M702\n", "3")

            return
    
    # *************************************************************************
    #                            startHeating Method
    # *************************************************************************
    def startHeating(self, temperature, extruder=0):
        r"""
        startHeating method

        Starts Heating procedure
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._setPointTemperature = temperature

            return self._beeCon.waitForStatus('M703 S%.2f\n' % temperature, '3')
    
    # *************************************************************************
    #                            getHeatingProgress Method
    # *************************************************************************
    def getHeatingProgress(self):
        r"""
        getHeatingProgress method

        Returns the heating state in decimal percentage (float: 0.00 - 1.00)
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        currentT = self.getNozzleTemperature()

        if self._setPointTemperature > 0:
            temp = currentT / self._setPointTemperature
            if temp > 1:  # protects against cases where the temperature overshoots the target
                return 1.0
            else:
                return temp
        else:
            return 0.0

    # *************************************************************************
    #                            getTransferState Method
    # *************************************************************************
    def getTransferState(self):
        r"""
        getTransferState method

        Returns the transfer file progress in decimal percentage (float: 0.00 - 1.00)
        """
        if self.isTransferring():
            return self._transfThread.getTransferCompletion()

        return 0.0
    
    # *************************************************************************
    #                            cancelHeating Method
    # *************************************************************************
    def cancelHeating(self):
        r"""
        cancelHeating method

        Cancels Heating
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._setPointTemperature = 0

            return self._beeCon.sendCmd("M704\n", "3")
    
    # *************************************************************************
    #                            goToHeatPos Method
    # *************************************************************************
    def goToHeatPos(self):
        r"""
        goToHeatPos method

        moves the printer to the heating coordinates
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            # set feedrate
            self._beeCon.sendCmd("G1 F15000\n")

            # set acceleration
            self._beeCon.sendCmd("M206 X400\n")

            # go to first point
            self._beeCon.sendCmd("G1 X30 Y0 Z10\n")

            # set acceleration
            self._beeCon.sendCmd("M206 X1000\n", "3")

            return

    # *************************************************************************
    #                            goToRestPos Method
    # *************************************************************************
    def goToRestPos(self):
        r"""
        goToRestPos method

        moves the printer to the rest position
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            # set feedrate
            self._beeCon.sendCmd("G1 F15000\n")

            # set acceleration
            self._beeCon.sendCmd("M206 X400\n")

            # go to first point
            self._beeCon.sendCmd("G1 X-50 Y0 Z110\n")

            # set acceleration
            self._beeCon.sendCmd("M206 X1000\n", "3")

            return

    # *************************************************************************
    #                            goToHeatPos Method
    # *************************************************************************
    def goToLoadUnloadPos(self):
        r"""
        goToLoadUnloadPos method

        moves the printer to the load/unload position
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.waitForStatus('M703\n', '3')

        return

    # *************************************************************************
    #                            setFilamentString Method
    # *************************************************************************
    def setFilamentString(self, filStr):
        r"""
        setFilamentString method

        Sets filament string

        arguments:
            filStr - filament string
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            return self._beeCon.sendCmd('M1000 %s' % filStr)
    
    # *************************************************************************
    #                            getFilamentString Method
    # *************************************************************************
    def getFilamentString(self):
        r"""
        getFilamentString method

        Returns filament string
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            replyStr = self._beeCon.sendCmd('M1001')
            splits = replyStr.split("'")

            if len(splits) > 1:
                filStr = splits[1]
            else:
                return 'A023 - Black'

            if '_no_file' in filStr:
                return ''

            return filStr
    
    # *************************************************************************
    #                            printFile Method
    # *************************************************************************
    def printFile(self, filePath, printTemperature=200, estimatedPrintTime=None, gcodeLines=None, sdFileName=None):
        r"""
        Transfers a file to the printer and starts printing

        :param filePath: Complete Path to the gcode file in the filesystem
        :param printTemperature: Target temperature for the selected filament
        :param estimatedPrintTime: Estimated print time in seconds (given by the estimator tool)
        :param gcodeLines: Number of lines of the gcode file to print (given by the estimator tool)
        :param sdFileName: Optional name of the SD file where the gcode will be stored in the printer (limited to 8 characters)
        :return: True if print starts successfully
        """
        if self.isTransferring():
            logger.error('File Transfer Thread active, please wait for transfer thread to end')
            return False

        # check if file exists
        if os.path.isfile(filePath) is False:
            logger.error("transferGCode: File does not exist")
            return False

        try:
            if self.getPrinterMode() == 'Bootloader':
                self.goToFirmware()

            if printTemperature is not None:
                #self.home()
                self.startHeating(printTemperature + 5)

            time.sleep(1)

            with self._commandLock:
                self._beeCon.read()

                self._transfThread = transferThread.FileTransferThread(
                    self._beeCon, filePath, 'print', sdFileName, printTemperature,
                     BeeCmd.generatePrintInfoHeader(filePath, estimatedPrintTime, gcodeLines))
                self._transfThread.start()

        except Exception as ex:
            logger.error("Error starting the print operation: %s", str(ex))
            return False

        return True

    # *************************************************************************
    #                            repeatLastPrint Method
    # *************************************************************************
    def repeatLastPrint(self, printTemperature=200):
        r"""
        repeatLastPrint method

        Starts printing last print

        returns True if print starts successfully

        """

        if self.isTransferring():
            logger.error('File Transfer Thread active, please wait for transfer thread to end')
            return False

        try:
            if self.getPrinterMode() == 'Bootloader':
                self.goToFirmware()

            if printTemperature is not None:
                #self.home()
                self.startHeating(printTemperature+5)

            time.sleep(1)

            with self._commandLock:
                self._beeCon.read()

                self._transfThread = transferThread.FileTransferThread(
                    self._beeCon, None, 'print', None, printTemperature)
                self._transfThread.start()

        except Exception as ex:
            logger.error("Error starting the print operation: %s", str(ex))
            return False

        return True

    # *************************************************************************
    #                            initSD Method
    # *************************************************************************
    def initSD(self):
        r"""
        initSD method

        inits Sd card
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            # Init SD
            self._beeCon.write("M21\n")

            tries = 10
            resp = ""
            while (tries > 0) and ("ok" not in resp.lower()):
                try:
                    resp += self._beeCon.read()
                    tries -= 1
                except Exception as ex:
                    logger.error("Error initializing SD Card: %s", str(ex))

            return tries

    # *************************************************************************
    #                            getFileList Method
    # *************************************************************************
    def getFileList(self):
        r"""
        getFileList method

        Returns list with GCode files strored in the printers memory
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        fList = {'FileNames': [], 'FilePaths': []}

        self.initSD()

        with self._commandLock:
            resp = ""
            self._beeCon.write("M20\n")

            while "end file list" not in resp.lower():
                resp += self._beeCon.read()

            lines = resp.split('\n')

            for l in lines:

                if "/" in l:
                    if "firmware.bck" in l.lower():
                        pass
                    elif "firmware.bin" in l.lower():
                        pass
                    elif "config.txt" in l.lower():
                        pass
                    elif "config.bck" in l.lower():
                        pass
                    elif l == "":
                        pass
                    else:
                        fName = l[1:len(l)-1]
                        fList['FileNames'].append(fName)
                        fList['FilePaths'].append('')

                elif "end file list" in l.lower():
                    return fList

            return fList

    # *************************************************************************
    #                            createFile Method
    # *************************************************************************
    def createFile(self, fileName):
        r"""
        createFile method

        Creates a file in the SD card root directory

        arguments:
            fileName - file name
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        # Init SD
        self.initSD()

        with self._commandLock:
            fn = fileName
            if len(fileName) > 8:
                fn = fileName[:8]

            cmdStr = "M30 " + fn + "\n"

            resp = self._beeCon.sendCmd(cmdStr)

            tries = 10
            while tries > 0:

                if "file created" in resp.lower():
                    logger.info("SD file created")
                    break
                elif "error" in resp.lower():
                    logger.error("Error creating file")
                    return False
                else:
                    resp = self._beeCon.sendCmd("\n")
                    logger.debug("Create file in SD: " + resp)

                tries -= 1
            if tries <= 0:
                return False

            return True

    # *************************************************************************
    #                            openFile Method
    # *************************************************************************
    def openFile(self, fileName):
        r"""
        openFile method

        opens file in the sd card root dir

        arguments:
            fileName - file name
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        # Init SD
        self.initSD()

        cmdStr = "M23 " + fileName + "\n"

        with self._commandLock:
            # Open File
            resp = self._beeCon.sendCmd(cmdStr)

            tries = 10
            while tries > 0:
                if "file opened" in resp.lower():
                    logger.debug("SD file opened")
                    break
                else:
                    resp = self._beeCon.sendCmd("\n")
                tries -= 1

            if tries <= 0:
                return False

            return True

    # *************************************************************************
    #                            startSDPrint Method
    # *************************************************************************
    def startSDPrint(self, sdFileName=''):
        r"""
        startSDPrint method

        starts printing selected file
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd('M33 %s' % sdFileName)

            return True

    # *************************************************************************
    #                            cancelPrint Method
    # *************************************************************************
    def cancelPrint(self):
        r"""
        cancelPrint method

        cancels current print and home the printer axis
        """
        logger.debug('Cancelling print...')

        if (self.isTransferring() or self.isHeating()) is True:
            self.cancelTransfer()
            time.sleep(2)  # Waits for thread to stop transferring
            with self._commandLock:
                self._beeCon.sendCmd("G28\n", "3")
            return True

        # We must make sure the status monitor thread if finished before cancelling the print to avoid
        # status updates even after the print was cancelled
        self.stopPrintStatusMonitor()
        if self._printStatusThread is not None:
            while self._printStatusThread.isRunning():
                time.sleep(0.1)

        with self._commandLock:
            self._beeCon.sendCmd("M112\n", "3")

        return True

    # *************************************************************************
    #                        getPrintVariables Method
    # *************************************************************************
    def getPrintVariables(self):
        r"""
        getPrintVariables method

        Returns dict with Print Variables:
            Estimated Time (seconds)
            Elapsed Time (seconds)
            Number of Lines
            Executed Lines
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            resp = self._beeCon.sendCmd('M32\n')

            if resp[:1] == 'A':
                try:
                    split = resp.split(' ')
                    for s in split:
                        if 'A' in s:
                            self._printStatus['Estimated Time'] = int(s[1:]) * 60
                        elif 'B' in s:
                            self._printStatus['Elapsed Time'] = (int(s[1:])//(60*1000)) * 60
                        elif 'C' in s:
                            self._printStatus['Lines'] = int(s[1:])
                        elif 'D' in s:
                            self._printStatus['Executed Lines'] = int(s[1:])
                            break  # If the D was found there is no need to process the string further
                except Exception as ex:
                    logger.warning('Error parsing print variables response: %s' % str(ex))

            return self._printStatus

    # *************************************************************************
    #                        setBlowerSpeed Method
    # *************************************************************************
    def setBlowerSpeed(self, speed):
        r"""
        setBlowerSpeed method
        
        Sets Blower Speed
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            cmd = 'M106 S' + str(speed) + '\n'
            self._beeCon.sendCmd(cmd)

            return
    
    # *************************************************************************
    #                        setFirmwareString Method
    # *************************************************************************
    def setFirmwareString(self, fwStr):
        r"""
        setFirmwareString method
        
        Sets new bootloader firmware String
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            cmd = 'M114 A' + str(fwStr) + '\n'
            self._beeCon.sendCmd(cmd, 'ok')

            return

    # *************************************************************************
    #                            flashFirmware Method
    # *************************************************************************
    def flashFirmware(self, fileName, firmwareString='BEEVC-BEETHEFIRST-10.0.0.BIN'):
        r"""
        flashFirmware method
        
        Flash new firmware
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        if ('linux' or 'darwin') in platform.system().lower():
            fileName = fileName.translate(None, ''.join("'"))
        elif ('win32' or 'cygwin') in platform.system().lower():
            fileName = fileName.translate(None, ''.join('"'))

        if os.path.isfile(fileName) is False:
            logger.warning("Flash firmware: File does not exist")
            return

        logger.info("Flashing new firmware File: %s", fileName)
        self.setFirmwareString('0.0.0')  # Clear FW Version

        self._transfThread = transferThread.FileTransferThread(self._beeCon, fileName, 'Firmware', firmwareString)
        self._transfThread.start()

        self._transfThread.join()

        if not self._transfThread.isTransferFirmwareSuccessful():
            return False

        # if the firmware file transfer was successful sets the firmware string
        self.setFirmwareString(firmwareString)

        return True
    
    # *************************************************************************
    #                            transferSDFile Method
    # *************************************************************************
    def transferSDFile(self, fileName, sdFileName=None):
        r"""
        transferSDFile method
        
        Transfers GCode file to printer internal memory
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        if os.path.isfile(fileName) is False:
            logger.warning("Gcode Transfer: File does not exist")
            return

        logger.info("Transfer GCode File: %s" % fileName)

        if sdFileName is not None:
            self._transfThread = transferThread.FileTransferThread(self._beeCon, fileName, 'gcode', sdFileName)
        else:
            self._transfThread = transferThread.FileTransferThread(self._beeCon, fileName, 'gcode')
        self._transfThread.start()

        return
    
    # *************************************************************************
    #                        getTransferCompletionState Method
    # *************************************************************************
    def getTransferCompletionState(self):
        r"""
        getTransferCompletionState method
        
        Returns current transfer completion percentage 
        """

        if self._transfThread.isAlive():
            p = self._transfThread.getTransferCompletionState()
            logger.info("Transfer State: %s" % str(p))
            return p

        return None
    
    # *************************************************************************
    #                        cancelTransfer Method
    # *************************************************************************
    def cancelTransfer(self):
        r"""
        cancelTransfer method
        
        Cancels Current Transfer 
        """
        if self._transfThread.isAlive():
            self._transfThread.cancelFileTransfer()
            return True
        
        return False

    # *************************************************************************
    #                            isTransferring Method
    # *************************************************************************
    def isTransferring(self):
        r"""
        isTransferring method
        
        Returns True if a file is being transfer
        """
        if self._transfThread is not None:
            return self._transfThread.isTransferring()
        
        return False

    # *************************************************************************
    #                            isHeating Method
    # *************************************************************************
    def isHeating(self):
        r"""
        isHeating method

        Returns True if heating is still in progress
        """
        if self._transfThread is not None:
            return self._transfThread.isHeating()

        return False
    
    # *************************************************************************
    #                            getFirmwareVersion Method
    # *************************************************************************
    def getFirmwareVersion(self):
        r"""
        getFirmwareVersion method
        
        Returns Firmware Version String
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        fw = 'BEEVC-BEETHEFIRST-0.0.0.BIN'
        if self._beeCon.dummyPlugConnected():
            return fw

        with self._commandLock:
            resp = self._beeCon.sendCmd('M115\n', 'ok')
            resp = resp.replace('N:0', '')
            resp = resp.replace(' ', '')

            split = resp.split('ok')

            if not self._inFirmware and not self._inBootloader:
                self.getPrinterMode()

            if len(split) > 0 and self._inBootloader:
                fw = split[1]
            elif len(split) > 0 and not self._inBootloader:
                fw = split[0]
            else:
                return None

        return fw.rstrip()
    
    # *************************************************************************
    #                            pausePrint Method
    # *************************************************************************
    def pausePrint(self):
        r"""
        pausePrint method
        
        Initiates pause process
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._pausing = True
            self._beeCon.sendCmd('M640\n', "3")

            self.stopPrintStatusMonitor()

            if self._beeCon.dummyPlugConnected():
                self._paused = True

        return
    
    # *************************************************************************
    #                            resumePrint Method
    # *************************************************************************
    def resumePrint(self):
        r"""
        resumePrint method
        
        Resume print from pause/_shutdown
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd('M643\n')
            self._pausing = False
            self._shutdown = False
            self._resuming = True

        return
    
    # *************************************************************************
    #                            enterShutdown Method
    # *************************************************************************
    def enterShutdown(self):
        r"""
        enterShutdown method
        
        Pauses print and sets printer in shutdown
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        if not self._pausing or not self._paused:
            self.pausePrint()

        if self._pausing and not self._paused:
            nextPullTime = time.time() + 1
            while not self._paused:
                t = time.time()
                if t > nextPullTime:
                    s = self.getStatus()

        with self._commandLock:
            self._beeCon.sendCmd('M36\n')
            self._shutdown = True

        return
    
    # *************************************************************************
    #                            clearShutdownFlag Method
    # *************************************************************************
    def clearShutdownFlag(self):
        r"""
        clearShutdownFlag method
        
        Clears shutdown Flag
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd('M505\n')

            return True
    
    # *************************************************************************
    #                            sendCmd Method
    # *************************************************************************
    def sendCmd(self, cmd, wait=None, timeout=None):
        r"""
        sendCmd method
        
        Sends command to printer
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            if '\n' not in cmd:
                cmd += '\n'

            return self._beeCon.sendCmd(cmd, wait, timeout)

    # *************************************************************************
    #                            startPrintStatusMonitor Method
    # *************************************************************************
    def startPrintStatusMonitor(self, statusCallback):
        """
        Starts the monitor thread for the print status progress

        arguments:
            statusCallback - The callback function to where the status object will be passed
        :return:
        """
        # starts the status thread
        if statusCallback is not None:
            self._printStatusThread = printStatusThread.PrintStatusThread(self._beeCon,
                                                                     statusCallback)
            self._printStatusThread.start()

    # *************************************************************************
    #                            stopPrintStatusMonitor Method
    # *************************************************************************
    def stopPrintStatusMonitor(self):
        """
        Stops the status monitor thread if it is running
        :return:
        """
        # starts the status thread
        if self._printStatusThread is not None and self._printStatusThread.isAlive():
            self._printStatusThread.stopPrintStatusMonitor()

    # *************************************************************************
    #                            getCommandLock Method
    # *************************************************************************
    def getCommandLock(self):
        """
        Returns the command Lock thread object
        :return:
        """
        return self._commandLock

    # *************************************************************************
    #                            setNozzleSize Method
    # *************************************************************************
    def setNozzleSize(self, nozzleSize):
        r"""
        setNozzleSize method

        Sets Nozzle Size

        arguments:
            nozzleSize - nozzle size
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            return self._beeCon.sendCmd('M1027 S%i' % nozzleSize)

    # *************************************************************************
    #                            getNozzleSize Method
    # *************************************************************************
    def getNozzleSize(self):
        r"""
        getNozzleSize method

        Returns getNozzle Size int
        """
        nozzle = 400
        if self._beeCon.dummyPlugConnected():
            return nozzle

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            replyStr = self._beeCon.sendCmd('M1028')
            splits1 = replyStr.split('\n')

            if len(splits1) > 1:
                splits = splits1[0].split("Nozzle Size:")

                nozzle = int(splits[1])

            return nozzle

    # *************************************************************************
    #                            setFilamentInSpool Method
    # *************************************************************************
    def setFilamentInSpool(self, filamentInSpool):
        r"""
        setFilamentInSpool method

        Sets Filament in Spool

        arguments:
            filamentInSpool - mm in spool
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            return self._beeCon.sendCmd('M1024 X{:10.2f}'.format(filamentInSpool))

    # *************************************************************************
    #                            getFilamentInSpool Method
    # *************************************************************************
    def getFilamentInSpool(self):
        r"""
        getFilamentInSpool method

        Returns get Filament In Spool (mm)
        """
        if self._beeCon.dummyPlugConnected():
            return 350.0

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            try:
                replyStr = self._beeCon.sendCmd('M1025', wait='Filament in Spool:')

                filStart = replyStr.index('Filament in Spool:')
                filEnd = replyStr[filStart:].find('\n')
                return float(replyStr[filStart+len('Filament in Spool:'):filEnd+filStart])
            except Exception as ex:
                # in case of communication error returns a negative value signal to signal the error
                return -1.0

    # *************************************************************************
    #                            setSerialNumber Method
    # *************************************************************************
    def setSerialNumber(self,sn):
        r"""
        setSerialNumber method
        :param sn: serial number
        :return: None
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            self._beeCon.sendCmd('M118 T{}'.format(sn))

    # *************************************************************************
    #                        getTemperatures Method
    # *************************************************************************
    def getTemperatures(self):
        r"""
        getTemperatures method
        :return: temperatures dict
        """

        with self._commandLock:
            tStr = self._beeCon.sendCmd('M105')

        re1 = '(T)'  # Variable Name 1
        re2 = '.*?'  # Non-greedy match on filler
        re3 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 1
        re4 = '.*?'  # Non-greedy match on filler
        re5 = '(B)'  # Variable Name 2
        re6 = '.*?'  # Non-greedy match on filler
        re7 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 2
        re8 = '.*?'  # Non-greedy match on filler
        re9 = '(R)'  # Variable Name 3
        re10 = '.*?'  # Non-greedy match on filler
        re11 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 3

        rg = re.compile(re1 + re2 + re3 + re4 + re5 + re6 + re7 + re8 + re9 + re10 + re11, re.IGNORECASE | re.DOTALL)
        m = rg.search(tStr)
        temperatures = {}
        if m:
            var1 = m.group(1)
            float1 = m.group(2)
            var2 = m.group(3)
            float2 = m.group(4)
            var3 = m.group(5)
            float3 = m.group(6)
            temperatures['Nozzle'] = float1
            temperatures['Block'] = float2
            temperatures['Electronics'] = float3

        return temperatures

    # *************************************************************************
    #                    getElectronicsTemperature Method
    # *************************************************************************
    def getElectronicsTemperature(self):
        r"""
        getElectronicsTemperature method
        :return: electronics temperature
        """

        t = self.getTemperatures()

        return t['Electronics']

    # *************************************************************************
    #                  getExtruderBlockTemperature Method
    # *************************************************************************
    def getExtruderBlockTemperature(self):
        r"""
        getExtruderBlockTemperature method
        :return: blocks temperature
        """

        t = self.getTemperatures()

        return t['Block']

    # *************************************************************************
    #                    getCurrentPrintFilename Method
    # *************************************************************************
    def getCurrentPrintFilename(self):
        r"""
        getCurrentPrintFilename method
        :return: string with the filename stored in the printer
        """
        if self._beeCon.dummyPlugConnected():
            return "TECNET3.gcode"

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        filename = ''
        with self._commandLock:
            try:
                replyStr = self._beeCon.sendCmd('M1034\n', 'ok')
                replyStrParts = replyStr.split('\n')

                if len(replyStrParts) > 1:
                    filename = replyStrParts[0].replace('\'', '')

                return filename
            except Exception as ex:
                # in case of communication error returns None
                logger.error(ex)
                return None

    # *************************************************************************
    #                          getExtruderStepsMM Method
    # *************************************************************************
    def getExtruderStepsMM(self):
        r"""
        getExtruderStepsMM method

        Returns extruder steps per mm
        """
        if self._beeCon.dummyPlugConnected():
            return 440 #441.3897

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            try:
                replyStr = self._beeCon.sendCmd('M200')

                eSteps = 441.3897

                re1 = '.*?'  # Non-greedy match on filler
                re2 = '[+-]?\\d*\\.\\d+(?![-+0-9\\.])'  # Uninteresting: float
                re3 = '.*?'  # Non-greedy match on filler
                re4 = '[+-]?\\d*\\.\\d+(?![-+0-9\\.])'  # Uninteresting: float
                re5 = '.*?'  # Non-greedy match on filler
                re6 = '[+-]?\\d*\\.\\d+(?![-+0-9\\.])'  # Uninteresting: float
                re7 = '.*?'  # Non-greedy match on filler
                re8 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 1

                rg = re.compile(re1 + re2 + re3 + re4 + re5 + re6 + re7 + re8, re.IGNORECASE | re.DOTALL)
                m = rg.search(replyStr)
                if m:
                    eSteps = m.group(1)

                return eSteps
            except Exception as ex:
                # in case of communication error returns a negative value signal to signal the error
                return -1.0

    # *************************************************************************
    #                         setExtruderStepsMM Method
    # *************************************************************************
    def setExtruderStepsMM(self, steps):
        r"""
        setExtruderStepsMM method

        Defines extruder steps per mm
        """

        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            try:
                resp = self._beeCon.sendCmd('M200 E{}'.format(str(steps)), wait='ok')
                #resp = self._beeCon.sendCmd('M1030')   #-> commented, to try to fix a bug of the validation of the operation of setting steps per mm, with M200.

                return resp
            except Exception as ex:
                # in case of communication error returns a negative value signal to signal the error
                return -1.0

    # *************************************************************************
    #                         resetPrinterConfig Method
    # *************************************************************************
    def resetPrinterConfig(self):
        r"""
        resetPrinterConfig method

        Resets the printer config to factory settings
        """
        if self.isTransferring():
            logger.debug('File Transfer Thread active, please wait for transfer thread to end')
            return None

        with self._commandLock:
            try:
                self._beeCon.sendCmd('M607', wait='ok')
                self._beeCon.sendCmd('M601', wait='ok')
                self._beeCon.sendCmd('M1030')

                return True
            except Exception as ex:
                # in case of communication error returns a negative value signal to signal the error
                logger.error('Error resetting printer configurations: %s' % str(ex))
                return False

    # *************************************************************************
    #                           isExtruderCalibrated Method
    # *************************************************************************
    def isExtruderCalibrated(self):
        r"""
        returns true if printer was previously calibrated
        :return:
        """

        steps = float(self.getExtruderStepsMM())

        return not steps == 441.3897

    @staticmethod
    def generatePrintInfoHeader(filePath, estimatedPrintTime, gcodeLines):
        """
        Auxiliary method to generate the header string that will be sent to the printer when the print job begins

        :filePath           complete path to the file being printed
        :estimatedPrintTime estimated print time (seconds)
        :gcodeLines         number of real gcode lines the file has
        """
        if estimatedPrintTime is None:
            return None

        header = "M31 A"
        estTimeMin = int(estimatedPrintTime / 60)  # converted to minutes
        header = header + str(estTimeMin)

        if gcodeLines is not None and gcodeLines > 0:
            header = header + " L" + str(gcodeLines)

        # Extracts the filename from the complete file path
        import ntpath
        if filePath is None:
            header = header + "\n"
            return header

        path, filename = ntpath.split(filePath)

        header = header + "\nM1033 " + filename
        header = header + "\n"

        return header
