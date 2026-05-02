"""
logging_config — structured logging setup for the OCR application.

Sets up a rotating file handler and a console handler. Call setup_logging()
once at application startup (in main.py) before any other imports.

Usage:
    from utils.logging_config import setup_logging
    setup_logging()

All modules should use:
    import logging
    logger = logging.getLogger(__name__)
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"
_DEFAULT_LOG_FILE = _DEFAULT_LOG_DIR / "ocr_app.log"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_level: int = logging.INFO,
    log_file: Path = _DEFAULT_LOG_FILE,
    console: bool = True,
) -> None:
    """Configure root logger with rotating file handler and optional console handler.

    Args:
        log_level: Logging level for both handlers (default: INFO).
        log_file:  Path to the rotating log file.
        console:   Whether to also log to stderr (default: True).
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if root_logger.handlers:
        root_logger.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    logging.getLogger(__name__).debug("Logging initialised (level=%s).", logging.getLevelName(log_level))
