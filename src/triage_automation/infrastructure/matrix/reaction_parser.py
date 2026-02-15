"""Parsing helpers for Matrix reaction events."""

from __future__ import annotations

from typing import Any

from triage_automation.application.services.reaction_service import ReactionEvent


def parse_matrix_reaction_event(
    *,
    room_id: str,
    event: dict[str, Any],
    bot_user_id: str,
) -> ReactionEvent | None:
    """Parse Matrix reaction event into normalized `ReactionEvent` model."""

    if event.get("type") != "m.reaction":
        return None

    sender = event.get("sender")
    if not isinstance(sender, str) or sender == bot_user_id:
        return None

    reaction_event_id = event.get("event_id")
    if not isinstance(reaction_event_id, str) or not reaction_event_id:
        return None

    content = event.get("content")
    if not isinstance(content, dict):
        return None

    relates = content.get("m.relates_to")
    if not isinstance(relates, dict):
        return None

    if relates.get("rel_type") != "m.annotation":
        return None

    related_event_id = relates.get("event_id")
    reaction_key = relates.get("key")
    if (
        not isinstance(related_event_id, str)
        or not related_event_id
        or not isinstance(reaction_key, str)
        or not reaction_key
    ):
        return None

    return ReactionEvent(
        room_id=room_id,
        reaction_event_id=reaction_event_id,
        reactor_user_id=sender,
        related_event_id=related_event_id,
        reaction_key=reaction_key,
    )
