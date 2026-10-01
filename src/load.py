#!/usr/bin/env python3
"""Compatibility entrypoint; implementation is in bee_cli.py."""
import sys
from bee_cli import main

if __name__ == "__main__":
    sys.exit(main(['load'] + sys.argv[1:]))
