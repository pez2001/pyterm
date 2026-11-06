#!/usr/bin/env python3
"""Launcher: python pixelterm.py [options]   (see --help)"""
import sys

from pixelterm.__main__ import main

if __name__ == '__main__':
    sys.exit(main() or 0)
