from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPENROUTER_MODELS = (
    "qwen/qwen-2.5-72b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "deepseek/deepseek-chat",
    "mistralai/mistral-small-3.1-24b-instruct",
)


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    openrouter_api_key: str
    openrouter_models: tuple[str, ...]
    whisper_model: str
    whisper_model_dir: Path
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
            openrouter_models=_parse_openrouter_models(),
            whisper_model=os.getenv("WHISPER_MODEL", "small"),
            whisper_model_dir=Path(
                os.getenv("WHISPER_MODEL_DIR", "./models/whisper-small")
            ).resolve(),
            whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
            whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            whisper_language=language if language else None,
            data_dir=Path(os.getenv("DATA_DIR", "./data")).resolve(),
            max_audio_mb=int(os.getenv("MAX_AUDIO_MB", "50")),
            openrouter_base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
        )


def _parse_openrouter_models() -> tuple[str, ...]:
    primary = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct").strip()
    extra = os.getenv("OPENROUTER_FALLBACK_MODELS", "").strip()
    models: list[str] = []
    for candidate in (primary, *extra.split(","), *DEFAULT_OPENROUTER_MODELS):
        name = candidate.strip()
        if name and name not in models:
            models.append(name)
    return tuple(models)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
