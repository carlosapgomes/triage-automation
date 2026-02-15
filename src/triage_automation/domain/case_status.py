"""Case status enum for triage state machine."""

from __future__ import annotations

from enum import StrEnum


class CaseStatus(StrEnum):
    """All case statuses defined by the handoff specification."""

    NEW = "NEW"
    R1_ACK_PROCESSING = "R1_ACK_PROCESSING"
    EXTRACTING = "EXTRACTING"
    LLM_STRUCT = "LLM_STRUCT"
    LLM_SUGGEST = "LLM_SUGGEST"
    R2_POST_WIDGET = "R2_POST_WIDGET"
    WAIT_DOCTOR = "WAIT_DOCTOR"
    DOCTOR_DENIED = "DOCTOR_DENIED"
    DOCTOR_ACCEPTED = "DOCTOR_ACCEPTED"
    R3_POST_REQUEST = "R3_POST_REQUEST"
    WAIT_APPT = "WAIT_APPT"
    APPT_CONFIRMED = "APPT_CONFIRMED"
    APPT_DENIED = "APPT_DENIED"
    FAILED = "FAILED"
    R1_FINAL_REPLY_POSTED = "R1_FINAL_REPLY_POSTED"
    WAIT_R1_CLEANUP_THUMBS = "WAIT_R1_CLEANUP_THUMBS"
    CLEANUP_RUNNING = "CLEANUP_RUNNING"
    CLEANED = "CLEANED"
