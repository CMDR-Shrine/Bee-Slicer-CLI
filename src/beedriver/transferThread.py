#!/usr/bin/env python

import threading
import time
import os
import usb
import math
import re
from beedriver import logger

"""
* Copyright (c) 2015 BEEVC - Electronic Systems This file is part of BEESOFT
* software: you can redistribute it and/or modify it under the terms of the GNU
* General Public License as published by the Free Software Foundation, either
* version 3 of the License, or (at your option) any later version. BEESOFT is
* distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
* without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
* PARTICULAR PURPOSE. See the GNU General Public License for more details. You
* should have received a copy of the GNU General Public License along with
* BEESOFT. If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "BVC Electronic Systems"
__license__ = ""


class FileTransferThread(threading.Thread):
    r"""
        FileTransferThread Class

        This class provides the methods to transfer files, flash firmware and start print

        __init__(connection, filePath, transferType, optionalString, temperature)        Initializes current class
        getTransferCompletionState()                                                     Returns current file transfer state 
        cancelFileTransfer()                                                             Cancels current file transfer
        transferFirmwareFile()                                                           Transfers Firmware File to printer
        multiBlockFileTransfer()                                                         Transfers Gcode File using multi blok transfers
        sendBlock(startPos, fileObj)                                                     Writes a block of messages
        sendBlockMsg(msg)                                                                Sends a block message to the printer
        waitForHeatingAndPrint(temperature)                                              Waits for setpoint temperature and starts printing the transferred file
    """

    transferring = False
    heating = False
    fileSize = 0
    bytesTransferred = 0
    filePath = None
    transferType = None
    optionalString = None
    temperature = 0
    flashFirmwareSuccess = False

    transmissionErrors = 0

    cancelTransfer = False
    
    MESSAGE_SIZE = 512
    BLOCK_SIZE = 64
    
    beeCon = None
    
    # *************************************************************************
    #                        __init__ Method
    # *************************************************************************
    def __init__(self, connection, filePath, transferType, optionalString=None, temperature=None, header=None):
        r"""
        __init__ Method

        Initializes this class

        """
        
        super(FileTransferThread, self).__init__()
        
        self.beeCon = connection
        self.filePath = filePath
        self.transferType = transferType
        self.optionalString = optionalString
        self.cancelTransfer = False
        self.temperature = temperature
        self.header = header

        if temperature is not None:
            self.heating = True

        if filePath is not None:
            self.fileSize = os.path.getsize(filePath)                         # Get Firmware size in bytes

        return
    
    def run(self):
        
        # super(FileTransferThread, self).run()
        
        if self.transferType.lower() == 'firmware':
            self.transferring = True
            logger.info('Starting Firmware Transfer')
            self.transferFirmwareFile()
            self.transferring = False
        
        elif self.transferType.lower() == 'gcode':
            self.transferring = True
            logger.info('Starting GCode Transfer')
            self.multiBlockFileTransfer()

            self.transferring = False

        elif self.transferType.lower() == 'print':
            # If no file path is given, print last file. Otherwise transfer file to printer
            if self.filePath is not None:
                self.transferring = True
                self.beeCon.setMonitorConnection(False)

                logger.info('Starting GCode Transfer')
                self.multiBlockFileTransfer()
                logger.info('File Transfer Finished. Heating...')

                self.beeCon.setMonitorConnection(True)
                self.transferring = False

            if not self.cancelTransfer:
                self.waitForHeatingAndPrint(self.temperature)
            self.heating = False
        else:
            logger.info('Unknown Transfer Type')

        logger.info('Exiting transfer thread')
        
        return

    # *************************************************************************
    #                        getTransferCompletionState Method
    # *************************************************************************
    def getTransferCompletionState(self):
        r"""
        getTransferCompletionState method
        
        Returns current file transfer state
        """
        if self.fileSize > 0:
            percent = (100 * self.bytesTransferred / self.fileSize)
            return "%.2f" % percent
        else:
            return None

    # *************************************************************************
    #                        getTransferCompletion Method
    # *************************************************************************
    def getTransferCompletion(self):
        r"""
        getTransferCompletion

        Returns current file transfer progress in decimal percentage (float 0.00 - 1.00)
        """
        if self.fileSize > 0:
            return float(self.bytesTransferred) / float(self.fileSize)
        else:
            return 0.0

    # *************************************************************************
    #                        cancelFileTransfer Method
    # *************************************************************************
    def cancelFileTransfer(self):
        r"""
        cancelFileTransfer method
        
        Cancels current file transfer
        """

        self.cancelTransfer = True

    # *************************************************************************
    #                        isTransferring Method
    # *************************************************************************
    def isTransferring(self):
        r"""
        isTransferring method

        Returns the transferring flag state
        """

        return self.transferring

    # *************************************************************************
    #                        isHeating Method
    # *************************************************************************
    def isHeating(self):
        r"""
        isHeating method

        Returns True if the printer is heating
        """

        return self.heating

    # *************************************************************************
    #                        isTransferFirmwareSuccessful Method
    # *************************************************************************
    def isTransferFirmwareSuccessful(self):
        r"""
        isTransferFirmwareSuccessful method

        Returns True if the transferring of the firmware file was successful
        """

        return self.flashFirmwareSuccess

    # *************************************************************************
    #                        transferFirmwareFile Method
    # *************************************************************************
    def transferFirmwareFile(self):
        r"""
        transferFirmwareFile method
        
        Transfers Firmware File to printer
        """
        
        cTime = time.time()                                # Get current time

        message = "M650 A" + str(self.fileSize) + "\n"     # Prepare Start Transfer Command string
        self.beeCon.write(message)                         # Send Start Transfer Command

        # Before continue wait for the reply from the Start Command transfer
        resp = ''
        while 'ok' not in resp:               # Once the printer is ready it replies 'ok'
            resp += self.beeCon.read()

        with open(self.filePath, 'rb') as f:  # Open file to start transfer

            while True:
                buf = f.read(64)              # Read 64 bytes from file

                if not buf:
                    break                     # if nothing left to read, transfer finished

                self.beeCon.write(buf)        # Send 64 bytes to the printer

                # time.sleep(0.0000001)       # Small delay helps remove sporadic errors

                # The printer will forward the received data
                # we then collect the received data and compare it to identify transfer errors
                ret = []
                while len(ret) < len(buf):                        # wait for the 64 bytes to be received
                    try:
                        ret += self.beeCon.ep_in.read(len(buf), 1000)
                    except usb.core.USBError as e:
                        if "timed out" in str(e.args):
                            pass
                        else:
                            break

                bRet = bytearray(ret)  # convert the received data to bytes
                if not bRet == buf:    # Compare the data received with data sent
                                    # If data received/sent are different cancel transfer and reset the printer manually
                    if not any(buf == bRet[i:len(buf) + i] for i in xrange(len(bRet) - len(buf) + 1)):
                        logger.error('Firmware Flash error, please reset the printer')
                        return False

                # sys.stdout.write('.')      # print dot to console
                # sys.stdout.flush()         # used only to provide a simple indication as the process in running
                self.bytesTransferred += len(buf)

        eTime = time.time()

        avgSpeed = self.fileSize//(eTime - cTime)

        logger.info("Flashing completed in %d seconds", eTime-cTime)
        logger.info("Average Transfer Speed %.2f bytes/second", avgSpeed)
        
        self.bytesTransferred = 0
        self.fileSize = 0

        self.flashFirmwareSuccess = True
        return True
    
    # *************************************************************************
    #                        multiBlockFileTransfer Method
    # *************************************************************************
    def multiBlockFileTransfer(self):
        r"""
        multiBlockFileTransfer method
        
        Transfers Gcode File using multi block transfers
        """

        offset = 0
        
        # Get commands interface
        beeCmd = self.beeCon.getCommandIntf()
        
        # Create File
        beeCmd.initSD()
        sdFileName = "ABCDE"
        
        # If a different SD Filename is provided
        if self.optionalString is not None:
            sdFileName = self.optionalString
            # REMOVE SPECIAL CHARS
            sdFileName = re.sub('[\W_]+', '', sdFileName)

            # CHECK FILENAME
            if len(sdFileName) > 8:
                sdFileName = sdFileName[:7]

            firstChar = sdFileName[0]

            if firstChar.isdigit():
                nameChars = list(sdFileName)
                nameChars[0] = 'a'
                sdFileName = "".join(nameChars)

        # Get Number of blocks to transfer
        blockBytes = beeCmd.MESSAGE_SIZE * beeCmd.BLOCK_SIZE
        nBlocks = int(math.ceil(float(self.fileSize)/float(blockBytes)))
        logger.info("Number of Blocks: %d", nBlocks)

        # CREATE SD FILE
        resp = beeCmd.createFile(sdFileName)
        if not resp:
            return

        # Send gcode header text
        if self.header is not None:
            offset = len(self.header)
            self.sendHeader(self.header)
        else:
            offset = 0

        # Start transfer
        blocksTransferred = 0
        self.bytesTransferred = 0

        startTime = time.time()

        # Load local file
        with open(self.filePath, 'rb') as f:

            beeCmd.transmissionErrors = 0

            while blocksTransferred < nBlocks and not self.cancelTransfer:

                startPos = self.bytesTransferred
                # endPos = self.bytesTransferred + blockBytes

                # bytes2write = endPos - startPos

                # if blocksTransferred == (nBlocks-1):
                #    endPos = self.fileSize

                blockTransferred = False
                while blockTransferred is False:

                    blockBytesTransferred = self.sendBlock(startPos, f, offset)
                    if blockBytesTransferred is None:
                        logger.info("transferGFile: Transfer aborted")
                        return False
                    else:
                        blockTransferred = True

                self.bytesTransferred += blockBytesTransferred
                blocksTransferred += 1
                # logger.info("transferGFile: Transferred %s / %s blocks %d / %d bytes",
                #            str(blocksTransferred), str(nBlocks), endPos, self.fileSize)

        if self.cancelTransfer:
            logger.info('multiBlockFileTransfer: File Transfer canceled')
            logger.info('multiBlockFileTransfer: %s / %s bytes transferred', str(self.bytesTransferred),str(self.fileSize))
            self.transferring = False
            beeCmd.cancelHeating()
            # self.cancelTransfer = False
            return

        logger.info("multiBlockFileTransfer: Transfer completed. Errors Resolved: %s", str(beeCmd.transmissionErrors))

        elapsedTime = time.time() - startTime
        avgSpeed = self.fileSize//elapsedTime
        logger.info("multiBlockFileTransfer: Elapsed time: %d seconds", elapsedTime)
        logger.info("multiBlockFileTransfer: Average Transfer Speed: %.2f bytes/second", avgSpeed)

        return

    # *************************************************************************
    #                        sendHeader Method
    # *************************************************************************

    def sendHeader(self, text):
        r"""
        sendHeader method

        writes the header of the gcode file

        arguments:
            text - header text

        returns:
            True if header transferred successfully
            False if an error occurred and communication was reestablished
            None if an error occurred and could not reestablish communication with printer

        Note: Header must be shorter than 512 bytes
        """
        endPos = len(text)

        self.beeCon.write("M28 D" + str(endPos - 1) + " A0\n")

        resp = self.beeCon.read()
        while "ok q:0" not in resp.lower():
            resp += self.beeCon.read()

        mResp = self.sendBlockMsg(text)
        if mResp is not True:
            return mResp

        return len(text)
    
    # *************************************************************************
    #                        sendBlock Method
    # *************************************************************************
    def sendBlock(self, startPos, fileObj, writeOffset=0):
        r"""
        sendBlock method

        writes a block of messages

        arguments:
            startPos - starting position of block
            fileObj - file object with file to write
            writeOffset  - possible offset caused by header

        returns:
            True if block transferred successfully
            False if an error occurred and communication was reestablished
            None if an error occurred and could not reestablish communication with printer
        """

        fileObj.seek(startPos)
        block2write = fileObj.read(self.MESSAGE_SIZE * self.BLOCK_SIZE)

        endPos = startPos + len(block2write)

        if writeOffset > 0:
            startPos = startPos + writeOffset
            endPos = endPos + writeOffset

        # self.StartTransfer(endPos,startPos)
        self.beeCon.write("M28 D" + str(endPos - 1) + " A" + str(startPos) + "\n")

        nMsg = int(math.ceil(float(len(block2write))/float(self.MESSAGE_SIZE)))
        msgBuf = []
        for i in range(nMsg):
            if i < nMsg:
                msgBuf.append(block2write[i*self.MESSAGE_SIZE:(i+1)*self.MESSAGE_SIZE])
            else:
                msgBuf.append(block2write[i*self.MESSAGE_SIZE:])

        resp = self.beeCon.read()
        while "ok q:0" not in resp.lower():
            resp += self.beeCon.read()
        # print(resp)
        # resp = self.beeCon.read(10) #force clear buffer

        for m in msgBuf:
            mResp = self.sendBlockMsg(m)
            if mResp is not True:
                return mResp

        return len(block2write)

    # *************************************************************************
    #                        sendBlockMsg Method
    # *************************************************************************
    def sendBlockMsg(self, msg):
        r"""
        sendBlockMsg method

        sends a block message to the printer.

        arguments:
            msg - message to be writen

        returns:
            True if message transferred successfully
            False if an error occurred and communication was reestablished
            None if an error occurred and could not reestablish communication with printer
        """

        # resp = self.beeCon.dispatch(msg)
        msgLen = len(msg)
        bWriten = self.beeCon.write(msg)
        if msgLen != bWriten:
            logger.info("Bytes lost")
            return False

        time.sleep(0.001)

        tries = 10
        resp = ""
        while (tries > 0) and ("tog" not in resp):
            try:
                resp += self.beeCon.read()
                tries -= 1
            except Exception as ex:
                logger.error(str(ex))
                logger.error("resp: {}".format(resp))
                tries = -1

        if tries > 0:
            return True
        else:
            cleaningTries = 5
            clean = False
            self.transmissionErrors += 1
            while cleaningTries > 0 and clean is False:
                beeCmd = self.beeCon.getCommandIntf()
                clean = beeCmd.cleanBuffer()
                time.sleep(0.5)
                self.beeCon.reconnect()

                cleaningTries -= 1

            if cleaningTries <= 0:
                return None

            if clean is False:
                return None

            return False

    # *************************************************************************
    #                        waitForHeatingAndPrint Method
    # *************************************************************************
    def waitForHeatingAndPrint(self, temperature):
        r"""
        waitForHeatingAndPrint method
        
        Waits for setpoint temperature and starts printing the transferred file
        """
        
        # Get commands interface
        beeCmd = self.beeCon.getCommandIntf()

        while beeCmd.getNozzleTemperature() < temperature:
            time.sleep(1)
            if self.cancelTransfer:
                beeCmd.cancelHeating()
                self.cancelTransfer = False
                return

        sdFileName = 'ABCDE'
        # If a different SD Filename is provided
        if self.optionalString is not None:
            sdFileName = self.optionalString
            # REMOVE SPECIAL CHARS
            sdFileName = re.sub('[\W_]+', '', sdFileName)
    
            # CHECK FILENAME
            if len(sdFileName) > 8:
                sdFileName = sdFileName[:7]
    
            firstChar = sdFileName[0]
    
            if firstChar.isdigit():
                nameChars = list(sdFileName)
                nameChars[0] = 'a'
                sdFileName = "".join(nameChars)
        
        logger.info('Heating Done. Beginning print...')
        self.beeCon.sendCmd('M33 %s\n' % sdFileName)

        return
