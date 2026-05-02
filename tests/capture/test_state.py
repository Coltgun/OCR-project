"""Tests for AppState enum and StateMachine transitions."""

from __future__ import annotations

import pytest

from capture.state import AppState, StateMachine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sm() -> StateMachine:
    """Return a fresh StateMachine in IDLE state."""
    return StateMachine()


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_starts_idle(self) -> None:
        sm = make_sm()
        assert sm.state == AppState.IDLE

    def test_is_idle_true_at_start(self) -> None:
        sm = make_sm()
        assert sm.is_idle is True


# ---------------------------------------------------------------------------
# Valid transitions from IDLE
# ---------------------------------------------------------------------------

class TestFromIdle:
    def test_idle_to_selecting(self) -> None:
        sm = make_sm()
        assert sm.trigger("select_region") is True
        assert sm.state == AppState.SELECTING

    def test_idle_to_capturing(self) -> None:
        sm = make_sm()
        assert sm.trigger("capture") is True
        assert sm.state == AppState.CAPTURING

    def test_idle_to_ocr_running(self) -> None:
        sm = make_sm()
        assert sm.trigger("run_ocr") is True
        assert sm.state == AppState.OCR_RUNNING

    def test_idle_to_exporting(self) -> None:
        sm = make_sm()
        assert sm.trigger("export") is True
        assert sm.state == AppState.EXPORTING


# ---------------------------------------------------------------------------
# Valid transitions back to IDLE
# ---------------------------------------------------------------------------

class TestReturnToIdle:
    def test_selecting_done(self) -> None:
        sm = make_sm()
        sm.trigger("select_region")
        assert sm.trigger("selection_done") is True
        assert sm.state == AppState.IDLE

    def test_selecting_cancel(self) -> None:
        sm = make_sm()
        sm.trigger("select_region")
        assert sm.trigger("cancel") is True
        assert sm.state == AppState.IDLE

    def test_capturing_done(self) -> None:
        sm = make_sm()
        sm.trigger("capture")
        assert sm.trigger("done") is True
        assert sm.state == AppState.IDLE

    def test_capturing_error(self) -> None:
        sm = make_sm()
        sm.trigger("capture")
        assert sm.trigger("error") is True
        assert sm.state == AppState.IDLE

    def test_ocr_running_done(self) -> None:
        sm = make_sm()
        sm.trigger("run_ocr")
        assert sm.trigger("done") is True
        assert sm.state == AppState.IDLE

    def test_ocr_running_cancel(self) -> None:
        sm = make_sm()
        sm.trigger("run_ocr")
        assert sm.trigger("cancel") is True
        assert sm.state == AppState.IDLE

    def test_ocr_running_error(self) -> None:
        sm = make_sm()
        sm.trigger("run_ocr")
        assert sm.trigger("error") is True
        assert sm.state == AppState.IDLE

    def test_exporting_done(self) -> None:
        sm = make_sm()
        sm.trigger("export")
        assert sm.trigger("done") is True
        assert sm.state == AppState.IDLE

    def test_exporting_error(self) -> None:
        sm = make_sm()
        sm.trigger("export")
        assert sm.trigger("error") is True
        assert sm.state == AppState.IDLE


# ---------------------------------------------------------------------------
# Invalid transitions silently ignored
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    def test_capture_while_capturing_ignored(self) -> None:
        sm = make_sm()
        sm.trigger("capture")
        result = sm.trigger("capture")
        assert result is False
        assert sm.state == AppState.CAPTURING

    def test_run_ocr_while_ocr_running_ignored(self) -> None:
        sm = make_sm()
        sm.trigger("run_ocr")
        result = sm.trigger("run_ocr")
        assert result is False
        assert sm.state == AppState.OCR_RUNNING

    def test_done_from_idle_ignored(self) -> None:
        sm = make_sm()
        result = sm.trigger("done")
        assert result is False
        assert sm.state == AppState.IDLE

    def test_unknown_action_ignored(self) -> None:
        sm = make_sm()
        result = sm.trigger("nonexistent_action")
        assert result is False
        assert sm.state == AppState.IDLE

    def test_export_while_selecting_ignored(self) -> None:
        sm = make_sm()
        sm.trigger("select_region")
        result = sm.trigger("export")
        assert result is False
        assert sm.state == AppState.SELECTING

    def test_capture_while_ocr_running_ignored(self) -> None:
        sm = make_sm()
        sm.trigger("run_ocr")
        result = sm.trigger("capture")
        assert result is False
        assert sm.state == AppState.OCR_RUNNING


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------

class TestSignalEmission:
    def test_state_changed_signal_emitted_on_valid_transition(self) -> None:
        sm = make_sm()
        received: list[tuple] = []
        sm.state_changed.connect(lambda old, new: received.append((old, new)))
        sm.trigger("capture")
        assert len(received) == 1
        assert received[0] == (AppState.IDLE, AppState.CAPTURING)

    def test_state_changed_not_emitted_on_invalid(self) -> None:
        sm = make_sm()
        received: list[tuple] = []
        sm.state_changed.connect(lambda old, new: received.append((old, new)))
        sm.trigger("done")  # invalid from IDLE
        assert len(received) == 0

    def test_signal_emitted_for_each_valid_step(self) -> None:
        sm = make_sm()
        received: list[tuple] = []
        sm.state_changed.connect(lambda old, new: received.append((old, new)))
        sm.trigger("capture")
        sm.trigger("done")
        assert len(received) == 2
        assert received[1] == (AppState.CAPTURING, AppState.IDLE)


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------

class TestConvenienceMethods:
    def test_select_region(self) -> None:
        sm = make_sm()
        assert sm.select_region() is True
        assert sm.state == AppState.SELECTING

    def test_capture_method(self) -> None:
        sm = make_sm()
        assert sm.capture() is True
        assert sm.state == AppState.CAPTURING

    def test_run_ocr_method(self) -> None:
        sm = make_sm()
        assert sm.run_ocr() is True
        assert sm.state == AppState.OCR_RUNNING

    def test_cancel_from_selecting(self) -> None:
        sm = make_sm()
        sm.select_region()
        assert sm.cancel() is True
        assert sm.is_idle

    def test_cancel_from_ocr_running(self) -> None:
        sm = make_sm()
        sm.run_ocr()
        assert sm.cancel() is True
        assert sm.is_idle

    def test_export_done(self) -> None:
        sm = make_sm()
        sm.export()
        assert sm.export_done() is True
        assert sm.is_idle
