"""Service for posting Room-2 root message plus structured reply context messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import (
    CaseRepositoryPort,
    CaseRoom2WidgetSnapshot,
)
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    MessageRepositoryPort,
)
from triage_automation.application.ports.prior_case_query_port import (
    PriorCaseContext,
    PriorCaseQueryPort,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.matrix.message_templates import (
    build_room2_case_decision_instructions_formatted_html,
    build_room2_case_decision_instructions_message,
    build_room2_case_pdf_formatted_html,
    build_room2_case_pdf_message,
    build_room2_case_summary_formatted_html,
    build_room2_case_summary_message,
    build_room2_case_text_attachment_filename,
)

logger = logging.getLogger(__name__)


class MatrixRoomPosterPort(Protocol):
    """Port used to post standard text messages into Matrix rooms."""

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        """Post text body to a room and return generated matrix event id."""

    async def reply_text(
        self,
        *,
        room_id: str,
        event_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        """Post reply text body to a room event and return generated matrix event id."""

    async def reply_file_text(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        text_content: str,
    ) -> str:
        """Post a text file attachment as reply and return generated matrix event id."""


@dataclass
class PostRoom2WidgetRetriableError(RuntimeError):
    """Retriable posting error with explicit failure cause category."""

    cause: str
    details: str

    def __str__(self) -> str:
        return f"{self.cause}: {self.details}"


class PostRoom2WidgetService:
    """Build Room-2 payload, post root + reply context messages, and advance case status."""

    def __init__(
        self,
        *,
        room2_id: str,
        widget_public_base_url: str,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        message_repository: MessageRepositoryPort,
        prior_case_queries: PriorCaseQueryPort,
        matrix_poster: MatrixRoomPosterPort,
    ) -> None:
        self._room2_id = room2_id
        self._widget_public_base_url = widget_public_base_url.rstrip("/")
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._message_repository = message_repository
        self._prior_case_queries = prior_case_queries
        self._matrix_poster = matrix_poster

    async def post_widget(self, *, case_id: UUID) -> dict[str, object]:
        """Post Room-2 root message and two context replies for doctor review."""

        logger.info("room2_widget_post_started case_id=%s", case_id)
        case = await self._case_repository.get_case_room2_widget_snapshot(case_id=case_id)
        if case is None:
            raise PostRoom2WidgetRetriableError(cause="room2", details="Case not found")

        if case.status not in {CaseStatus.LLM_SUGGEST, CaseStatus.R2_POST_WIDGET}:
            raise PostRoom2WidgetRetriableError(
                cause="room2",
                details=f"Case status {case.status.value} is not ready for Room-2 widget post",
            )

        if case.extracted_text is None or not case.extracted_text.strip():
            raise PostRoom2WidgetRetriableError(
                cause="room2",
                details="Missing extracted_text for Room-2 case context post",
            )
        if case.agency_record_number is None:
            raise PostRoom2WidgetRetriableError(
                cause="room2",
                details="Missing agency_record_number for Room-2 widget",
            )
        if case.structured_data_json is None:
            raise PostRoom2WidgetRetriableError(
                cause="room2",
                details="Missing structured_data_json for Room-2 widget",
            )
        if case.summary_text is None:
            raise PostRoom2WidgetRetriableError(
                cause="room2",
                details="Missing summary_text for Room-2 widget",
            )
        if case.suggested_action_json is None:
            raise PostRoom2WidgetRetriableError(
                cause="room2",
                details="Missing suggested_action_json for Room-2 widget",
            )
        structured_data_json = case.structured_data_json
        summary_text = case.summary_text
        suggested_action_json = case.suggested_action_json
        assert structured_data_json is not None
        assert summary_text is not None
        assert suggested_action_json is not None

        prior_context = await self._prior_case_queries.lookup_recent_context(
            case_id=case_id,
            agency_record_number=case.agency_record_number,
            now=datetime.now(tz=UTC),
        )
        logger.info(
            "room2_widget_prior_lookup case_id=%s prior_case_found=%s prior_denial_count_7d=%s",
            case_id,
            prior_context.prior_case is not None,
            prior_context.prior_denial_count_7d,
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="system",
                event_type="PRIOR_CASE_LOOKUP_COMPLETED",
                payload={
                    "agency_record_number": case.agency_record_number,
                    "prior_case_found": prior_context.prior_case is not None,
                    "prior_case_id": (
                        str(prior_context.prior_case.prior_case_id)
                        if prior_context.prior_case is not None
                        else None
                    ),
                    "prior_denial_count_7d": prior_context.prior_denial_count_7d,
                },
            )
        )

        root_body = build_room2_case_pdf_message(
            case_id=case.case_id,
            agency_record_number=case.agency_record_number,
            extracted_text=case.extracted_text,
        )
        root_formatted_body = build_room2_case_pdf_formatted_html(
            case_id=case.case_id,
            agency_record_number=case.agency_record_number,
            extracted_text=case.extracted_text,
        )
        root_event_id = await self._matrix_poster.send_text(
            room_id=self._room2_id,
            body=root_body,
            formatted_body=root_formatted_body,
        )
        logger.info(
            "room2_widget_posted case_id=%s room_id=%s event_id=%s",
            case.case_id,
            self._room2_id,
            root_event_id,
        )

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case.case_id,
                room_id=self._room2_id,
                event_id=root_event_id,
                sender_user_id=None,
                kind="room2_case_root",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case.case_id,
                actor_type="bot",
                room_id=self._room2_id,
                matrix_event_id=root_event_id,
                event_type="ROOM2_WIDGET_POSTED",
                payload={
                    "case_id": str(case.case_id),
                    "record_number": case.agency_record_number,
                },
            )
        )

        text_attachment_filename = build_room2_case_text_attachment_filename(
            case_id=case.case_id
        )
        text_attachment_event_id = await self._matrix_poster.reply_file_text(
            room_id=self._room2_id,
            event_id=root_event_id,
            filename=text_attachment_filename,
            text_content=case.extracted_text,
        )
        logger.info(
            (
                "room2_context_attachment_posted case_id=%s room_id=%s event_id=%s "
                "parent_event_id=%s"
            ),
            case.case_id,
            self._room2_id,
            text_attachment_event_id,
            root_event_id,
        )

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case.case_id,
                room_id=self._room2_id,
                event_id=text_attachment_event_id,
                sender_user_id=None,
                kind="room2_case_text_attachment",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case.case_id,
                actor_type="bot",
                room_id=self._room2_id,
                matrix_event_id=text_attachment_event_id,
                event_type="ROOM2_CASE_TEXT_ATTACHMENT_POSTED",
                payload={
                    "reply_to_event_id": root_event_id,
                    "filename": text_attachment_filename,
                },
            )
        )

        summary_body = build_room2_case_summary_message(
            case_id=case.case_id,
            structured_data=structured_data_json,
            summary_text=summary_text,
            suggested_action=suggested_action_json,
        )
        summary_formatted_body = build_room2_case_summary_formatted_html(
            case_id=case.case_id,
            structured_data=structured_data_json,
            summary_text=summary_text,
            suggested_action=suggested_action_json,
        )
        summary_event_id = await self._matrix_poster.reply_text(
            room_id=self._room2_id,
            event_id=root_event_id,
            body=summary_body,
            formatted_body=summary_formatted_body,
        )
        logger.info(
            "room2_summary_posted case_id=%s room_id=%s event_id=%s parent_event_id=%s",
            case.case_id,
            self._room2_id,
            summary_event_id,
            root_event_id,
        )

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case.case_id,
                room_id=self._room2_id,
                event_id=summary_event_id,
                sender_user_id=None,
                kind="room2_case_summary",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case.case_id,
                actor_type="bot",
                room_id=self._room2_id,
                matrix_event_id=summary_event_id,
                event_type="ROOM2_CASE_SUMMARY_POSTED",
                payload={"reply_to_event_id": root_event_id},
            )
        )

        instructions_body = build_room2_case_decision_instructions_message(
            case_id=case.case_id
        )
        instructions_formatted_body = build_room2_case_decision_instructions_formatted_html(
            case_id=case.case_id
        )
        instructions_event_id = await self._matrix_poster.reply_text(
            room_id=self._room2_id,
            event_id=root_event_id,
            body=instructions_body,
            formatted_body=instructions_formatted_body,
        )
        logger.info(
            (
                "room2_instructions_posted case_id=%s room_id=%s event_id=%s "
                "parent_event_id=%s"
            ),
            case.case_id,
            self._room2_id,
            instructions_event_id,
            root_event_id,
        )

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case.case_id,
                room_id=self._room2_id,
                event_id=instructions_event_id,
                sender_user_id=None,
                kind="room2_case_instructions",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case.case_id,
                actor_type="bot",
                room_id=self._room2_id,
                matrix_event_id=instructions_event_id,
                event_type="ROOM2_CASE_INSTRUCTIONS_POSTED",
                payload={"reply_to_event_id": root_event_id},
            )
        )

        status_before_wait = case.status
        if case.status == CaseStatus.LLM_SUGGEST:
            await self._case_repository.update_status(
                case_id=case.case_id,
                status=CaseStatus.R2_POST_WIDGET,
            )
            status_before_wait = CaseStatus.R2_POST_WIDGET

        await self._case_repository.update_status(
            case_id=case.case_id,
            status=CaseStatus.WAIT_DOCTOR,
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case.case_id,
                actor_type="system",
                event_type="CASE_STATUS_CHANGED",
                payload={
                    "from_status": status_before_wait.value,
                    "to_status": CaseStatus.WAIT_DOCTOR.value,
                },
            )
        )

        logger.info(
            "room2_widget_post_completed case_id=%s to_status=%s",
            case.case_id,
            CaseStatus.WAIT_DOCTOR.value,
        )
        return {}


def _build_widget_payload(
    *,
    case: CaseRoom2WidgetSnapshot,
    prior_context: PriorCaseContext,
    widget_public_base_url: str,
) -> dict[str, object]:
    assert case.agency_record_number is not None
    assert case.structured_data_json is not None
    assert case.summary_text is not None
    assert case.suggested_action_json is not None

    structured_data = case.structured_data_json
    suggested_action_json = case.suggested_action_json

    payload: dict[str, object] = {
        "case_id": str(case.case_id),
        "agency_record_number": case.agency_record_number,
        "structured_data": structured_data,
        "summary": case.summary_text,
        "suggested_action": {
            "suggestion": _extract_suggestion(suggested_action_json),
        },
        "widget_launch": {
            "case_id": str(case.case_id),
            "url": _build_widget_launch_url(
                widget_public_base_url=widget_public_base_url,
                case_id=case.case_id,
            ),
            "bootstrap_path": "/widget/room2/bootstrap",
            "submit_path": "/widget/room2/submit",
        },
    }

    rationale = _extract_rationale(suggested_action_json)
    if rationale is not None:
        casted_suggested_action = payload["suggested_action"]
        assert isinstance(casted_suggested_action, dict)
        casted_suggested_action["rationale"] = rationale

    policy_precheck = structured_data.get("policy_precheck")
    if isinstance(policy_precheck, dict):
        payload["policy_precheck"] = policy_precheck

    asa = _extract_nested_dict(structured_data, "eda", "asa")
    if asa is not None:
        payload["asa"] = asa

    cardiovascular_risk = _extract_nested_dict(structured_data, "eda", "cardiovascular_risk")
    if cardiovascular_risk is not None:
        payload["cardiovascular_risk"] = cardiovascular_risk

    support_recommendation = suggested_action_json.get("support_recommendation")
    if isinstance(support_recommendation, str):
        payload["llm_support_recommendation"] = support_recommendation

    if prior_context.prior_case is not None:
        payload["prior_case"] = {
            "prior_case_id": str(prior_context.prior_case.prior_case_id),
            "decided_at": prior_context.prior_case.decided_at.isoformat(),
            "decision": prior_context.prior_case.decision,
            "reason": prior_context.prior_case.reason,
        }
        if prior_context.prior_denial_count_7d is not None:
            payload["prior_denial_count_7d"] = prior_context.prior_denial_count_7d

    return payload


def _build_widget_launch_url(*, widget_public_base_url: str, case_id: UUID) -> str:
    """Return deterministic Room-2 widget launch URL bound to the case identifier."""

    return f"{widget_public_base_url}/widget/room2?case_id={case_id}"


def _extract_suggestion(suggested_action_json: dict[str, Any]) -> str:
    value = suggested_action_json.get("suggestion")
    if isinstance(value, str):
        return value
    raise PostRoom2WidgetRetriableError(
        cause="room2",
        details="suggested_action_json.suggestion must be a string",
    )


def _extract_rationale(suggested_action_json: dict[str, Any]) -> str | None:
    value = suggested_action_json.get("rationale")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        short_reason = value.get("short_reason")
        if isinstance(short_reason, str):
            return short_reason
    return None


def _extract_nested_dict(
    payload: dict[str, Any],
    key: str,
    nested_key: str,
) -> dict[str, Any] | None:
    value = payload.get(key)
    if not isinstance(value, dict):
        return None
    nested = value.get(nested_key)
    if not isinstance(nested, dict):
        return None
    return nested
