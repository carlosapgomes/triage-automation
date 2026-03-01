from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import pytest

from apps.bot_matrix.main import (
    _SYNC_HTTP_TIMEOUT_BUFFER_SECONDS,
    build_bot_matrix_runtime,
    run_room1_intake_listener,
)
from triage_automation.config.settings import Settings
from triage_automation.infrastructure.matrix.http_client import (
    MatrixHttpClient,
    MatrixTransportError,
)


class _FlakySyncClient:
    def __init__(self, *, stop_event: asyncio.Event) -> None:
        self._stop_event = stop_event
        self.sync_calls = 0

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        _ = since, timeout_ms
        self.sync_calls += 1
        if self.sync_calls == 1:
            raise MatrixTransportError("sync transport failure")
        self._stop_event.set()
        return {"next_batch": "s2", "rooms": {"join": {}}}

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        _ = room_id, event_id, body
        return "$reply"

    async def send_text(self, *, room_id: str, body: str) -> str:
        _ = room_id, body
        return "$send"


class _InviteSyncClient:
    def __init__(self, *, stop_event: asyncio.Event) -> None:
        self._stop_event = stop_event
        self.join_calls: list[str] = []

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        _ = since, timeout_ms
        self._stop_event.set()
        return {
            "next_batch": "s3",
            "rooms": {
                "join": {},
                "invite": {
                    "!room1:example.org": {"invite_state": {"events": []}},
                    "!room2:example.org": {"invite_state": {"events": []}},
                    "!room3:example.org": {"invite_state": {"events": []}},
                    "!room4:example.org": {"invite_state": {"events": []}},
                    "!other:example.org": {"invite_state": {"events": []}},
                },
            },
        }

    async def join_room(self, *, room_id: str) -> None:
        self.join_calls.append(room_id)

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        _ = room_id, event_id, body
        return "$reply"

    async def send_text(self, *, room_id: str, body: str) -> str:
        _ = room_id, body
        return "$send"


class _InviteFailingSyncClient:
    def __init__(self, *, stop_event: asyncio.Event) -> None:
        self._stop_event = stop_event

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        _ = since, timeout_ms
        self._stop_event.set()
        return {
            "next_batch": "s4",
            "rooms": {
                "join": {},
                "invite": {
                    "!room4:example.org": {"invite_state": {"events": []}},
                },
            },
        }

    async def join_room(self, *, room_id: str) -> None:
        _ = room_id
        raise RuntimeError("forbidden")

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        _ = room_id, event_id, body
        return "$reply"

    async def send_text(self, *, room_id: str, body: str) -> str:
        _ = room_id, body
        return "$send"


class _InviteRetrySyncClient:
    def __init__(self, *, stop_event: asyncio.Event) -> None:
        self._stop_event = stop_event
        self.sync_calls = 0
        self.join_calls = 0

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        _ = since, timeout_ms
        self.sync_calls += 1
        if self.sync_calls >= 2:
            self._stop_event.set()
        return {
            "next_batch": f"s-retry-{self.sync_calls}",
            "rooms": {
                "join": {},
                "invite": {
                    "!room4:example.org": {"invite_state": {"events": []}},
                },
            },
        }

    async def join_room(self, *, room_id: str) -> None:
        _ = room_id
        self.join_calls += 1
        if self.join_calls == 1:
            raise RuntimeError("temporary join failure")

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        _ = room_id, event_id, body
        return "$reply"

    async def send_text(self, *, room_id: str, body: str) -> str:
        _ = room_id, body
        return "$send"


class _InviteReinviteSyncClient:
    def __init__(self, *, stop_event: asyncio.Event) -> None:
        self._stop_event = stop_event
        self.sync_calls = 0
        self.join_calls: list[str] = []

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        _ = since, timeout_ms
        self.sync_calls += 1
        if self.sync_calls >= 3:
            self._stop_event.set()

        invite_rooms: dict[str, object] = {}
        if self.sync_calls in {1, 3}:
            invite_rooms["!room4:example.org"] = {"invite_state": {"events": []}}

        return {
            "next_batch": f"s-reinvite-{self.sync_calls}",
            "rooms": {
                "join": {},
                "invite": invite_rooms,
            },
        }

    async def join_room(self, *, room_id: str) -> None:
        self.join_calls.append(room_id)

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        _ = room_id, event_id, body
        return "$reply"

    async def send_text(self, *, room_id: str, body: str) -> str:
        _ = room_id, body
        return "$send"


