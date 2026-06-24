from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from telegram import Update
from telegram.error import NetworkError, TimedOut

from telegram.ext import Application

from meeting_secretary.bot import build_application, setup_logging, setup_bot_commands
from meeting_secretary.config import Settings
from meeting_secretary.transcription import Transcriber

logger = logging.getLogger(__name__)


@dataclass
class BotRuntime:
    settings: Settings
    whisper_ready: bool = field(default=False, init=False)
    bot_running: bool = field(default=False, init=False)
    last_error: str | None = field(default=None, init=False)
    _application: Application | None = field(default=None, init=False, repr=False)

    async def preload_whisper(self) -> None:
        app = build_application(self.settings)
        transcriber: Transcriber = app.bot_data["transcriber"]
        logger.info("Pre-loading Whisper model…")
        try:
            await asyncio.get_running_loop().run_in_executor(None, transcriber.preload)
            self.whisper_ready = True
            logger.info("Whisper model ready")
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("Whisper preload failed")

    async def start(self) -> None:
        if self._application is not None:
            return

        application = build_application(self.settings)
        for attempt in range(1, 6):
            try:
                await application.initialize()
                await application.start()
                await setup_bot_commands(application)
                await application.updater.start_polling(
                    allowed_updates=Update.ALL_TYPES,
                )
                self._application = application
                self.bot_running = True
                self.last_error = None
                logger.info("Telegram bot polling started")
                return
            except (NetworkError, TimedOut) as exc:
                self.last_error = str(exc)
                try:
                    await application.shutdown()
                except Exception:
                    pass
                if attempt >= 5:
                    logger.exception("Telegram connection failed after %d attempts", attempt)
                    raise
                delay = 10 * attempt
                logger.warning(
                    "Telegram connection failed (%s), retry %d/5 in %ds…",
                    exc,
                    attempt,
                    delay,
                )
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        application = self._application
        if application is None:
            return

        try:
            if application.updater.running:
                await application.updater.stop()
            await application.stop()
            await application.shutdown()
        finally:
            self._application = None
            self.bot_running = False
            logger.info("Telegram bot stopped")


def create_runtime() -> BotRuntime:
    from dotenv import load_dotenv

    load_dotenv()
    setup_logging()
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.whisper_model_dir.mkdir(parents=True, exist_ok=True)
    return BotRuntime(settings=settings)
