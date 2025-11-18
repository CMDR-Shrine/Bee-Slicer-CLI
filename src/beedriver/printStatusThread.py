#!/usr/bin/env python

import threading
import time

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


class PrintStatusThread(threading.Thread):
    r"""
        StatusThread Class

        This class monitors the current status of a printing operation
    """

    # *************************************************************************
    #                        __init__ Method
    # *************************************************************************
    def __init__(self, connection, responseCallback):
        r"""
        __init__ Method

        Initializes this class

        """
        super(PrintStatusThread, self).__init__()
        self._responseCallback = responseCallback
        self._beeConn = connection
        self._commands = connection.getCommandIntf()
        self._active = True

        return

    def run(self):

        printVars = dict()
        while self._active:

            if self._beeConn.dummyPlugConnected():
                # Simulated print job progress
                printVars['Lines'] = 300
                if 'Executed Lines' not in printVars:
                    printVars['Executed Lines'] = 3
                else:
                    printVars['Executed Lines'] += 30
                printVars['Estimated Time'] = 7000
                if 'Elapsed Time' not in printVars:
                    printVars['Elapsed Time'] = 10
                else:
                    printVars['Elapsed Time'] += 30
            else:
                printVars = self._commands.getPrintVariables()

            if 'Lines' in printVars and 'Executed Lines' in printVars and printVars['Lines'] is not None and \
                    printVars['Executed Lines'] >= printVars['Lines']:
                # the print has finished
                self._responseCallback(printVars)
                return

            self._responseCallback(printVars)
            time.sleep(3)

    def stopPrintStatusMonitor(self):
        """
        Forces the Status thread monitor to stop
        :return:
        """
        self._active = False

    def isRunning(self):
        """
        Returns true if the monitor is still running or false if not
        :return:
        """
        return self.isAlive()
