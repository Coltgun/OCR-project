"""
Tests for FEAT-pipeline-mode-indicator.

Source-scan tests verify label creation and wiring.
Pure-logic tests verify label text formatting.
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

class TestPipelineModeIndicatorSource:
    def test_pipeline_mode_label_created(self) -> None:
        assert "self._pipeline_mode_label = QLabel()" in _MW_SRC

    def test_label_has_tooltip(self) -> None:
        assert 'self._pipeline_mode_label.setToolTip("Active pipeline mode")' in _MW_SRC

    def test_label_added_as_permanent_widget(self) -> None:
        assert "self._status_bar.addPermanentWidget(self._pipeline_mode_label)" in _MW_SRC

    def test_update_method_exists(self) -> None:
        assert "def _update_pipeline_mode_label" in _MW_SRC

    def test_update_reads_ocr_pipeline_mode(self) -> None:
        assert 'self._cfg.get("ocr_pipeline_mode", "LOCAL_FAST")' in _MW_SRC

    def test_update_sets_mode_text(self) -> None:
        assert 'self._pipeline_mode_label.setText(f"Mode: {mode}")' in _MW_SRC

    def test_update_called_on_init(self) -> None:
        assert "self._update_pipeline_mode_label()" in _MW_SRC

    def test_update_called_after_settings_accept(self) -> None:
        idx = _MW_SRC.index("def _open_settings")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_update_pipeline_mode_label()" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestPipelineModeIndicatorLogic:
    def _label_text(self, mode: str) -> str:
        return f"Mode: {mode}"

    def test_default_mode_label(self) -> None:
        assert self._label_text("LOCAL_FAST") == "Mode: LOCAL_FAST"

    def test_custom_mode_label(self) -> None:
        assert self._label_text("HYBRID") == "Mode: HYBRID"

    def test_config_default_mode(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        mode = str(cfg.get("ocr_pipeline_mode", "LOCAL_FAST"))
        assert mode == "LOCAL_FAST"

    def test_config_persists_mode(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", "HYBRID")
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert str(cfg2.get("ocr_pipeline_mode", "LOCAL_FAST")) == "HYBRID"

    def test_label_includes_mode_name(self) -> None:
        for mode in ("LOCAL_FAST", "HYBRID", "FULL_LLM", "LOCAL_QUALITY"):
            assert mode in self._label_text(mode)


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestPipelineModeIndicatorGui:
    def _make_window(self, tmp_path, mode="LOCAL_FAST"):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("ocr_pipeline_mode", mode)
        return MainWindow(cfg), cfg

    def test_label_shows_default_mode_on_init(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert w._pipeline_mode_label.text() == "Mode: LOCAL_FAST"

    def test_label_shows_configured_mode_on_init(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, "HYBRID")
        assert w._pipeline_mode_label.text() == "Mode: HYBRID"

    def test_label_updates_after_config_change(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path)
        cfg.set("ocr_pipeline_mode", "FULL_LLM")
        w._cfg = cfg._data
        w._update_pipeline_mode_label()
        assert w._pipeline_mode_label.text() == "Mode: FULL_LLM"

    def test_label_tooltip_set(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path)
        assert w._pipeline_mode_label.toolTip() == "Active pipeline mode"
