"""Yapay zekâ (Gemini veya Claude) destekli öneri katmanı.

Kural tabanlı motorun ürettiği aday tarifleri; envanter, SKT durumu ve beslenme hedefleriyle birlikte
Claude'a verir. Model adaylar arasından seçim yapar, yeniden sıralar ve her öneri için kısa bir gerekçe
yazar. Model yalnızca aday ID'leri döndürebildiği için eksik malzeme tespiti ve fiyatlandırma
deterministik kalır; model "uydurma" tarif ya da malzeme ekleyemez.

Claude erişilemezse (anahtar yok, ağ hatası, ret vb.) çağıran taraf kural tabanlı sıralamaya döner.
"""

import json
import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.domain.recommender import RecipeMatch

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen Meall adlı bir ev yemek planlama uygulamasının mutfak asistanısın.
Görevin: verilen ADAY tarifler arasından haneye en uygun olanları seçip sıralamak.

Önceliklerin, sırasıyla:
1. Bozulmak üzere olan (days_left küçük) ürünleri tüketerek gıda israfını önlemek.
2. Eksik malzemesi az olan, evdekilerle yapılabilen tarifleri öne almak.
3. Hanenin beslenme hedefine uyum (nutrition_fit, 0-1) ve çeşitlilik (benzer tarifleri arka arkaya önerme).

Yalnızca aday listesindeki recipe_id değerlerini kullan. Her öneri için Türkçe, tek cümlelik,
kullanıcıya hitap eden somut bir gerekçe yaz (ör. hangi ürünü kurtardığını söyle)."""


class AiPick(BaseModel):
    recipe_id: int
    reason: str = Field(description="Türkçe, tek cümlelik gerekçe")


class AiRanking(BaseModel):
    picks: list[AiPick]


@dataclass
class AiResult:
    matches: list[RecipeMatch]
    used: bool
    error: str | None = None


def _candidate_payload(matches: list[RecipeMatch]) -> list[dict]:
    return [
        {
            "recipe_id": m.recipe.id,
            "name": m.recipe.name,
            "tags": m.recipe.tags,
            "prep_minutes": m.recipe.prep_minutes,
            "rule_score": m.score,
            "coverage": m.coverage,
            "kcal_per_serving": m.per_serving.kcal,
            "protein_per_serving_g": m.per_serving.protein_g,
            # Hanenin kişisel hedefine uyum puanı (0-1). Boy/kilo/kalori hedefi gönderilmez (veri minimizasyonu).
            "nutrition_fit": m.nutrition_fit,
            "uses_expiring": [{"item": e.ingredient_name, "days_left": e.days_left} for e in m.uses_expiring],
            "missing": [m_.ingredient.name for m_ in m.missing],
        }
        for m in matches
    ]


RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"recipe_id": {"type": "integer"}, "reason": {"type": "string"}},
                "required": ["recipe_id", "reason"],
            },
        }
    },
    "required": ["picks"],
}


def _apply_picks(matches: list[RecipeMatch], picks: list[AiPick], limit: int) -> AiResult:
    by_id = {m.recipe.id: m for m in matches}
    ranked: list[RecipeMatch] = []
    for pick in picks:
        match = by_id.pop(pick.recipe_id, None)
        if match is None:
            continue  # aday dışı / tekrar eden ID'leri yok say
        match.ai_reason = pick.reason
        ranked.append(match)
        if len(ranked) >= limit:
            break
    if not ranked:
        return AiResult(matches, used=False, error="Yapay zekâ geçerli bir öneri döndürmedi")
    return AiResult(ranked, used=True)


def _user_payload(matches: list[RecipeMatch], inventory_summary: list[dict], limit: int) -> str:
    return json.dumps(
        {"inventory": inventory_summary, "candidates": _candidate_payload(matches), "return_at_most": limit},
        ensure_ascii=False,
    )


def rerank_with_gemini(matches: list[RecipeMatch], *, inventory_summary: list[dict], limit: int) -> AiResult:
    if not matches:
        return AiResult(matches, used=False)
    from app.services import gemini

    try:
        data = gemini.generate_json(SYSTEM_PROMPT, _user_payload(matches, inventory_summary, limit), RANKING_SCHEMA,
                                    name="ranking")
        picks = AiRanking.model_validate(data).picks
    except gemini.GeminiError as exc:
        return AiResult(matches, used=False, error=str(exc))
    except ValueError:
        return AiResult(matches, used=False, error="Yapay zekâ yanıtı beklenen biçimde değil")
    return _apply_picks(matches, picks, limit)


def rerank_with_claude(
    matches: list[RecipeMatch],
    *,
    inventory_summary: list[dict],
    limit: int,
    model: str,
    effort: str,
) -> AiResult:
    if not matches:
        return AiResult(matches, used=False)
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return AiResult(matches, used=False, error="anthropic paketi kurulu değil")

    user_content = _user_payload(matches, inventory_summary, limit)

    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.parse(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            # Güvenlik sınıflandırıcısı bir isteği reddederse sunucu tarafında uygun modele düşer
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": user_content}],
            output_format=AiRanking,
        )
    except anthropic.APIConnectionError as exc:
        log.warning("Claude bağlantı hatası: %s", exc)
        return AiResult(matches, used=False, error="Yapay zekâ servisine bağlanılamadı")
    except anthropic.RateLimitError:
        return AiResult(matches, used=False, error="Yapay zekâ servisi şu an yoğun (rate limit)")
    except anthropic.APIStatusError as exc:
        log.warning("Claude API hatası %s: %s", exc.status_code, exc.message)
        return AiResult(matches, used=False, error=f"Yapay zekâ servisi hata döndü ({exc.status_code})")
    except Exception as exc:  # kimlik bilgisi yok vb.
        log.warning("Claude çağrısı başarısız: %s", exc)
        return AiResult(matches, used=False, error="Yapay zekâ servisi yapılandırılmamış")

    if response.stop_reason == "refusal" or response.parsed_output is None:
        return AiResult(matches, used=False, error="Yapay zekâ bu isteğe yanıt vermedi")

    return _apply_picks(matches, response.parsed_output.picks, limit)
