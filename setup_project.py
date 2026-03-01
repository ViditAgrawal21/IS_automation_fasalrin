"""
Project setup helper for IS Claim Automation.
Creates required directories and installs Playwright browsers.
Run once after cloning: python setup_project.py
"""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DIRECTORIES = [
    "profiles",
    "logs",
]


def setup():
    print("Setting up IS Claim Automation...")

    # Create directories
    for d in DIRECTORIES:
        path = os.path.join(PROJECT_ROOT, d)
        os.makedirs(path, exist_ok=True)
        print(f"  Directory: {d}/")

    # Install Python dependencies
    print("\nInstalling Python dependencies...")
    req_file = os.path.join(PROJECT_ROOT, "requirements.txt")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])

    # Install Playwright browsers
    print("\nInstalling Playwright Chromium browser...")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

    print("\nSetup complete! Run: python main.py")


if __name__ == "__main__":
    setup()
