"""
HotkeyListener — global system hotkeys via pynput, bridged to Qt via signals.

pynput runs in a daemon background thread. GUI methods must NEVER be called
directly from that thread. This module uses Qt signals to safely cross the
thread boundary: the listener emits Python signals that are connected to
Qt slots in the main thread.

Default keybindings (overridden by config["keybindings"]):
    F7  → toggle_overlay
    F8  → reset_area
    F9  → capture
    F10 → new_section
    F11 → send_to_ocr
    Esc → cancel
"""

from __future__ import annotations

import logging
from typing import Callable

from pynput import keyboard
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

_DEFAULT_BINDINGS: dict[str, str] = {
    "capture": "f9",
    "new_section": "f10",
    "send_to_ocr": "f11",
    "reset_area": "f8",
    "toggle_overlay": "f7",
    "cancel": "escape",
}

_PYNPUT_KEY_MAP: dict[str, keyboard.Key] = {
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
    "escape": keyboard.Key.esc,
    "esc": keyboard.Key.esc,
}


class HotkeyListener(QObject):
    """System-wide hotkey listener that emits Qt signals on key press.

    All signals are emitted from the pynput thread. Connect them to slots
    in the main thread — Qt's queued connection mechanism ensures thread safety.

    Signals:
        capture_pressed:        F9 (or configured key)
        new_section_pressed:    F10
        send_to_ocr_pressed:    F11
        reset_area_pressed:     F8
        toggle_overlay_pressed: F7
        cancel_pressed:         Escape
    """

    capture_pressed = Signal()
    new_section_pressed = Signal()
    send_to_ocr_pressed = Signal()
    reset_area_pressed = Signal()
    toggle_overlay_pressed = Signal()
    cancel_pressed = Signal()

    def __init__(
        self,
        config: dict | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._listener: keyboard.Listener | None = None
        self._key_to_signal: dict[keyboard.Key, Callable] = {}
        self._build_key_map(config or {})

    def _build_key_map(self, config: dict) -> None:
        """Build the mapping from pynput Key objects to signal emitters."""
        bindings_cfg: dict = config.get("keybindings", {})
        bindings = {**_DEFAULT_BINDINGS, **bindings_cfg}

        action_signals: dict[str, Callable] = {
            "capture": self.capture_pressed.emit,
            "new_section": self.new_section_pressed.emit,
            "send_to_ocr": self.send_to_ocr_pressed.emit,
            "reset_area": self.reset_area_pressed.emit,
            "toggle_overlay": self.toggle_overlay_pressed.emit,
            "cancel": self.cancel_pressed.emit,
        }

        self._key_to_signal = {}
        for action, key_str in bindings.items():
            pynput_key = _PYNPUT_KEY_MAP.get(key_str.lower())
            if pynput_key is None:
                logger.warning(
                    "HotkeyListener: unknown key '%s' for action '%s', skipping.",
                    key_str,
                    action,
                )
                continue
            if action not in action_signals:
                logger.warning(
                    "HotkeyListener: unknown action '%s', skipping.", action
                )
                continue
            self._key_to_signal[pynput_key] = action_signals[action]
            logger.debug(
                "HotkeyListener: bound %s → %s", key_str.upper(), action
            )

    def reload(self, config: dict) -> None:
        """Rebuild the key map from an updated config without restarting the thread.

        Safe to call from the main thread while the listener is running.

        Args:
            config: Updated full application config dict.
        """
        self._build_key_map(config)
        logger.info("HotkeyListener: key map reloaded.")

    def start(self) -> None:
        """Start the pynput listener daemon thread."""
        if self._listener is not None and self._listener.is_alive():
            logger.debug("HotkeyListener: already running.")
            return

        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()
        logger.info("HotkeyListener: started.")

    def stop(self) -> None:
        """Stop the pynput listener thread."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("HotkeyListener: stopped.")

    @property
    def is_running(self) -> bool:
        """True if the listener thread is active."""
        return self._listener is not None and self._listener.is_alive()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Called by pynput on every key press (runs in pynput thread)."""
        try:
            emit_fn = self._key_to_signal.get(key)
            if emit_fn is not None:
                emit_fn()
        except Exception as exc:
            logger.error("HotkeyListener: error in _on_press: %s", exc)
