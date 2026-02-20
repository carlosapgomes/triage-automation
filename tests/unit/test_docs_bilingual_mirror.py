from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_docs_portuguese_default_have_english_links_and_mirror_files() -> None:
    docs_dir = Path("docs")
    doc_names = sorted(path.name for path in docs_dir.glob("*.md"))

    assert doc_names
    for name in doc_names:
        pt_path = Path("docs") / name
        en_path = Path("docs/en") / name

        assert pt_path.exists()
        assert en_path.exists()

        pt_content = _read(pt_path)
        assert f"Idioma: **Portugues (BR)** | [English](en/{name})" in pt_content


def test_docs_english_mirror_have_portuguese_links() -> None:
    for name in sorted(path.name for path in Path("docs/en").glob("*.md")):
        en_path = Path("docs/en") / name
        en_content = _read(en_path)
        assert f"Language: [Portugues (BR)](../{name}) | **English**" in en_content


def test_docs_directory_and_english_mirror_have_matching_file_names() -> None:
    docs_names = {path.name for path in Path("docs").glob("*.md")}
    docs_en_names = {path.name for path in Path("docs/en").glob("*.md")}

    assert docs_names
    assert docs_names == docs_en_names
