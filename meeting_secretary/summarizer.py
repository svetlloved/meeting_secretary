from __future__ import annotations

import logging

import httpx

from meeting_secretary.config import Settings

logger = logging.getLogger(__name__)

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


class Summarizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def summarize(self, transcript: str, meeting_title: str | None = None) -> str:
        title = meeting_title or "Встреча"
        user_prompt = (
            f"Название встречи: {title}\n\n"
            f"Транскрипт:\n\n{transcript}"
        )

        payload = {
            "model": self._settings.openrouter_model,
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
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected OpenRouter response: %s", data)
            raise RuntimeError("Invalid response from OpenRouter") from exc

        return content.strip()
