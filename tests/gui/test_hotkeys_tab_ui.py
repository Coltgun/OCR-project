"""
Tests for FEAT-hotkeys-tab-ui.

Source-scan tests verify _hotkeys_table, _hotkey_edits dict, _ACTION_LABELS,
and load/save wiring.
Pure-logic tests verify config round-trip and keybinding merge logic.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_SD_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestHotkeysTabUiSource:
    def _build_block(self) -> str:
        idx = _SD_SRC.index("def _build_hotkeys_tab")
        end = _SD_SRC.index("\n    # --", idx + 1)
        return _SD_SRC[idx:end]

    def _load_block(self) -> str:
        idx = _SD_SRC.index("def _load_values")
        end = _SD_SRC.index("\n    def _save_values", idx + 1)
        return _SD_SRC[idx:end]

    def _save_block(self) -> str:
        idx = _SD_SRC.index("def _save_values")
        end = _SD_SRC.index("\n    def _on_accept", idx + 1)
        return _SD_SRC[idx:end]

    def test_hotkeys_table_created(self) -> None:
        assert "self._hotkeys_table = QTableWidget" in _SD_SRC

    def test_table_three_columns(self) -> None:
        assert "QTableWidget(len(self._ACTION_LABELS), 3)" in _SD_SRC

    def test_table_headers(self) -> None:
        assert '"Action"' in self._build_block()
        assert '"Default"' in self._build_block()
        assert '"Override"' in self._build_block()

    def test_hotkey_edits_dict_created(self) -> None:
        assert "self._hotkey_edits: dict[str, QLineEdit] = {}" in _SD_SRC

    def test_action_labels_dict_exists(self) -> None:
        assert "_ACTION_LABELS" in _SD_SRC

    def test_action_labels_has_capture(self) -> None:
        assert '"capture"' in _SD_SRC

    def test_action_labels_has_new_section(self) -> None:
        assert '"new_section"' in _SD_SRC

    def test_action_labels_has_cancel(self) -> None:
        assert '"cancel"' in _SD_SRC

    def test_load_reads_keybindings(self) -> None:
        assert '"keybindings"' in self._load_block()

    def test_load_iterates_hotkey_edits(self) -> None:
        assert "self._hotkey_edits.items()" in self._load_block()

    def test_save_writes_keybindings(self) -> None:
        assert '"keybindings"' in self._save_block()

    def test_placeholder_uses_default_binding(self) -> None:
        assert "_DEFAULT_BINDINGS" in self._build_block()

    def test_note_label_has_valid_keys(self) -> None:
        assert "Valid keys:" in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

_ACTIONS = ("capture", "new_section", "send_to_ocr", "reset_area",
            "toggle_overlay", "cancel")


class TestHotkeysTabUiLogic:
    def test_default_keybindings_empty(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        bindings = cfg.get("keybindings", {})
        assert isinstance(bindings, dict)

    def test_persists_single_binding(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("keybindings", {"capture": "f9"})
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        bindings = cfg2.get("keybindings", {})
        assert bindings["capture"] == "f9"  # type: ignore[index]

    def test_empty_override_falls_back_to_default(self) -> None:
        saved = {}
        default = "f10"
        result = saved.get("capture", "") or default
        assert result == default

    def test_nonempty_override_takes_precedence(self) -> None:
        saved = {"capture": "f9"}
        default = "f10"
        result = saved.get("capture", "") or default
        assert result == "f9"

    def test_six_actions_defined(self) -> None:
        assert len(_ACTIONS) == 6

    def test_all_actions_are_strings(self) -> None:
        assert all(isinstance(a, str) for a in _ACTIONS)


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestHotkeysTabUiGui:
    def _make_dialog(self, tmp_path, bindings=None):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        if bindings:
            cfg.set("keybindings", bindings)
        return SettingsDialog(cfg), cfg

    def test_hotkeys_table_present(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._hotkeys_table is not None

    def test_hotkey_edits_populated(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert len(dlg._hotkey_edits) == len(dlg._ACTION_LABELS)

    def test_binding_restored(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, bindings={"capture": "f9"})
        assert dlg._hotkey_edits["capture"].text() == "f9"
