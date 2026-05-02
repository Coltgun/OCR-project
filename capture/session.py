"""
CaptureSession — manages folder/file structure for one OCR capture session.

A session has:
  - A root directory:  <working_root_dir>/<session_name>/
  - Chapter folders:   <root>/1/, <root>/2/, ...  (plain integers, no zero-pad)
  - Image files:       <root>/<folder>/0001.png, 0002.png, ...  (4-digit zero-pad)

P0 CORRECTNESS: All folder and image ordering MUST use numeric sort.
Never use os.listdir() or sorted() without key=lambda x: int(x).
"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.file_utils import sort_image_paths_numeric

logger = logging.getLogger(__name__)


class SessionNameError(ValueError):
    """Raised when a session name fails validation (must be non-empty digits only)."""


class CaptureSession:
    """Manages folder/file layout for a single OCR capture session.

    Args:
        session_root: Fully resolved root directory for this session
                      (e.g. Path("D:/ocr_sessions/003")).
        resume:       If True and the directory already exists, resume by
                      scanning existing folder/image counts from disk.
                      If False, treat as a fresh session (directory may exist
                      but counters start from what is already on disk regardless).
    """

    def __init__(self, session_root: Path, resume: bool = True) -> None:
        self._root = session_root
        self._folder_counters: dict[int, int] = {}
        self._current_folder: int = 1

        if resume and self._root.exists():
            self._resume_from_disk()
        else:
            self._root.mkdir(parents=True, exist_ok=True)
            logger.info("CaptureSession: new session at '%s'.", self._root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def root(self) -> Path:
        """Absolute path to the session root directory."""
        return self._root

    @property
    def current_folder(self) -> int:
        """Current chapter folder number (1-based)."""
        return self._current_folder

    @property
    def folder_count(self) -> int:
        """Total number of chapter folders seen so far (including current)."""
        return self._current_folder

    def folder_path(self, folder_num: int) -> Path:
        """Return the Path for chapter folder *folder_num*.

        Creates the directory if it does not exist.
        """
        p = self._root / str(folder_num)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_next_image_path(self, folder_num: int | None = None) -> Path:
        """Return the Path where the next screenshot should be saved.

        Increments the counter for *folder_num*. If *folder_num* is None,
        uses the current active folder.

        Args:
            folder_num: Chapter folder number. Defaults to current_folder.

        Returns:
            Path like <session_root>/<folder_num>/0007.png
        """
        if folder_num is None:
            folder_num = self._current_folder

        if folder_num not in self._folder_counters:
            self._init_counter_from_disk(folder_num)

        self._folder_counters[folder_num] += 1
        filename = f"{self._folder_counters[folder_num]:04d}.png"
        folder = self.folder_path(folder_num)
        path = folder / filename
        logger.debug(
            "CaptureSession: next image path for folder %d: %s",
            folder_num,
            path,
        )
        return path

    def new_section(self) -> int:
        """Advance to the next chapter folder number and return it."""
        self._current_folder += 1
        logger.info(
            "CaptureSession: advanced to folder %d.", self._current_folder
        )
        return self._current_folder

    def image_count(self, folder_num: int) -> int:
        """Return the number of images saved so far in *folder_num*."""
        if folder_num not in self._folder_counters:
            self._init_counter_from_disk(folder_num)
        return self._folder_counters[folder_num]

    def total_images(self) -> int:
        """Return the total number of images across all chapter folders."""
        total = 0
        for fn in range(1, self._current_folder + 1):
            total += self.image_count(fn)
        return total

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_session_name(name: str) -> str:
        """Validate and return *name* if it is a non-empty digit-only string.

        Args:
            name: Candidate session name (e.g. "003", "42").

        Returns:
            The validated name (stripped of whitespace).

        Raises:
            SessionNameError: If the name is empty or contains non-digit chars.
        """
        name = name.strip()
        if not name:
            raise SessionNameError("Session name must not be empty.")
        if not name.isdigit():
            raise SessionNameError(
                f"Session name must contain digits only (got '{name}'). "
                "Acceptable: '001', '42'. Rejected: 'chapter1', 'test'."
            )
        return name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resume_from_disk(self) -> None:
        """Scan the session root to find the highest existing folder number
        and initialise all folder counters from the images already on disk."""
        numeric_folders: list[int] = []
        for item in self._root.iterdir():
            if item.is_dir():
                try:
                    numeric_folders.append(int(item.name))
                except ValueError:
                    pass

        if numeric_folders:
            self._current_folder = max(numeric_folders)
            for fn in numeric_folders:
                self._init_counter_from_disk(fn)
            logger.info(
                "CaptureSession: resumed at '%s' — %d folder(s), current=%d.",
                self._root,
                len(numeric_folders),
                self._current_folder,
            )
        else:
            logger.info(
                "CaptureSession: resume requested but no numeric folders found at '%s'. "
                "Starting fresh.",
                self._root,
            )

    def _init_counter_from_disk(self, folder_num: int) -> None:
        """Scan folder *folder_num* and set its counter to the highest existing image number."""
        folder = self._root / str(folder_num)
        if not folder.is_dir():
            self._folder_counters[folder_num] = 0
            return

        png_files = [p for p in folder.iterdir() if p.suffix.lower() == ".png"]
        if png_files:
            try:
                sorted_files = sort_image_paths_numeric(png_files)
                self._folder_counters[folder_num] = int(sorted_files[-1].stem)
            except ValueError:
                self._folder_counters[folder_num] = len(png_files)
        else:
            self._folder_counters[folder_num] = 0
