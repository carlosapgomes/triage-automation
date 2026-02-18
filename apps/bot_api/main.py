"""bot-api entrypoint and HTTP route wiring."""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI

from triage_automation.application.ports.auth_token_repository_port import (
    AuthTokenRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import CaseRepositoryPort
from triage_automation.application.ports.user_repository_port import UserRepositoryPort
from triage_automation.application.services.auth_service import AuthService
from triage_automation.application.services.case_monitoring_service import CaseMonitoringService
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.db.auth_event_repository import SqlAlchemyAuthEventRepository
from triage_automation.infrastructure.db.auth_token_repository import SqlAlchemyAuthTokenRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.user_repository import SqlAlchemyUserRepository
from triage_automation.infrastructure.http.auth_guard import WidgetAuthGuard
from triage_automation.infrastructure.http.auth_router import build_auth_router
from triage_automation.infrastructure.http.dashboard_router import build_dashboard_router
from triage_automation.infrastructure.http.monitoring_router import build_monitoring_router
from triage_automation.infrastructure.logging import configure_logging
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher
from triage_automation.infrastructure.security.token_service import OpaqueTokenService

BOT_API_HOST = "0.0.0.0"
BOT_API_PORT = 8000
logger = logging.getLogger(__name__)


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


def build_user_repository(database_url: str) -> UserRepositoryPort:
    """Build user repository with SQLAlchemy session factory."""

    session_factory = create_session_factory(database_url)
    return SqlAlchemyUserRepository(session_factory)


def build_case_repository(database_url: str) -> CaseRepositoryPort:
    """Build case repository with SQLAlchemy session factory."""

    session_factory = create_session_factory(database_url)
    return SqlAlchemyCaseRepository(session_factory)


def create_app(
    *,
    auth_service: AuthService | None = None,
    auth_token_repository: AuthTokenRepositoryPort | None = None,
    user_repository: UserRepositoryPort | None = None,
    case_repository: CaseRepositoryPort | None = None,
    monitoring_service: CaseMonitoringService | None = None,
    auth_guard: WidgetAuthGuard | None = None,
    token_service: OpaqueTokenService | None = None,
    database_url: str | None = None,
) -> FastAPI:
    """Create FastAPI app for runtime routes."""

    if database_url is None or auth_service is None or auth_token_repository is None:
        settings = load_settings()
        if database_url is None:
            database_url = settings.database_url
        configure_logging(level=settings.log_level)

    if auth_service is None:
        assert database_url is not None
        auth_service = build_auth_service(database_url)
    if auth_token_repository is None:
        assert database_url is not None
        auth_token_repository = build_auth_token_repository(database_url)
    if user_repository is None:
        assert database_url is not None
        user_repository = build_user_repository(database_url)
    if case_repository is None:
        assert database_url is not None
        case_repository = build_case_repository(database_url)
    if token_service is None:
        token_service = OpaqueTokenService()
    if monitoring_service is None:
        monitoring_service = CaseMonitoringService(case_repository=case_repository)
    if auth_guard is None:
        auth_guard = WidgetAuthGuard(
            token_service=token_service,
            auth_token_repository=auth_token_repository,
            user_repository=user_repository,
        )

    assert auth_service is not None
    assert auth_token_repository is not None
    assert monitoring_service is not None
    assert auth_guard is not None
    assert token_service is not None
    assert database_url is not None

    app = FastAPI()
    app.include_router(
        build_auth_router(
            auth_service=auth_service,
            auth_token_repository=auth_token_repository,
            token_service=token_service,
        )
    )
    app.include_router(
        build_monitoring_router(
            monitoring_service=monitoring_service,
            auth_guard=auth_guard,
        )
    )
    app.include_router(build_dashboard_router(monitoring_service=monitoring_service))

    return app


def build_runtime_app(
    *,
    auth_service: AuthService | None = None,
    auth_token_repository: AuthTokenRepositoryPort | None = None,
    user_repository: UserRepositoryPort | None = None,
    case_repository: CaseRepositoryPort | None = None,
    monitoring_service: CaseMonitoringService | None = None,
    auth_guard: WidgetAuthGuard | None = None,
    token_service: OpaqueTokenService | None = None,
    database_url: str | None = None,
) -> FastAPI:
    """Build runtime FastAPI application preserving existing endpoint contracts."""

    return create_app(
        auth_service=auth_service,
        auth_token_repository=auth_token_repository,
        user_repository=user_repository,
        case_repository=case_repository,
        monitoring_service=monitoring_service,
        auth_guard=auth_guard,
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
