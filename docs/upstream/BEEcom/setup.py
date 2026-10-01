#!/usr/bin/env python
# coding=utf-8

# Requirements for the application
INSTALL_REQUIRES = ["pyusb"]

from distutils.core import setup

setup(name='beecom',
      version='0.3.35',
      description='BVC Printer Python driver',
      long_description=open("README.md").read(),
      author="BVC Electronic Systems",
      author_email="support@beeverycreative.com",
      license="AGPLv3",
      url='https://github.com/beeverycreative/BEEcom',
      packages=['beedriver'],
      # py_modules=['beedriver.connection', 'beedriver.commands', 'beedriver.transferThread', 'beedriver.printStatusThread']
      )
