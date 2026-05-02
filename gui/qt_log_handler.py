"""
QtLogHandler — bridges Python logging to a Qt signal.

Usage:
    handler = QtLogHandler()
    handler.emitter.message_logged.connect(my_text_edit.append)
    logging.getLogger().addHandler(handler)

The handler is thread-safe: the signal is emitted from whatever thread calls
logging.  Qt's queued connection guarantees that the slot is executed on the
main thread, so no manual locking is required.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class _LogEmitter(QObject):
    """Minimal QObject that carries the message_logged signal."""

    message_logged = Signal(str)


class QtLogHandler(logging.Handler):
    """A logging.Handler that forwards formatted records via a Qt signal.

    Attributes:
        emitter: The QObject whose ``message_logged(str)`` signal is emitted
                 for every log record.
    """

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self.emitter = _LogEmitter()

    def emit(self, record: logging.LogRecord) -> None:
        """Format *record* and emit it via the signal."""
        try:
            msg = self.format(record)
            self.emitter.message_logged.emit(msg)
        except Exception:  # pragma: no cover — handler errors must not crash the app
            self.handleError(record)
