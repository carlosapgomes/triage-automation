from __future__ import annotations

from triage_automation.infrastructure.matrix.sync_events import (
    iter_invited_room_ids,
    iter_joined_room_timeline_events,
)


def test_iter_invited_room_ids_extracts_room_ids_from_rooms_invite() -> None:
    sync_payload: dict[str, object] = {
        "rooms": {
            "invite": {
                "!room1:example.org": {"invite_state": {"events": []}},
                "!room4:example.org": {"invite_state": {"events": []}},
            }
        }
    }

    invited_room_ids = iter_invited_room_ids(sync_payload)

    assert invited_room_ids == ["!room1:example.org", "!room4:example.org"]


def test_iter_invited_room_ids_ignores_invalid_invite_payloads() -> None:
    assert iter_invited_room_ids({}) == []
    assert iter_invited_room_ids({"rooms": {"invite": []}}) == []
    assert iter_invited_room_ids({"rooms": {"invite": {123: {}}}}) == []


def test_iter_joined_room_timeline_events_keeps_join_behavior_with_invites_present() -> None:
    sync_payload: dict[str, object] = {
        "rooms": {
            "join": {
                "!room1:example.org": {
                    "timeline": {
                        "events": [
                            {
                                "event_id": "$event-1",
                                "sender": "@human:example.org",
                                "type": "m.room.message",
                            }
                        ]
                    }
                }
            },
            "invite": {
                "!room4:example.org": {"invite_state": {"events": []}},
            },
        }
    }

    events = iter_joined_room_timeline_events(sync_payload)

    assert len(events) == 1
    assert events[0].room_id == "!room1:example.org"
    assert events[0].event["event_id"] == "$event-1"
