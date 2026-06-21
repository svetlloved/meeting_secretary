"""Download faster-whisper-small into ./models/whisper-small (gitignored)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

REPO_ID = "Systran/faster-whisper-small"
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "models" / "whisper-small"


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    target.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Downloading %s -> %s (~500 MB)", REPO_ID, target)

    snapshot_download(
        repo_id=REPO_ID,
        local_dir=str(target),
    )

    model_bin = target / "model.bin"
    if not model_bin.exists():
        raise SystemExit(f"Download finished but model.bin not found in {target}")

    size_mb = model_bin.stat().st_size / (1024 * 1024)
    logging.info("Done: model.bin %.1f MB at %s", size_mb, target)


if __name__ == "__main__":
    main()
