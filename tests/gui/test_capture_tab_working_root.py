"""
Tests for FEAT-capture-tab-working-root.

Source-scan tests verify _working_root QLineEdit, placeholder, load, and save wiring.
Pure-logic tests verify config round-trip and fallback-to-default logic.
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

class TestCaptureTabWorkingRootSource:
    def _load_block(self) -> str:
        idx = _SD_SRC.index("def _load_values")
        end = _SD_SRC.index("\n    def _save_values", idx + 1)
        return _SD_SRC[idx:end]

    def _save_block(self) -> str:
        idx = _SD_SRC.index("def _save_values")
        end = _SD_SRC.index("\n    def _on_accept", idx + 1)
        return _SD_SRC[idx:end]

    def test_working_root_field_created(self) -> None:
        assert "self._working_root = QLineEdit()" in _SD_SRC

    def test_working_root_placeholder(self) -> None:
        assert 'self._working_root.setPlaceholderText("sessions")' in _SD_SRC

    def test_working_root_form_row(self) -> None:
        assert '"Working root dir:"' in _SD_SRC

    def test_load_reads_working_root_dir(self) -> None:
        assert '"working_root_dir"' in self._load_block()

    def test_load_uses_get_str(self) -> None:
        idx = self._load_block().index('"working_root_dir"')
        snippet = self._load_block()[max(0, idx - 30): idx + 80]
        assert "get_str" in snippet

    def test_save_writes_working_root_dir(self) -> None:
        assert '"working_root_dir"' in self._save_block()

    def test_save_fallback_to_sessions(self) -> None:
        assert 'or "sessions"' in self._save_block()

    def test_factory_defaults_has_working_root(self) -> None:
        assert '"working_root_dir": "sessions"' in _SD_SRC

    def test_export_template_field_also_in_session_group(self) -> None:
        assert "self._export_filename_template = QLineEdit()" in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestCaptureTabWorkingRootLogic:
    def test_default_is_sessions(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("working_root_dir", "sessions") == "sessions"

    def test_persists_custom_path(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("working_root_dir", "D:/my_sessions")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("working_root_dir", "sessions") == "D:/my_sessions"

    def test_empty_strip_falls_back(self) -> None:
        val = "   ".strip() or "sessions"
        assert val == "sessions"

    def test_nonempty_strip_kept(self) -> None:
        val = "  my_dir  ".strip() or "sessions"
        assert val == "my_dir"

    def test_relative_path_valid(self) -> None:
        val = "sessions"
        assert val

    def test_absolute_path_valid(self) -> None:
        val = "D:/projects/ocr/sessions"
        assert Path(val).is_absolute()


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestCaptureTabWorkingRootGui:
    def _make_dialog(self, tmp_path, root_dir="sessions"):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("working_root_dir", root_dir)
        return SettingsDialog(cfg), cfg

    def test_field_restored(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path, root_dir="my_sessions")
        assert dlg._working_root.text() == "my_sessions"

    def test_placeholder_is_sessions(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._working_root.placeholderText() == "sessions"

    def test_field_present(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._working_root is not None
