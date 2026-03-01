"""
Build script for IS Claim Automation — creates a standalone .exe using PyInstaller.

Usage:
    python build.py

Output:
    dist/ISClaimAutomation/ISClaimAutomation.exe
"""

import subprocess
import sys
import os
import shutil

APP_NAME = "ISClaimAutomation"
MAIN_SCRIPT = "main.py"
ICON = None  # Set to "icon.ico" if you have one


def build():
    print("=" * 50)
    print("Building IS Claim Automation .exe")
    print("=" * 50)

    # Ensure PyInstaller is installed
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Find Playwright browser path
    pw_browsers = None
    try:
        from playwright._impl._driver import compute_driver_executable
        driver_exec = compute_driver_executable()
        pw_dir = os.path.dirname(driver_exec)
        # Check common Playwright browser locations
        local_browsers = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ms-playwright")
        if os.path.exists(local_browsers):
            pw_browsers = local_browsers
            print(f"Playwright browsers: {pw_browsers}")
    except Exception as e:
        print(f"Warning: Could not locate Playwright browsers: {e}")

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",           # No console window
        "--noconfirm",          # Overwrite previous build
        "--clean",
        # Add all source directories as data
        "--add-data", f"utils{os.pathsep}utils",
        "--add-data", f"automation{os.pathsep}automation",
        "--add-data", f"excel_engine{os.pathsep}excel_engine",
        "--add-data", f"ui{os.pathsep}ui",
        # Hidden imports
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--hidden-import", "openpyxl",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.fernet",
    ]

    if ICON and os.path.exists(ICON):
        cmd.extend(["--icon", ICON])

    cmd.append(MAIN_SCRIPT)

    print(f"\nRunning: {' '.join(cmd)}\n")
    subprocess.check_call(cmd)

    # Copy Playwright browsers to dist
    dist_dir = os.path.join("dist", APP_NAME)
    if pw_browsers and os.path.exists(pw_browsers):
        dest = os.path.join(dist_dir, "browsers")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        print(f"\nCopying Playwright browsers to {dest}...")
        shutil.copytree(pw_browsers, dest)

    # Create required directories in dist
    for d in ["profiles", "logs"]:
        os.makedirs(os.path.join(dist_dir, d), exist_ok=True)

    print("\n" + "=" * 50)
    print(f"BUILD COMPLETE!")
    print(f"Executable: dist/{APP_NAME}/{APP_NAME}.exe")
    print("=" * 50)


if __name__ == "__main__":
    build()
