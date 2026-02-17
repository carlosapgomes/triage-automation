from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_runtime_smoke_runbook_exists_and_covers_required_flows() -> None:
    runbook = _read("docs/runtime-smoke.md")
    uvicorn_cmd = (
        "uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000"
    )

    assert "## Local UV Runtime Smoke" in runbook
    assert "## Cloudflare Tunnel Webhook Validation" in runbook
    assert "## Deterministic LLM Smoke Path" in runbook
    assert uvicorn_cmd in runbook
    assert "uv run python -m apps.bot_matrix.main" in runbook
    assert "uv run python -m apps.worker.main" in runbook
    assert "curl -i -X POST \"http://127.0.0.1:8000/callbacks/triage-decision\"" in runbook
    assert "x-signature" in runbook


def test_runtime_smoke_runbook_parity_with_compose_commands() -> None:
    compose = _read("docker-compose.yml")
    runbook = _read("docs/runtime-smoke.md")
    compose_uvicorn_cmd = (
        'command: ["uv", "run", "uvicorn", "apps.bot_api.main:create_app", '
        '"--factory", "--host", "0.0.0.0", "--port", "8000"]'
    )

    assert compose_uvicorn_cmd in compose
    assert 'command: ["uv", "run", "python", "-m", "apps.bot_matrix.main"]' in compose
    assert 'command: ["uv", "run", "python", "-m", "apps.worker.main"]' in compose

    assert "docker compose up --build" in runbook
    assert "docker compose logs -f bot-api bot-matrix worker" in runbook


def test_manual_e2e_runbook_exists_and_covers_matrix_reply_positive_flow() -> None:
    runbook = _read("docs/manual_e2e_runbook.md")

    assert "## Room-2 Structured Reply Positive Path" in runbook
    assert "message I" in runbook
    assert "message II" in runbook
    assert "message III" in runbook
    assert "reply to message I" in runbook
    assert "desktop" in runbook
    assert "mobile" in runbook
    assert "DOCTOR_ACCEPTED" in runbook
    assert "post_room3_request" in runbook


def test_manual_e2e_runbook_defines_widget_negative_auth_checks() -> None:
    runbook = _read("docs/manual_e2e_runbook.md")

    assert "## Widget Negative Auth Checks" in runbook
    assert "without Authorization" in runbook
    assert "reader role token" in runbook
    assert "401" in runbook
    assert "403" in runbook
    assert "state/job mutation" in runbook


def test_manual_e2e_runbook_defines_room2_negative_reply_checks() -> None:
    runbook = _read("docs/manual_e2e_runbook.md")

    assert "## Room-2 Negative Reply Checks" in runbook
    assert "malformed template" in runbook
    assert "wrong reply-parent" in runbook
    assert "error_code: invalid_template" in runbook
    assert "no decision mutation" in runbook
