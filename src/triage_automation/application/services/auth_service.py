"""Application authentication service for credential verification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from triage_automation.application.ports.auth_event_repository_port import (
    AuthEventCreateInput,
    AuthEventRepositoryPort,
)
from triage_automation.application.ports.password_hasher_port import PasswordHasherPort
from triage_automation.application.ports.user_repository_port import UserRecord, UserRepositoryPort


class AuthOutcome(StrEnum):
    """Supported authentication outcomes."""

    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    INACTIVE_USER = "inactive_user"


@dataclass(frozen=True)
class AuthResult:
    """Authentication result model."""

    outcome: AuthOutcome
    user: UserRecord | None = None


class AuthService:
    """Authenticate credentials and append auth audit events."""

    def __init__(
        self,
        *,
        users: UserRepositoryPort,
        auth_events: AuthEventRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        self._users = users
        self._auth_events = auth_events
        self._password_hasher = password_hasher

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AuthResult:
        """Authenticate user credentials and always emit auth event."""

        user = await self._users.get_by_email(email=email)
        if user is None:
            await self._auth_events.append_event(
                AuthEventCreateInput(
                    user_id=None,
                    event_type="login_failed",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    payload={"email": email, "reason": "invalid_credentials"},
                )
            )
            return AuthResult(outcome=AuthOutcome.INVALID_CREDENTIALS, user=None)

        if not user.is_active:
            await self._auth_events.append_event(
                AuthEventCreateInput(
                    user_id=user.user_id,
                    event_type="login_blocked_inactive",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    payload={"email": email},
                )
            )
            return AuthResult(outcome=AuthOutcome.INACTIVE_USER, user=None)

        is_valid = self._password_hasher.verify_password(
            password=password,
            password_hash=user.password_hash,
        )
        if not is_valid:
            await self._auth_events.append_event(
                AuthEventCreateInput(
                    user_id=user.user_id,
                    event_type="login_failed",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    payload={"email": email, "reason": "invalid_credentials"},
                )
            )
            return AuthResult(outcome=AuthOutcome.INVALID_CREDENTIALS, user=None)

        await self._auth_events.append_event(
            AuthEventCreateInput(
                user_id=user.user_id,
                event_type="login_success",
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"email": email, "role": user.role.value},
            )
        )
        return AuthResult(outcome=AuthOutcome.SUCCESS, user=user)
