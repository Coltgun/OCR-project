"""Tests for CaptureSession — folder/file management and counter logic."""

from __future__ import annotations

import pytest
from pathlib import Path

from capture.session import CaptureSession, SessionNameError


# ---------------------------------------------------------------------------
# SessionNameError validation
# ---------------------------------------------------------------------------

class TestValidateSessionName:
    def test_valid_plain_digits(self) -> None:
        assert CaptureSession.validate_session_name("42") == "42"

    def test_valid_zero_padded(self) -> None:
        assert CaptureSession.validate_session_name("003") == "003"

    def test_strips_whitespace(self) -> None:
        assert CaptureSession.validate_session_name("  7  ") == "7"

    def test_empty_raises(self) -> None:
        with pytest.raises(SessionNameError, match="empty"):
            CaptureSession.validate_session_name("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(SessionNameError, match="empty"):
            CaptureSession.validate_session_name("   ")

    def test_alpha_raises(self) -> None:
        with pytest.raises(SessionNameError, match="digits only"):
            CaptureSession.validate_session_name("chapter1")

    def test_text_raises(self) -> None:
        with pytest.raises(SessionNameError, match="digits only"):
            CaptureSession.validate_session_name("test")

    def test_mixed_raises(self) -> None:
        with pytest.raises(SessionNameError, match="digits only"):
            CaptureSession.validate_session_name("001a")


# ---------------------------------------------------------------------------
# Fresh session (no disk files)
# ---------------------------------------------------------------------------

class TestFreshSession:
    def test_root_created(self, tmp_path: Path) -> None:
        root = tmp_path / "001"
        CaptureSession(root)
        assert root.is_dir()

    def test_initial_folder_is_1(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        assert s.current_folder == 1

    def test_get_next_image_path_first_call(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        p = s.get_next_image_path()
        assert p.name == "0001.png"
        assert p.parent == s.folder_path(1)

    def test_get_next_image_path_increments(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        paths = [s.get_next_image_path() for _ in range(5)]
        names = [p.name for p in paths]
        assert names == ["0001.png", "0002.png", "0003.png", "0004.png", "0005.png"]

    def test_get_next_image_path_explicit_folder(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        p = s.get_next_image_path(folder_num=3)
        assert p.parent.name == "3"
        assert p.name == "0001.png"

    def test_new_section_advances_folder(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        assert s.new_section() == 2
        assert s.current_folder == 2

    def test_new_section_multiple(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        for expected in range(2, 6):
            assert s.new_section() == expected

    def test_independent_counters_per_folder(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        s.get_next_image_path(1)
        s.get_next_image_path(1)
        s.get_next_image_path(2)
        assert s.image_count(1) == 2
        assert s.image_count(2) == 1

    def test_folder_path_creates_directory(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        p = s.folder_path(5)
        assert p.is_dir()
        assert p.name == "5"

    def test_total_images_empty(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        assert s.total_images() == 0

    def test_total_images_counts_across_folders(self, tmp_path: Path) -> None:
        s = CaptureSession(tmp_path / "001")
        s.get_next_image_path(1)
        s.get_next_image_path(1)
        s.new_section()
        s.get_next_image_path(2)
        assert s.total_images() == 3


# ---------------------------------------------------------------------------
# Resume from disk
# ---------------------------------------------------------------------------

class TestResumeFromDisk:
    def _make_session_on_disk(self, root: Path) -> None:
        """Create a session directory with some pre-existing images."""
        for folder_num, img_count in [(1, 3), (2, 5)]:
            folder = root / str(folder_num)
            folder.mkdir(parents=True)
            for i in range(1, img_count + 1):
                (folder / f"{i:04d}.png").touch()

    def test_resume_detects_current_folder(self, tmp_path: Path) -> None:
        root = tmp_path / "session"
        self._make_session_on_disk(root)
        s = CaptureSession(root, resume=True)
        assert s.current_folder == 2

    def test_resume_continues_image_count(self, tmp_path: Path) -> None:
        root = tmp_path / "session"
        self._make_session_on_disk(root)
        s = CaptureSession(root, resume=True)
        p = s.get_next_image_path(2)
        assert p.name == "0006.png"

    def test_resume_folder_1_continues(self, tmp_path: Path) -> None:
        root = tmp_path / "session"
        self._make_session_on_disk(root)
        s = CaptureSession(root, resume=True)
        p = s.get_next_image_path(1)
        assert p.name == "0004.png"

    def test_resume_empty_session_starts_at_folder_1(self, tmp_path: Path) -> None:
        root = tmp_path / "session"
        root.mkdir()
        s = CaptureSession(root, resume=True)
        assert s.current_folder == 1

    def test_resume_numeric_sort_not_lexicographic(self, tmp_path: Path) -> None:
        """P0: Resuming with folders 1-11 must set current_folder=11, not 9."""
        root = tmp_path / "session"
        for fn in range(1, 12):
            folder = root / str(fn)
            folder.mkdir(parents=True)
            (folder / "0001.png").touch()
        s = CaptureSession(root, resume=True)
        assert s.current_folder == 11, (
            f"Expected current_folder=11 (numeric max), got {s.current_folder}. "
            "This indicates a lexicographic sort bug."
        )

    def test_resume_image_counter_numeric_sort(self, tmp_path: Path) -> None:
        """P0: Images 1-11 in a folder must resume at counter=11, not 9."""
        root = tmp_path / "session"
        folder = root / "1"
        folder.mkdir(parents=True)
        for i in range(1, 12):
            (folder / f"{i:04d}.png").touch()
        s = CaptureSession(root, resume=True)
        p = s.get_next_image_path(1)
        assert p.name == "0012.png", (
            f"Expected 0012.png, got {p.name}. Likely lexicographic sort bug."
        )


# ---------------------------------------------------------------------------
# folder_path naming convention
# ---------------------------------------------------------------------------

class TestFolderNaming:
    def test_folder_name_is_plain_integer(self, tmp_path: Path) -> None:
        """Folder names must be plain integers, no zero-padding."""
        s = CaptureSession(tmp_path / "s")
        for n in range(1, 15):
            p = s.folder_path(n)
            assert p.name == str(n), f"Expected '{n}', got '{p.name}' (zero-padded?)"

    def test_image_name_is_four_digit_zero_padded(self, tmp_path: Path) -> None:
        """Image names must be exactly 4-digit zero-padded."""
        s = CaptureSession(tmp_path / "s")
        p = s.get_next_image_path(1)
        assert p.name == "0001.png"
        assert len(p.stem) == 4
