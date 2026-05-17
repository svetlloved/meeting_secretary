from __future__ import annotations

import logging

from telegram.error import BadRequest

logger = logging.getLogger(__name__)

# Лимит Telegram — 4096; оставляем запас под заголовок.
DEFAULT_CHUNK_SIZE = 4000


def _split_text(text: str, chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Стараемся резать по переносу строки, а не посередине слова.
            newline = text.rfind("\n", start, end)
            if newline > start:
                end = newline + 1
        chunks.append(text[start:end])
        start = end
    return chunks


async def _send_one(message, text: str, *, parse_mode: str | None) -> None:
    try:
        await message.reply_text(text, parse_mode=parse_mode)
    except BadRequest as exc:
        if parse_mode is None:
            raise
        logger.warning("Telegram rejected parse_mode=%s: %s", parse_mode, exc)
        await message.reply_text(text, parse_mode=None)


async def reply_text_safe(
    message,
    body: str,
    *,
    header: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """Отправка транскрипта/постмита без разметки — не ломается на *, _, | и т.д."""
    text = f"{header}\n\n{body}" if header else body
    for chunk in _split_text(text, chunk_size):
        await _send_one(message, chunk, parse_mode=None)
