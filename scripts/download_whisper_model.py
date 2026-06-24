"""Download faster-whisper model into ./models/whisper-<size> (gitignored)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

MODELS: dict[str, tuple[str, str]] = {
    "small": ("Systran/faster-whisper-small", "~500 MB"),
    "medium": ("Systran/faster-whisper-medium", "~1.5 GB"),
    "large-v3": ("Systran/faster-whisper-large-v3", "~3 GB"),
}


def _resolve_model() -> tuple[str, Path, str, str]:
    model = os.getenv("WHISPER_MODEL", "medium").strip().lower()
    if model not in MODELS:
        known = ", ".join(sorted(MODELS))
        raise SystemExit(f"Unknown WHISPER_MODEL={model!r}. Supported: {known}")

    repo_id, size_hint = MODELS[model]
    default_dir = Path(__file__).resolve().parent.parent / "models" / f"whisper-{model}"
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else default_dir
    return model, target, repo_id, size_hint


def main() -> None:
    model, target, repo_id, size_hint = _resolve_model()
    target.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Downloading %s (%s) -> %s", repo_id, size_hint, target)

    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target),
    )

    model_bin = target / "model.bin"
    if not model_bin.exists():
        raise SystemExit(f"Download finished but model.bin not found in {target}")

    size_mb = model_bin.stat().st_size / (1024 * 1024)
    logging.info("Done: whisper-%s model.bin %.1f MB at %s", model, size_mb, target)


if __name__ == "__main__":
    main()
