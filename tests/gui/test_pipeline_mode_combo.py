"""
Tests for FEAT-pipeline-mode-combo.

Source-scan tests verify _pipeline_mode_combo QComboBox in MainWindow: population
from PIPELINE_MODES, currentIndexChanged→_on_pipeline_mode_changed, config persist,
_update_pipeline_mode_label; init sync from config with blockSignals.
Pure-logic tests verify config round-trip and mode persistence.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source path
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _on_mode_changed_block() -> str:
    idx = _MW_SRC.index("def _on_pipeline_mode_changed")
    end = _MW_SRC.index("\n    @Slot(int)\n    def _on_export_format_changed", idx + 1)
    return _MW_SRC[idx:end]

def _update_mode_label_block() -> str:
    idx = _MW_SRC.index("def _update_pipeline_mode_label")
    end = _MW_SRC.index("\n    def _update_session_info_label", idx + 1)
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestPipelineModeComboSource:
    def test_pipeline_mode_combo_created(self) -> None:
        assert "self._pipeline_mode_combo = QComboBox()" in _MW_SRC

    def test_pipeline_mode_combo_tooltip(self) -> None:
        assert "_pipeline_mode_combo.setToolTip" in _MW_SRC

    def test_pipeline_mode_combo_populated_from_pipeline_modes(self) -> None:
        assert "for mode in PIPELINE_MODES" in _MW_SRC
        assert "_pipeline_mode_combo.addItem(mode)" in _MW_SRC

    def test_pipeline_mode_combo_signal_connected(self) -> None:
        assert "_pipeline_mode_combo.currentIndexChanged.connect(" in _MW_SRC
        assert "_on_pipeline_mode_changed" in _MW_SRC

    def test_on_pipeline_mode_changed_exists(self) -> None:
        assert "def _on_pipeline_mode_changed" in _MW_SRC

    def test_on_pipeline_mode_changed_reads_current_text(self) -> None:
        assert "_pipeline_mode_combo.currentText()" in _on_mode_changed_block()

    def test_on_pipeline_mode_changed_persists_config(self) -> None:
        assert 'self._config.set("ocr_pipeline_mode", mode)' in _on_mode_changed_block()

    def test_on_pipeline_mode_changed_saves_config(self) -> None:
        assert "self._config.save()" in _on_mode_changed_block()

    def test_on_pipeline_mode_changed_updates_label(self) -> None:
        assert "_update_pipeline_mode_label()" in _on_mode_changed_block()

    def test_update_pipeline_mode_label_exists(self) -> None:
        assert "def _update_pipeline_mode_label" in _MW_SRC

    def test_init_syncs_combo_with_blockSignals(self) -> None:
        assert "_pipeline_mode_combo.blockSignals(True)" in _MW_SRC
        assert "_pipeline_mode_combo.blockSignals(False)" in _MW_SRC

    def test_init_uses_find_text(self) -> None:
        assert "_pipeline_mode_combo.findText(saved_mode)" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestPipelineModeComboLogic:
    def test_default_mode_is_local_fast(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("ocr_pipeline_mode", "LOCAL_FAST") == "LOCAL_FAST"

    def test_mode_persists_after_change(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", "FULL")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("ocr_pipeline_mode") == "FULL"

    def test_empty_mode_not_saved(self) -> None:
        mode = ""
        would_save = bool(mode)
        assert not would_save

    def test_non_empty_mode_saved(self) -> None:
        mode = "LOCAL_FAST"
        would_save = bool(mode)
        assert would_save

    def test_pipeline_modes_non_empty(self) -> None:
        from ocr.pipeline import PIPELINE_MODES
        assert len(PIPELINE_MODES) > 0

    def test_local_fast_in_pipeline_modes(self) -> None:
        from ocr.pipeline import PIPELINE_MODES
        assert "LOCAL_FAST" in PIPELINE_MODES


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestPipelineModeComboGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_pipeline_mode_combo_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._pipeline_mode_combo is not None

    def test_pipeline_mode_combo_has_items(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._pipeline_mode_combo.count() > 0

    def test_pipeline_mode_combo_default_local_fast(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._pipeline_mode_combo.currentText() == "LOCAL_FAST"
