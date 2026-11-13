"""KVKK ve kullanım metinleri. Metin değişince LEGAL_VERSION artırılır; kullanıcıdan yeniden onay istenir."""

from pathlib import Path

LEGAL_VERSION = "2026-11-13.3"
LEGAL_DIR = Path(__file__).parent

DOCUMENTS = {
    "aydinlatma": "aydinlatma-metni.md",
    "acik-riza": "acik-riza-metni.md",
    "kullanim-kosullari": "kullanim-kosullari.md",
    "cerez": "cerez-ve-yerel-depolama.md",
}


def read_document(slug: str) -> str | None:
    name = DOCUMENTS.get(slug)
    if name is None:
        return None
    return (LEGAL_DIR / name).read_text(encoding="utf-8")
