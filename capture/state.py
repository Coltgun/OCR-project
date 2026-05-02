"""
AppState and StateMachine — enforce valid state transitions for the OCR app.

State diagram:
    IDLE
     ├──[select_region]──→ SELECTING
     │                         └──[selection_done / cancel]──→ IDLE
     ├──[capture]──→ CAPTURING
     │                   └──[done / error]──→ IDLE
     ├──[run_ocr]──→ OCR_RUNNING
     │                   └──[done / cancel / error]──→ IDLE
     └──[export]──→ EXPORTING
                        └──[done / error]──→ IDLE

Invalid transitions are silently ignored (hotkeys pressed at wrong time).
Valid transitions emit the state_changed signal for the GUI to react to.
"""

from __future__ import annotations

import logging
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class AppState(Enum):
    """All possible application states."""

    IDLE = auto()
    SELECTING = auto()
    CAPTURING = auto()
    OCR_RUNNING = auto()
    EXPORTING = auto()


# Valid transitions: {from_state: {trigger: to_state}}
_TRANSITIONS: dict[AppState, dict[str, AppState]] = {
    AppState.IDLE: {
        "select_region": AppState.SELECTING,
        "capture": AppState.CAPTURING,
        "run_ocr": AppState.OCR_RUNNING,
        "export": AppState.EXPORTING,
    },
    AppState.SELECTING: {
        "selection_done": AppState.IDLE,
        "cancel": AppState.IDLE,
    },
    AppState.CAPTURING: {
        "done": AppState.IDLE,
        "error": AppState.IDLE,
    },
    AppState.OCR_RUNNING: {
        "done": AppState.IDLE,
        "cancel": AppState.IDLE,
        "error": AppState.IDLE,
    },
    AppState.EXPORTING: {
        "done": AppState.IDLE,
        "error": AppState.IDLE,
    },
}


class StateMachine(QObject):
    """Enforces valid state transitions and emits signals on change.

    Signals:
        state_changed(AppState, AppState):  Emitted on every valid transition
                                            with (old_state, new_state).
    """

    state_changed = Signal(object, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state: AppState = AppState.IDLE

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> AppState:
        """Current application state."""
        return self._state

    @property
    def is_idle(self) -> bool:
        """True when the state machine is in IDLE."""
        return self._state == AppState.IDLE

    # ------------------------------------------------------------------
    # Transition triggers
    # ------------------------------------------------------------------

    def trigger(self, action: str) -> bool:
        """Attempt the transition for *action* from the current state.

        Invalid transitions are silently ignored.

        Args:
            action: Trigger name, e.g. "capture", "done", "cancel".

        Returns:
            True if the transition occurred, False if it was ignored.
        """
        valid = _TRANSITIONS.get(self._state, {})
        if action not in valid:
            logger.debug(
                "StateMachine: ignored '%s' in state %s (no valid transition).",
                action,
                self._state.name,
            )
            return False

        old = self._state
        self._state = valid[action]
        logger.info(
            "StateMachine: %s -[%s]-> %s",
            old.name,
            action,
            self._state.name,
        )
        self.state_changed.emit(old, self._state)
        return True

    # ------------------------------------------------------------------
    # Convenience trigger methods (for direct connection to Qt slots)
    # ------------------------------------------------------------------

    def select_region(self) -> bool:
        """Trigger the select_region action (IDLE → SELECTING)."""
        return self.trigger("select_region")

    def selection_done(self) -> bool:
        """Trigger the selection_done action (SELECTING → IDLE)."""
        return self.trigger("selection_done")

    def capture(self) -> bool:
        """Trigger the capture action (IDLE → CAPTURING)."""
        return self.trigger("capture")

    def capture_done(self) -> bool:
        """Trigger the done action from CAPTURING (CAPTURING → IDLE)."""
        return self.trigger("done")

    def capture_error(self) -> bool:
        """Trigger an error from CAPTURING (CAPTURING → IDLE)."""
        return self.trigger("error")

    def run_ocr(self) -> bool:
        """Trigger the run_ocr action (IDLE → OCR_RUNNING)."""
        return self.trigger("run_ocr")

    def ocr_done(self) -> bool:
        """Trigger the done action from OCR_RUNNING (OCR_RUNNING → IDLE)."""
        return self.trigger("done")

    def cancel(self) -> bool:
        """Trigger the cancel action from the current state."""
        return self.trigger("cancel")

    def export(self) -> bool:
        """Trigger the export action (IDLE → EXPORTING)."""
        return self.trigger("export")

    def export_done(self) -> bool:
        """Trigger the done action from EXPORTING (EXPORTING → IDLE)."""
        return self.trigger("done")
