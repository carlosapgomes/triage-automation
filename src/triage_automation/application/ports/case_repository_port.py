"""Port for case persistence operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from triage_automation.domain.case_status import CaseStatus


class DuplicateCaseOriginEventError(ValueError):
    """Raised when a case with the same room1 origin event already exists."""


@dataclass(frozen=True)
class CaseCreateInput:
    """Input payload for creating a case row."""

    case_id: UUID
    status: CaseStatus
    room1_origin_room_id: str
    room1_origin_event_id: str
    room1_sender_user_id: str


@dataclass(frozen=True)
class CaseRecord:
    """Case persistence model used across repository boundaries."""

    case_id: UUID
    status: CaseStatus
    room1_origin_room_id: str
    room1_origin_event_id: str
    room1_sender_user_id: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CaseRoom2WidgetSnapshot:
    """Case fields required to build and post the Room-2 widget payload."""

    case_id: UUID
    status: CaseStatus
    pdf_mxc_url: str | None
    extracted_text: str | None
    agency_record_number: str | None
    structured_data_json: dict[str, Any] | None
    summary_text: str | None
    suggested_action_json: dict[str, Any] | None


@dataclass(frozen=True)
class CaseDoctorDecisionSnapshot:
    """Case fields required by doctor decision callback handling."""

    case_id: UUID
    status: CaseStatus
    doctor_decided_at: datetime | None
    agency_record_number: str | None = None
    structured_data_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class DoctorDecisionUpdateInput:
    """Doctor decision write payload used by compare-and-set persistence."""

    case_id: UUID
    doctor_user_id: str
    decision: str
    support_flag: str
    reason: str | None


@dataclass(frozen=True)
class SchedulerDecisionUpdateInput:
    """Scheduler decision write payload for compare-and-set persistence."""

    case_id: UUID
    scheduler_user_id: str
    appointment_status: str
    appointment_at: datetime | None
    appointment_location: str | None
    appointment_instructions: str | None
    appointment_reason: str | None


@dataclass(frozen=True)
class CaseFinalReplySnapshot:
    """Case fields required by Room-1 final reply posting handlers."""

    case_id: UUID
    status: CaseStatus
    room1_origin_room_id: str
    room1_origin_event_id: str
    agency_record_number: str | None
    structured_data_json: dict[str, Any] | None
    room1_final_reply_event_id: str | None
    doctor_reason: str | None
    appointment_at: datetime | None
    appointment_location: str | None
    appointment_instructions: str | None
    appointment_reason: str | None


@dataclass(frozen=True)
class Room1FinalReplyReactionSnapshot:
    """Case fields required by Room-1 final reaction cleanup trigger logic."""

    case_id: UUID
    status: CaseStatus
    cleanup_triggered_at: datetime | None


@dataclass(frozen=True)
class CaseLlmInteractionCreateInput:
    """Append-only payload for persisting LLM input/output transcript records."""

    case_id: UUID
    stage: Literal["LLM1", "LLM2"]
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    prompt_system_name: str | None
    prompt_system_version: int | None
    prompt_user_name: str | None
    prompt_user_version: int | None
    model_name: str | None


@dataclass(frozen=True)
class CaseRecoverySnapshot:
    """Case fields required for restart recovery scans."""

    case_id: UUID
    status: CaseStatus
    room1_final_reply_event_id: str | None
    cleanup_triggered_at: datetime | None
    cleanup_completed_at: datetime | None


@dataclass(frozen=True)
class CaseMonitoringListFilter:
    """Filter/pagination options for dashboard case listing queries."""

    status: CaseStatus | None
    activity_from: datetime | None
    activity_to: datetime | None
    page: int
    page_size: int


@dataclass(frozen=True)
class CaseMonitoringListItem:
    """Case row projection returned by monitoring list queries."""

    case_id: UUID
    status: CaseStatus
    latest_activity_at: datetime
    patient_name: str | None = None
    agency_record_number: str | None = None


@dataclass(frozen=True)
class CaseMonitoringListPage:
    """Paginated monitoring list payload returned by case repository."""

    items: list[CaseMonitoringListItem]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class CaseMonitoringTimelineItem:
    """Unified timeline event projection for monitoring case detail."""

    source: Literal["pdf", "llm", "matrix"]
    channel: str
    timestamp: datetime
    room_id: str | None
    actor: str | None
    event_type: str
    content_text: str | None
    payload: dict[str, Any] | None


@dataclass(frozen=True)
class CaseMonitoringDetail:
    """Per-case monitoring detail including unified chronological timeline."""

    case_id: UUID
    status: CaseStatus
    timeline: list[CaseMonitoringTimelineItem]
    patient_name: str | None = None
    agency_record_number: str | None = None


class CaseRepositoryPort(Protocol):
    """Async case repository contract."""

    async def create_case(self, payload: CaseCreateInput) -> CaseRecord:
        """Create a case row or raise DuplicateCaseOriginEventError."""

    async def get_case_by_origin_event_id(self, origin_event_id: str) -> CaseRecord | None:
        """Retrieve case by Room-1 origin event id."""

    async def get_case_room2_widget_snapshot(
        self,
        *,
        case_id: UUID,
    ) -> CaseRoom2WidgetSnapshot | None:
        """Load case artifacts used by Room-2 widget posting flow."""

    async def get_case_doctor_decision_snapshot(
        self,
        *,
        case_id: UUID,
    ) -> CaseDoctorDecisionSnapshot | None:
        """Load case state used by doctor decision callback handling."""

    async def apply_doctor_decision_if_waiting(
        self,
        payload: DoctorDecisionUpdateInput,
    ) -> bool:
        """CAS update from WAIT_DOCTOR to decision state; returns whether applied."""

    async def apply_scheduler_decision_if_waiting(
        self,
        payload: SchedulerDecisionUpdateInput,
    ) -> bool:
        """CAS update from WAIT_APPT to appointment decision state; returns whether applied."""

    async def get_case_final_reply_snapshot(
        self,
        *,
        case_id: UUID,
    ) -> CaseFinalReplySnapshot | None:
        """Load case fields needed to render and post final Room-1 reply message."""

    async def mark_room1_final_reply_posted(
        self,
        *,
        case_id: UUID,
        room1_final_reply_event_id: str,
    ) -> bool:
        """Set final reply linkage and transition to WAIT_R1_CLEANUP_THUMBS once."""

    async def get_by_room1_final_reply_event_id(
        self,
        *,
        room1_final_reply_event_id: str,
    ) -> Room1FinalReplyReactionSnapshot | None:
        """Resolve case by Room-1 final reply event id for cleanup reaction routing."""

    async def claim_cleanup_trigger_if_first(
        self,
        *,
        case_id: UUID,
        reactor_user_id: str,
    ) -> bool:
        """CAS claim of cleanup trigger (first thumbs only) and move status to CLEANUP_RUNNING."""

    async def mark_cleanup_completed(self, *, case_id: UUID) -> None:
        """Set cleanup_completed_at and transition case status to CLEANED."""

    async def list_non_terminal_cases_for_recovery(self) -> list[CaseRecoverySnapshot]:
        """List non-terminal cases used by restart recovery scans."""

    async def list_cases_for_monitoring(
        self,
        *,
        filters: CaseMonitoringListFilter,
    ) -> CaseMonitoringListPage:
        """List cases ordered by latest activity with period/status filters and pagination."""

    async def get_case_monitoring_detail(
        self,
        *,
        case_id: UUID,
    ) -> CaseMonitoringDetail | None:
        """Return case status and unified chronological timeline by case id."""

    async def update_status(self, *, case_id: UUID, status: CaseStatus) -> None:
        """Update case status and touch updated_at timestamp."""

    async def store_pdf_extraction(
        self,
        *,
        case_id: UUID,
        pdf_mxc_url: str,
        extracted_text: str,
        agency_record_number: str | None = None,
        agency_record_extracted_at: datetime | None = None,
    ) -> None:
        """Persist PDF source, extracted/cleaned text, and optional record extraction fields."""

    async def append_case_report_transcript(
        self,
        *,
        case_id: UUID,
        extracted_text: str,
    ) -> None:
        """Append full extracted report text for audit retrieval by case."""

    async def append_case_llm_interaction(self, payload: CaseLlmInteractionCreateInput) -> None:
        """Append one LLM interaction transcript row linked to case id."""

    async def store_llm1_artifacts(
        self,
        *,
        case_id: UUID,
        structured_data_json: dict[str, Any],
        summary_text: str,
    ) -> None:
        """Persist validated LLM1 structured payload and summary text."""

    async def store_llm2_artifacts(
        self,
        *,
        case_id: UUID,
        suggested_action_json: dict[str, Any],
    ) -> None:
        """Persist validated and policy-reconciled LLM2 suggestion payload."""
