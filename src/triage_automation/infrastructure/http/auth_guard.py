"""Auth header parsing and admin-guard helpers for widget endpoints."""

from __future__ import annotations

from triage_automation.application.ports.auth_token_repository_port import AuthTokenRepositoryPort
from triage_automation.application.ports.user_repository_port import UserRecord, UserRepositoryPort
from triage_automation.application.services.access_guard_service import AccessGuardService
from triage_automation.infrastructure.security.token_service import OpaqueTokenService


class MissingAuthTokenError(PermissionError):
    """Raised when a bearer token is required but not provided."""


class InvalidAuthTokenError(PermissionError):
    """Raised when bearer token header or persisted token is invalid."""


def extract_bearer_token(authorization_header: str | None) -> str:
    """Extract opaque token from standard `Authorization: Bearer <token>` header."""

    if authorization_header is None or not authorization_header.strip():
        raise MissingAuthTokenError("missing bearer token")

    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise InvalidAuthTokenError("invalid bearer token header")

    return parts[1]


class WidgetAuthGuard:
    """Resolve authenticated widget caller and enforce admin-only submit access."""

    def __init__(
        self,
        *,
        token_service: OpaqueTokenService,
        auth_token_repository: AuthTokenRepositoryPort,
        user_repository: UserRepositoryPort,
        access_guard: AccessGuardService | None = None,
    ) -> None:
        self._token_service = token_service
        self._auth_token_repository = auth_token_repository
        self._user_repository = user_repository
        self._access_guard = access_guard or AccessGuardService()

    async def require_admin_user(self, *, authorization_header: str | None) -> UserRecord:
        """Resolve active caller from bearer token and require explicit `admin` role."""

        user = await self._resolve_active_user(authorization_header=authorization_header)
        self._access_guard.require_admin(role=user.role)
        return user

    async def require_audit_user(self, *, authorization_header: str | None) -> UserRecord:
        """Resolve active caller and require dashboard audit-read permission."""

        user = await self._resolve_active_user(authorization_header=authorization_header)
        self._access_guard.require_audit_read(role=user.role)
        return user

    async def _resolve_active_user(self, *, authorization_header: str | None) -> UserRecord:
        """Resolve bearer token to an active persisted user record."""

        token = extract_bearer_token(authorization_header)
        token_hash = self._token_service.hash_token(token)
        token_record = await self._auth_token_repository.get_active_by_hash(token_hash=token_hash)
        if token_record is None:
            raise InvalidAuthTokenError("invalid or expired auth token")

        user = await self._user_repository.get_by_id(user_id=token_record.user_id)
        if user is None or not user.is_active:
            raise InvalidAuthTokenError("invalid or expired auth token")

        return user
