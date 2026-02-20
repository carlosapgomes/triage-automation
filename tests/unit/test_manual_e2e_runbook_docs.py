from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_runtime_smoke_runbook_exists_and_covers_required_flows() -> None:
    runbook = _read("docs/runtime-smoke.md")
    uvicorn_cmd = (
        "uv run uvicorn apps.bot_api.main:create_app --factory --host 0.0.0.0 --port 8000"
    )

    assert "## Smoke local com UV" in runbook
    assert "## Caminho deterministico de LLM no smoke" in runbook
    assert uvicorn_cmd in runbook
    assert "uv run python -m apps.bot_matrix.main" in runbook
    assert "uv run python -m apps.worker.main" in runbook
    assert "respostas estruturadas Matrix" in runbook
    assert "/callbacks/triage-decision" not in runbook
    assert "x-signature" not in runbook


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


def test_runtime_smoke_runbook_declares_matrix_only_decision_path() -> None:
    runbook = _read("docs/runtime-smoke.md")

    assert "/callbacks/triage-decision" not in runbook
    assert "Cloudflare Tunnel Webhook Validation" not in runbook
    assert "decisoes padrao da Sala 2 usam respostas estruturadas Matrix" in runbook


def test_manual_e2e_runbook_exists_and_covers_matrix_reply_positive_flow() -> None:
    runbook = _read("docs/manual_e2e_runbook.md")

    assert "## Caminho positivo de resposta estruturada da Sala 2" in runbook
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

    assert "## Checagens negativas de auth do widget" in runbook
    assert "without Authorization" in runbook
    assert "reader role token" in runbook
    assert "401" in runbook
    assert "403" in runbook
    assert "state/job mutation" in runbook


def test_manual_e2e_runbook_defines_room2_negative_reply_checks() -> None:
    runbook = _read("docs/manual_e2e_runbook.md")

    assert "## Checagens negativas de reply da Sala 2" in runbook
    assert "malformed template" in runbook
    assert "wrong reply-parent" in runbook
    assert "error_code: invalid_template" in runbook
    assert "no decision mutation" in runbook


def test_manual_e2e_runbook_defines_dashboard_api_and_auditable_timeline_checks() -> None:
    runbook = _read("docs/manual_e2e_runbook.md")

    assert "## Checagens de dashboard e API de monitoramento" in runbook
    assert "/dashboard/cases" in runbook
    assert "/monitoring/cases" in runbook
    assert "/monitoring/cases/{case_id}" in runbook
    assert "chronological timeline" in runbook
    assert "ACK" in runbook
    assert "human reply" in runbook


def test_manual_e2e_runbook_defines_prompt_authorization_flow_checks() -> None:
    runbook = _read("docs/manual_e2e_runbook.md")

    assert "## Fluxo de autorizacao de gerenciamento de prompts" in runbook
    assert "/admin/prompts/versions" in runbook
    assert "/admin/prompts/{prompt_name}/active" in runbook
    assert "/admin/prompts/{prompt_name}/activate" in runbook
    assert "reader token" in runbook
    assert "admin token" in runbook
    assert "403" in runbook
    assert "200" in runbook
    assert "prompt_version_activated" in runbook
