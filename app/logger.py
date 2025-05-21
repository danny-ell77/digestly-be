"""
Logger module for the application.
"""

import logging
import os
import sys
from typing import Optional

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Create logger
logger = logging.getLogger("digestly")
logger.setLevel(getattr(logging, LOG_LEVEL))

# Add console handler if not already added
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console_handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: The name of the logger. If None, returns the root logger.

    Returns:
        A logger instance.
    """
    if name:
        return logging.getLogger(f"digestly.{name}")
    return logger
