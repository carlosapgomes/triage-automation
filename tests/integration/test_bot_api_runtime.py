from __future__ import annotations

from fastapi.routing import APIRoute

from apps.bot_api import main as bot_api_main
from triage_automation.infrastructure.security.token_service import OpaqueTokenService


class _DummyDecisionService:
    async def handle(self, payload: object) -> object:
        _ = payload
        raise RuntimeError("not used in route-shape test")


class _DummyAuthService:
    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str,
    ) -> object:
        _ = email, password, ip_address, user_agent
        raise RuntimeError("not used in route-shape test")


class _DummyAuthTokenRepository:
    async def create_token(self, payload: object) -> object:
        _ = payload
        raise RuntimeError("not used in route-shape test")


def test_main_starts_uvicorn_with_factory(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        bot_api_main,
        "uvicorn",
        type("UvicornStub", (), {"run": _fake_run}),
        raising=False,
    )

    bot_api_main.main()

    assert captured["app"] == "apps.bot_api.main:create_app"
    assert captured["kwargs"] == {"host": "0.0.0.0", "port": 8000, "factory": True}


def test_build_runtime_app_exposes_existing_route_paths() -> None:
    app = bot_api_main.build_runtime_app(
        webhook_hmac_secret="runtime-secret",
        decision_service=_DummyDecisionService(),
        auth_service=_DummyAuthService(),
        auth_token_repository=_DummyAuthTokenRepository(),
        token_service=OpaqueTokenService(),
        database_url="sqlite+aiosqlite:///unused.db",
    )

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert paths == {"/auth/login", "/callbacks/triage-decision"}
