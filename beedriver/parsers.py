#!/usr/bin/env python

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


# *************************************************************************
#                        parseLogReply Method
# *************************************************************************
def parseLogReply(replyLine,printer='BEETHEFIRST PLUS'):
    logLine = None

    if ('\n' in replyLine):
        replyLines = replyLine.split('ok Q:')

        re1 = '.*?'  # Non-greedy match on filler
        re2 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 1
        re3 = '.*?'  # Non-greedy match on filler
        re4 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 2
        re5 = '.*?'  # Non-greedy match on filler
        re6 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 3
        re7 = '.*?'  # Non-greedy match on filler
        re8 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 4
        re9 = '.*?'  # Non-greedy match on filler
        re10 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 5
        re11 = '.*?'  # Non-greedy match on filler
        re12 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 6
        re13 = '.*?'  # Non-greedy match on filler
        re14 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 7
        re15 = '.*?'  # Non-greedy match on filler
        re16 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 8
        re17 = '.*?'  # Non-greedy match on filler
        re18 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 9
        re19 = '.*?'  # Non-greedy match on filler
        re20 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 10
        re21 = '.*?'  # Non-greedy match on filler
        re22 = '(\\d+)'  # Integer Number 1
        if printer == 'BEETHEFIRST PLUS':
            re23 = '.*?'  # Non-greedy match on filler
            re24 = '(\\d+)'  # Integer Number 2
            re25 = '.*?'  # Non-greedy match on filler
            re26 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 11

            rg = re.compile(
                re1 + re2 + re3 + re4 + re5 + re6 + re7 + re8 + re9 + re10 + re11 + re12 + re13 + re14 + re15 + re16 + re17 + re18 + re19 + re20 + re21 + re22 + re23 + re24 + re25 + re26,
                re.IGNORECASE | re.DOTALL)
        elif printer == 'BEETHEFIRST':
            re23 = '.*?'  # Non-greedy match on filler
            re24 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 11

            rg = re.compile(
                re1 + re2 + re3 + re4 + re5 + re6 + re7 + re8 + re9 + re10 + re11 + re12 + re13 + re14 + re15 + re16 + re17 + re18 + re19 + re20 + re21 + re22 + re23 + re24,
                re.IGNORECASE | re.DOTALL)
        else:
            logger.info('Unknown Printer')

        m = rg.search(replyLines[0])
        # m = rg.search(reply)
        if m:
            float1 = m.group(1)
            float2 = m.group(2)
            float3 = m.group(3)
            float4 = m.group(4)
            float5 = m.group(5)
            float6 = m.group(6)
            float7 = m.group(7)
            float8 = m.group(8)
            float9 = m.group(9)
            float10 = m.group(10)
            int1 = m.group(11)
            if printer == 'BEETHEFIRST PLUS':
                int2 = m.group(12)
                float11 = m.group(13)
                logLine = "{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(float1, float2, float3, float4, float5,
                                                                            float6, float7, float8, float9, float10,
                                                                            int1, int2, float11)
            elif printer == 'BEETHEFIRST':
                float11 = m.group(12)
                logLine = "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(float1, float2, float3, float4, float5,
                                                                            float6, float7, float8, float9, float10,
                                                                            int1, float11)


    return logLine


# *************************************************************************
#                        parseTemperatureReply Method
# *************************************************************************
def parseTemperatureReply(replyLine):
    logLine = None
    # reply = reply.replace('\n','')
    if ('\n' in replyLine):
        # replyLines = reply.split('ok Q:')

        re1 = '(T)'  # Any Single Character 1
        re2 = '.*?'  # Non-greedy match on filler
        re3 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 1
        re4 = '.*?'  # Non-greedy match on filler
        re5 = '(B)'  # Any Single Character 2
        re6 = '.*?'  # Non-greedy match on filler
        re7 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 2
        re8 = '.*?'  # Non-greedy match on filler
        re9 = '(R)'  # Any Single Character 3
        re10 = '.*?'  # Non-greedy match on filler
        re11 = '([+-]?\\d*\\.\\d+)(?![-+0-9\\.])'  # Float 3

        # rg = re.compile(re1+re2+re3+re4+re5+re6+re7+re8+re9,re.IGNORECASE|re.DOTALL)
        rg = re.compile(re1 + re2 + re3 + re4 + re5 + re6 + re7 + re8 + re9 + re10 + re11, re.IGNORECASE | re.DOTALL)
        # m = rg.search(replyLines[0])
        m = rg.search(replyLine)
        if m:
            w1 = m.group(1)
            float1 = m.group(2)
            w2 = m.group(3)
            float2 = m.group(4)
            w3 = m.group(5)
            float3 = m.group(6)
            logLine = "{},{},{}\n".format(float1, float2, float3)

    return logLine
