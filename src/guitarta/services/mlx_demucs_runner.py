import argparse
import wave
from pathlib import Path

import numpy as np

from guitarta.services.audio_processor import DEMUX_MODEL


def main() -> int:
    parser = argparse.ArgumentParser(description="Run demucs-mlx with stdlib WAV I/O.")
    parser.add_argument("audio_path")
    parser.add_argument("-n", "--name", default=DEMUX_MODEL)
    parser.add_argument("-o", "--out", required=True)
    parser.add_argument("--shifts", type=int, default=1)
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument("--segment", type=float, default=None)
    parser.add_argument("-b", "--batch-size", type=int, default=8)
    args = parser.parse_args()

    audio_path = Path(args.audio_path)
    output_dir = Path(args.out) / audio_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading WAV: {audio_path}", flush=True)
    wav, sample_rate = _read_pcm_wav(audio_path)

    from demucs_mlx.api import Separator

    print(f"Loading MLX model: {args.name}", flush=True)
    separator = Separator(
        model=args.name,
        shifts=args.shifts,
        overlap=args.overlap,
        segment=args.segment,
        batch_size=args.batch_size,
        progress=True,
    )
    if sample_rate != separator.samplerate:
        raise RuntimeError(
            f"Expected {separator.samplerate}Hz WAV, got {sample_rate}Hz. "
            "AudioProcessor should extract 44100Hz PCM WAV before separation."
        )

    print("Running MLX separation...", flush=True)
    _, stems = separator.separate_tensor(wav)

    for name, stem in stems.items():
        stem_path = output_dir / f"{name}.wav"
        _write_pcm_wav(stem_path, np.asarray(stem), separator.samplerate)
        print(f"Wrote: {stem_path}", flush=True)
    return 0


def _read_pcm_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as reader:
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        sample_rate = reader.getframerate()
        frames = reader.getnframes()
        if sample_width != 2:
            raise RuntimeError(f"Expected 16-bit PCM WAV, got {sample_width * 8}-bit.")
        raw = reader.readframes(frames)
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    audio = audio.reshape(-1, channels).T
    return np.ascontiguousarray(audio), sample_rate


def _write_pcm_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    if audio.ndim != 2:
        raise RuntimeError(f"Expected stem shape (channels, frames), got {audio.shape}.")
    audio = _prevent_clip(audio)
    interleaved = np.ascontiguousarray(audio.T)
    pcm = np.clip(interleaved * 32767.0, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(audio.shape[0])
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(pcm.tobytes())


def _prevent_clip(audio: np.ndarray) -> np.ndarray:
    max_value = float(np.max(np.abs(audio))) if audio.size else 0.0
    scale = max(1.01 * max_value, 1.0)
    return audio / scale


if __name__ == "__main__":
    raise SystemExit(main())
