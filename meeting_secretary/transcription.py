from __future__ import annotations

import logging
import time
from pathlib import Path

from faster_whisper import WhisperModel

from meeting_secretary.config import Settings

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: WhisperModel | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def preload(self) -> None:
        """Load (and download on first run) the Whisper model before handling requests."""
        logger.info(
            "Whisper preload started: path=%s device=%s compute_type=%s",
            self._settings.whisper_model_dir,
            self._settings.whisper_device,
            self._settings.whisper_compute_type,
        )
        started = time.perf_counter()
        self._get_model()
        logger.info("Whisper preload finished in %.1fs", time.perf_counter() - started)

    def _model_path(self) -> str:
        path = self._settings.whisper_model_dir
        if not path.is_dir():
            raise RuntimeError(
                f"Whisper model not found at {path}. "
                "Run: python scripts/download_whisper_model.py"
            )
        if not (path / "model.bin").exists():
            raise RuntimeError(
                f"Whisper model.bin missing in {path}. "
                "Run: python scripts/download_whisper_model.py"
            )
        return str(path)

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            started = time.perf_counter()
            model_path = self._model_path()
            logger.info(
                "Loading Whisper from %s device=%s compute_type=%s",
                model_path,
                self._settings.whisper_device,
                self._settings.whisper_compute_type,
            )
            try:
                self._model = WhisperModel(
                    model_path,
                    device=self._settings.whisper_device,
                    compute_type=self._settings.whisper_compute_type,
                )
            except Exception:
                logger.exception("Failed to load Whisper model")
                raise
            logger.info(
                "Whisper model loaded in %.1fs",
                time.perf_counter() - started,
            )
        return self._model

    def transcribe(self, audio_path: Path) -> str:
        size_kb = audio_path.stat().st_size / 1024
        logger.info(
            "Transcription started: file=%s size=%.1f KB language=%s",
            audio_path.name,
            size_kb,
            self._settings.whisper_language,
        )
        started = time.perf_counter()
        model = self._get_model()

        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=self._settings.whisper_language,
                vad_filter=True,
                beam_size=5,
            )
        except Exception:
            logger.exception("Whisper transcribe() failed for %s", audio_path)
            raise

        parts: list[str] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                parts.append(text)
                logger.debug(
                    "Segment %.1f-%.1fs: %s",
                    segment.start,
                    segment.end,
                    text[:80],
                )

        transcript = "\n".join(parts).strip()
        duration = getattr(info, "duration", None)
        logger.info(
            "Transcription finished in %.1fs: segments=%d chars=%d audio_duration=%s",
            time.perf_counter() - started,
            len(parts),
            len(transcript),
            f"{duration:.1f}s" if duration else "unknown",
        )
        if not transcript:
            logger.warning("Transcription returned empty text for %s", audio_path.name)
        return transcript
