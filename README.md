# Meeting Secretary

Telegram-бот — личный секретарь для встреч: запись голосом → транскрипция (Whisper **medium** на CPU) → постмит с договорённостями и action items (LLM через [OpenRouter](https://openrouter.ai)).

**Бот:** [@my_meeting_secretary_bot](https://t.me/my_meeting_secretary_bot)

## Возможности

- Отправьте голосовое или аудио — сразу получите транскрипт и постмит
- Несколько записей одной встречи: начните сессию, пришлите все части и завершите её
- Постмит: резюме, участники, решения, таблица задач (кто / что / срок)
- Русский язык по умолчанию (`WHISPER_LANGUAGE=ru`)

## Требования

- Python 3.10+
- Токен Telegram-бота ([@BotFather](https://t.me/BotFather))
- API-ключ [OpenRouter](https://openrouter.ai/keys)

## Установка

```bash
cd meeting-secretary
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env
```

При первом запуске Whisper скачает модель `medium` (~1.5 ГБ).

## Запуск

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python -m meeting_secretary
```

## Использование

Откройте [@my_meeting_secretary_bot](https://t.me/my_meeting_secretary_bot) и отправьте голосовое или аудиофайл. Команда `/start` — справка.

## Переменные окружения

См. `.env.example`. Основные:

- `TELEGRAM_BOT_TOKEN` — токен бота
- `OPENROUTER_API_KEY` — ключ OpenRouter
- `OPENROUTER_MODEL` — модель для суммаризации
- `WHISPER_*` — параметры распознавания (по умолчанию medium + CPU + int8)

## Производительность

Whisper medium на CPU: ориентировочно 1–3× длительности аудио в зависимости от машины. Длинные встречи лучше дробить на несколько голосовых.
