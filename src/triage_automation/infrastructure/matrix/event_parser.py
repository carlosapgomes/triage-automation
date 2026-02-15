"""Parsing helpers for Matrix Room-1 intake events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedRoom1PdfIntakeEvent:
    """Normalized Room-1 PDF intake event required for case creation."""

    room_id: str
    event_id: str
    sender_user_id: str
    mxc_url: str
    filename: str | None
    mimetype: str | None


def parse_room1_pdf_intake_event(
    *,
    room_id: str,
    event: dict[str, Any],
    bot_user_id: str,
) -> ParsedRoom1PdfIntakeEvent | None:
    """Parse Room-1 event, returning normalized payload if it's a valid human PDF."""

    sender = event.get("sender")
    if not isinstance(sender, str) or sender == bot_user_id:
        return None

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        return None

    content = event.get("content")
    if not isinstance(content, dict):
        return None

    msgtype = content.get("msgtype")
    if msgtype != "m.file":
        return None

    info = content.get("info")
    info_dict = info if isinstance(info, dict) else {}

    mimetype = info_dict.get("mimetype")
    filename = content.get("body") if isinstance(content.get("body"), str) else None

    url: str | None = None
    raw_url = content.get("url")
    if isinstance(raw_url, str):
        url = raw_url
    elif isinstance(content.get("file"), dict):
        encrypted = content["file"]
        encrypted_url = encrypted.get("url")
        if isinstance(encrypted_url, str):
            url = encrypted_url

    if not isinstance(url, str) or not url.startswith("mxc://"):
        return None

    is_pdf = False
    if isinstance(mimetype, str) and mimetype.lower() == "application/pdf":
        is_pdf = True
    elif isinstance(filename, str) and filename.lower().endswith(".pdf"):
        is_pdf = True

    if not is_pdf:
        return None

    return ParsedRoom1PdfIntakeEvent(
        room_id=room_id,
        event_id=event_id,
        sender_user_id=sender,
        mxc_url=url,
        filename=filename,
        mimetype=mimetype if isinstance(mimetype, str) else None,
    )
