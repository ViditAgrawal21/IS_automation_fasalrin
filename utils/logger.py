"""
Logging utility for the IS Claim Automation system.
Logs to both file and provides callback support for UI integration.
"""

import logging
import os
from datetime import datetime
from path_helper import get_app_dir

LOG_DIR = os.path.join(get_app_dir(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Create a unique log file per session
_log_filename = os.path.join(LOG_DIR, f"claim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Configure file handler
_file_handler = logging.FileHandler(_log_filename, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

# Configure logger
logger = logging.getLogger("ISClaimAutomation")
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)


def log_info(message: str):
    """Log an informational message."""
    logger.info(message)


def log_error(message: str):
    """Log an error message."""
    logger.error(message)


def log_warning(message: str):
    """Log a warning message."""
    logger.warning(message)


def log_debug(message: str):
    """Log a debug message."""
    logger.debug(message)


def get_log_file_path() -> str:
    """Return the current log file path."""
    return _log_filename
