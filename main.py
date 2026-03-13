"""
IS Claim Automation — Entry Point.

Launches the Tkinter dashboard for the IS Claim Automation system.
Run this file: python main.py
"""

import sys
import os
import multiprocessing

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.dashboard import launch

if __name__ == "__main__":
    multiprocessing.freeze_support()
    launch()
