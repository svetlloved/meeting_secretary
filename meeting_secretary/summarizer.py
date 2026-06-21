from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from meeting_secretary.config import Settings

logger = logging.getLogger(__name__)

MAX_RETRIES_PER_MODEL = 3
RETRYABLE_STATUS = {429, 502, 503}
SKIP_MODEL_STATUS = {400, 404}

SYSTEM_PROMPT = """Ты — личный секретарь по итогам встреч. По транскрипту составь постмит на русском языке.

Структура ответа (используй Markdown):

## Краткое резюме
2–4 предложения: о чём встреча и главный итог.

## Участники
Список имён/ролей, если они упоминались. Если неясно — напиши «не определены из записи».

## Ключевые темы и решения
Маркированный список: что обсудили и к чему пришли.

## Договорённости и action items
Таблица в Markdown:

| Задача | Ответственный | Срок | Статус |
|--------|---------------|------|--------|
| ... | ... | ... | открыта |

Правила:
- Выделяй только явные или логически следующие из контекста обязательства.
- Если ответственный или срок не названы — пиши «уточнить».
- Не выдумывай факты, которых нет в транскрипте.
- Если встреча без конкретных поручений — так и укажи.

## Риски и открытые вопросы
Что осталось нерешённым.

## Следующие шаги
Короткий список ближайших действий по приоритету."""


def _retry_delay_seconds(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after_header = response.headers.get("Retry-After")
        if retry_after_header:
            try:
                return float(retry_after_header) + 1
            except ValueError:
                pass

        try:
            data = response.json()
            meta = data.get("error", {}).get("metadata", {})
            retry_after = meta.get("retry_after_seconds")
            if retry_after is not None:
                return float(retry_after) + 1
        except Exception:
            pass

    return min(30.0, 5.0 * (2**attempt))


class Summarizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._timeout = httpx.Timeout(connect=15.0, read=90.0, write=30.0, pool=30.0)

    async def summarize(self, transcript: str, meeting_title: str | None = None) -> str:
        title = meeting_title or "Встреча"
        user_prompt = (
            f"Название встречи: {title}\n\n"
            f"Транскрипт:\n\n{transcript}"
        )

        base_payload: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/meeting-secretary",
            "X-Title": "Meeting Secretary Bot",
        }

        url = f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"
        logger.info(
            "OpenRouter request started: models=%s title=%r transcript_chars=%d",
            self._settings.openrouter_models,
            title,
            len(transcript),
        )
        started = time.perf_counter()
        last_error: Exception | None = None

        async with httpx.AsyncClient(
            timeout=self._timeout,
            trust_env=False,
        ) as client:
            for model in self._settings.openrouter_models:
                payload = {**base_payload, "model": model}
                for attempt in range(MAX_RETRIES_PER_MODEL):
                    try:
                        response = await client.post(url, json=payload, headers=headers)
                    except httpx.HTTPError as exc:
                        delay = _retry_delay_seconds(None, attempt)
                        logger.warning(
                            "OpenRouter network error for model=%s (attempt %d/%d): %s — retry in %.0fs",
                            model,
                            attempt + 1,
                            MAX_RETRIES_PER_MODEL,
                            exc,
                            delay,
                        )
                        last_error = exc
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code == 200:
                        data = response.json()
                        try:
                            content = data["choices"][0]["message"]["content"]
                        except (KeyError, IndexError, TypeError) as exc:
                            logger.error(
                                "Unexpected OpenRouter response from %s: %s",
                                model,
                                data,
                            )
                            raise RuntimeError(
                                "Invalid response from OpenRouter"
                            ) from exc

                        logger.info(
                            "OpenRouter request finished in %.1fs via %s: response_chars=%d",
                            time.perf_counter() - started,
                            model,
                            len(content),
                        )
                        return content.strip()

                    if response.status_code in SKIP_MODEL_STATUS:
                        logger.warning(
                            "OpenRouter model unavailable %s: %s",
                            model,
                            response.text[:300],
                        )
                        last_error = RuntimeError(
                            f"Model {model} unavailable: {response.text[:200]}"
                        )
                        break

                    if response.status_code in RETRYABLE_STATUS:
                        delay = _retry_delay_seconds(response, attempt)
                        logger.warning(
                            "OpenRouter %s for model=%s, retry in %.0fs (attempt %d/%d): %s",
                            response.status_code,
                            model,
                            delay,
                            attempt + 1,
                            MAX_RETRIES_PER_MODEL,
                            response.text[:300],
                        )
                        last_error = httpx.HTTPStatusError(
                            f"OpenRouter {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                        await asyncio.sleep(delay)
                        continue

                    logger.error(
                        "OpenRouter HTTP error %s for model=%s: %s",
                        response.status_code,
                        model,
                        response.text[:500],
                    )
                    response.raise_for_status()

                logger.warning("Switching OpenRouter model after failures: %s", model)

        raise RuntimeError(
            "OpenRouter недоступен: бесплатные модели заняты или недоступны. "
            "Подождите 1–2 минуты и попробуйте снова."
        ) from last_error
