#!/usr/bin/env python

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
import logging

__all__ = ["commands", "connection", "transferThread", "printStatusThread", "logThread","parsers"]

# Logger configuration
logger = logging.getLogger('beecom')
logger.setLevel(logging.INFO)

# create file handler which logs even debug messages
# fh = logging.FileHandler('bee_console.log')
# fh.setLevel(logging.INFO)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# create formatter and add it to the handlers
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# fh.setFormatter(formatter)

# add the handlers to logger
logger.addHandler(ch)
# logger.addHandler(fh)
