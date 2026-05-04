"""
main.py — application entry point.

Usage:
    Double-click run.bat  (recommended)
    Or: conda activate chinese-ocr && python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.session_dialog import SessionDialog
from utils.config_manager import ConfigManager
from utils.logging_config import setup_logging


def main() -> int:
    """Initialise and run the application. Returns the exit code."""
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("Simplified Chinese OCR")
    app.setOrganizationName("OCRProject")

    config_manager = ConfigManager()

    window = MainWindow(config_manager)
    window.show()

    window._start_new_session()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
