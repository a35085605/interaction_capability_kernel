from __future__ import annotations

import unittest

from eventing import EventDispatchError
from eventing.adapters import InMemoryEventBus


class EventBusTests(unittest.TestCase):
    def test_subscribers_receive_matching_events_in_registration_order(self) -> None:
        bus = InMemoryEventBus()
        observed: list[str] = []

        bus.subscribe(str, lambda event: observed.append(f"first:{event}"))
        bus.subscribe(object, lambda event: observed.append(f"all:{event}"))
        bus.subscribe(str, lambda event: observed.append(f"second:{event}"))

        bus.publish("ready")

        self.assertEqual(
            observed,
            ["first:ready", "all:ready", "second:ready"],
        )

    def test_reentrant_publication_is_fifo_not_recursive(self) -> None:
        bus = InMemoryEventBus()
        observed: list[str] = []

        def first(event: str) -> None:
            observed.append("first")
            bus.publish(7)

        bus.subscribe(str, first)
        bus.subscribe(str, lambda event: observed.append("second"))
        bus.subscribe(int, lambda event: observed.append("integer"))

        bus.publish("event")

        self.assertEqual(observed, ["first", "second", "integer"])

    def test_unsubscribe_removes_only_the_requested_registration(self) -> None:
        bus = InMemoryEventBus()
        observed: list[str] = []
        first = bus.subscribe(str, lambda event: observed.append("first"))
        bus.subscribe(str, lambda event: observed.append("second"))

        self.assertTrue(bus.unsubscribe(first))
        self.assertFalse(bus.unsubscribe(first))
        bus.publish("event")

        self.assertEqual(observed, ["second"])

    def test_handler_failures_do_not_block_other_delivery(self) -> None:
        bus = InMemoryEventBus()
        observed: list[str] = []

        def fail(event: str) -> None:
            observed.append("failed-handler")
            bus.publish(1)
            raise RuntimeError("boom")

        bus.subscribe(str, fail)
        bus.subscribe(str, lambda event: observed.append("later-handler"))
        bus.subscribe(int, lambda event: observed.append("queued-event"))

        with self.assertRaises(EventDispatchError) as caught:
            bus.publish("event")

        self.assertEqual(
            observed,
            ["failed-handler", "later-handler", "queued-event"],
        )
        self.assertEqual(len(caught.exception.failures), 1)
        self.assertIsInstance(caught.exception.failures[0].error, RuntimeError)


if __name__ == "__main__":
    unittest.main()
