"""
EventBus — lightweight publish/subscribe event system.

Decouples modules: publishers emit named events with keyword payloads;
subscribers register callbacks without importing the publisher.

All cross-module communication MUST go through the event bus singleton.
Never import directly between feature modules (gui, ocr, capture, etc.).

Canonical event names
---------------------
ocr.image_complete   (image_id: str, results: list, confidence_avg: float)
ocr.batch_complete   (folder_id: int, result_count: int)
capture.new_image    (image_id: str, folder_id: int, image_array: object)
capture.new_section  (folder_id: int)
export.complete      (output_path: str, chapter_count: int)
pipeline.stage_complete (stage_name: str, input_count: int, output_count: int)

Usage:
    from core.event_bus import event_bus

    # Subscribe (typically in __init__ of a component):
    event_bus.subscribe("ocr.batch_complete", self._on_batch_done)

    # Publish (typically inside a worker/pipeline):
    event_bus.publish("ocr.batch_complete", folder_id=3, result_count=42)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Simple synchronous publish/subscribe event bus."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Register *callback* to be called whenever *event* is published.

        The same callback can be registered multiple times and will be called
        multiple times. Callers are responsible for avoiding duplicates.
        """
        self._listeners[event].append(callback)
        logger.debug("EventBus: subscribed %s to '%s'.", callback.__qualname__, event)

    def unsubscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Remove the first occurrence of *callback* from *event* listeners.

        No-op if the callback is not registered.
        """
        listeners = self._listeners.get(event, [])
        try:
            listeners.remove(callback)
            logger.debug(
                "EventBus: unsubscribed %s from '%s'.", callback.__qualname__, event
            )
        except ValueError:
            logger.warning(
                "EventBus: unsubscribe called for %s on '%s' but not registered.",
                callback.__qualname__,
                event,
            )

    def publish(self, event: str, **kwargs: object) -> None:
        """Call all callbacks registered for *event*, passing **kwargs**.

        Exceptions raised by individual callbacks are caught and logged so
        that one bad subscriber cannot break the entire publish chain.
        """
        callbacks = list(self._listeners.get(event, []))
        logger.debug("EventBus: publishing '%s' to %d subscriber(s).", event, len(callbacks))
        for cb in callbacks:
            try:
                cb(**kwargs)
            except Exception:
                logger.exception(
                    "EventBus: callback %s raised an exception handling '%s'.",
                    cb.__qualname__,
                    event,
                )

    def subscriber_count(self, event: str) -> int:
        """Return the number of callbacks registered for *event*."""
        return len(self._listeners.get(event, []))

    def clear(self, event: str | None = None) -> None:
        """Remove all subscriptions for *event*, or all events if None.

        Primarily intended for use in tests to reset state between cases.
        """
        if event is None:
            self._listeners.clear()
        else:
            self._listeners.pop(event, None)


event_bus: EventBus = EventBus()
