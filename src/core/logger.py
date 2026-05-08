"""
Centralized logging configuration for the telemarketing system.

Usage:
    from core.logger import get_logger
    logger = get_logger(__name__)
    logger.debug("...")
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


_log_initialized = False


def setup_logging(level: int = logging.DEBUG, log_dir: str = None):
    """Configure root logger with console + file handlers."""
    global _log_initialized
    if _log_initialized:
        return

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers
    root.handlers.clear()

    # Formatter with ms precision
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "data" / "logs"
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    _log_initialized = True
    logging.getLogger(__name__).info("Logging initialized (level=%s)", logging.getLevelName(level))


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name."""
    if not _log_initialized:
        setup_logging()
    return logging.getLogger(name)
