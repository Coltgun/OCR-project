"""
Tests for FEAT-keyboard-shortcuts-display.

Verifies that the Hotkeys tab in SettingsDialog uses a QTableWidget with
3 columns (Action, Default, Override) instead of plain QFormLayout rows.

Source-scan tests only (no Qt import needed), plus @gui+@skip GUI tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent
_SETTINGS_SRC = (_ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source-scan tests
# ---------------------------------------------------------------------------

class TestHotkeysTableSource:
    def test_qtablewidget_imported(self) -> None:
        assert "QTableWidget" in _SETTINGS_SRC

    def test_qtablewidgetitem_imported(self) -> None:
        assert "QTableWidgetItem" in _SETTINGS_SRC

    def test_qheaderview_imported(self) -> None:
        assert "QHeaderView" in _SETTINGS_SRC

    def test_hotkeys_table_created(self) -> None:
        assert "self._hotkeys_table = QTableWidget" in _SETTINGS_SRC

    def test_table_has_three_columns(self) -> None:
        assert "QTableWidget(len(self._ACTION_LABELS), 3)" in _SETTINGS_SRC

    def test_column_headers_set(self) -> None:
        assert '["Action", "Default", "Override"]' in _SETTINGS_SRC

    def test_action_column_stretches(self) -> None:
        assert "ResizeMode.Stretch" in _SETTINGS_SRC

    def test_default_column_resize_to_contents(self) -> None:
        assert "ResizeMode.ResizeToContents" in _SETTINGS_SRC

    def test_vertical_header_hidden(self) -> None:
        assert "verticalHeader().setVisible(False)" in _SETTINGS_SRC

    def test_no_selection_mode(self) -> None:
        assert "SelectionMode.NoSelection" in _SETTINGS_SRC

    def test_edit_triggers_disabled(self) -> None:
        assert "NoEditTriggers" in _SETTINGS_SRC

    def test_default_key_shown_uppercase(self) -> None:
        assert ".upper()" in _SETTINGS_SRC

    def test_override_edit_set_as_cell_widget(self) -> None:
        assert "setCellWidget(row, 2, edit)" in _SETTINGS_SRC

    def test_action_item_not_editable(self) -> None:
        assert "ItemIsEnabled" in _SETTINGS_SRC

    def test_default_item_centered(self) -> None:
        assert "AlignCenter" in _SETTINGS_SRC

    def test_override_edit_has_placeholder(self) -> None:
        assert "edit.setPlaceholderText" in _SETTINGS_SRC

    def test_hotkey_edits_keyed_by_action(self) -> None:
        assert "self._hotkey_edits[action] = edit" in _SETTINGS_SRC

    def test_action_labels_class_attribute(self) -> None:
        assert "_ACTION_LABELS: dict[str, str]" in _SETTINGS_SRC

    def test_valid_keys_note_still_present(self) -> None:
        assert "Valid keys" in _SETTINGS_SRC

    def test_override_blank_hint_present(self) -> None:
        assert "Leave Override blank" in _SETTINGS_SRC


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestHotkeysTableGui:
    def _make_dialog(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return SettingsDialog(cfg), cfg

    def test_table_has_six_rows(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._hotkeys_table.rowCount() == 6

    def test_table_has_three_columns(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._hotkeys_table.columnCount() == 3

    def test_action_column_not_empty(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._hotkeys_table.item(0, 0).text() != ""

    def test_default_column_is_uppercase(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        for row in range(dlg._hotkeys_table.rowCount()):
            text = dlg._hotkeys_table.item(row, 1).text()
            assert text == text.upper()

    def test_override_column_has_line_edits(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QLineEdit
        dlg, _ = self._make_dialog(tmp_path)
        for row in range(dlg._hotkeys_table.rowCount()):
            widget = dlg._hotkeys_table.cellWidget(row, 2)
            assert isinstance(widget, QLineEdit)

    def test_hotkey_edits_dict_uses_table_edits(self, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QLineEdit
        dlg, _ = self._make_dialog(tmp_path)
        for action, edit in dlg._hotkey_edits.items():
            assert isinstance(edit, QLineEdit)

    def test_save_reads_from_table_edits(self, tmp_path: Path) -> None:
        dlg, cfg = self._make_dialog(tmp_path)
        dlg._hotkey_edits["capture"].setText("f1")
        dlg._save_values()
        assert cfg.get("keybindings", {}).get("capture") == "f1"

    def test_load_populates_table_edits(self, tmp_path: Path) -> None:
        from gui.settings_dialog import SettingsDialog
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("keybindings", {"capture": "f2"})
        dlg = SettingsDialog(cfg)
        assert dlg._hotkey_edits["capture"].text() == "f2"
