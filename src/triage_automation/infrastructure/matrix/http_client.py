"""Concrete Matrix HTTP adapter for send/reply/redact/media-download operations."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


@dataclass(frozen=True)
class MatrixHttpResponse:
    """Normalized HTTP response data returned by transport implementations."""

    status_code: int
    body_bytes: bytes


class MatrixHttpTransportPort(Protocol):
    """Transport protocol used by Matrix HTTP adapter."""

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> MatrixHttpResponse:
        """Execute one HTTP request and return normalized response data."""


class MatrixAdapterError(RuntimeError):
    """Raised for normalized Matrix adapter failures."""


class UrllibMatrixHttpTransport:
    """urllib-based async transport implementation for Matrix HTTP calls."""

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> MatrixHttpResponse:
        """Execute HTTP request in a worker thread and normalize HTTP errors."""

        return await asyncio.to_thread(
            self._request_sync,
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout_seconds=timeout_seconds,
        )

    def _request_sync(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> MatrixHttpResponse:
        request = Request(url=url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                status_code = int(response.getcode())
                payload = response.read()
                return MatrixHttpResponse(status_code=status_code, body_bytes=payload)
        except HTTPError as error:
            payload = error.read()
            return MatrixHttpResponse(status_code=int(error.code), body_bytes=payload)
        except URLError as error:
            raise MatrixAdapterError(f"transport connection failure: {error}") from error


class MatrixHttpClient:
    """Matrix REST API adapter implementing runtime room/message/media operations."""

    def __init__(
        self,
        *,
        homeserver_url: str,
        access_token: str,
        transport: MatrixHttpTransportPort | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._homeserver_url = homeserver_url.rstrip("/")
        self._access_token = access_token
        self._transport = transport or UrllibMatrixHttpTransport()
        self._timeout_seconds = timeout_seconds

    async def send_text(self, *, room_id: str, body: str) -> str:
        """Send plain text message to room and return created Matrix event id."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/send/m.room.message/{quote(txn_id, safe='')}"
        )
        response = await self._request_json(
            operation="send_text",
            method="PUT",
            path=path,
            payload={"msgtype": "m.text", "body": body},
        )
        return _extract_event_id(response=response, operation="send_text")

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Reply to a room event with plain text and return created Matrix event id."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/send/m.room.message/{quote(txn_id, safe='')}"
        )
        response = await self._request_json(
            operation="reply_text",
            method="PUT",
            path=path,
            payload={
                "msgtype": "m.text",
                "body": body,
                "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
            },
        )
        return _extract_event_id(response=response, operation="reply_text")

    async def redact_event(self, *, room_id: str, event_id: str) -> None:
        """Redact room event using Matrix client API."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/redact/{quote(event_id, safe='')}/{quote(txn_id, safe='')}"
        )
        await self._request_json(
            operation="redact_event",
            method="POST",
            path=path,
            payload={},
        )

    async def download_mxc(self, mxc_url: str) -> bytes:
        """Download MXC media payload bytes."""

        server_name, media_id = _parse_mxc_url(mxc_url)
        path = (
            "/_matrix/media/v3/download/"
            f"{quote(server_name, safe='')}/{quote(media_id, safe='')}"
        )
        response = await self._request_bytes(
            operation="download_mxc",
            method="GET",
            path=path,
            body=None,
            content_type=None,
        )
        return response.body_bytes

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        """Fetch Matrix sync response for timeline polling."""

        query: dict[str, str] = {"timeout": str(timeout_ms)}
        if since is not None and since:
            query["since"] = since
        path = f"/_matrix/client/v3/sync?{urlencode(query)}"
        return await self._request_json(
            operation="sync",
            method="GET",
            path=path,
            payload={},
        )

    async def _request_json(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        body = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        response = await self._request_bytes(
            operation=operation,
            method=method,
            path=path,
            body=body,
            content_type="application/json" if payload is not None else None,
        )
        try:
            decoded = json.loads(response.body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MatrixAdapterError(f"{operation} returned invalid JSON payload") from error
        if not isinstance(decoded, dict):
            raise MatrixAdapterError(f"{operation} returned non-object JSON payload")
        return decoded

    async def _request_bytes(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        body: bytes | None,
        content_type: str | None,
    ) -> MatrixHttpResponse:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
        }
        if content_type is not None:
            headers["Content-Type"] = content_type

        url = f"{self._homeserver_url}{path}"
        try:
            response = await self._transport.request(
                method=method,
                url=url,
                headers=headers,
                body=body,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception as error:  # noqa: BLE001
            raise MatrixAdapterError(f"{operation} transport failure") from error

        if response.status_code < 200 or response.status_code >= 300:
            details = _decode_error_payload(response.body_bytes)
            raise MatrixAdapterError(
                f"{operation} failed with status {response.status_code}: {details}"
            )

        return response


def _new_txn_id() -> str:
    return uuid4().hex


def _extract_event_id(*, response: dict[str, object], operation: str) -> str:
    event_id = response.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id
    raise MatrixAdapterError(f"{operation} response missing event_id")


def _parse_mxc_url(mxc_url: str) -> tuple[str, str]:
    parsed = urlparse(mxc_url)
    if parsed.scheme != "mxc" or not parsed.netloc or not parsed.path:
        raise MatrixAdapterError(f"download_mxc invalid mxc url: {mxc_url}")
    media_id = parsed.path.lstrip("/")
    if not media_id:
        raise MatrixAdapterError(f"download_mxc invalid mxc url: {mxc_url}")
    return parsed.netloc, media_id


def _decode_error_payload(payload: bytes) -> str:
    if not payload:
        return "empty response body"
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        return "<binary>"
    return decoded[:200]
