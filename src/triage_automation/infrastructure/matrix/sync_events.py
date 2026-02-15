"""Helpers for parsing Matrix `/sync` responses into timeline events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True)
class MatrixTimelineEvent:
    """Room-scoped timeline event extracted from Matrix sync payload."""

    room_id: str
    event: dict[str, Any]


def extract_next_batch_token(
    sync_payload: Mapping[str, Any],
    *,
    fallback: str | None = None,
) -> str | None:
    """Return sync `next_batch` token when present, else fallback value."""

    token = sync_payload.get("next_batch")
    if isinstance(token, str) and token:
        return token
    return fallback


def iter_joined_room_timeline_events(sync_payload: Mapping[str, Any]) -> list[MatrixTimelineEvent]:
    """Extract timeline events for joined rooms from Matrix sync payload."""

    rooms = sync_payload.get("rooms")
    if not isinstance(rooms, Mapping):
        return []

    joined_rooms = rooms.get("join")
    if not isinstance(joined_rooms, Mapping):
        return []

    extracted: list[MatrixTimelineEvent] = []
    for room_id, room_body in joined_rooms.items():
        if not isinstance(room_id, str) or not isinstance(room_body, Mapping):
            continue

        timeline = room_body.get("timeline")
        if not isinstance(timeline, Mapping):
            continue

        events = timeline.get("events")
        if not isinstance(events, list):
            continue

        for event in events:
            if isinstance(event, dict):
                extracted.append(
                    MatrixTimelineEvent(
                        room_id=room_id,
                        event=cast("dict[str, Any]", event),
                    )
                )

    return extracted
