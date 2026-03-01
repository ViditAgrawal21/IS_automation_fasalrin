"""
Path helper for IS Claim Automation.

Provides a single function to get the application base directory.
Works correctly in both:
  - Development mode (running from source via `python main.py`)
  - Frozen mode (running as a PyInstaller .exe)

All modules that need to read/write files (profiles, logs, secret.key)
should use get_app_dir() instead of __file__-based paths.
"""

import sys
import os


def get_app_dir() -> str:
    """
    Return the application base directory.

    - Frozen (.exe): directory containing the executable
    - Source: the is_automation/ project root
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))
