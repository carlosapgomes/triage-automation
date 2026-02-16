from __future__ import annotations

import asyncio
import logging

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
                intake_service=object(),  # no routed events in this test
                reaction_service=object(),  # no routed events in this test
                room3_reply_service=object(),  # no routed events in this test
                room1_id="!room1:example.org",
                room2_id="!room2:example.org",
                room3_id="!room3:example.org",
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


def test_build_runtime_matrix_client_uses_sync_timeout_buffer() -> None:
    settings = Settings.model_construct(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        matrix_homeserver_url="https://matrix.example.org",
        matrix_bot_user_id="@bot:example.org",
        matrix_access_token="token",
        matrix_sync_timeout_ms=30_000,
        matrix_poll_interval_seconds=1.0,
        worker_poll_interval_seconds=1.0,
        webhook_public_url="https://webhook.example.org",
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
