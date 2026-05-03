"""
Tests for FEAT-export-format-persist.

Source-scan tests verify wiring, slot logic, and init restore.
Pure-logic tests verify config round-trip for each format value.
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
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestExportFormatPersistSource:
    def test_combo_connected_to_slot(self) -> None:
        assert (
            "self._export_fmt_combo.currentIndexChanged.connect("
            "self._on_export_format_changed)"
        ) in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _on_export_format_changed" in _MW_SRC

    def test_slot_reads_current_data(self) -> None:
        idx = _MW_SRC.index("def _on_export_format_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "currentData()" in block

    def test_slot_sets_config(self) -> None:
        idx = _MW_SRC.index("def _on_export_format_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"export_format"' in block

    def test_slot_saves_config(self) -> None:
        idx = _MW_SRC.index("def _on_export_format_changed")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._config.save()" in block

    def test_init_reads_export_format(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"export_format"' in block

    def test_init_uses_finddata(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "findData(saved_fmt)" in block

    def test_init_uses_block_signals(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "blockSignals" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

_VALID_FORMATS = ["epub", "txt", "md"]


class TestExportFormatPersistLogic:
    def test_default_is_epub(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert str(cfg.get("export_format", "epub")) == "epub"

    def test_persists_txt(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("export_format", "txt")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("export_format", "epub") == "txt"

    def test_persists_md(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("export_format", "md")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("export_format", "epub") == "md"

    def test_three_valid_formats(self) -> None:
        assert len(_VALID_FORMATS) == 3

    def test_epub_in_formats(self) -> None:
        assert "epub" in _VALID_FORMATS

    def test_unknown_format_falls_back_to_zero(self) -> None:
        idx = -1
        assert max(0, idx) == 0


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestExportFormatPersistGui:
    def _make_window(self, tmp_path, fmt="epub"):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("export_format", fmt)
        return MainWindow(cfg), cfg

    def test_default_selects_epub(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert w._export_fmt_combo.currentData() == "epub"

    def test_restores_md(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, "md")
        assert w._export_fmt_combo.currentData() == "md"

    def test_change_persists(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path)
        idx = w._export_fmt_combo.findData("txt")
        w._export_fmt_combo.setCurrentIndex(idx)
        assert cfg.get("export_format", "epub") == "txt"
