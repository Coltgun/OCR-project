"""
conftest.py — pytest session-wide configuration.

PySide6 version note:
    PySide6 6.8.x and conda-forge cv2 are mutually incompatible in the same
    process on Windows (both load Qt DLLs that conflict).
    PySide6 6.11.x resolves the conflict — keep it pinned to >=6.11.
    See docs/KNOWN_ISSUES.md for details.

Custom markers:
    gui  — tests that require a live QApplication.  Skipped in the default
           headless run; run with: pytest -m gui tests/gui/
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "gui: mark test as requiring a live QApplication (skipped in headless mode)",
    )
