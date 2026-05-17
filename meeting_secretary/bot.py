from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from meeting_secretary.audio import convert_to_wav, merge_wav_files
from meeting_secretary.config import Settings
from meeting_secretary.formatting import reply_text_safe
from meeting_secretary.sessions import SessionStore
from meeting_secretary.summarizer import Summarizer
from meeting_secretary.transcription import Transcriber

logger = logging.getLogger(__name__)

HELP_TEXT = """Привет! Я личный секретарь для встреч.

Как пользоваться:
1. /new [название] — начать запись встречи
2. Отправляйте голосовые сообщения или аудиофайлы (можно несколько подряд)
3. /done — транскрипция + постмит с договорённостями
4. /cancel — отменить текущую сессию

Другие команды:
• /status — сколько частей записано
• /title Новое название — задать название встречи

Можно отправить один аудиофайл без /new — обработаю сразу.

Технологии: Whisper small (CPU) + OpenRouter LLM."""


def _user_dir(settings: Settings, user_id: int, session_id: str) -> Path:
    path = settings.data_dir / str(user_id) / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    store: SessionStore = context.application.bot_data["sessions"]
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    if user is None:
        return

    title = " ".join(context.args).strip() or None
    session = store.start(user.id, title=title)
    _user_dir(settings, user.id, session.session_id)

    label = f" «{title}»" if title else ""
    await update.effective_message.reply_text(
        f"Сессия начата{label}. Отправляйте голосовые/аудио. Когда закончите — /done",
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    store: SessionStore = context.application.bot_data["sessions"]
    user = update.effective_user
    if user is None:
        return
    if store.get(user.id) is None:
        await update.effective_message.reply_text("Нет активной сессии.")
        return
    store.clear(user.id)
    await update.effective_message.reply_text("Сессия отменена.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    store: SessionStore = context.application.bot_data["sessions"]
    user = update.effective_user
    if user is None:
        return
    session = store.get(user.id)
    if session is None:
        await update.effective_message.reply_text("Нет активной сессии. Используйте /new")
        return
    title = session.title or "без названия"
    await update.effective_message.reply_text(
        f"Сессия: {session.session_id}\n"
        f"Название: {title}\n"
        f"Частей записи: {session.part_count}",
    )


async def cmd_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    store: SessionStore = context.application.bot_data["sessions"]
    user = update.effective_user
    if user is None:
        return
    session = store.get(user.id)
    if session is None:
        await update.effective_message.reply_text("Сначала /new")
        return
    title = " ".join(context.args).strip()
    if not title:
        await update.effective_message.reply_text("Укажите название: /title Спринт-планирование")
        return
    session.title = title
    await update.effective_message.reply_text(f"Название: {title}")


async def _download_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    dest: Path,
) -> None:
    message = update.effective_message
    if message is None:
        raise RuntimeError("No message")

    if message.voice:
        file = await context.bot.get_file(message.voice.file_id)
    elif message.audio:
        file = await context.bot.get_file(message.audio.file_id)
    elif message.document and message.document.mime_type and message.document.mime_type.startswith(
        "audio/"
    ):
        file = await context.bot.get_file(message.document.file_id)
    else:
        raise RuntimeError("Unsupported message type")

    await file.download_to_drive(custom_path=str(dest))


async def _process_meeting(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    audio_paths: list[Path],
    title: str | None,
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    transcriber: Transcriber = context.application.bot_data["transcriber"]
    summarizer: Summarizer = context.application.bot_data["summarizer"]

    message = update.effective_message
    if message is None:
        return

    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=ChatAction.TYPING,
    )
    status = await message.reply_text("Конвертирую аудио…")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wav_parts: list[Path] = []
        for index, source in enumerate(audio_paths, start=1):
            wav = tmp_path / f"part_{index}.wav"
            convert_to_wav(source, wav)
            wav_parts.append(wav)

        merged = tmp_path / "meeting.wav"
        if len(wav_parts) == 1:
            merged = wav_parts[0]
        else:
            merge_wav_files(wav_parts, merged)

        await status.edit_text("Распознаю вашу речь (Whisper small, CPU)…")
        loop = asyncio.get_running_loop()
        transcript = await loop.run_in_executor(
            None,
            transcriber.transcribe,
            merged,
        )

        if not transcript:
            await status.edit_text("В записи не удалось распознать речь.")
            return

        await status.edit_text("Формирую постмит (OpenRouter)…")
        summary = await summarizer.summarize(transcript, meeting_title=title)

    await status.delete()

    preview = transcript[:3500] + ("…" if len(transcript) > 3500 else "")
    await reply_text_safe(message, preview, header="📝 Транскрипт")
    if len(transcript) > 3500:
        await reply_text_safe(message, transcript)

    await reply_text_safe(message, summary, header="📋 Постмит")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    store: SessionStore = context.application.bot_data["sessions"]
    user = update.effective_user
    if user is None:
        return

    session = store.get(user.id)
    if session is None or not session.audio_paths:
        await update.effective_message.reply_text(
            "Нет записей. Отправьте голосовые или /new и затем аудио.",
        )
        return

    try:
        await _process_meeting(
            update,
            context,
            list(session.audio_paths),
            session.title,
        )
    except Exception as exc:
        logger.exception("Processing failed")
        await update.effective_message.reply_text(f"Ошибка: {exc}")
    finally:
        store.clear(user.id)


async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    store: SessionStore = context.application.bot_data["sessions"]
    user = update.effective_user
    if user is None:
        return

    message = update.effective_message
    if message is None:
        return

    size = 0
    if message.voice:
        size = message.voice.file_size or 0
    elif message.audio:
        size = message.audio.file_size or 0
    elif message.document:
        size = message.document.file_size or 0

    max_bytes = settings.max_audio_mb * 1024 * 1024
    if size > max_bytes:
        await message.reply_text(
            f"Файл слишком большой (лимит {settings.max_audio_mb} МБ).",
        )
        return

    session = store.get(user.id)
    instant = session is None

    if instant:
        session = store.start(user.id)

    work_dir = _user_dir(settings, user.id, session.session_id)
    part_index = len(session.audio_paths) + 1
    suffix = ".ogg" if message.voice else ".audio"
    dest = work_dir / f"part_{part_index:03d}{suffix}"

    try:
        await _download_audio(update, context, dest)
        session.audio_paths.append(dest)
    except Exception as exc:
        logger.exception("Download failed")
        await message.reply_text(f"Не удалось сохранить аудио: {exc}")
        return

    if instant:
        await message.reply_text("Обрабатываю запись…")
        try:
            await _process_meeting(
                update,
                context,
                list(session.audio_paths),
                session.title,
            )
        except Exception as exc:
            logger.exception("Processing failed")
            await message.reply_text(f"Ошибка: {exc}")
        finally:
            store.clear(user.id)
        return

    await message.reply_text(
        f"Часть {session.part_count} сохранена. Ещё аудио или /done",
    )


def build_application(settings: Settings) -> Application:
    app = (
        Application.builder()
        .token(settings.telegram_token)
        .build()
    )
    app.bot_data["settings"] = settings
    app.bot_data["sessions"] = SessionStore()
    app.bot_data["transcriber"] = Transcriber(settings)
    app.bot_data["summarizer"] = Summarizer(settings)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("title", cmd_title))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(
        MessageHandler(
            filters.VOICE | filters.AUDIO | filters.Document.AUDIO,
            on_audio,
        ),
    )
    return app


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    app = build_application(settings)
    logger.info("Meeting Secretary bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
