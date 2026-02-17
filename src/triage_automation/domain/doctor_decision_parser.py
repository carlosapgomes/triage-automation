"""Strict parser for Room-2 doctor decision reply templates."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

_REQUIRED_KEYS = ("decision", "support_flag", "reason", "case_id")
_ALLOWED_DECISIONS = {"accept", "deny"}
_ALLOWED_SUPPORT_FLAGS = {"none", "anesthesist", "anesthesist_icu"}


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

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        raise DoctorDecisionParseError("empty_message")

    parsed_fields: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            raise DoctorDecisionParseError("invalid_line_format")

        key_raw, value = line.split(":", 1)
        key = key_raw.strip().lower()
        if key not in _REQUIRED_KEYS:
            raise DoctorDecisionParseError("unknown_field")
        if key in parsed_fields:
            raise DoctorDecisionParseError("duplicate_field")
        parsed_fields[key] = value.strip()

    for required_key in _REQUIRED_KEYS:
        if required_key not in parsed_fields:
            raise DoctorDecisionParseError(f"missing_{required_key}_line")

    decision = parsed_fields["decision"].lower()
    if decision not in _ALLOWED_DECISIONS:
        raise DoctorDecisionParseError("invalid_decision_value")

    support_flag = parsed_fields["support_flag"].lower()
    if support_flag not in _ALLOWED_SUPPORT_FLAGS:
        raise DoctorDecisionParseError("invalid_support_flag_value")

    case_raw = parsed_fields["case_id"]
    try:
        case_id = UUID(case_raw)
    except ValueError as error:
        raise DoctorDecisionParseError("invalid_case_line") from error
    if expected_case_id is not None and case_id != expected_case_id:
        raise DoctorDecisionParseError("case_id_mismatch")

    reason_raw = parsed_fields["reason"]
    reason = reason_raw if reason_raw else None

    return DoctorDecisionReplyParsed(
        case_id=case_id,
        decision=decision,
        support_flag=support_flag,
        reason=reason,
    )
