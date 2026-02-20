from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_setup_doc_runtime_section_is_matrix_only() -> None:
    setup = _read("docs/setup.md")

    assert "webhook HMAC validation" not in setup
    assert "Cloudflare tunnel callback reachability" not in setup
    assert "WEBHOOK_PUBLIC_URL" not in setup
    assert "WIDGET_PUBLIC_URL" not in setup
    assert "WEBHOOK_HMAC_SECRET" not in setup
    assert "respostas estruturadas Matrix" in setup


def test_architecture_doc_no_longer_describes_webhook_callback_surface() -> None:
    architecture = _read("docs/architecture.md")

    assert "HTTP ingress for webhook callbacks" not in architecture
    assert "Webhook callback route" not in architecture
    assert "bot-api" in architecture


def test_readme_no_longer_exposes_callback_as_runtime_contract() -> None:
    readme = _read("README.md")

    assert "POST /callbacks/triage-decision" not in readme
    assert "Webhook Callback ---> bot-api" not in readme
    assert "bot-api" in readme
