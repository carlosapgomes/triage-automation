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


class MatrixTransportError(MatrixAdapterError):
    """Raised when Matrix transport layer fails before receiving an HTTP response."""


class MatrixRequestError(MatrixAdapterError):
    """Raised when Matrix responds with a non-success HTTP status code."""

    def __init__(self, *, operation: str, status_code: int, details: str) -> None:
        self.operation = operation
        self.status_code = status_code
        self.details = details
        super().__init__(f"{operation} failed with status {status_code}: {details}")


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

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        """Send plain text message to room and return created Matrix event id."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/send/m.room.message/{quote(txn_id, safe='')}"
        )
        payload: dict[str, object] = {"msgtype": "m.text", "body": body}
        if formatted_body is not None and formatted_body.strip():
            payload["format"] = "org.matrix.custom.html"
            payload["formatted_body"] = formatted_body

        response = await self._request_json(
            operation="send_text",
            method="PUT",
            path=path,
            payload=payload,
        )
        return _extract_event_id(response=response, operation="send_text")

    async def send_file_from_mxc(
        self,
        *,
        room_id: str,
        filename: str,
        mxc_url: str,
        mimetype: str,
    ) -> str:
        """Send `m.file` event in room referencing an existing MXC media URL."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/send/m.room.message/{quote(txn_id, safe='')}"
        )
        response = await self._request_json(
            operation="send_file_from_mxc",
            method="PUT",
            path=path,
            payload={
                "msgtype": "m.file",
                "body": filename,
                "filename": filename,
                "url": mxc_url,
                "info": {"mimetype": mimetype},
            },
        )
        return _extract_event_id(response=response, operation="send_file_from_mxc")

    async def reply_text(
        self,
        *,
        room_id: str,
        event_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        """Reply to a room event with plain text and return created Matrix event id."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/send/m.room.message/{quote(txn_id, safe='')}"
        )
        payload: dict[str, object] = {
            "msgtype": "m.text",
            "body": body,
            "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
        }
        if formatted_body is not None and formatted_body.strip():
            payload["format"] = "org.matrix.custom.html"
            payload["formatted_body"] = formatted_body

        response = await self._request_json(
            operation="reply_text",
            method="PUT",
            path=path,
            payload=payload,
        )
        return _extract_event_id(response=response, operation="reply_text")

    async def reply_file_text(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        text_content: str,
    ) -> str:
        """Upload a UTF-8 text file and reply with `m.file` event referencing it."""

        payload_bytes = text_content.encode("utf-8")
        content_uri = await self.upload_media(
            filename=filename,
            content_type="text/plain; charset=utf-8",
            payload_bytes=payload_bytes,
        )

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/send/m.room.message/{quote(txn_id, safe='')}"
        )
        response = await self._request_json(
            operation="reply_file_text",
            method="PUT",
            path=path,
            payload={
                "msgtype": "m.file",
                "body": filename,
                "filename": filename,
                "url": content_uri,
                "info": {
                    "mimetype": "text/plain",
                    "size": len(payload_bytes),
                },
                "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
            },
        )
        return _extract_event_id(response=response, operation="reply_file_text")

    async def reply_file_from_mxc(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        mxc_url: str,
        mimetype: str,
    ) -> str:
        """Reply with `m.file` event referencing an existing MXC media URL."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/send/m.room.message/{quote(txn_id, safe='')}"
        )
        response = await self._request_json(
            operation="reply_file_from_mxc",
            method="PUT",
            path=path,
            payload={
                "msgtype": "m.file",
                "body": filename,
                "filename": filename,
                "url": mxc_url,
                "info": {"mimetype": mimetype},
                "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
            },
        )
        return _extract_event_id(response=response, operation="reply_file_from_mxc")

    async def upload_media(
        self,
        *,
        filename: str,
        content_type: str,
        payload_bytes: bytes,
    ) -> str:
        """Upload media bytes and return Matrix `mxc://` URI."""

        encoded_filename = quote(filename, safe="")
        candidate_paths = [
            f"/_matrix/media/v3/upload?filename={encoded_filename}",
            f"/_matrix/client/v1/media/upload?filename={encoded_filename}",
        ]

        last_error: MatrixRequestError | None = None
        for path in candidate_paths:
            try:
                response = await self._request_json_bytes_body(
                    operation="upload_media",
                    method="POST",
                    path=path,
                    body=payload_bytes,
                    content_type=content_type,
                )
                return _extract_content_uri(response=response, operation="upload_media")
            except MatrixRequestError as error:
                if error.status_code == 404:
                    last_error = error
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise MatrixAdapterError("upload_media failed: no media upload path succeeded")

    async def redact_event(self, *, room_id: str, event_id: str) -> None:
        """Redact room event using Matrix client API."""

        txn_id = _new_txn_id()
        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/redact/{quote(event_id, safe='')}/{quote(txn_id, safe='')}"
        )
        await self._request_json(
            operation="redact_event",
            method="PUT",
            path=path,
            payload={},
        )

    async def download_mxc(self, mxc_url: str) -> bytes:
        """Download MXC media payload bytes."""

        server_name, media_id = _parse_mxc_url(mxc_url)
        candidate_paths = [
            (
                "/_matrix/client/v1/media/download/"
                f"{quote(server_name, safe='')}/{quote(media_id, safe='')}"
            ),
            (
                "/_matrix/media/v3/download/"
                f"{quote(server_name, safe='')}/{quote(media_id, safe='')}"
            ),
        ]

        last_error: MatrixRequestError | None = None
        for path in candidate_paths:
            try:
                response = await self._request_bytes(
                    operation="download_mxc",
                    method="GET",
                    path=path,
                    body=None,
                    content_type=None,
                )
                return response.body_bytes
            except MatrixRequestError as error:
                # Some homeservers expose authenticated media on client/v1 only.
                if error.status_code == 404:
                    last_error = error
                    continue
                raise

        if last_error is not None:
            raise last_error

        raise MatrixAdapterError("download_mxc failed: no media download path succeeded")

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

    async def is_user_joined(self, *, room_id: str, user_id: str) -> bool:
        """Return whether user currently has `join` membership in the room."""

        path = (
            "/_matrix/client/v3/rooms/"
            f"{quote(room_id, safe='')}/state/m.room.member/{quote(user_id, safe='')}"
        )
        try:
            response = await self._request_json(
                operation="is_user_joined",
                method="GET",
                path=path,
                payload={},
            )
        except MatrixRequestError as error:
            if error.status_code == 404:
                return False
            raise

        membership = response.get("membership")
        return isinstance(membership, str) and membership == "join"

    async def join_room(self, *, room_id: str) -> None:
        """Join invited Matrix room using client join endpoint."""

        path = f"/_matrix/client/v3/rooms/{quote(room_id, safe='')}/join"
        await self._request_json(
            operation="join_room",
            method="POST",
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

    async def _request_json_bytes_body(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        body: bytes,
        content_type: str,
    ) -> dict[str, object]:
        response = await self._request_bytes(
            operation=operation,
            method=method,
            path=path,
            body=body,
            content_type=content_type,
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
            raise MatrixTransportError(f"{operation} transport failure") from error

        if response.status_code < 200 or response.status_code >= 300:
            details = _decode_error_payload(response.body_bytes)
            raise MatrixRequestError(
                operation=operation,
                status_code=response.status_code,
                details=details,
            )

        return response


def _new_txn_id() -> str:
    return uuid4().hex


def _extract_event_id(*, response: dict[str, object], operation: str) -> str:
    event_id = response.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id
    raise MatrixAdapterError(f"{operation} response missing event_id")


def _extract_content_uri(*, response: dict[str, object], operation: str) -> str:
    content_uri = response.get("content_uri")
    if isinstance(content_uri, str) and content_uri.startswith("mxc://"):
        return content_uri
    raise MatrixAdapterError(f"{operation} response missing content_uri")


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
