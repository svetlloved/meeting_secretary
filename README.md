# Meeting Secretary

Telegram-бот — личный секретарь для встреч: запись голосом → транскрипция (Whisper **medium** на CPU) → постмит с договорённостями и action items (LLM через [OpenRouter](https://openrouter.ai)).

## Возможности

- Несколько голосовых сообщений в одной встрече (`/new` → аудио → `/done`)
- Или одно сообщение — сразу полная обработка
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

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Справка |
| `/new [название]` | Начать сессию записи |
| голосовое / аудио | Добавить фрагмент (или обработать сразу без `/new`) |
| `/done` | Транскрипция + постмит |
| `/status` | Статус сессии |
| `/title ...` | Название встречи |
| `/cancel` | Отмена сессии |

## Переменные окружения

См. `.env.example`. Основные:

- `TELEGRAM_BOT_TOKEN` — токен бота
- `OPENROUTER_API_KEY` — ключ OpenRouter
- `OPENROUTER_MODEL` — модель для суммаризации
- `WHISPER_*` — параметры распознавания (по умолчанию medium + CPU + int8)

## Производительность

Whisper medium на CPU: ориентировочно 1–3× длительности аудио в зависимости от машины. Длинные встречи лучше дробить на несколько голосовых и собирать через `/done`.
