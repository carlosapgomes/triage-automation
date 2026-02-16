"""Shared logging configuration helpers for long-running processes."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(*, level: str) -> None:
    """Configure process logging with consistent format and runtime level."""

    normalized_level = level.strip().upper() if level.strip() else "INFO"
    resolved_level = getattr(logging, normalized_level, logging.INFO)

    logging.basicConfig(
        level=resolved_level,
        format=_LOG_FORMAT,
    )
