"""
AboutDialog — Help > About dialog for the Simplified Chinese OCR app.

Displays application version, runtime versions (Python, PySide6), and a
GitHub link. No external dependencies beyond PySide6.
"""

from __future__ import annotations

import sys

from PySide6 import __version__ as _pyside6_version
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

APP_NAME = "Simplified Chinese OCR"
APP_VERSION = "0.1.0-dev"
GITHUB_URL = "https://github.com/Coltgun/OCR-project"


class AboutDialog(QDialog):
    """Modal About dialog showing version and attribution information.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(360)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 16)

        title = QLabel(f"<h2>{APP_NAME}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel(f"<b>Version:</b> {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        runtime_label = QLabel(
            f"<b>Python:</b> {py_ver} &nbsp;|&nbsp; <b>PySide6:</b> {_pyside6_version}"
        )
        runtime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(runtime_label)

        link_label = QLabel(
            f'<a href="{GITHUB_URL}">{GITHUB_URL}</a>'
        )
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
