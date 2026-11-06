#!/usr/bin/env python3
"""Launcher: python pyvterm.py [options]   (see --help)"""
import sys

from pyvterm.__main__ import main

if __name__ == '__main__':
    sys.exit(main() or 0)