@dataclass
class _CallSpy:
    calls: int = 0

    async def ingest_pdf_event(self, parsed_event: object) -> None:
        _ = parsed_event
        self.calls += 1

    async def handle(self, parsed_event: object) -> None:
        _ = parsed_event
        self.calls += 1

    async def handle_reply(self, parsed_event: object) -> object:
        _ = parsed_event
        self.calls += 1
        return object()

    async def get_case_message_by_room_event(self, *, room_id: str, event_id: str) -> None:
        _ = room_id, event_id
        self.calls += 1
        return None

    async def append_case_matrix_message_transcript(self, payload: object) -> None:
        _ = payload
        self.calls += 1

    async def add_message(self, payload: object) -> None:
        _ = payload
        self.calls += 1


@pytest.mark.asyncio
async def test_room1_listener_retries_after_transport_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = asyncio.Event()
    matrix_client = _FlakySyncClient(stop_event=stop_event)

    with caplog.at_level(logging.INFO):
        await asyncio.wait_for(
            run_room1_intake_listener(
                matrix_client=matrix_client,
                message_repository=object(),  # no routed events in this test
                intake_service=object(),  # no routed events in this test
                reaction_service=object(),  # no routed events in this test
                room2_reply_service=object(),  # no routed events in this test
                room3_reply_service=object(),  # no routed events in this test
                room1_id="!room1:example.org",
                room2_id="!room2:example.org",
                room3_id="!room3:example.org",
                room4_id="!room4:example.org",
                bot_user_id="@bot:example.org",
                sync_timeout_ms=30_000,
                poll_interval_seconds=0.0,
                stop_event=stop_event,
            ),
            timeout=1.0,
        )

    assert matrix_client.sync_calls == 2
    assert "bot_matrix_listener_started" in caplog.text
    assert "Matrix sync transport failure; retrying on next poll cycle." in caplog.text


@pytest.mark.asyncio
async def test_room1_listener_autojoin_targets_only_configured_rooms_without_clinical_mutation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = asyncio.Event()
    matrix_client = _InviteSyncClient(stop_event=stop_event)
    intake_service = _CallSpy()
    reaction_service = _CallSpy()
    room2_reply_service = _CallSpy()
    message_repository = _CallSpy()
    room3_reply_service = _CallSpy()

    with caplog.at_level(logging.INFO):
        await asyncio.wait_for(
            run_room1_intake_listener(
                matrix_client=matrix_client,
                message_repository=message_repository,
                intake_service=intake_service,
                reaction_service=reaction_service,
                room2_reply_service=room2_reply_service,
                room3_reply_service=room3_reply_service,
                room1_id="!room1:example.org",
                room2_id="!room2:example.org",
                room3_id="!room3:example.org",
                room4_id="!room4:example.org",
                bot_user_id="@bot:example.org",
                sync_timeout_ms=30_000,
                poll_interval_seconds=0.0,
                stop_event=stop_event,
            ),
            timeout=1.0,
        )

    assert matrix_client.join_calls == [
        "!room1:example.org",
        "!room2:example.org",
        "!room3:example.org",
        "!room4:example.org",
    ]
    assert "bot_matrix_invite_autojoin_succeeded room_id=!room1:example.org" in caplog.text
    assert "bot_matrix_invite_autojoin_succeeded room_id=!room4:example.org" in caplog.text
    assert intake_service.calls == 0
    assert reaction_service.calls == 0
    assert room2_reply_service.calls == 0
    assert message_repository.calls == 0
    assert room3_reply_service.calls == 0


