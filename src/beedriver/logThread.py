#!/usr/bin/env python

import threading
import time
import os
from beedriver import parsers
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


class LogThread(threading.Thread):
    r"""
        LogThread Class

        This class provides the methods to debug and log printer actions


    """

    # *************************************************************************
    #                        __init__ Method
    # *************************************************************************
    def __init__(self, connection, logJob='TemperatureLog', frequency=1,logFileName='aaa.csv', samples=0, hideLog=True):
        r"""
        __init__ Method

        Initializes this class

        """

        super(LogThread, self).__init__()

        self.beeCon = connection
        self._logJog = logJob
        self._freq = frequency
        self._logFileName = './logs/' + logFileName
        self._samples = samples
        self._logFile = None
        self._hideLog = hideLog
        self._stopLog = False
        self._printer = self.beeCon.connectedPrinter['Product']

        if not os.path.exists('logs'):
            os.makedirs('logs')

        return

    # *************************************************************************
    #                        run Method
    # *************************************************************************
    def run(self):

        super(LogThread, self).run()

        #########################
        #    Temperature Log
        #########################
        if self._logJog == 'TemperatureLog':
            self._logFile = open(self._logFileName,'w')
            #self._logFile.write("T,B\n")
            self._logFile.close()
            self._logFile = open(self._logFileName,"a")
            if self._samples > 0:
                self.finiteTemperatureLog()
            else:
                self.continuousTemperatureLog()
            self._logFile.close()
            self.beeCon.sendCmd("M300\n")
            self.beeCon.sendCmd("M300\n")

        #########################
        #    Print Log
        #########################
        elif self._logJog == 'PrintLog':
            self._logFile = open(self._logFileName,'w')
            #logFile.write("Time,Current T,Target T,PWM Output,kp,ki,kd,pterm,iterm,dterm,Block T,Block Vent,Blower,Z\n")
            self._logFile.close()
            self._logFile = open(self._logFileName,"a")
            self.printingLog()
            self._logFile.close()

        #########################
        #    Printer Status Log
        #########################
        elif self._logJog == 'StatusLog':
            self._logFile = open(self._logFileName,'w')
            #logFile.write("Time,Current T,Target T,PWM Output,kp,ki,kd,pterm,iterm,dterm,Block T,Block Vent,Blower,Z\n")
            self._logFile.close()
            self._logFile = open(self._logFileName,"a")
            if self._samples > 0:
                self.finiteStatusLog()
            else:
                self.continuousStatusLog()
            self._logFile.close()


        logger.info('Exiting log thread')

        return


    # *************************************************************************
    #                        stop Method
    # *************************************************************************
    def stop(self):

        self._stopLog = True

        logger.info('Cancelling log thread')

        return

    # *************************************************************************
    #                        show Method
    # *************************************************************************
    def show(self):

        self._hideLog = False

        return

    # *************************************************************************
    #                        hide Method
    # *************************************************************************
    def hide(self):

        self._hideLog = True

        return

    # *************************************************************************
    #                        finiteTemperatureLog Method
    # *************************************************************************
    def finiteTemperatureLog(self):


        logger.info("Starting loging temperatures {} samples to {} at {} records per second".format(self._samples,self._logFileName,self._freq))

        self._t = 0
        for i in range(0,self._samples):
            reply = self.beeCon.sendCmd("M105\n")
            parsedLine = parsers.parseTemperatureReply(reply,self._printer)
            if parsedLine is not None:
                self._logFile.write("{},{}".format(self._t, parsedLine))
                if not self._hideLog:
                    logger.info("{}/{} {}".format(i,self._samples,parsedLine))

            if self._stopLog:
                break
            time.sleep(self._freq)
            self._t += self._freq


        return

    # *************************************************************************
    #                        finiteStatusLog Method
    # *************************************************************************
    def finiteStatusLog(self):


        logger.info("Starting loging Status {} samples to {} at {} records per second".format(self._samples,self._logFileName,self._freq))

        self._t = 0
        for i in range(0,self._samples):
            reply = self.beeCon.sendCmd("M1029\n")
            parsedLine = parsers.parseLogReply(reply,self._printer)
            if parsedLine is not None:
                self._logFile.write("{},{}".format(self._t, parsedLine))
                if not self._hideLog:
                    logger.info("{}/{} {}".format(i,self._samples,parsedLine))

            if self._stopLog:
                break
            time.sleep(self._freq)
            self._t += self._freq


        return

    # *************************************************************************
    #                        continuousStatusLog Method
    # *************************************************************************
    def continuousStatusLog(self):


        logger.info("Starting loging Status to {} at {} records per second".format(self._logFileName,self._freq))

        self._t = 0
        while not self._stopLog:
            reply = self.beeCon.sendCmd("M1029\n")
            parsedLine = parsers.parseLogReply(reply,self._printer)
            if parsedLine is not None:
                self._logFile.write("{},{}".format(self._t, parsedLine))
                if not self._hideLog:
                    logger.info(parsedLine)

            time.sleep(self._freq)
            self._t += self._freq


        return

    # *************************************************************************
    #                        continuousTemperatureLog Method
    # *************************************************************************
    def continuousTemperatureLog(self):


        logger.info("Starting loging temperatures to {} at {} records per second".format(self._logFileName,self._freq))

        self._t = 0
        while not self._stopLog:
            reply = self.beeCon.sendCmd("M105\n")
            parsedLine = parsers.parseTemperatureReply(reply,self._printer)
            if parsedLine is not None:
                i = i + 1
                self._logFile.write("{},{}".format(self._t, parsedLine))
                if not self._hideLog:
                    logger.info(parsedLine)

            time.sleep(self._freq)
            self._t += self._freq


        return

    # *************************************************************************
    #                        printingLog Method
    # *************************************************************************
    def printingLog(self):

        beeCmd = self.beeCon.getCommandIntf()

        while beeCmd.getStatus() is None:
            logger.info("Waiting for print to start")
            time.sleep(self._freq)

        logger.info("Starting loging temperatures during print to {} at {} records per second".format(self._logFileName,self._freq))

        self._stopLog = False

        self._t = 0
        i = 0
        while not self._stopLog:
            st = beeCmd.getStatus()
            if st is not None:
                if 'SD_Print' not in st:
                    self._stopLog = True
            reply = beeCmd.sendCmd("M1029\n")

            parsedLine = parsers.parseLogReply(reply)
            if parsedLine is not None:
                i = i + 1
                self._logFile.write("{},{}".format(self._t,parsedLine))
                if not self._hideLog:
                    logger.info("{}: {}".format(i,parsedLine))

            time.sleep(self._freq)
            self._t += self._freq

        return

