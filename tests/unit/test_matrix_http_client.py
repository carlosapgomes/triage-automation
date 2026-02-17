from __future__ import annotations

import json
import re
from dataclasses import dataclass

import pytest

from triage_automation.infrastructure.matrix.http_client import (
    MatrixAdapterError,
    MatrixHttpClient,
    MatrixHttpResponse,
)


@dataclass
class _QueuedTransport:
    responses: list[MatrixHttpResponse]
    error: Exception | None = None

    def __post_init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> MatrixHttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_send_text_posts_message_payload_and_returns_event_id() -> None:
    transport = _QueuedTransport(
        responses=[
            MatrixHttpResponse(
                status_code=200,
                body_bytes=b'{"event_id":"$evt-send-1"}',
            )
        ]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    event_id = await client.send_text(room_id="!room:example.org", body="hello")

    assert event_id == "$evt-send-1"
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "PUT"
    assert re.match(
        (
            r"^https://matrix\.example\.org/_matrix/client/v3/rooms/%21room%3Aexample\.org/"
            r"send/m\.room\.message/[0-9a-f]{32}$"
        ),
        str(call["url"]),
    )
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer access-token"
    payload = json.loads((call["body"] or b"").decode("utf-8"))
    assert payload == {"msgtype": "m.text", "body": "hello"}


@pytest.mark.asyncio
async def test_reply_text_includes_reply_relation() -> None:
    transport = _QueuedTransport(
        responses=[MatrixHttpResponse(status_code=200, body_bytes=b'{"event_id":"$evt-reply-1"}')]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    event_id = await client.reply_text(
        room_id="!room:example.org",
        event_id="$origin-1",
        body="processing...",
    )

    assert event_id == "$evt-reply-1"
    payload = json.loads((transport.calls[0]["body"] or b"").decode("utf-8"))
    assert payload["msgtype"] == "m.text"
    assert payload["body"] == "processing..."
    assert payload["m.relates_to"]["m.in_reply_to"]["event_id"] == "$origin-1"


@pytest.mark.asyncio
async def test_send_text_includes_formatted_body_when_provided() -> None:
    transport = _QueuedTransport(
        responses=[
            MatrixHttpResponse(
                status_code=200,
                body_bytes=b'{"event_id":"$evt-send-html-1"}',
            )
        ]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    event_id = await client.send_text(
        room_id="!room:example.org",
        body="# titulo",
        formatted_body="<h1>titulo</h1>",
    )

    assert event_id == "$evt-send-html-1"
    payload = json.loads((transport.calls[0]["body"] or b"").decode("utf-8"))
    assert payload["msgtype"] == "m.text"
    assert payload["body"] == "# titulo"
    assert payload["format"] == "org.matrix.custom.html"
    assert payload["formatted_body"] == "<h1>titulo</h1>"


@pytest.mark.asyncio
async def test_reply_text_includes_formatted_body_when_provided() -> None:
    transport = _QueuedTransport(
        responses=[
            MatrixHttpResponse(
                status_code=200,
                body_bytes=b'{"event_id":"$evt-reply-html-1"}',
            )
        ]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    event_id = await client.reply_text(
        room_id="!room:example.org",
        event_id="$origin-1",
        body="# resumo",
        formatted_body="<h1>resumo</h1>",
    )

    assert event_id == "$evt-reply-html-1"
    payload = json.loads((transport.calls[0]["body"] or b"").decode("utf-8"))
    assert payload["msgtype"] == "m.text"
    assert payload["body"] == "# resumo"
    assert payload["format"] == "org.matrix.custom.html"
    assert payload["formatted_body"] == "<h1>resumo</h1>"
    assert payload["m.relates_to"]["m.in_reply_to"]["event_id"] == "$origin-1"


@pytest.mark.asyncio
async def test_upload_media_posts_bytes_and_returns_content_uri() -> None:
    transport = _QueuedTransport(
        responses=[
            MatrixHttpResponse(
                status_code=200,
                body_bytes=b'{"content_uri":"mxc://example.org/media-1"}',
            )
        ]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    content_uri = await client.upload_media(
        filename="arquivo.txt",
        content_type="text/plain; charset=utf-8",
        payload_bytes=b"linha 1\nlinha 2\n",
    )

    assert content_uri == "mxc://example.org/media-1"
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert (
        str(call["url"])
        == "https://matrix.example.org/_matrix/media/v3/upload?filename=arquivo.txt"
    )
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert headers["Content-Type"] == "text/plain; charset=utf-8"
    assert call["body"] == b"linha 1\nlinha 2\n"


@pytest.mark.asyncio
async def test_reply_file_text_uploads_then_posts_m_file_reply() -> None:
    transport = _QueuedTransport(
        responses=[
            MatrixHttpResponse(
                status_code=200,
                body_bytes=b'{"content_uri":"mxc://example.org/media-file"}',
            ),
            MatrixHttpResponse(status_code=200, body_bytes=b'{"event_id":"$evt-file-1"}'),
        ]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    event_id = await client.reply_file_text(
        room_id="!room:example.org",
        event_id="$origin-1",
        filename="contexto.txt",
        text_content="linha A\nlinha B",
    )

    assert event_id == "$evt-file-1"
    assert len(transport.calls) == 2

    upload_call = transport.calls[0]
    assert upload_call["method"] == "POST"
    assert (
        str(upload_call["url"])
        == "https://matrix.example.org/_matrix/media/v3/upload?filename=contexto.txt"
    )
    assert upload_call["body"] == b"linha A\nlinha B"

    message_call = transport.calls[1]
    assert message_call["method"] == "PUT"
    payload = json.loads((message_call["body"] or b"").decode("utf-8"))
    assert payload["msgtype"] == "m.file"
    assert payload["body"] == "contexto.txt"
    assert payload["filename"] == "contexto.txt"
    assert payload["url"] == "mxc://example.org/media-file"
    assert payload["info"]["mimetype"] == "text/plain"
    assert payload["info"]["size"] == len(b"linha A\nlinha B")
    assert payload["m.relates_to"]["m.in_reply_to"]["event_id"] == "$origin-1"


@pytest.mark.asyncio
async def test_redact_event_calls_redaction_endpoint() -> None:
    transport = _QueuedTransport(responses=[MatrixHttpResponse(status_code=200, body_bytes=b"{}")])
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    await client.redact_event(room_id="!room:example.org", event_id="$event-3")

    assert len(transport.calls) == 1
    assert transport.calls[0]["method"] == "PUT"
    assert re.match(
        (
            r"^https://matrix\.example\.org/_matrix/client/v3/rooms/%21room%3Aexample\.org/"
            r"redact/%24event-3/[0-9a-f]{32}$"
        ),
        str(transport.calls[0]["url"]),
    )


@pytest.mark.asyncio
async def test_download_mxc_fetches_media_bytes() -> None:
    transport = _QueuedTransport(
        responses=[MatrixHttpResponse(status_code=200, body_bytes=b"%PDF...")]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    payload = await client.download_mxc("mxc://example.org/media-id")

    assert payload == b"%PDF..."
    assert len(transport.calls) == 1
    assert transport.calls[0]["method"] == "GET"
    assert (
        str(transport.calls[0]["url"])
        == "https://matrix.example.org/_matrix/client/v1/media/download/example.org/media-id"
    )


@pytest.mark.asyncio
async def test_download_mxc_falls_back_to_media_v3_when_client_v1_returns_not_found() -> None:
    transport = _QueuedTransport(
        responses=[
            MatrixHttpResponse(status_code=404, body_bytes=b'{"errcode":"M_NOT_FOUND"}'),
            MatrixHttpResponse(status_code=200, body_bytes=b"%PDF..."),
        ]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    payload = await client.download_mxc("mxc://example.org/media-id")

    assert payload == b"%PDF..."
    assert len(transport.calls) == 2
    assert (
        str(transport.calls[0]["url"])
        == "https://matrix.example.org/_matrix/client/v1/media/download/example.org/media-id"
    )
    assert (
        str(transport.calls[1]["url"])
        == "https://matrix.example.org/_matrix/media/v3/download/example.org/media-id"
    )


@pytest.mark.asyncio
async def test_non_success_status_raises_normalized_matrix_adapter_error() -> None:
    transport = _QueuedTransport(
        responses=[MatrixHttpResponse(status_code=500, body_bytes=b'{"error":"boom"}')]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    with pytest.raises(MatrixAdapterError) as exc_info:
        await client.send_text(room_id="!room:example.org", body="hello")

    assert "send_text failed with status 500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transport_exception_raises_normalized_matrix_adapter_error() -> None:
    transport = _QueuedTransport(
        responses=[],
        error=RuntimeError("connection refused"),
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    with pytest.raises(MatrixAdapterError) as exc_info:
        await client.download_mxc("mxc://example.org/media-id")

    assert "download_mxc transport failure" in str(exc_info.value)


@pytest.mark.asyncio
async def test_is_user_joined_returns_true_for_join_membership() -> None:
    transport = _QueuedTransport(
        responses=[MatrixHttpResponse(status_code=200, body_bytes=b'{"membership":"join"}')]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    result = await client.is_user_joined(
        room_id="!room:example.org",
        user_id="@doctor:example.org",
    )

    assert result is True
    assert len(transport.calls) == 1
    assert transport.calls[0]["method"] == "GET"
    assert (
        str(transport.calls[0]["url"])
        == (
            "https://matrix.example.org/_matrix/client/v3/rooms/%21room%3Aexample.org/"
            "state/m.room.member/%40doctor%3Aexample.org"
        )
    )


@pytest.mark.asyncio
async def test_is_user_joined_returns_false_when_membership_event_not_found() -> None:
    transport = _QueuedTransport(
        responses=[MatrixHttpResponse(status_code=404, body_bytes=b'{"errcode":"M_NOT_FOUND"}')]
    )
    client = MatrixHttpClient(
        homeserver_url="https://matrix.example.org",
        access_token="access-token",
        transport=transport,
    )

    result = await client.is_user_joined(
        room_id="!room:example.org",
        user_id="@intruder:example.org",
    )

    assert result is False
