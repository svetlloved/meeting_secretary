from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    openrouter_api_key: str
    openrouter_model: str
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    whisper_language: str | None
    data_dir: Path
    max_audio_mb: int
    openrouter_base_url: str

    @classmethod
    def from_env(cls) -> Settings:
        language = os.getenv("WHISPER_LANGUAGE", "ru").strip()
        return cls(
            telegram_token=_require("TELEGRAM_BOT_TOKEN"),
            openrouter_api_key=_require("OPENROUTER_API_KEY"),
            openrouter_model=os.getenv(
                "OPENROUTER_MODEL", "google/gemini-2.0-flash-001"
            ),
            whisper_model=os.getenv("WHISPER_MODEL", "small"),
            whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
            whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            whisper_language=language if language else None,
            data_dir=Path(os.getenv("DATA_DIR", "./data")).resolve(),
            max_audio_mb=int(os.getenv("MAX_AUDIO_MB", "50")),
            openrouter_base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
        )


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
