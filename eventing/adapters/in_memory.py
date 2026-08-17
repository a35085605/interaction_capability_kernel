from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import TypeVar, cast
from uuid import uuid4

from eventing.models import (
    EventDispatchError,
    EventHandlerFailure,
    EventSubscriptionToken,
)


EventT = TypeVar("EventT")


@dataclass(frozen=True, slots=True)
class _Subscription:
    token: EventSubscriptionToken
    event_type: type[object]
    handler: Callable[[object], None]


class InMemoryEventBus:
    """Thread-safe in-process FIFO event bus with serial handler dispatch.

    One active publisher drains the shared FIFO queue. Re-entrant or concurrent
    publications are appended and delivered after the current event, which
    prevents recursive handler stacks and preserves publication order at the bus
    boundary. Subscribers are invoked in registration order.

    Handler failures do not prevent later subscribers or queued events from
    receiving delivery. The active dispatcher raises one ``EventDispatchError``
    after the queue is drained so failures remain observable without corrupting
    dispatch state.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscriptions: list[_Subscription] = []
        self._queue: deque[object] = deque()
        self._dispatching = False

    def subscribe(
        self,
        event_type: type[EventT],
        handler: Callable[[EventT], None],
    ) -> EventSubscriptionToken:
        if not isinstance(event_type, type):
            raise TypeError("event_type must be a type")
        if not callable(handler):
            raise TypeError("handler must be callable")

        token = EventSubscriptionToken(uuid4().hex)
        subscription = _Subscription(
            token=token,
            event_type=cast(type[object], event_type),
            handler=cast(Callable[[object], None], handler),
        )
        with self._lock:
            self._subscriptions.append(subscription)
        return token

    def unsubscribe(self, token: EventSubscriptionToken) -> bool:
        if not isinstance(token, EventSubscriptionToken):
            raise TypeError("token must be EventSubscriptionToken")
        with self._lock:
            for index, subscription in enumerate(self._subscriptions):
                if subscription.token == token:
                    del self._subscriptions[index]
                    return True
        return False

    def publish(self, event: object) -> None:
        with self._lock:
            self._queue.append(event)
            if self._dispatching:
                return
            self._dispatching = True

        failures: list[EventHandlerFailure] = []
        try:
            while True:
                with self._lock:
                    if not self._queue:
                        self._dispatching = False
                        break
                    current = self._queue.popleft()
                    subscriptions = tuple(
                        subscription
                        for subscription in self._subscriptions
                        if isinstance(current, subscription.event_type)
                    )

                for subscription in subscriptions:
                    try:
                        subscription.handler(current)
                    except BaseException as exc:
                        failures.append(
                            EventHandlerFailure(
                                event=current,
                                handler=subscription.handler,
                                error=exc,
                            )
                        )
        finally:
            with self._lock:
                if self._dispatching:
                    self._dispatching = False

        if failures:
            raise EventDispatchError(tuple(failures))


__all__ = ["InMemoryEventBus"]
