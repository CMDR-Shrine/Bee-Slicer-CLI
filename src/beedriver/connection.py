#!/usr/bin/env python
import threading
import time
import datetime

import usb
import usb.core
from beedriver.commands import BeeCmd
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


class Conn:
    r"""
        Connection Class

        This class provides the methods to manage and control communication with the
        BeeTheFirst 3D printer

        __init__()                                              Initializes current class
        getPrinterList()                                        Returns a Dictionary list of the printers.
        connectToPrinter(selectedPrinter)                       Establishes Connection to selected printer
        connectToFirstPrinter()                                 Establishes Connection to first printer found
        connectToPrinterWithSN(serialNumber)                    Establishes Connection to printer by serial number
        write(message,timeout)                                  writes data to the communication buffer
        read()                                                  read data from the communication buffer
        dispatch(message)                                       writes data to the buffer and reads the response
        sendCmd(cmd,wait,to)                                    Sends a command to the 3D printer
        waitFor(cmd, s, timeout)                                writes command to the printer and waits for the response
        waitForStatus(cmd, s, timeout)                         writes command to the printer and waits for status the response
        close()                                                 closes active communication with the printer
        isConnected()                                           Returns the current state of the printer connection
        getCommandIntf()                                        Returns the BeeCmd object with the command interface for higher level operations
        reconnect()                                             closes and re-establishes the connection with the printer
    """

    READ_TIMEOUT = 2000
    DEFAULT_READ_LENGTH = 512

    # *************************************************************************
    #                            __init__ Method
    # *************************************************************************
    def __init__(self, disconnectCallback=None, dummyPlug=False):
        r"""
        __init__ Method

        Initializes this class

        receives as argument the BeeConnection object and verifies the
        connection status

        """

        self.dev = None

        self.ep_in = None
        self.ep_out = None

        self.cfg = None
        self.intf = None

        self.transferring = False
        self.fileSize = 0
        self.bytesTransferred = 0
        self._dummyPlug = dummyPlug
        self._dummyTemperature = 0.0

        self._disconnectCallback = disconnectCallback

        self.connected = None

        self.backend = None

        self.printerList = None
        self.connectedPrinter = None

        self.command_intf = None     # Commands interface

        self._connectionLock = threading.Lock()
        self._connectionRLock = threading.RLock()

        self._connectionMonitor = None
        self._monitorConnection = True

        self._lastExceptionMsg = None
        self._lastExceptionTimestamp = None
        self._sameExceptionCounter = 0

        return

    # *************************************************************************
    #                        getPrinterList Method
    # *************************************************************************
    def getPrinterList(self):
        r"""
        getPrinterList method

        Returns a Dictionary list of the printers.
        """
        self.printerList = []
        dev_list = []

        if not self._dummyPlug:
            try:
                for dev in usb.core.find(idVendor=0xffff, idProduct=0x014e, find_all=True):
                    dev_list.append(dev)

                for dev in usb.core.find(idVendor=0x29c9, find_all=True):
                    dev_list.append(dev)

                # Smoothieboard
                for dev in usb.core.find(idVendor=0x1d50, find_all=True):
                    dev_list.append(dev)
            except Exception as ex:  # If any problems occurs in USB connection, enters to dummyplug mode
                print 'BEEcom FATAL Error when trying to connect to USB interface: ' + str(ex)
                print 'Check that you have libusb correctly installed.'
                pass

        if self._dummyPlug is True:
            # creates a dummy interface
            printer = {'VendorID': '10697', 'ProductID': '1',
                       'Manufacturer': 'BEEVERYCREATIVE', 'Product':
                           'BEETHEFIRST PLUS A', 'Serial Number': '0000000003', 'Interfaces': []}
            self.printerList.append(printer)

            return self.printerList

        for dev in dev_list:
            try:
                currentSerialNumber = str(dev.serial_number)
            except:
                currentSerialNumber = '0000000001'
                pass

            # Removes null character from the string returned from the usb driver
            currentSerialNumber = currentSerialNumber.strip('\x00')

            # Try to read manufacturer and product, but handle langid errors
            try:
                manufacturer = dev.manufacturer
            except:
                manufacturer = 'Unknown'
                pass

            try:
                product = dev.product
            except:
                product = 'Unknown'
                pass

            printer = {'VendorID': str(dev.idVendor),
                       'ProductID': str(dev.idProduct),
                       'Manufacturer': manufacturer,
                       'Product': product,
                       'Serial Number': currentSerialNumber,
                       'Interfaces': []}
            for config in dev:
                for intf in config:
                    interface = dict()
                    interface['Class'] = intf.bInterfaceClass
                    # endPoints = intf.endpoints()
                    interface['EP Out'] = usb.util.find_descriptor(intf,
                                                                    # match the first OUT endpoint
                                                                    custom_match=lambda lb: usb.util.endpoint_direction(lb.bEndpointAddress) == usb.util.ENDPOINT_OUT)
                    interface['EP In'] = usb.util.find_descriptor(intf,
                                                                    # match the first OUT endpoint
                                                                    custom_match=lambda lb: usb.util.endpoint_direction(lb.bEndpointAddress) == usb.util.ENDPOINT_IN)
                    printer['Interfaces'].append(interface)
            self.printerList.append(printer)
        
        # logger.info('Found %d Printers.' % len(self.printerList))
        
        return self.printerList
    
    # *************************************************************************
    #                        connectToPrinter Method
    # *************************************************************************
    def connectToPrinter(self, selectedPrinter):
        r"""
        connectToPrinter method

        Establishes Connection to selected printer
        
        returns False if connection fails
        """

        self.connectedPrinter = selectedPrinter
        logger.info('...Connecting to %s with serial number %s', str(selectedPrinter['Product']), str(selectedPrinter['Serial Number']))

        if self._dummyPlug is True:
            self.connected = True
            return True

        self.ep_out = self.connectedPrinter['Interfaces'][0]['EP Out']
        self.ep_in = self.connectedPrinter['Interfaces'][0]['EP In']
        
        # Verify that the end points exist
        assert self.ep_out is not None
        assert self.ep_in is not None
        
        self.dev = self.ep_out.device
        try:
            self.dev.set_configuration()
            self.dev.reset()
            time.sleep(2.0)  # Increased delay for device initialization after USB reset
            #self.dev.set_configuration()
            self.cfg = self.dev.get_active_configuration()
            self.intf = self.cfg[(0, 0)]
            self.connected = True
            logger.info("Connection established successfully, connected=%s", self.connected)
        except usb.core.USBError as usb_exception:
            logger.error("USB exception while connecting to printer: %s", str(usb_exception))
            self._handleUSBException(usb_exception, "USB exception while connecting to printer")
            # Clean up USB resources on failure
            try:
                if self.dev is not None:
                    usb.util.dispose_resources(self.dev)
            except:
                pass
            self.ep_out = None
            self.ep_in = None
            self.connected = False
            return False
        except Exception as e:
            logger.error("Unexpected exception while connecting to printer: %s", str(e))
            # Clean up USB resources on failure
            try:
                if self.dev is not None:
                    usb.util.dispose_resources(self.dev)
            except:
                pass
            self.ep_out = None
            self.ep_in = None
            self.connected = False
            return False
        
        return True
    
    # *************************************************************************
    #                        connectToFirstPrinter Method
    # *************************************************************************
    def connectToFirstPrinter(self):
        r"""
        connectToFirstPrinter method

        Establishes Connection to first printer found
        
        returns False if connection fails
        """
        
        self.getPrinterList()
        
        if len(self.printerList) > 0:
            self.connectToPrinter(self.printerList[0])
            return True
        
        return False
    
    # *************************************************************************
    #                        connectToPrinterWithSN Method
    # *************************************************************************
    def connectToPrinterWithSN(self, serialNumber):
        r"""
        connectToPrinterWithSN method

        Establishes Connection to printer by serial number
        
        returns False if connection fails
        """
        
        for printer in self.printerList:
            SN = str(printer['Serial Number'])
            if SN == serialNumber:
                self.connectToPrinter(printer)
                return True
            
        return False

    # *************************************************************************
    #                        getConnectedPrinterName Method
    # *************************************************************************
    def getConnectedPrinterName(self):
        r"""
        Returns the name of the connected printer or None if not connected
        """
        if self.isConnected():
            return self.connectedPrinter['Product']

        return None

    # *************************************************************************
    #                        getConnectedPrinterSN Method
    # *************************************************************************
    def getConnectedPrinterSN(self):
        r"""
        Returns the serial number of the connected printer or None if not connected
        """
        if self.isConnected():
            return self.connectedPrinter['Serial Number']

        return None

    # *************************************************************************
    #                        write Method
    # *************************************************************************
    def write(self, message, timeout=500):
        r"""
        write method

        writes a message to the communication buffer

        arguments:
            message - data to be writen
            timeout - optional communication timeout (default = 500ms)

        returns:
            byteswriten - bytes writen to the buffer
        """
        
        bytes_written = 0

        with self._connectionRLock:
            if self._dummyPlug is True:
                return len(message)
            else:
                try:
                    if self.ep_out is None:  # This means something bad happened with the connection
                        self._handleUnexpectedConnectionDrop()

                    bytes_written = self.ep_out.write(message, timeout)
                except usb.core.USBError as usb_exception:
                    self._handleUSBException(usb_exception, "USB write data exception")

        return bytes_written

    # *************************************************************************
    #                        read Method
    # *************************************************************************
    def read(self, timeout=2000, readLen=512):
        r"""
        reads existing data from the communication buffer

        arguments:
            timeout - optional communication timeout
            readLen - optional read length in bytes

        returns:
            sret - string with data read from the buffer
        """

        resp = ""

        with self._connectionRLock:
            if self._dummyPlug is True:
                return "ok Q:0"

            try:

                if self.ep_in is None:  # This means something bad happened with the connection
                    self._handleUnexpectedConnectionDrop()

                self.write("")
                ret = self.ep_in.read(readLen, timeout)
                resp = ''.join([chr(x) for x in ret])
            except usb.core.USBError as usb_exception:
                self._handleUSBException(usb_exception, "USB read data exception")

        return resp

    # *************************************************************************
    #                        dispatch Method
    # *************************************************************************
    def dispatch(self, message):
        r"""
        dispatch method

        writes data to the communication buffers and read existing data

        arguments:
            message - data to be writen

        returns:
            sret - string with data read from the buffer
        """
        timeout = Conn.READ_TIMEOUT
        resp = "No response"

        with self._connectionLock:
            if self._dummyPlug is True:
                return "ok Q:0"

            try:
                time.sleep(0.009)
                self.ep_out.write(message)
                time.sleep(0.009)

            except usb.core.USBError as usb_exception:
                self._handleUSBException(usb_exception, "USB dispatch (write) data exception")

            try:
                ret = self.ep_in.read(Conn.DEFAULT_READ_LENGTH, timeout)
                resp = ''.join([chr(x) for x in ret])

            except usb.core.USBError as usb_exception:
                self._handleUSBException(usb_exception, "USB dispatch (read) data exception")

        return resp

    # *************************************************************************
    #                        sendCmd Method
    # *************************************************************************
    def sendCmd(self, cmd, wait=None, timeout=None):
        r"""
        sendCmd method

        sends command to the printer

        arguments:
            cmd - command to send
            wait - optional wait for reply
            timeout - optional communication timeout

        returns:
            resp - string with data read from the buffer
        """
        if '\n' not in cmd:
            cmd += "\n"

        if self._dummyPlug is True:
            if cmd == 'M625\n':
                return "S:3"
            if cmd == 'M105\n':
                if self._dummyTemperature == 240.0:
                    self._dummyTemperature = 0.0
                self._dummyTemperature += 10.0
                return "T:" + str(self._dummyTemperature) + " ok Q:0"

            return "ok Q:0"

        if wait is None:
            resp = self.dispatch(cmd)
        else:
            if wait.isdigit():
                resp = self.waitForStatus(cmd, wait, timeout)
            else:
                resp = self.waitFor(cmd, wait, timeout)

        return resp

    # *************************************************************************
    #                        waitFor Method
    # *************************************************************************
    def waitFor(self, cmd, s, timeout=None):
        r"""
        waitFor method

        writes command to the printer and waits for the response

        arguments:
            cmd - command to send
            s - string to be found in the response
            timeout - optional communication timeout (seconds)

        returns:
            resp - string with data read from the buffer
        """
        c_time = time.time()
        resp = ""

        with self._connectionLock:
            if self._dummyPlug is True:
                return s

            self.write(cmd)

            while s not in resp:
                try:
                    resp += self.read()
                except Exception as ex:
                    logger.error("Exception while waiting for response from printer: %s", str(ex))
                    return resp

                # Checks timeout
                if timeout is not None:
                    e_time = time.time()
                    if e_time-c_time > timeout:
                        break

        return resp

    # *************************************************************************
    #                        waitForStatus Method
    # *************************************************************************
    def waitForStatus(self, cmd, s, timeout=None):
        r"""
        waitForStatus method

        writes command to the printer and waits for status the response

        arguments:
            cmd - commmand to send
            s - string to be found in the response
            timeout - optional communication timeout (seconds)

        returns:
            resp - string with data read from the buffer
        """
        c_time = time.time()
        resp = ""

        with self._connectionLock:
            if self._dummyPlug is True:
                return "ok Q:0 S:" + str(s)

            self.write(cmd)

            str2find = "S:" + str(s)

            while "ok" not in resp:

                try:
                    resp += self.read()
                except Exception as ex:
                    logger.error("Exception while waiting for ok response from printer: %s", str(ex))
                    return resp

                # Checks timeout
                if timeout is not None:
                    e_time = time.time()
                    if e_time-c_time > timeout:
                        break

            while str2find not in resp:
                try:
                    self.write("M625\n")
                    time.sleep(0.5)
                    resp += self.read()
                except Exception as ex:
                    logger.error("Exception while waiting for %s response: %s", str2find, str(ex))
                    break

        return resp

    # *************************************************************************
    #                        close Method
    # *************************************************************************
    def close(self):
        r"""
        Closes active connection with printer
        """
        try:
            if self.ep_out is not None:
                # release the device
                usb.util.dispose_resources(self.dev)
                self.ep_out = None
                self.ep_in = None
                self.intf = None
                self.cfg = None
                #usb.util.release_interface(self.dev, self.intf)    #not needed after dispose

                self.connected = False
        except usb.core.USBError as e:
            logger.error("USB exception while closing connection to printer: %s", str(e))

        return

    # *************************************************************************
    #                        isConnected Method
    # *************************************************************************
    def isConnected(self):
        r"""
        isConnected method

        returns the connection state

        returns:
            True if connected
            False if disconnected
        """

        return self.connected

    # *************************************************************************
    #                        getCommandIntf Method
    # *************************************************************************
    def getCommandIntf(self):
        r"""
        getCommandIntf method

        returns Comm object which contains the printer commands interface

        returns:
            Comm if connected
            None if disconnected
        """
        if self.isConnected():
            self.command_intf = BeeCmd(self)

        return self.command_intf

    # *************************************************************************
    #                        reconnect Method
    # *************************************************************************
    def reconnect(self):
        r"""
        reconnect method

        tries to reconnect to the printer

        returns:
            True if connected
            False if disconnected
        """
        
        SN = str(self.connectedPrinter['Serial Number'])
        self.close()
        time.sleep(0.5)
        self.getPrinterList()
        self.connectToPrinterWithSN(SN)
        
        return self.connected

    # *************************************************************************
    #                        ping Method
    # *************************************************************************
    def ping(self):
        r"""
        ping method

        tries to contact the printer

        returns:
            True if connected
            False if disconnected
        """
        with self._connectionLock:
            try:
                if self.ep_out is None:
                    return False

                bytesw = self.ep_out.write('M637\n', 5000)

                if bytesw == 0:
                    logger.warning('Ping failed...')
                    return False

            except usb.core.USBError as usb_exception:
                # If the connection is busy and the operation timesout ignores the error and considers the ping success
                if "Operation timed out" in str(usb_exception):
                    logger.warning('Ping timeout...')
                    return True

                logger.error('Ping error:' + str(usb_exception))
                return False

            return True

    def startConnectionMonitor(self):
        """
        Starts the connection monitor thread to check if the connection is still active
        :return:
        """
        if self._disconnectCallback is not None and self._connectionMonitor is None:
            self._connectionMonitor = threading.Thread(
                target=self._connectionMonitorThread, name="bee_connection._conn_monitor_thread")
            self._connectionMonitor.daemon = True
            self._connectionMonitor.start()

    def setMonitorConnection(self, status):
        """
        Sets the monitor connection flag
        :param status:
        :return:
        """
        self._monitorConnection = status

    def dummyPlugConnected(self):
        """
        Gets the dummyPlug flag variable
        """
        return self._dummyPlug

    def _handleUSBException(self, exception, loggerMsg):
        """
        Handles any special case for USB exceptions from libusb
        :param exception:
        :param loggerMsg:
        :return:
        """
        libusbMsg = str(exception)
        warning_messages = ['Operation timed out', 'timeout']
        critical_messages = ['Input/Output Error', 'Pipe error']

        # checks if the message is just considered a warning
        for msg in warning_messages:
            if msg in libusbMsg:
                if not self._exceptionLoggedRecently(libusbMsg):
                    logger.warning(loggerMsg + ": " + libusbMsg)

                self._lastExceptionTimestamp = datetime.datetime.now()
                self._lastExceptionMsg = libusbMsg
                return

        # if the message is in the critical error message group, considers that there was a connection drop
        for cr_msg in critical_messages:
            if cr_msg in libusbMsg:
                if not self._exceptionLoggedRecently(libusbMsg):
                    logger.error(loggerMsg + ": " + libusbMsg)

                self._handleUnexpectedConnectionDrop()
                self._lastExceptionTimestamp = datetime.datetime.now()
                self._lastExceptionMsg = libusbMsg
                return

        if not self._exceptionLoggedRecently(libusbMsg):
            logger.error(loggerMsg + ": " + libusbMsg)
        else:
            # If more than 20 equal exceptions are logged in a short time frame (1 min.), considers a connection drop
            if self._sameExceptionCounter >= 20:
                self._handleUnexpectedConnectionDrop()

        self._lastExceptionTimestamp = datetime.datetime.now()
        self._lastExceptionMsg = libusbMsg

    def _handleUnexpectedConnectionDrop(self):
        logger.error("Unexpected connection drop! Trying to reconnect...")
        self._monitorConnection = False
        time.sleep(1)

        # if the monitor thread still hasn't signalled the client to disconnect, we can try to reconnect
        if self.connected is True:
            if not self.connectToFirstPrinter():
                self.connected = False
                # In case the reconnect was not successful signals the client to disconnect
                if self._disconnectCallback is not None:
                    self._disconnectCallback()
            else:
                # if the reconnection succeeded restarts the connection monitor
                self._connectionMonitor = None
                self.startConnectionMonitor()

    def _exceptionLoggedRecently(self, exceptionMsg):
        sameExceptionTimeThreshold = datetime.datetime.now() - datetime.timedelta(minutes=1)  # One minute ago

        # if an equal exception was logged during the last minute, returns true
        if self._lastExceptionMsg is not None and self._lastExceptionTimestamp is not None \
                and self._lastExceptionMsg == exceptionMsg and \
                self._lastExceptionTimestamp > sameExceptionTimeThreshold:

                self._sameExceptionCounter += 1
                return True

        # resets the counter if its different or not recent
        self._sameExceptionCounter = 0
        return False

    def _connectionMonitorThread(self):
        """
        Monitor thread to check if the connection to the printer is still active
        :return:
        """
        # This variables is the number of seconds before a shutdown is simulated
        # and can be used if we want to simulate a disconnect from the printer.
        # If no disconnect simulation is intended just use a big enough value
        dummyPlugDisconnectSim = 10000

        failedPings = 3
        while self.connected is True:
            time.sleep(1)
            if self._monitorConnection is True:
                try:
                    if self._dummyPlug is True:
                        if dummyPlugDisconnectSim == 0:
                            self._disconnectCallback()
                            self.connected = False
                            return
                        else:
                            dummyPlugDisconnectSim -= 1
                            continue

                    if not self.ping():
                        failedPings -= 1
                    else:
                        failedPings = 3

                    if failedPings == 0:
                        self._disconnectCallback()
                        self.connected = False

                except Exception as ex:
                    logger.warning('Unexpected exception while pinging the printer for connection: %s' % str(ex))
                    continue
