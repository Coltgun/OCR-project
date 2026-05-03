"""
Tests for FEAT-pipeline-tab-ui.

Source-scan tests verify _mode_combo QComboBox, PIPELINE_MODES population,
and load/save wiring.
Pure-logic tests verify PIPELINE_MODES contents and config round-trip.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager
from ocr.pipeline import PIPELINE_MODES


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_SD_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestPipelineTabUiSource:
    def _build_block(self) -> str:
        idx = _SD_SRC.index("def _build_pipeline_tab")
        end = _SD_SRC.index("\n    # --- API", idx + 1)
        return _SD_SRC[idx:end]

    def _load_block(self) -> str:
        idx = _SD_SRC.index("def _load_values")
        end = _SD_SRC.index("\n    def _save_values", idx + 1)
        return _SD_SRC[idx:end]

    def _save_block(self) -> str:
        idx = _SD_SRC.index("def _save_values")
        end = _SD_SRC.index("\n    def _on_accept", idx + 1)
        return _SD_SRC[idx:end]

    def test_pipeline_tab_method_exists(self) -> None:
        assert "def _build_pipeline_tab" in _SD_SRC

    def test_pipeline_modes_imported(self) -> None:
        assert "PIPELINE_MODES" in _SD_SRC

    def test_mode_combo_created(self) -> None:
        assert "self._mode_combo = QComboBox()" in _SD_SRC

    def test_combo_populated_from_pipeline_modes(self) -> None:
        assert "for mode in PIPELINE_MODES" in self._build_block()

    def test_mode_group_exists(self) -> None:
        assert '"Active mode:"' in _SD_SRC

    def test_load_reads_pipeline_mode(self) -> None:
        assert '"ocr_pipeline_mode"' in self._load_block()

    def test_load_uses_find_text(self) -> None:
        assert "_mode_combo.findText" in self._load_block()

    def test_save_writes_pipeline_mode(self) -> None:
        assert '"ocr_pipeline_mode"' in self._save_block()

    def test_save_uses_current_text(self) -> None:
        assert "_mode_combo.currentText()" in self._save_block()

    def test_factory_defaults_has_pipeline_mode(self) -> None:
        assert '"ocr_pipeline_mode"' in _SD_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestPipelineTabUiLogic:
    def test_pipeline_modes_nonempty(self) -> None:
        assert len(PIPELINE_MODES) > 0

    def test_local_fast_in_modes(self) -> None:
        assert "LOCAL_FAST" in PIPELINE_MODES

    def test_all_modes_are_strings(self) -> None:
        assert all(isinstance(m, str) for m in PIPELINE_MODES)

    def test_default_mode_persists(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", "LOCAL_FAST")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("ocr_pipeline_mode", "") == "LOCAL_FAST"

    def test_factory_default_is_local_fast(self) -> None:
        assert '"ocr_pipeline_mode": "LOCAL_FAST"' in _SD_SRC

    def test_mode_count_matches_pipeline_modes(self) -> None:
        assert len(PIPELINE_MODES) >= 3


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestPipelineTabUiGui:
    def _make_dialog(self, tmp_path, mode="LOCAL_FAST"):
        from PySide6.QtWidgets import QApplication
        from gui.settings_dialog import SettingsDialog
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", mode)
        return SettingsDialog(cfg), cfg

    def test_combo_populated(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._mode_combo.count() == len(PIPELINE_MODES)

    def test_mode_restored(self, tmp_path: Path) -> None:
        first_mode = list(PIPELINE_MODES.keys())[0]
        dlg, _ = self._make_dialog(tmp_path, mode=first_mode)
        assert dlg._mode_combo.currentText() == first_mode

    def test_combo_present(self, tmp_path: Path) -> None:
        dlg, _ = self._make_dialog(tmp_path)
        assert dlg._mode_combo is not None
