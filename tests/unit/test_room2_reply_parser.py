from __future__ import annotations

from uuid import UUID

from triage_automation.infrastructure.matrix.room2_reply_parser import (
    parse_room2_decision_reply_event,
)


def _room2_reply_event(
    *,
    event_id: str,
    sender: str,
    body: str,
    reply_to_event_id: str,
) -> dict[str, object]:
    return {
        "type": "m.room.message",
        "event_id": event_id,
        "sender": sender,
        "content": {
            "msgtype": "m.text",
            "body": body,
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": reply_to_event_id,
                }
            },
        },
    }


def test_parse_room2_reply_accepts_valid_reply_to_active_root() -> None:
    active_root_event_id = "$room2-root-1"
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: ok\n"
        "case_id: 11111111-1111-1111-1111-111111111111\n"
    )
    event = _room2_reply_event(
        event_id="$room2-reply-1",
        sender="@doctor:example.org",
        body=body,
        reply_to_event_id=active_root_event_id,
    )

    parsed = parse_room2_decision_reply_event(
        room_id="!room2:example.org",
        event=event,
        bot_user_id="@bot:example.org",
        active_root_event_id=active_root_event_id,
    )

    assert parsed is not None
    assert parsed.sender_user_id == "@doctor:example.org"
    assert parsed.reply_to_event_id == active_root_event_id
    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"
    assert str(parsed.case_id) == "11111111-1111-1111-1111-111111111111"


def test_parse_room2_reply_rejects_missing_reply_relation() -> None:
    event = {
        "type": "m.room.message",
        "event_id": "$room2-reply-2",
        "sender": "@doctor:example.org",
        "content": {
            "msgtype": "m.text",
            "body": (
                "decision: accept\n"
                "support_flag: none\n"
                "reason: ok\n"
                "case_id: 11111111-1111-1111-1111-111111111111\n"
            ),
        },
    }

    parsed = parse_room2_decision_reply_event(
        room_id="!room2:example.org",
        event=event,
        bot_user_id="@bot:example.org",
        active_root_event_id="$room2-root-1",
    )

    assert parsed is None


def test_parse_room2_reply_rejects_wrong_parent_reply_target() -> None:
    event = _room2_reply_event(
        event_id="$room2-reply-3",
        sender="@doctor:example.org",
        body=(
            "decision: accept\n"
            "support_flag: none\n"
            "reason: ok\n"
            "case_id: 11111111-1111-1111-1111-111111111111\n"
        ),
        reply_to_event_id="$room2-root-other",
    )

    parsed = parse_room2_decision_reply_event(
        room_id="!room2:example.org",
        event=event,
        bot_user_id="@bot:example.org",
        active_root_event_id="$room2-root-1",
    )

    assert parsed is None


def test_parse_room2_reply_rejects_invalid_template_even_with_correct_parent() -> None:
    active_root_event_id = "$room2-root-1"
    event = _room2_reply_event(
        event_id="$room2-reply-4",
        sender="@doctor:example.org",
        body="hello doctor free text",
        reply_to_event_id=active_root_event_id,
    )

    parsed = parse_room2_decision_reply_event(
        room_id="!room2:example.org",
        event=event,
        bot_user_id="@bot:example.org",
        active_root_event_id=active_root_event_id,
    )

    assert parsed is None


def test_parse_room2_reply_rejects_case_id_mismatch_against_expected() -> None:
    active_root_event_id = "$room2-root-1"
    event = _room2_reply_event(
        event_id="$room2-reply-5",
        sender="@doctor:example.org",
        body=(
            "decision: accept\n"
            "support_flag: none\n"
            "reason: ok\n"
            "case_id: 11111111-1111-1111-1111-111111111111\n"
        ),
        reply_to_event_id=active_root_event_id,
    )

    parsed = parse_room2_decision_reply_event(
        room_id="!room2:example.org",
        event=event,
        bot_user_id="@bot:example.org",
        active_root_event_id=active_root_event_id,
        expected_case_id=UUID("22222222-2222-2222-2222-222222222222"),
    )

    assert parsed is None


def test_parse_room2_reply_rejects_event_from_bot_sender() -> None:
    active_root_event_id = "$room2-root-1"
    event = _room2_reply_event(
        event_id="$room2-reply-bot",
        sender="@bot:example.org",
        body=(
            "decision: accept\n"
            "support_flag: none\n"
            "reason: ok\n"
            "case_id: 11111111-1111-1111-1111-111111111111\n"
        ),
        reply_to_event_id=active_root_event_id,
    )

    parsed = parse_room2_decision_reply_event(
        room_id="!room2:example.org",
        event=event,
        bot_user_id="@bot:example.org",
        active_root_event_id=active_root_event_id,
    )

    assert parsed is None
