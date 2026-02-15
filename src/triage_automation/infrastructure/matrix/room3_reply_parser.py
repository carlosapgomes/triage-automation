"""Parsing helpers for Matrix Room-3 scheduler reply events."""

from __future__ import annotations

from typing import Any

from triage_automation.application.services.room3_reply_service import Room3ReplyEvent


def parse_room3_reply_event(
    *,
    room_id: str,
    event: dict[str, Any],
    bot_user_id: str,
) -> Room3ReplyEvent | None:
    """Parse Matrix message event into normalized Room-3 reply payload."""

    if event.get("type") != "m.room.message":
        return None

    sender = event.get("sender")
    if not isinstance(sender, str) or sender == bot_user_id:
        return None

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        return None

    content = event.get("content")
    if not isinstance(content, dict):
        return None

    if content.get("msgtype") != "m.text":
        return None

    body = content.get("body")
    if not isinstance(body, str):
        return None

    relates = content.get("m.relates_to")
    if not isinstance(relates, dict):
        return None

    reply_meta = relates.get("m.in_reply_to")
    if not isinstance(reply_meta, dict):
        return None

    reply_to_event_id = reply_meta.get("event_id")
    if not isinstance(reply_to_event_id, str) or not reply_to_event_id:
        return None

    return Room3ReplyEvent(
        room_id=room_id,
        event_id=event_id,
        sender_user_id=sender,
        body=body,
        reply_to_event_id=reply_to_event_id,
    )
