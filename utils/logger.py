"""
utils/logger.py

Phase 6 - Logging

Enterprise-style logging: every action (auth attempts, errors, warnings,
endpoint tests, exports, program exit) goes to logs/app.log with
rotation so the file doesn't grow unbounded, plus a lighter console
stream for interactive use.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"


def setup_logger(name: str = "btp_toolkit", level: str = "INFO") -> logging.Logger:
    """Configure and return the toolkit's shared logger.

    Safe to call multiple times — handlers are only attached once.
    """
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # keep the CLI screen clean; details go to the file
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger


# Module-level logger for simple `from utils.logger import logger` imports,
# matching the existing usage in app.py. Level is upgraded once AppConfig
# loads, via reconfigure().
logger = setup_logger()


def reconfigure(level: str) -> None:
    """Update the shared logger's level once config.py has resolved it."""
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
