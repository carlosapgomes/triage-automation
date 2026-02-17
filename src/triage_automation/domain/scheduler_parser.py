"""Strict parser for Room-3 scheduler reply templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

_BRT = ZoneInfo("America/Bahia")
_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "case": ("case", "caso"),
    "status": ("status", "situacao", "situação"),
    "date_time": ("data_hora", "datahora", "datetime", "data_hora_brt"),
    "location": ("location", "local"),
    "instructions": ("instructions", "instrucoes", "instruções"),
    "reason": ("reason", "motivo"),
}
_EMPTY_REASON_MARKERS = {
    "",
    "(opcional)",
    "opcional",
    "(vazio)",
    "vazio",
    "-",
    "n/a",
    "na",
}


@dataclass(frozen=True)
class SchedulerReplyParsed:
    """Normalized scheduler reply fields extracted from strict template text."""

    case_id: UUID
    appointment_status: str
    appointment_at: datetime | None
    location: str | None
    instructions: str | None
    reason: str | None


@dataclass(frozen=True)
class SchedulerParseError(ValueError):
    """Deterministic parse failure with machine-readable reason."""

    reason: str

    def __str__(self) -> str:
        return self.reason


def parse_scheduler_reply(*, body: str, expected_case_id: UUID) -> SchedulerReplyParsed:
    """Parse denied/confirmed scheduler reply template for a specific case id."""

    lines = _normalized_message_lines(body=body)
    if not lines:
        raise SchedulerParseError("empty_message")

    if _extract_value(lines=lines, key="status") is not None:
        return _parse_status_template(lines=lines, expected_case_id=expected_case_id)

    case_id = _extract_case_id(lines=lines)
    if case_id != expected_case_id:
        raise SchedulerParseError("case_id_mismatch")

    parsed_lines = _strip_section_headers(lines)
    if not parsed_lines:
        raise SchedulerParseError("empty_message")

    first_line = parsed_lines[0].strip().lower()
    if first_line in {"denied", "negado"}:
        reason = _extract_value(lines=parsed_lines, key="reason")
        return SchedulerReplyParsed(
            case_id=case_id,
            appointment_status="denied",
            appointment_at=None,
            location=None,
            instructions=None,
            reason=reason,
        )

    appointment_at = _parse_brt_datetime(parsed_lines[0])
    location = _extract_required_value(lines=parsed_lines, key="location")
    instructions = _extract_required_value(lines=parsed_lines, key="instructions")

    return SchedulerReplyParsed(
        case_id=case_id,
        appointment_status="confirmed",
        appointment_at=appointment_at,
        location=location,
        instructions=instructions,
        reason=None,
    )


def _parse_status_template(
    *,
    lines: list[str],
    expected_case_id: UUID,
) -> SchedulerReplyParsed:
    case_id = _extract_case_id(lines=lines)
    if case_id != expected_case_id:
        raise SchedulerParseError("case_id_mismatch")

    status_raw = _extract_required_value(lines=lines, key="status").strip().lower()
    if status_raw in {"confirmado", "confirmed"}:
        date_time_raw = _extract_required_value(lines=lines, key="date_time")
        appointment_at = _parse_brt_datetime(date_time_raw)
        location = _extract_required_value(lines=lines, key="location")
        instructions = _extract_required_value(lines=lines, key="instructions")
        return SchedulerReplyParsed(
            case_id=case_id,
            appointment_status="confirmed",
            appointment_at=appointment_at,
            location=location,
            instructions=instructions,
            reason=None,
        )

    if status_raw in {"negado", "denied"}:
        reason_raw = _extract_value(lines=lines, key="reason")
        reason = _normalize_reason(reason_raw)
        return SchedulerReplyParsed(
            case_id=case_id,
            appointment_status="denied",
            appointment_at=None,
            location=None,
            instructions=None,
            reason=reason,
        )

    raise SchedulerParseError("invalid_status_value")


def _extract_case_id(*, lines: list[str]) -> UUID:
    value = _extract_required_value(lines=lines, key="case")
    try:
        return UUID(value)
    except ValueError as error:
        raise SchedulerParseError("invalid_case_line") from error


def _strip_section_headers(lines: list[str]) -> list[str]:
    """Normalize optional section header lines used in Room-3 templates."""

    if not lines:
        return lines

    first_line = lines[0].strip().lower()
    if first_line in {"confirmed", "confirmed:", "confirmado", "confirmado:"}:
        return lines[1:]
    if first_line in {"denied:", "negado:"}:
        if len(lines) >= 2 and lines[1].strip().lower() in {"denied", "negado"}:
            return lines[1:]
        return ["denied", *lines[1:]]

    return lines


def _extract_required_value(*, lines: list[str], key: str) -> str:
    value = _extract_value(lines=lines, key=key)
    if value is None or not value:
        if key == "case":
            raise SchedulerParseError("missing_case_line")
        raise SchedulerParseError(f"missing_{key}_line")
    return value


def _extract_value(*, lines: list[str], key: str) -> str | None:
    aliases = _KEY_ALIASES.get(key, (key,))
    prefixes = tuple(f"{alias.lower()}:" for alias in aliases)
    for line in lines:
        normalized = line.lower()
        for prefix in prefixes:
            if normalized.startswith(prefix):
                return line[len(prefix) :].strip()
    return None


def _normalized_message_lines(*, body: str) -> list[str]:
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        lines.append(line)
    return lines


def _normalize_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    normalized = reason.strip()
    if normalized.lower() in _EMPTY_REASON_MARKERS:
        return None
    return normalized


def _parse_brt_datetime(line: str) -> datetime:
    expected_suffix = " BRT"
    if not line.endswith(expected_suffix):
        raise SchedulerParseError("invalid_confirmed_datetime")

    raw = line[: -len(expected_suffix)]
    try:
        naive = datetime.strptime(raw, "%d-%m-%Y %H:%M")
    except ValueError as error:
        raise SchedulerParseError("invalid_confirmed_datetime") from error

    return naive.replace(tzinfo=_BRT)
