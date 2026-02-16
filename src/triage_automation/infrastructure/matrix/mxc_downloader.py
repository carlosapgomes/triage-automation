"""MXC media download adapter for worker PDF processing."""

from __future__ import annotations

from typing import Protocol


class MatrixMediaClientPort(Protocol):
    """Protocol for Matrix media download capability."""

    async def download_mxc(self, mxc_url: str) -> bytes:
        """Download raw bytes for a Matrix MXC URI."""


class MxcDownloadError(RuntimeError):
    """Raised when MXC media cannot be downloaded."""


class MatrixMxcDownloader:
    """Wrapper around Matrix media client with normalized errors."""

    def __init__(self, media_client: MatrixMediaClientPort) -> None:
        self._media_client = media_client

    async def download_pdf(self, mxc_url: str) -> bytes:
        """Download PDF bytes from MXC URI or raise MxcDownloadError."""

        try:
            payload = await self._media_client.download_mxc(mxc_url)
        except Exception as error:  # noqa: BLE001
            raise MxcDownloadError(
                f"Failed to download MXC content: {mxc_url} ({error})"
            ) from error

        if not payload:
            raise MxcDownloadError(f"Downloaded empty payload for MXC URI: {mxc_url}")

        return payload
