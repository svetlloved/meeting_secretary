from __future__ import annotations

import logging
from pathlib import Path

import av

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


def _make_resampler() -> av.audio.resampler.AudioResampler:
    return av.audio.resampler.AudioResampler(
        format="s16",
        layout="mono",
        rate=SAMPLE_RATE,
    )


def _mux_frames(
    out_container: av.container.output.OutputContainer,
    out_stream: av.stream.Stream,
    frames: list[av.AudioFrame],
) -> None:
    for frame in frames:
        if frame is None:
            continue
        for packet in out_stream.encode(frame):
            out_container.mux(packet)


def _decode_to_wav_stream(
    source: Path,
    out_container: av.container.output.OutputContainer,
    out_stream: av.stream.Stream,
) -> None:
    with av.open(str(source)) as in_container:
        if not in_container.streams.audio:
            raise RuntimeError(f"В файле нет аудио: {source.name}")

        in_stream = in_container.streams.audio[0]
        resampler = _make_resampler()

        for frame in in_container.decode(in_stream):
            _mux_frames(out_container, out_stream, list(resampler.resample(frame)))

        _mux_frames(out_container, out_stream, list(resampler.resample(None)))


def convert_to_wav(source: Path, destination: Path) -> Path:
    """Convert arbitrary audio to 16 kHz mono WAV for Whisper (PyAV, без ffmpeg)."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with av.open(str(destination), "w", format="wav") as out_container:
            out_stream = out_container.add_stream("pcm_s16le", rate=SAMPLE_RATE)
            out_stream.layout = "mono"
            _decode_to_wav_stream(source, out_container, out_stream)
            for packet in out_stream.encode(None):
                out_container.mux(packet)
    except av.AVError as exc:
        logger.exception("Audio conversion failed for %s", source)
        raise RuntimeError(f"Не удалось конвертировать аудио: {exc}") from exc

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("Конвертация дала пустой файл — проверьте формат записи")

    return destination


def merge_wav_files(sources: list[Path], destination: Path) -> Path:
    if not sources:
        raise ValueError("No audio files to merge")
    if len(sources) == 1:
        return sources[0]

    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with av.open(str(destination), "w", format="wav") as out_container:
            out_stream = out_container.add_stream("pcm_s16le", rate=SAMPLE_RATE)
            out_stream.layout = "mono"

            for source in sources:
                _decode_to_wav_stream(source, out_container, out_stream)

            for packet in out_stream.encode(None):
                out_container.mux(packet)
    except av.AVError as exc:
        logger.exception("Audio merge failed")
        raise RuntimeError(f"Не удалось объединить части записи: {exc}") from exc

    return destination
