"""
Browser management with session persistence for IS Claim Automation.
Saves/loads browser storage state to avoid repeated captcha entry.
"""

import sys
import os
import subprocess
import shutil

# When running as a frozen .exe, check for bundled browsers first,
# then fall back to system-installed browsers in %LOCALAPPDATA%\ms-playwright
if getattr(sys, "frozen", False):
    _bundled = os.path.join(os.path.dirname(sys.executable), "browsers")
    _system = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    if os.path.isdir(_bundled):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _bundled
    elif os.path.isdir(_system):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _system

from playwright.sync_api import sync_playwright
from path_helper import get_app_dir

SESSION_DIR = os.path.join(get_app_dir(), "profiles")


def _get_session_path(profile_name: str) -> str:
    """Get the session storage file path for a profile."""
    return os.path.join(SESSION_DIR, f"{profile_name}_session.json")


def _install_playwright_chromium():
    """Install Playwright chromium — works for both script and frozen exe."""
    if getattr(sys, "frozen", False):
        # In frozen exe, find the real Python or use playwright CLI directly
        # Try to find playwright in PATH or use the bundled driver
        from playwright._impl._driver import compute_driver_executable
        driver = compute_driver_executable()
        if isinstance(driver, tuple):
            driver = driver[0]
        subprocess.check_call([str(driver), "install", "chromium"])
    else:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


def start_browser(profile_name: str = None, headless: bool = False):
    """
    Launch a Chromium browser with optional session persistence.

    Args:
        profile_name: If provided, attempts to load saved session cookies.
        headless: If False (default), shows the browser window.

    Returns:
        tuple: (playwright_instance, browser, context, page)
    """
    p = sync_playwright().start()
    try:
        browser = p.chromium.launch(
            headless=headless,
            args=["--start-maximized"]
        )
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            _install_playwright_chromium()
            browser = p.chromium.launch(
                headless=headless,
                args=["--start-maximized"]
            )
        else:
            raise

    # Try to load existing session
    session_path = _get_session_path(profile_name) if profile_name else None

    if session_path and os.path.exists(session_path):
        try:
            context = browser.new_context(
                storage_state=session_path,
                no_viewport=True
            )
        except Exception:
            context = browser.new_context(no_viewport=True)
    else:
        context = browser.new_context(no_viewport=True)

    # Set default timeouts — aggressive for speed
    context.set_default_timeout(15000)
    context.set_default_navigation_timeout(30000)

    page = context.new_page()
    return p, browser, context, page


def save_session(context, profile_name: str):
    """Save browser cookies/storage state for future sessions."""
    try:
        session_path = _get_session_path(profile_name)
        os.makedirs(os.path.dirname(session_path), exist_ok=True)
        context.storage_state(path=session_path)
    except Exception:
        pass


def close_browser(p, browser):
    """Safely close browser and playwright."""
    try:
        browser.close()
    except Exception:
        pass
    try:
        p.stop()
    except Exception:
        pass


def take_screenshot(page, filename: str) -> str:
    """Take a screenshot and save it. Returns the file path."""
    screenshot_dir = os.path.join(get_app_dir(), "logs")
    os.makedirs(screenshot_dir, exist_ok=True)
    filepath = os.path.join(screenshot_dir, filename)
    try:
        page.screenshot(path=filepath, full_page=True)
    except Exception:
        pass
    return filepath
