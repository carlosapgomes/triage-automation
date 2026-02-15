"""bot-matrix entrypoint."""

from __future__ import annotations

from triage_automation.application.services.room1_intake_service import Room1IntakeService
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory


class _PlaceholderMatrixPoster:
    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        raise NotImplementedError("Matrix client integration is implemented in later slices")


def build_room1_intake_service() -> Room1IntakeService:
    """Build Room-1 intake service dependencies for bot-matrix runtime."""

    settings = load_settings()
    session_factory = create_session_factory(settings.database_url)

    return Room1IntakeService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        matrix_poster=_PlaceholderMatrixPoster(),
    )


def main() -> None:
    """Initialize bot-matrix runtime dependencies."""

    build_room1_intake_service()


if __name__ == "__main__":
    main()
