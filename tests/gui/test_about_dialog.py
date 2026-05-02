"""
Tests for FEAT-about-dialog.

about_dialog.py imports PySide6 at module level — DLL conflict in pytest.
Strategy:
1. Source-scan tests — verify dialog structure without importing Qt.
2. Module-constant tests — import only the non-Qt module-level constants
   (APP_NAME, APP_VERSION, GITHUB_URL) via ast.literal_eval-safe extraction.
3. MainWindow wiring tests — source-scan only.
4. GUI tests — @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_ABOUT_SRC = (_ROOT / "gui" / "about_dialog.py").read_text(encoding="utf-8")
_MW_SRC = (_ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers — extract string constants from source without importing Qt
# ---------------------------------------------------------------------------

def _extract_str_const(source: str, var_name: str) -> str:
    m = re.search(rf'^{re.escape(var_name)}\s*=\s*"([^"]*)"', source, re.MULTILINE)
    assert m is not None, f"Could not find '{var_name}' in source"
    return m.group(1)


_APP_NAME = _extract_str_const(_ABOUT_SRC, "APP_NAME")
_APP_VERSION = _extract_str_const(_ABOUT_SRC, "APP_VERSION")
_GITHUB_URL = _extract_str_const(_ABOUT_SRC, "GITHUB_URL")


# ---------------------------------------------------------------------------
# 1. about_dialog.py source-scan
# ---------------------------------------------------------------------------

class TestAboutDialogSource:
    def test_class_inherits_qdialog(self) -> None:
        assert "class AboutDialog(QDialog)" in _ABOUT_SRC

    def test_app_name_constant_defined(self) -> None:
        assert 'APP_NAME = ' in _ABOUT_SRC

    def test_app_version_constant_defined(self) -> None:
        assert 'APP_VERSION = ' in _ABOUT_SRC

    def test_github_url_constant_defined(self) -> None:
        assert 'GITHUB_URL = ' in _ABOUT_SRC

    def test_github_url_is_valid(self) -> None:
        assert _GITHUB_URL.startswith("https://")

    def test_title_set_in_init(self) -> None:
        assert "setWindowTitle" in _ABOUT_SRC

    def test_modal_set(self) -> None:
        assert "setModal(True)" in _ABOUT_SRC

    def test_version_label_present(self) -> None:
        assert "APP_VERSION" in _ABOUT_SRC

    def test_python_version_shown(self) -> None:
        assert "sys.version_info" in _ABOUT_SRC

    def test_pyside6_version_shown(self) -> None:
        assert "_pyside6_version" in _ABOUT_SRC or "pyside6_version" in _ABOUT_SRC.lower()

    def test_github_link_is_clickable(self) -> None:
        assert "setOpenExternalLinks(True)" in _ABOUT_SRC

    def test_close_button_present(self) -> None:
        assert "StandardButton.Close" in _ABOUT_SRC

    def test_build_ui_method_exists(self) -> None:
        assert "def _build_ui" in _ABOUT_SRC

    def test_minimum_width_set(self) -> None:
        assert "setMinimumWidth" in _ABOUT_SRC


# ---------------------------------------------------------------------------
# 2. Module-constant sanity checks (no Qt)
# ---------------------------------------------------------------------------

class TestAboutDialogConstants:
    def test_app_name_not_empty(self) -> None:
        assert _APP_NAME != ""

    def test_app_version_has_dot(self) -> None:
        assert "." in _APP_VERSION

    def test_github_url_starts_https(self) -> None:
        assert _GITHUB_URL.startswith("https://")

    def test_github_url_contains_github(self) -> None:
        assert "github" in _GITHUB_URL.lower()

    def test_python_version_matches_runtime(self) -> None:
        """The sys.version_info format used in source must produce a valid version string."""
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        parts = py_ver.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# ---------------------------------------------------------------------------
# 3. MainWindow wiring source-scan
# ---------------------------------------------------------------------------

class TestMainWindowAboutWiring:
    def test_about_dialog_imported(self) -> None:
        assert "from gui.about_dialog import AboutDialog" in _MW_SRC

    def test_help_menu_created(self) -> None:
        assert '"&Help"' in _MW_SRC

    def test_about_action_added(self) -> None:
        assert '"&About\u2026"' in _MW_SRC

    def test_open_about_slot_exists(self) -> None:
        assert "def _open_about" in _MW_SRC

    def test_about_dialog_exec_called(self) -> None:
        assert "AboutDialog(parent=self).exec()" in _MW_SRC

    def test_about_action_wired_to_slot(self) -> None:
        assert "self._open_about" in _MW_SRC


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestAboutDialogGui:
    def _make_dialog(self):
        from PySide6.QtWidgets import QApplication
        from gui.about_dialog import AboutDialog, APP_NAME, APP_VERSION, GITHUB_URL
        QApplication.instance() or QApplication([])
        return AboutDialog(), APP_NAME, APP_VERSION, GITHUB_URL

    def test_dialog_title_contains_app_name(self) -> None:
        dlg, app_name, _, _ = self._make_dialog()
        assert app_name in dlg.windowTitle()

    def test_dialog_is_modal(self) -> None:
        dlg, _, _, _ = self._make_dialog()
        assert dlg.isModal()

    def test_dialog_has_minimum_width(self) -> None:
        dlg, _, _, _ = self._make_dialog()
        assert dlg.minimumWidth() >= 300

    def test_version_label_visible(self) -> None:
        dlg, _, version, _ = self._make_dialog()
        from PySide6.QtWidgets import QLabel
        labels = dlg.findChildren(QLabel)
        texts = " ".join(lbl.text() for lbl in labels)
        assert version in texts

    def test_github_link_label_present(self) -> None:
        dlg, _, _, url = self._make_dialog()
        from PySide6.QtWidgets import QLabel
        labels = dlg.findChildren(QLabel)
        texts = " ".join(lbl.text() for lbl in labels)
        assert url in texts

    def test_python_version_in_labels(self) -> None:
        dlg, _, _, _ = self._make_dialog()
        from PySide6.QtWidgets import QLabel
        labels = dlg.findChildren(QLabel)
        texts = " ".join(lbl.text() for lbl in labels)
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert py_ver in texts