@pytest.mark.asyncio
async def test_room1_listener_logs_warning_when_invite_autojoin_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = asyncio.Event()
    matrix_client = _InviteFailingSyncClient(stop_event=stop_event)

    with caplog.at_level(logging.INFO):
        await asyncio.wait_for(
            run_room1_intake_listener(
                matrix_client=matrix_client,
                message_repository=object(),
                intake_service=object(),
                reaction_service=object(),
                room2_reply_service=object(),
                room3_reply_service=object(),
                room1_id="!room1:example.org",
                room2_id="!room2:example.org",
                room3_id="!room3:example.org",
                room4_id="!room4:example.org",
                bot_user_id="@bot:example.org",
                sync_timeout_ms=30_000,
                poll_interval_seconds=0.0,
                stop_event=stop_event,
            ),
            timeout=1.0,
        )

    assert "bot_matrix_invite_autojoin_failed room_id=!room4:example.org" in caplog.text
    assert "reason=forbidden" in caplog.text


@pytest.mark.asyncio
async def test_room1_listener_retries_invite_autojoin_on_subsequent_poll(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = asyncio.Event()
    matrix_client = _InviteRetrySyncClient(stop_event=stop_event)

    with caplog.at_level(logging.INFO):
        await asyncio.wait_for(
            run_room1_intake_listener(
                matrix_client=matrix_client,
                message_repository=object(),
                intake_service=object(),
                reaction_service=object(),
                room2_reply_service=object(),
                room3_reply_service=object(),
                room1_id="!room1:example.org",
                room2_id="!room2:example.org",
                room3_id="!room3:example.org",
                room4_id="!room4:example.org",
                bot_user_id="@bot:example.org",
                sync_timeout_ms=30_000,
                poll_interval_seconds=0.0,
                stop_event=stop_event,
            ),
            timeout=1.0,
        )

    assert matrix_client.sync_calls == 2
    assert matrix_client.join_calls == 2
    assert (
        "bot_matrix_invite_autojoin_failed room_id=!room4:example.org reason=temporary join failure"
        in caplog.text
    )
    assert "bot_matrix_invite_autojoin_succeeded room_id=!room4:example.org" in caplog.text


@pytest.mark.asyncio
async def test_room1_listener_reaccepts_invite_after_reinvite_for_allowed_room(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = asyncio.Event()
    matrix_client = _InviteReinviteSyncClient(stop_event=stop_event)

    with caplog.at_level(logging.INFO):
        await asyncio.wait_for(
            run_room1_intake_listener(
                matrix_client=matrix_client,
                message_repository=object(),
                intake_service=object(),
                reaction_service=object(),
                room2_reply_service=object(),
                room3_reply_service=object(),
                room1_id="!room1:example.org",
                room2_id="!room2:example.org",
                room3_id="!room3:example.org",
                room4_id="!room4:example.org",
                bot_user_id="@bot:example.org",
                sync_timeout_ms=30_000,
                poll_interval_seconds=0.0,
                stop_event=stop_event,
            ),
            timeout=1.0,
        )

    assert matrix_client.sync_calls == 3
    assert matrix_client.join_calls == ["!room4:example.org", "!room4:example.org"]
    assert caplog.text.count("bot_matrix_invite_autojoin_succeeded room_id=!room4:example.org") == 2


def test_build_runtime_matrix_client_uses_sync_timeout_buffer() -> None:
    settings = Settings.model_construct(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        room4_id="!room4:example.org",
        matrix_homeserver_url="https://matrix.example.org",
        matrix_bot_user_id="@bot:example.org",
        matrix_access_token="token",
        matrix_sync_timeout_ms=30_000,
        matrix_poll_interval_seconds=1.0,
        worker_poll_interval_seconds=1.0,
        webhook_public_url="https://webhook.example.org",
        widget_public_url="https://webhook.example.org",
        database_url="sqlite+aiosqlite:///tmp.db",
        webhook_hmac_secret="secret",
        llm_runtime_mode="deterministic",
        openai_api_key=None,
        openai_model_llm1="gpt-4o-mini",
        openai_model_llm2="gpt-4o-mini",
        log_level="INFO",
    )

    runtime = build_bot_matrix_runtime(
        settings=settings,
        room1_intake_service=object(),
        reaction_service=object(),
        room3_reply_service=object(),
    )

    assert isinstance(runtime.matrix_client, MatrixHttpClient)
    assert runtime.matrix_client._timeout_seconds == (
        settings.matrix_sync_timeout_ms / 1000 + _SYNC_HTTP_TIMEOUT_BUFFER_SECONDS
    )
