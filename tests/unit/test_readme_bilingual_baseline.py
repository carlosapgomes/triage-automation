from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_readme_default_is_portuguese_with_english_link() -> None:
    readme = _read("README.md")

    assert "Idioma: **Portugues (BR)** | [English](README.en.md)" in readme
    assert "servico de backend" in readme
    assert "## Checklist de contribuicao da documentacao bilingue" in readme


def test_english_readme_exists_with_portuguese_link() -> None:
    readme_en_path = Path("README.en.md")
    assert readme_en_path.exists()

    readme_en = readme_en_path.read_text(encoding="utf-8")
    assert "Language: [Portugues (BR)](README.md) | **English**" in readme_en
    assert "backend service" in readme_en
    assert "## Bilingual Documentation Contribution Checklist" in readme_en
