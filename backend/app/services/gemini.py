"""Gemini istemcisi (Google'ın OpenAI uyumlu uç noktası üzerinden, httpx ile).

Yapılandırılmış çıktı için JSON şeması kullanılır. Model yoğunsa veya erişilemiyorsa listedeki bir sonraki
modele geçilir.
"""

import json
import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
RETRYABLE = {404, 429, 500, 502, 503, 504}


class GeminiError(Exception):
    pass


def generate_json(system: str, content: list[dict] | str, schema: dict, *, name: str = "result",
                  timeout: float = 90, rounds: int = 1) -> dict:
    """`rounds` > 1 ise tüm modeller yoğunken artan beklemeyle yeniden dener (toplu betikler için)."""
    last_exc: GeminiError | None = None
    for attempt in range(rounds):
        try:
            return _generate_once(system, content, schema, name=name, timeout=timeout)
        except GeminiError as exc:
            if "geçersiz" in str(exc) or "çözümlenemedi" in str(exc):
                raise
            last_exc = exc
            if attempt + 1 < rounds:
                import time

                time.sleep(10 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


def _generate_once(system: str, content: list[dict] | str, schema: dict, *, name: str, timeout: float) -> dict:
    s = get_settings()
    if not s.gemini_api_key:
        raise GeminiError("Gemini API anahtarı yapılandırılmamış (MEALBIRD_GEMINI_API_KEY)")
    body_base = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
    }
    last = "bilinmeyen hata"
    for model in s.gemini_models:
        try:
            resp = httpx.post(
                f"{s.gemini_base_url}/chat/completions",
                json={**body_base, "model": model},
                headers={"Authorization": f"Bearer {s.gemini_api_key}"},
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            last = f"bağlantı hatası: {exc}"
            continue
        if resp.status_code in RETRYABLE:
            last = f"{model}: HTTP {resp.status_code}"
            log.warning("Gemini %s kullanılamadı (%s), sonraki model deneniyor", model, resp.status_code)
            continue
        if resp.status_code in (401, 403):
            raise GeminiError("Gemini anahtarı geçersiz veya yetkisiz")
        if resp.status_code >= 400:
            raise GeminiError(f"Gemini hata döndürdü: HTTP {resp.status_code}")
        try:
            data = resp.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                raise GeminiError(f"Gemini yanıtı tamamlanmadı ({choice.get('finish_reason')})")
            return json.loads(choice["message"]["content"])
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise GeminiError(f"Gemini yanıtı çözümlenemedi: {exc}") from exc
    raise GeminiError(f"Gemini şu an yanıt vermiyor ({last}). Biraz sonra tekrar deneyin.")
