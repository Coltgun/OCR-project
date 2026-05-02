"""Tests for core/event_bus.py — EventBus."""

from __future__ import annotations

import pytest

from core.event_bus import EventBus


def fresh_bus() -> EventBus:
    """Return a new EventBus with no subscriptions."""
    return EventBus()


# ---------------------------------------------------------------------------
# subscribe / publish
# ---------------------------------------------------------------------------

class TestSubscribePublish:
    def test_subscriber_is_called_on_publish(self) -> None:
        bus = fresh_bus()
        received: list[dict] = []

        def handler(**kwargs: object) -> None:
            received.append(kwargs)

        bus.subscribe("test.event", handler)
        bus.publish("test.event", value=42)

        assert len(received) == 1
        assert received[0]["value"] == 42

    def test_kwargs_forwarded_correctly(self) -> None:
        bus = fresh_bus()
        captured: list[dict] = []
        bus.subscribe("evt", lambda **kw: captured.append(kw))
        bus.publish("evt", a=1, b="two", c=True)
        assert captured == [{"a": 1, "b": "two", "c": True}]

    def test_multiple_subscribers_all_called(self) -> None:
        bus = fresh_bus()
        log: list[str] = []
        bus.subscribe("evt", lambda **kw: log.append("first"))
        bus.subscribe("evt", lambda **kw: log.append("second"))
        bus.publish("evt")
        assert log == ["first", "second"]

    def test_publish_with_no_subscribers_is_noop(self) -> None:
        bus = fresh_bus()
        bus.publish("silent.event", data="anything")

    def test_unrelated_event_not_triggered(self) -> None:
        bus = fresh_bus()
        log: list[str] = []
        bus.subscribe("event.a", lambda **kw: log.append("a"))
        bus.publish("event.b")
        assert log == []

    def test_subscriber_called_multiple_times_on_multiple_publishes(self) -> None:
        bus = fresh_bus()
        count = [0]
        bus.subscribe("tick", lambda **kw: count.__setitem__(0, count[0] + 1))
        bus.publish("tick")
        bus.publish("tick")
        bus.publish("tick")
        assert count[0] == 3


# ---------------------------------------------------------------------------
# unsubscribe
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_unsubscribed_handler_not_called(self) -> None:
        bus = fresh_bus()
        log: list[str] = []

        def handler(**kw: object) -> None:
            log.append("called")

        bus.subscribe("evt", handler)
        bus.unsubscribe("evt", handler)
        bus.publish("evt")
        assert log == []

    def test_unsubscribe_only_removes_one_occurrence(self) -> None:
        bus = fresh_bus()
        count = [0]

        def handler(**kw: object) -> None:
            count[0] += 1

        bus.subscribe("evt", handler)
        bus.subscribe("evt", handler)
        bus.unsubscribe("evt", handler)
        bus.publish("evt")
        assert count[0] == 1

    def test_unsubscribe_nonexistent_is_noop(self) -> None:
        bus = fresh_bus()
        bus.unsubscribe("evt", lambda **kw: None)


# ---------------------------------------------------------------------------
# Error isolation
# ---------------------------------------------------------------------------

class TestErrorIsolation:
    def test_exception_in_subscriber_does_not_prevent_others(self) -> None:
        bus = fresh_bus()
        log: list[str] = []

        def bad_handler(**kw: object) -> None:
            raise RuntimeError("subscriber error")

        def good_handler(**kw: object) -> None:
            log.append("good")

        bus.subscribe("evt", bad_handler)
        bus.subscribe("evt", good_handler)
        bus.publish("evt")
        assert log == ["good"]

    def test_exception_does_not_propagate_to_publisher(self) -> None:
        bus = fresh_bus()
        bus.subscribe("evt", lambda **kw: (_ for _ in ()).throw(ValueError("oops")))
        bus.publish("evt")


# ---------------------------------------------------------------------------
# subscriber_count
# ---------------------------------------------------------------------------

class TestSubscriberCount:
    def test_zero_for_unknown_event(self) -> None:
        bus = fresh_bus()
        assert bus.subscriber_count("never.subscribed") == 0

    def test_correct_count_after_subscribes(self) -> None:
        bus = fresh_bus()
        bus.subscribe("e", lambda **kw: None)
        bus.subscribe("e", lambda **kw: None)
        assert bus.subscriber_count("e") == 2

    def test_decreases_after_unsubscribe(self) -> None:
        bus = fresh_bus()
        fn = lambda **kw: None
        bus.subscribe("e", fn)
        bus.subscribe("e", fn)
        bus.unsubscribe("e", fn)
        assert bus.subscriber_count("e") == 1


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_specific_event_removes_it(self) -> None:
        bus = fresh_bus()
        log: list[str] = []
        bus.subscribe("evt", lambda **kw: log.append("x"))
        bus.clear("evt")
        bus.publish("evt")
        assert log == []

    def test_clear_specific_event_leaves_others_intact(self) -> None:
        bus = fresh_bus()
        log: list[str] = []
        bus.subscribe("a", lambda **kw: log.append("a"))
        bus.subscribe("b", lambda **kw: log.append("b"))
        bus.clear("a")
        bus.publish("a")
        bus.publish("b")
        assert log == ["b"]

    def test_clear_all_removes_everything(self) -> None:
        bus = fresh_bus()
        log: list[str] = []
        bus.subscribe("a", lambda **kw: log.append("a"))
        bus.subscribe("b", lambda **kw: log.append("b"))
        bus.clear()
        bus.publish("a")
        bus.publish("b")
        assert log == []
