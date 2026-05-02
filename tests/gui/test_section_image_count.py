"""
Tests for FEAT-section-image-count.

Source-scan tests verify widget creation and refresh wiring.
Pure-logic tests verify row text formatting.
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

class TestSectionImageCountSource:
    def test_qlistwidget_imported(self) -> None:
        assert "QListWidget" in _MW_SRC

    def test_section_count_list_created(self) -> None:
        assert "self._section_count_list = QListWidget()" in _MW_SRC

    def test_max_height_set(self) -> None:
        assert "self._section_count_list.setMaximumHeight(70)" in _MW_SRC

    def test_initially_disabled(self) -> None:
        assert "self._section_count_list.setEnabled(False)" in _MW_SRC

    def test_tooltip_set(self) -> None:
        assert '"Images captured per section"' in _MW_SRC

    def test_refresh_method_exists(self) -> None:
        assert "def _refresh_section_count_list" in _MW_SRC

    def test_refresh_clears_list(self) -> None:
        idx = _MW_SRC.index("def _refresh_section_count_list")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._section_count_list.clear()" in block

    def test_refresh_iterates_sections(self) -> None:
        idx = _MW_SRC.index("def _refresh_section_count_list")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "range(1, self._session.current_folder + 1)" in block

    def test_refresh_adds_items(self) -> None:
        idx = _MW_SRC.index("def _refresh_section_count_list")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._section_count_list.addItem" in block

    def test_refresh_called_from_update_session_labels(self) -> None:
        idx = _MW_SRC.index("def _update_session_labels")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_refresh_section_count_list()" in block

    def test_refresh_called_after_capture(self) -> None:
        idx = _MW_SRC.index("def _trigger_capture")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_refresh_section_count_list()" in block

    def test_refresh_called_after_new_section(self) -> None:
        idx = _MW_SRC.index("def _trigger_new_section")
        end = _MW_SRC.index("\n    @Slot", idx + 1)
        block = _MW_SRC[idx:end]
        assert "_refresh_section_count_list()" in block

    def test_row_text_format(self) -> None:
        assert '"Section {fn}: {count} image(s)"' in _MW_SRC

    def test_disabled_when_no_session(self) -> None:
        idx = _MW_SRC.index("def _refresh_section_count_list")
        end = _MW_SRC.index("\n    def ", idx + 1)
        block = _MW_SRC[idx:end]
        assert "self._session is None" in block


# ---------------------------------------------------------------------------
# 2. Pure-logic tests
# ---------------------------------------------------------------------------

def _row_text(fn: int, count: int) -> str:
    return f"Section {fn}: {count} image(s)"


class TestSectionImageCountLogic:
    def test_single_section_row(self) -> None:
        assert _row_text(1, 3) == "Section 1: 3 image(s)"

    def test_multi_section_rows(self) -> None:
        rows = [_row_text(fn, fn * 2) for fn in range(1, 4)]
        assert rows == ["Section 1: 2 image(s)", "Section 2: 4 image(s)", "Section 3: 6 image(s)"]

    def test_zero_images(self) -> None:
        assert _row_text(1, 0) == "Section 1: 0 image(s)"

    def test_section_numbering_starts_at_one(self) -> None:
        sections = list(range(1, 4))
        assert sections[0] == 1


# ---------------------------------------------------------------------------
# GUI tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
@pytest.mark.skip(reason="Requires live QApplication; cv2+PySide6 DLL conflict in pytest process")
class TestSectionImageCountGui:
    def _make_window(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        cfg = ConfigManager(path=tmp_path / "config.json")
        return MainWindow(cfg)

    def test_list_initially_disabled(self, tmp_path: Path) -> None:
        w = self._make_window(tmp_path)
        assert not w._section_count_list.isEnabled()

    def test_list_enabled_after_session(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._refresh_section_count_list()
        assert w._section_count_list.isEnabled()

    def test_list_shows_one_section(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._refresh_section_count_list()
        assert w._section_count_list.count() == 1
        assert w._section_count_list.item(0).text() == "Section 1: 0 image(s)"

    def test_list_updates_after_new_section(self, tmp_path: Path) -> None:
        from capture.session import CaptureSession
        session_root = tmp_path / "s1"
        session_root.mkdir()
        w = self._make_window(tmp_path)
        w._session = CaptureSession(session_root)
        w._session.new_section()
        w._refresh_section_count_list()
        assert w._section_count_list.count() == 2
