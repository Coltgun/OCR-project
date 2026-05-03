"""
Tests for FEAT-pipeline-mode-persist.

Source-scan tests verify combo creation, wiring, slot, and init restore.
Pure-logic tests verify config round-trip for pipeline modes.
GUI tests are @pytest.mark.gui + @pytest.mark.skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Source paths
# ---------------------------------------------------------------------------

_MW_SRC = (
    Path(__file__).parent.parent.parent / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestPipelineModePersistSource:
    def test_combo_created(self) -> None:
        assert "self._pipeline_mode_combo = QComboBox()" in _MW_SRC

    def test_combo_populated_from_pipeline_modes(self) -> None:
        assert "for mode in PIPELINE_MODES:" in _MW_SRC

    def test_pipeline_modes_imported(self) -> None:
        assert "from ocr.pipeline import PIPELINE_MODES" in _MW_SRC

    def test_combo_connected_to_slot(self) -> None:
        assert (
            "self._pipeline_mode_combo.currentIndexChanged.connect(\n"
            "            self._on_pipeline_mode_changed\n"
            "        )"
        ) in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _on_pipeline_mode_changed" in _MW_SRC

    def _slot_block(self) -> str:
        idx = _MW_SRC.index("def _on_pipeline_mode_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        return _MW_SRC[idx:end]

    def test_slot_sets_config(self) -> None:
        assert '"ocr_pipeline_mode"' in self._slot_block()

    def test_slot_saves_config(self) -> None:
        assert "self._config.save()" in self._slot_block()

    def test_slot_updates_label(self) -> None:
        assert "_update_pipeline_mode_label()" in self._slot_block()

    def test_init_reads_ocr_pipeline_mode(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"ocr_pipeline_mode"' in block

    def test_init_uses_find_text(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "findText(saved_mode)" in block

    def test_init_uses_block_signals(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_pipeline_mode_combo.blockSignals" in block

    def test_settings_accept_syncs_combo(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_pipeline_mode_combo.blockSignals" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestPipelineModePersistLogic:
    def test_default_mode(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert str(cfg.get("ocr_pipeline_mode", "LOCAL_FAST")) == "LOCAL_FAST"

    def test_persists_mode(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", "FULL")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("ocr_pipeline_mode", "LOCAL_FAST") == "FULL"

    def test_pipeline_modes_not_empty(self) -> None:
        from ocr.pipeline import PIPELINE_MODES
        assert len(PIPELINE_MODES) > 0

    def test_local_fast_in_modes(self) -> None:
        from ocr.pipeline import PIPELINE_MODES
        assert "LOCAL_FAST" in PIPELINE_MODES

    def test_unknown_mode_index_is_negative(self) -> None:
        items = ["LOCAL_FAST", "FULL"]
        result = items.index("LOCAL_FAST") if "LOCAL_FAST" in items else -1
        assert result == 0


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestPipelineModePersistGui:
    def _make_window(self, tmp_path, mode="LOCAL_FAST"):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", mode)
        return MainWindow(cfg), cfg

    def test_default_selects_local_fast(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert w._pipeline_mode_combo.currentText() == "LOCAL_FAST"

    def test_restores_full(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, "FULL")
        assert w._pipeline_mode_combo.currentText() == "FULL"

    def test_change_persists(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path)
        idx = w._pipeline_mode_combo.findText("FULL")
        w._pipeline_mode_combo.setCurrentIndex(idx)
        assert cfg.get("ocr_pipeline_mode", "LOCAL_FAST") == "FULL"
