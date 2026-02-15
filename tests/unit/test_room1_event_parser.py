from __future__ import annotations

from triage_automation.infrastructure.matrix.event_parser import parse_room1_pdf_intake_event


def _base_event() -> dict[str, object]:
    return {
        "event_id": "$event-1",
        "sender": "@doctor:example.org",
        "content": {
            "msgtype": "m.file",
            "body": "report.pdf",
            "url": "mxc://example.org/abc123",
            "info": {"mimetype": "application/pdf"},
        },
    }


def test_ignore_non_human_event_from_bot_user() -> None:
    event = _base_event()
    event["sender"] = "@bot:example.org"

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=event,
        bot_user_id="@bot:example.org",
    )

    assert parsed is None


def test_ignore_non_pdf_message() -> None:
    event = _base_event()
    content = event["content"]
    assert isinstance(content, dict)
    content["msgtype"] = "m.text"

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=event,
        bot_user_id="@bot:example.org",
    )

    assert parsed is None


def test_valid_pdf_message_parses_successfully() -> None:
    event = _base_event()

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=event,
        bot_user_id="@bot:example.org",
    )

    assert parsed is not None
    assert parsed.room_id == "!room1:example.org"
    assert parsed.event_id == "$event-1"
    assert parsed.sender_user_id == "@doctor:example.org"
    assert parsed.mxc_url == "mxc://example.org/abc123"
    assert parsed.filename == "report.pdf"
    assert parsed.mimetype == "application/pdf"
