from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from meeting_secretary.runtime import BotRuntime, create_runtime

logger = logging.getLogger(__name__)

_runtime: BotRuntime | None = None


def get_runtime() -> BotRuntime:
    if _runtime is None:
        raise RuntimeError("Application runtime is not initialized")
    return _runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runtime
    _runtime = create_runtime()
    await _runtime.preload_whisper()
    await _runtime.start()
    yield
    await _runtime.stop()
    _runtime = None


app = FastAPI(
    title="Meeting Secretary",
    description="Telegram-бот для транскрипции встреч и постмитов",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "meeting-secretary",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    runtime = get_runtime()
    payload: dict[str, Any] = {
        "whisper_ready": runtime.whisper_ready,
        "bot_running": runtime.bot_running,
        "last_error": runtime.last_error,
    }
    if runtime.whisper_ready and runtime.bot_running:
        payload["status"] = "ready"
        return JSONResponse(payload)

    payload["status"] = "not_ready"
    return JSONResponse(payload, status_code=503)


def main() -> None:
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "meeting_secretary.server:app",
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
