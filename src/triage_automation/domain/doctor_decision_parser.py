"""Strict parser for Room-2 doctor decision reply templates."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

_REQUIRED_KEYS = ("decision", "support_flag", "case_id")
_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "decision": ("decision", "decisao", "decisão"),
    "support_flag": ("support_flag", "suporte"),
    "reason": ("reason", "motivo"),
    "case_id": ("case_id", "caso"),
}
_FORBIDDEN_TYPED_IDENTITY_KEYS = {
    "doctor_user_id",
    "medico_user_id",
    "usuario_medico",
}
_DECISION_ALIASES: dict[str, str] = {
    "accept": "accept",
    "deny": "deny",
    "aceitar": "accept",
    "aceito": "accept",
    "aceita": "accept",
    "negar": "deny",
    "negado": "deny",
    "negar.": "deny",
}
_SUPPORT_ALIASES: dict[str, str] = {
    "none": "none",
    "nenhum": "none",
    "anesthesist": "anesthesist",
    "anestesista": "anesthesist",
    "anesthesist_icu": "anesthesist_icu",
    "anestesista_uti": "anesthesist_icu",
    "anestesista_icu": "anesthesist_icu",
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
_UUID_PATTERN = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


@dataclass(frozen=True)
class DoctorDecisionReplyParsed:
    """Normalized doctor decision fields extracted from strict template text."""

    case_id: UUID
    decision: str
    support_flag: str
    reason: str | None


@dataclass(frozen=True)
class DoctorDecisionParseError(ValueError):
    """Deterministic parse failure with machine-readable reason."""

    reason: str

    def __str__(self) -> str:
        return self.reason


def parse_doctor_decision_reply(
    *,
    body: str,
    expected_case_id: UUID | None = None,
) -> DoctorDecisionReplyParsed:
    """Parse strict Room-2 doctor decision reply template."""

    lines = _normalized_message_lines(body=body)
    if not lines:
        raise DoctorDecisionParseError("empty_message")

    parsed_fields: dict[str, str] = {}
    for line in lines:
        normalized_line = line.replace("：", ":")
        if ":" not in normalized_line:
            continue

        key_raw, value = normalized_line.split(":", 1)
        normalized_key = _normalize_key(key_raw.strip())
        if normalized_key in _FORBIDDEN_TYPED_IDENTITY_KEYS:
            raise DoctorDecisionParseError("unknown_field")
        parsed_key = _resolve_key(normalized_key)
        if parsed_key is None:
            continue
        if parsed_key in parsed_fields:
            raise DoctorDecisionParseError("duplicate_field")
        parsed_fields[parsed_key] = value.strip()

    for required_key in _REQUIRED_KEYS:
        if required_key not in parsed_fields:
            raise DoctorDecisionParseError(f"missing_{required_key}_line")

    decision_raw = parsed_fields["decision"].lower()
    decision = _DECISION_ALIASES.get(decision_raw)
    if decision is None:
        raise DoctorDecisionParseError("invalid_decision_value")

    support_raw = parsed_fields["support_flag"].lower()
    support_flag = _SUPPORT_ALIASES.get(support_raw)
    if support_flag is None:
        raise DoctorDecisionParseError("invalid_support_flag_value")
    _validate_decision_support_flag(decision=decision, support_flag=support_flag)

    case_raw = parsed_fields["case_id"]
    case_match = _UUID_PATTERN.search(case_raw)
    if case_match is not None:
        case_raw = case_match.group(1)
    try:
        case_id = UUID(case_raw)
    except ValueError as error:
        raise DoctorDecisionParseError("invalid_case_line") from error
    if expected_case_id is not None and case_id != expected_case_id:
        raise DoctorDecisionParseError("case_id_mismatch")

    reason = None if decision == "accept" else _normalize_reason(parsed_fields.get("reason", ""))

    return DoctorDecisionReplyParsed(
        case_id=case_id,
        decision=decision,
        support_flag=support_flag,
        reason=reason,
    )


def _validate_decision_support_flag(*, decision: str, support_flag: str) -> None:
    """Enforce decision/support_flag invariants used by doctor decision contract."""

    if decision == "deny" and support_flag != "none":
        raise DoctorDecisionParseError("invalid_support_flag_for_decision")


def _normalize_key(raw_key: str) -> str:
    return _normalize_token(raw_key)


def _resolve_key(normalized_key: str) -> str | None:
    for canonical, aliases in _KEY_ALIASES.items():
        alias_set = {_normalize_token(alias) for alias in aliases}
        if normalized_key in alias_set:
            return canonical
    return None


def _normalized_message_lines(*, body: str) -> list[str]:
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        if line.startswith(">"):
            continue
        lines.append(line)
    return lines


def _normalize_reason(reason_raw: str) -> str | None:
    normalized = reason_raw.strip()
    if normalized.lower() in _EMPTY_REASON_MARKERS:
        return None
    return normalized


def _normalize_token(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.strip("`*_ ")
    normalized = normalized.replace("-", "_").replace("/", "_").replace(" ", "_")
    normalized = _strip_diacritics(normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def _strip_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(character for character in decomposed if not unicodedata.combining(character))
