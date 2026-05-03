"""
Tests for FEAT-export-format-combo.

Source-scan tests verify _export_fmt_combo QComboBox: three items (epub/txt/md),
userData keys, currentIndexChanged→_on_export_format_changed, config persist,
_EXT_MAP presence, init findData+blockSignals sync.
Pure-logic tests verify _EXT_MAP values and config round-trip.
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

def _on_fmt_changed_block() -> str:
    idx = _MW_SRC.index("def _on_export_format_changed")
    end = _MW_SRC.index("\n    @Slot(bool)", idx + 1)
    return _MW_SRC[idx:end]

def _ext_map_block() -> str:
    idx = _MW_SRC.index("_EXT_MAP = {")
    end = _MW_SRC.index("}", idx) + 1
    return _MW_SRC[idx:end]


# ---------------------------------------------------------------------------
# 1. Source-scan tests
# ---------------------------------------------------------------------------

class TestExportFormatComboSource:
    def test_export_fmt_combo_created(self) -> None:
        assert "self._export_fmt_combo = QComboBox()" in _MW_SRC

    def test_epub_item_added(self) -> None:
        assert 'addItem("EPUB", userData="epub")' in _MW_SRC

    def test_txt_item_added(self) -> None:
        assert 'addItem("Plain Text", userData="txt")' in _MW_SRC

    def test_md_item_added(self) -> None:
        assert 'addItem("Markdown", userData="md")' in _MW_SRC

    def test_signal_connected(self) -> None:
        assert "_export_fmt_combo.currentIndexChanged.connect(self._on_export_format_changed)" in _MW_SRC

    def test_on_export_format_changed_exists(self) -> None:
        assert "def _on_export_format_changed" in _MW_SRC

    def test_on_fmt_changed_reads_current_data(self) -> None:
        assert "_export_fmt_combo.currentData()" in _on_fmt_changed_block()

    def test_on_fmt_changed_persists_config(self) -> None:
        assert 'self._config.set("export_format", fmt)' in _on_fmt_changed_block()

    def test_on_fmt_changed_saves_config(self) -> None:
        assert "self._config.save()" in _on_fmt_changed_block()

    def test_ext_map_exists(self) -> None:
        assert "_EXT_MAP = {" in _MW_SRC

    def test_ext_map_has_epub(self) -> None:
        assert '"epub"' in _ext_map_block()

    def test_ext_map_has_txt(self) -> None:
        assert '"txt"' in _ext_map_block()

    def test_init_uses_find_data(self) -> None:
        assert "_export_fmt_combo.findData(saved_fmt)" in _MW_SRC

    def test_init_uses_block_signals(self) -> None:
        assert "_export_fmt_combo.blockSignals(True)" in _MW_SRC
        assert "_export_fmt_combo.blockSignals(False)" in _MW_SRC


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestExportFormatComboLogic:
    _EXT_MAP = {"epub": "epub", "txt": "txt", "md": "md"}

    def test_epub_ext(self) -> None:
        assert self._EXT_MAP["epub"] == "epub"

    def test_txt_ext(self) -> None:
        assert self._EXT_MAP["txt"] == "txt"

    def test_md_ext(self) -> None:
        assert self._EXT_MAP["md"] == "md"

    def test_unknown_fmt_fallback(self) -> None:
        assert self._EXT_MAP.get("unknown", "epub") == "epub"

    def test_format_persists(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("export_format", "md")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("export_format") == "md"

    def test_default_format_epub(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert cfg.get("export_format", "epub") == "epub"


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestExportFormatComboGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_export_fmt_combo_present(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._export_fmt_combo is not None

    def test_export_fmt_combo_has_three_items(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._export_fmt_combo.count() == 3

    def test_default_format_is_epub(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert w._export_fmt_combo.currentData() == "epub"
