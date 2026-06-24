# Meeting Secretary

Telegram-бот — личный секретарь для встреч: запись голосом → транскрипция (Whisper **medium** на CPU) → постмит с договорённостями и action items (LLM через [OpenRouter](https://openrouter.ai)).

**Бот:** [@my_meeting_secretary_bot](https://t.me/my_meeting_secretary_bot)

## Возможности

- Отправьте голосовое или аудио — сразу получите транскрипт и постмит
- Несколько записей одной встречи: начните сессию, пришлите все части и завершите её
- Постмит: резюме, участники, решения, таблица задач (кто / что / срок)
- Русский язык по умолчанию (`WHISPER_LANGUAGE=ru`)

## Требования

- Python 3.10+ (локальный запуск) или Docker + Docker Compose
- Токен Telegram-бота ([@BotFather](https://t.me/BotFather))
- API-ключ [OpenRouter](https://openrouter.ai/keys)

## Архитектура

Один процесс: **FastAPI** (Uvicorn) + **Telegram-бот** внутри него.

```
Telegram API  ←── long polling ──  бот (python-telegram-bot)
                                        │
                                   Whisper + OpenRouter
                                        │
FastAPI :8000  ←── /health, /ready ──  мониторинг (Docker healthcheck)
```

**Telegram не шлёт запросы в FastAPI.** Бот сам опрашивает `api.telegram.org` (long polling). FastAPI нужен как оболочка процесса и для проверок готовности (`/health`, `/ready`) — в том числе в Docker.

И локальный `python -m meeting_secretary`, и Docker запускают одно и то же: Uvicorn + FastAPI, а при старте приложения поднимается бот.

## Установка (локально)

```bash
cd meeting-secretary
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env
```

При первом запуске Whisper скачает модель `medium` (~1.5 ГБ):

```bash
python scripts/download_whisper_model.py
```

## Запуск

### Docker (рекомендуется для сервера)

```bash
cp .env.example .env
# отредактируйте .env

docker compose up -d --build
```

Проверка:

```bash
curl http://localhost:8000/ready
docker compose logs -f
```

Остановка: `docker compose down`

Модель Whisper вшивается в образ при сборке. Данные сессий хранятся в Docker-volume `meeting-data`.

### Локально (разработка)

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python -m meeting_secretary
```

Команда выше поднимает FastAPI на порту `8000` (по умолчанию) и внутри него — Telegram-бот.

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
