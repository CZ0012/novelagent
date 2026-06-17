"""Append-only event log for canon mutations."""

from __future__ import annotations

from storygraph.models.graph import EventLogEntry


class InMemoryEventLog:
    def __init__(self) -> None:
        self._events: list[EventLogEntry] = []

    def append(self, event: EventLogEntry) -> EventLogEntry:
        if any(existing.event_id == event.event_id for existing in self._events):
            return self.get(event.event_id)
        self._events.append(event)
        return event

    def get(self, event_id: str) -> EventLogEntry:
        for event in self._events:
            if event.event_id == event_id:
                return event
        raise KeyError(event_id)

    def list(self) -> list[EventLogEntry]:
        return list(self._events)

