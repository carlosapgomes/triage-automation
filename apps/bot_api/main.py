"""bot-api entrypoint and HTTP route wiring."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from triage_automation.application.dto.webhook_models import (
    TriageDecisionWebhookPayload,
    TriageDecisionWebhookResponse,
)
from triage_automation.application.ports.auth_token_repository_port import (
    AuthTokenRepositoryPort,
)
from triage_automation.application.services.auth_service import AuthService
from triage_automation.application.services.handle_doctor_decision_service import (
    HandleDoctorDecisionOutcome,
    HandleDoctorDecisionService,
)
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.auth_event_repository import SqlAlchemyAuthEventRepository
from triage_automation.infrastructure.db.auth_token_repository import SqlAlchemyAuthTokenRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.user_repository import SqlAlchemyUserRepository
from triage_automation.infrastructure.http.auth_router import build_auth_router
from triage_automation.infrastructure.http.hmac_auth import verify_hmac_signature
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher
from triage_automation.infrastructure.security.token_service import OpaqueTokenService

BOT_API_HOST = "0.0.0.0"
BOT_API_PORT = 8000


def build_decision_service(database_url: str) -> HandleDoctorDecisionService:
    """Build decision handling service with SQLAlchemy-backed dependencies."""

    session_factory = create_session_factory(database_url)
    return HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
    )


def build_auth_service(database_url: str) -> AuthService:
    """Build authentication service with SQLAlchemy-backed dependencies."""

    session_factory = create_session_factory(database_url)
    return AuthService(
        users=SqlAlchemyUserRepository(session_factory),
        auth_events=SqlAlchemyAuthEventRepository(session_factory),
        password_hasher=BcryptPasswordHasher(),
    )


def build_auth_token_repository(database_url: str) -> AuthTokenRepositoryPort:
    """Build opaque auth token repository with SQLAlchemy session factory."""

    session_factory = create_session_factory(database_url)
    return SqlAlchemyAuthTokenRepository(session_factory)


def create_app(
    *,
    webhook_hmac_secret: str | None = None,
    decision_service: HandleDoctorDecisionService | None = None,
    auth_service: AuthService | None = None,
    auth_token_repository: AuthTokenRepositoryPort | None = None,
    token_service: OpaqueTokenService | None = None,
    database_url: str | None = None,
) -> FastAPI:
    """Create FastAPI app for webhook callbacks and login foundation routes."""

    should_load_settings = webhook_hmac_secret is None or decision_service is None
    if should_load_settings or (
        database_url is None and (auth_service is None or auth_token_repository is None)
    ):
        settings = load_settings()
        if webhook_hmac_secret is None:
            webhook_hmac_secret = settings.webhook_hmac_secret
        if database_url is None:
            database_url = settings.database_url
        if decision_service is None:
            decision_service = build_decision_service(database_url)

    if auth_service is None:
        assert database_url is not None
        auth_service = build_auth_service(database_url)
    if auth_token_repository is None:
        assert database_url is not None
        auth_token_repository = build_auth_token_repository(database_url)
    if token_service is None:
        token_service = OpaqueTokenService()

    assert decision_service is not None
    assert webhook_hmac_secret is not None
    assert auth_service is not None
    assert auth_token_repository is not None
    assert token_service is not None

    app = FastAPI()
    app.include_router(
        build_auth_router(
            auth_service=auth_service,
            auth_token_repository=auth_token_repository,
            token_service=token_service,
        )
    )

    @app.post(
        "/callbacks/triage-decision",
        response_model=TriageDecisionWebhookResponse,
    )
    async def triage_decision_callback(request: Request) -> TriageDecisionWebhookResponse:
        raw_body = await request.body()
        signature = request.headers.get("x-signature")

        if not verify_hmac_signature(
            secret=webhook_hmac_secret,
            body=raw_body,
            provided_signature=signature,
        ):
            raise HTTPException(status_code=401, detail="invalid signature")

        try:
            payload = TriageDecisionWebhookPayload.model_validate_json(raw_body)
        except ValidationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        result = await decision_service.handle(payload)

        if result.outcome is HandleDoctorDecisionOutcome.NOT_FOUND:
            raise HTTPException(status_code=404, detail="case not found")

        if result.outcome is HandleDoctorDecisionOutcome.WRONG_STATE:
            raise HTTPException(status_code=409, detail="case not in WAIT_DOCTOR")

        return TriageDecisionWebhookResponse(ok=True)

    return app


def build_runtime_app(
    *,
    webhook_hmac_secret: str | None = None,
    decision_service: HandleDoctorDecisionService | None = None,
    auth_service: AuthService | None = None,
    auth_token_repository: AuthTokenRepositoryPort | None = None,
    token_service: OpaqueTokenService | None = None,
    database_url: str | None = None,
) -> FastAPI:
    """Build runtime FastAPI application preserving existing endpoint contracts."""

    return create_app(
        webhook_hmac_secret=webhook_hmac_secret,
        decision_service=decision_service,
        auth_service=auth_service,
        auth_token_repository=auth_token_repository,
        token_service=token_service,
        database_url=database_url,
    )


def run_asgi_server(*, host: str = BOT_API_HOST, port: int = BOT_API_PORT) -> None:
    """Run bot-api as a long-lived ASGI process using application factory mode."""

    uvicorn.run(
        "apps.bot_api.main:create_app",
        host=host,
        port=port,
        factory=True,
    )


def main() -> None:
    """Run bot-api runtime process."""

    run_asgi_server()


if __name__ == "__main__":
    main()
