"""OpenAI chat-completions adapter implementing the generic LLM client port."""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OpenAiHttpResponse:
    """Normalized HTTP response data returned by OpenAI transports."""

    status_code: int
    body_bytes: bytes


class OpenAiHttpTransportPort(Protocol):
    """Transport protocol used by OpenAI HTTP adapter."""

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> OpenAiHttpResponse:
        """Execute one HTTP request and return normalized response data."""


class OpenAiAdapterError(RuntimeError):
    """Raised for normalized OpenAI adapter failures."""


class UrllibOpenAiHttpTransport:
    """urllib-based async transport implementation for OpenAI HTTP calls."""

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> OpenAiHttpResponse:
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
    ) -> OpenAiHttpResponse:
        request = Request(url=url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                status_code = int(response.getcode())
                payload = response.read()
                return OpenAiHttpResponse(status_code=status_code, body_bytes=payload)
        except HTTPError as error:
            payload = error.read()
            return OpenAiHttpResponse(status_code=int(error.code), body_bytes=payload)
        except URLError as error:
            raise OpenAiAdapterError(f"transport connection failure: {error}") from error


class OpenAiChatCompletionsClient:
    """OpenAI `/v1/chat/completions` adapter for runtime LLM execution."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float | None = None,
        response_schema_name: str | None = None,
        response_schema: dict[str, object] | None = None,
        transport: OpenAiHttpTransportPort | None = None,
        timeout_seconds: float = 30.0,
        base_url: str = "https://api.openai.com",
    ) -> None:
        api_key_value = api_key.strip()
        model_value = model.strip()
        if not api_key_value:
            raise ValueError("api_key must be a non-empty string")
        if not model_value:
            raise ValueError("model must be a non-empty string")
        if temperature is not None and not (0.0 <= temperature <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        if (response_schema_name is None) != (response_schema is None):
            raise ValueError(
                "response_schema_name and response_schema must be provided together"
            )
        if response_schema_name is not None and not response_schema_name.strip():
            raise ValueError("response_schema_name must be a non-empty string")

        self._api_key = api_key_value
        self._model = model_value
        self._temperature = temperature
        self._response_schema_name = response_schema_name
        self._response_schema = response_schema
        self._transport = transport or UrllibOpenAiHttpTransport()
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url.rstrip("/")

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return assistant text from OpenAI chat completion response."""

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
        }
        if self._response_schema_name is None or self._response_schema is None:
            payload["response_format"] = {"type": "json_object"}
        else:
            normalized_schema = _normalize_openai_strict_schema(self._response_schema)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": self._response_schema_name,
                    "schema": normalized_schema,
                    "strict": True,
                },
            }
        if self._temperature is not None and self._supports_custom_temperature():
            payload["temperature"] = self._temperature
        response = await self._request_json(
            operation="chat_completions",
            method="POST",
            path="/v1/chat/completions",
            payload=payload,
        )
        return _extract_assistant_content(response=response)

    @property
    def model_name(self) -> str:
        """Return configured OpenAI model name for this client instance."""

        return self._model

    def _supports_custom_temperature(self) -> bool:
        """Return whether this model accepts explicit non-default temperature values."""

        return not self._model.lower().startswith("gpt-5")

    async def _request_json(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        response = await self._request_bytes(
            operation=operation,
            method=method,
            path=path,
            body=body,
            content_type="application/json",
        )
        try:
            decoded = json.loads(response.body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenAiAdapterError(f"{operation} returned invalid JSON payload") from error
        if not isinstance(decoded, dict):
            raise OpenAiAdapterError(f"{operation} returned non-object JSON payload")
        return cast("dict[str, object]", decoded)

    async def _request_bytes(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        body: bytes | None,
        content_type: str | None,
    ) -> OpenAiHttpResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        if content_type is not None:
            headers["Content-Type"] = content_type

        url = f"{self._base_url}{path}"
        try:
            response = await self._transport.request(
                method=method,
                url=url,
                headers=headers,
                body=body,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception as error:  # noqa: BLE001
            raise OpenAiAdapterError(f"{operation} transport failure") from error

        if response.status_code < 200 or response.status_code >= 300:
            details = _decode_error_payload(response.body_bytes)
            raise OpenAiAdapterError(
                f"{operation} failed with status {response.status_code}: {details}"
            )
        return response


def _extract_assistant_content(*, response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAiAdapterError("chat_completions response missing choices")

    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise OpenAiAdapterError("chat_completions response has invalid choices payload")

    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise OpenAiAdapterError("chat_completions response missing message payload")

    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") != "text":
                continue
            text_value = part.get("text")
            if isinstance(text_value, str):
                text_parts.append(text_value)
        if text_parts:
            return "".join(text_parts)

    raise OpenAiAdapterError("chat_completions response missing assistant content")


def _decode_error_payload(payload: bytes) -> str:
    if not payload:
        return "empty response body"
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        return "<binary>"
    return decoded[:200]


def _normalize_openai_strict_schema(schema: dict[str, object]) -> dict[str, object]:
    """Normalize JSON Schema so OpenAI strict mode accepts all object nodes."""

    normalized = copy.deepcopy(schema)
    _normalize_schema_node(normalized)
    return normalized


def _normalize_schema_node(node: object) -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        properties = node.get("properties")
        if node_type == "object" and isinstance(properties, dict):
            property_names = [str(name) for name in properties.keys()]
            node["required"] = property_names
            node.setdefault("additionalProperties", False)

        for value in node.values():
            _normalize_schema_node(value)
        return

    if isinstance(node, list):
        for value in node:
            _normalize_schema_node(value)
