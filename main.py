#!/usr/bin/env python3
"""
Root entry point to run the interactive Duffel API CLI menu.
Usage:
    python main.py
"""

import os
import sys

# Ensure src is on Python module path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from duffel.cli import DuffelCLI

if __name__ == "__main__":
    cli = DuffelCLI()
    cli.run()
