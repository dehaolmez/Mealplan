"""OSM'deki şube adı/markasını katalogdaki market zinciriyle eşleştirir.

OSM verisi gönüllüler tarafından girildiği için yazımlar tutarsızdır: "BİM", "Bim", "BIM Birleşik Mağazalar",
"A-101", "Şok Market", "Migros Jet"… Hepsini Türkçe karakterleri sadeleştirilmiş, noktalama temizlenmiş
biçimde karşılaştırırız.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

_TR_FOLD = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u"})


def normalize(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "ı").lower().translate(_TR_FOLD)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class ChainPattern:
    chain_id: int
    alias: str  # normalize edilmiş


def build_patterns(chains: Iterable[tuple[int, str, str]]) -> list[ChainPattern]:
    """chains: (id, ad, virgüllü takma adlar). Uzun takma adlar önce denenir (ör. 'migros jet' > 'migros')."""
    patterns = []
    for chain_id, name, aliases in chains:
        for alias in {name, *aliases.split(",")}:
            norm = normalize(alias)
            if norm:
                patterns.append(ChainPattern(chain_id, norm))
    patterns.sort(key=lambda p: len(p.alias), reverse=True)
    return patterns


def match_chain(patterns: list[ChainPattern], *candidates: str | None) -> int | None:
    """Önce `brand`, sonra `name` gibi adayları sırayla dener; takma ad tam kelime olarak geçmeli."""
    for raw in candidates:
        if not raw:
            continue
        text = f" {normalize(raw)} "
        for p in patterns:
            if f" {p.alias} " in text:
                return p.chain_id
    return None
