from __future__ import annotations

import logging
from pathlib import Path

from faster_whisper import WhisperModel

from meeting_secretary.config import Settings

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                "Loading Whisper model=%s device=%s compute_type=%s",
                self._settings.whisper_model,
                self._settings.whisper_device,
                self._settings.whisper_compute_type,
            )
            self._model = WhisperModel(
                self._settings.whisper_model,
                device=self._settings.whisper_device,
                compute_type=self._settings.whisper_compute_type,
            )
        return self._model

    def transcribe(self, audio_path: Path) -> str:
        model = self._get_model()
        segments, _info = model.transcribe(
            str(audio_path),
            language=self._settings.whisper_language,
            vad_filter=True,
            beam_size=5,
        )
        parts: list[str] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
