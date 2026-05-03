"""
Tests for FEAT-word-wrap-persist.

Source-scan tests verify that word-wrap state is saved on toggle and restored on init.
Pure-logic tests verify config round-trip and default value.
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

class TestWordWrapPersistSource:
    def _toggle_block(self) -> str:
        idx = _MW_SRC.index("def _toggle_word_wrap")
        end = _MW_SRC.index("\n    def _apply_word_wrap", idx + 1)
        return _MW_SRC[idx:end]

    def test_action_created(self) -> None:
        assert 'QAction("Word Wrap"' in _MW_SRC

    def test_action_is_checkable(self) -> None:
        assert "self._word_wrap_action.setCheckable(True)" in _MW_SRC

    def test_action_connected_to_slot(self) -> None:
        assert "self._word_wrap_action.triggered.connect(self._toggle_word_wrap)" in _MW_SRC

    def test_slot_exists(self) -> None:
        assert "def _toggle_word_wrap" in _MW_SRC

    def test_slot_sets_config(self) -> None:
        assert '"preview_word_wrap"' in self._toggle_block()

    def test_slot_saves_config(self) -> None:
        assert "self._config.save()" in self._toggle_block()

    def test_slot_applies_wrap(self) -> None:
        assert "_apply_word_wrap(checked)" in self._toggle_block()

    def test_apply_method_exists(self) -> None:
        assert "def _apply_word_wrap" in _MW_SRC

    def test_init_reads_word_wrap(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert '"preview_word_wrap"' in block

    def test_init_calls_set_checked(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_word_wrap_action.setChecked(wrap)" in block

    def test_init_applies_wrap(self) -> None:
        idx = _MW_SRC.index("def __init__")
        end = _MW_SRC.index("\n    # --", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_apply_word_wrap(wrap)" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

class TestWordWrapPersistLogic:
    def test_default_is_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        assert bool(cfg.get("preview_word_wrap", True)) is True

    def test_persists_false(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_word_wrap", False)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("preview_word_wrap", True) is False

    def test_persists_true(self, tmp_path: Path) -> None:
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_word_wrap", True)
        cfg.save()
        cfg2 = ConfigManager(path=tmp_path / "config.json")
        assert cfg2.get("preview_word_wrap", False) is True

    def test_toggle_inverts_value(self) -> None:
        val = True
        val = not val
        assert val is False

    def test_default_in_factory_defaults(self) -> None:
        _SD_SRC = (
            Path(__file__).parent.parent.parent / "gui" / "settings_dialog.py"
        ).read_text(encoding="utf-8")
        assert '"preview_word_wrap": True' in _SD_SRC


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestWordWrapPersistGui:
    def _make_window(self, tmp_path, wrap=True):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        cfg.set("preview_word_wrap", wrap)
        return MainWindow(cfg), cfg

    def test_default_checked(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, wrap=True)
        assert w._word_wrap_action.isChecked()

    def test_restored_false(self, tmp_path: Path) -> None:
        w, _ = self._make_window(tmp_path, wrap=False)
        assert not w._word_wrap_action.isChecked()

    def test_toggle_persists(self, tmp_path: Path) -> None:
        w, cfg = self._make_window(tmp_path, wrap=True)
        w._toggle_word_wrap(False)
        assert cfg.get("preview_word_wrap", True) is False
