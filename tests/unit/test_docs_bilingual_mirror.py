from __future__ import annotations

from pathlib import Path

_DOC_NAMES = (
    "architecture.md",
    "manual_e2e_runbook.md",
    "runtime-smoke.md",
    "security.md",
    "setup.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_docs_portuguese_default_have_english_links_and_mirror_files() -> None:
    for name in _DOC_NAMES:
        pt_path = Path("docs") / name
        en_path = Path("docs/en") / name

        assert pt_path.exists()
        assert en_path.exists()

        pt_content = _read(pt_path)
        assert f"Idioma: **Portugues (BR)** | [English](en/{name})" in pt_content


def test_docs_english_mirror_have_portuguese_links() -> None:
    for name in _DOC_NAMES:
        en_path = Path("docs/en") / name
        en_content = _read(en_path)
        assert f"Language: [Portugues (BR)](../{name}) | **English**" in en_content
