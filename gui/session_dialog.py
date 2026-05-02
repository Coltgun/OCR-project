"""
SessionDialog — asks the user for a working folder name at startup.

Validates: non-empty digits only (e.g. "001", "42"). Rejects "chapter1", "".
If the folder already exists, prompts resume vs overwrite.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from capture.session import CaptureSession, SessionNameError
from utils.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class SessionDialog(QDialog):
    """Modal dialog for starting or resuming a capture session.

    After exec() returns QDialog.Accepted, read:
        dialog.session_root  — resolved Path for the session
        dialog.resume        — True = resume existing, False = new/overwrite
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config_manager
        self.session_root: Path | None = None
        self.resume: bool = True

        self.setWindowTitle("New Session")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("<b>Start a Capture Session</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Enter a session folder name (digits only, e.g. 001, 42).\n"
            "Images will be saved under: "
            f"<i>{self._working_root()}/&lt;name&gt;/</i>"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        name_row = QHBoxLayout()
        name_label = QLabel("Folder name:")
        name_label.setFixedWidth(90)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. 001")
        self._name_edit.setMaxLength(20)
        name_row.addWidget(name_label)
        name_row.addWidget(self._name_edit)
        layout.addLayout(name_row)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #cc0000;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._name_edit.returnPressed.connect(self._on_accept)
        self._name_edit.setFocus()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        """Validate input and accept or show an error."""
        raw = self._name_edit.text()
        try:
            name = CaptureSession.validate_session_name(raw)
        except SessionNameError as exc:
            self._show_error(str(exc))
            return

        root = Path(self._working_root()) / name

        if root.exists() and any(root.iterdir()):
            choice = QMessageBox.question(
                self,
                "Folder Exists",
                f"<b>{root}</b> already exists.<br><br>"
                "Resume (append to existing images) or Overwrite (delete and restart)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Yes:
                self.resume = True
            else:
                self.resume = False
                self._delete_session_root(root)
        else:
            self.resume = False

        self.session_root = root
        self._hide_error()
        self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _working_root(self) -> str:
        val = self._config.get("working_root_dir")
        return str(val) if val is not None else "sessions"

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _hide_error(self) -> None:
        self._error_label.setVisible(False)

    @staticmethod
    def _delete_session_root(root: Path) -> None:
        """Recursively delete *root* to allow a clean overwrite."""
        import shutil
        try:
            shutil.rmtree(root)
            logger.info("SessionDialog: deleted existing session root '%s'.", root)
        except OSError as exc:
            logger.error(
                "SessionDialog: failed to delete '%s': %s", root, exc
            )
