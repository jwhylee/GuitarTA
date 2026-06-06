import math
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional


class Metronome:
    def __init__(self, play_tick: Callable[[bool], None]):
        self.play_tick = play_tick
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, bpm: int, beats_per_bar: int, accent_first_beat: bool) -> None:
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            args=(max(20, bpm), max(1, beats_per_bar), accent_first_beat),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2)
        self._thread = None

    def _loop(self, bpm: int, beats_per_bar: int, accent_first_beat: bool) -> None:
        interval = 60.0 / bpm
        beat = 0
        next_tick = time.monotonic()
        while not self._stop.is_set():
            is_accent = accent_first_beat and beat == 0
            self.play_tick(is_accent)
            beat = (beat + 1) % beats_per_bar
            next_tick += interval
            remaining = max(0.0, next_tick - time.monotonic())
            self._stop.wait(remaining)


def ensure_click_wav(path: Path, frequency: int, duration_seconds: float = 0.045) -> Path:
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    frames = int(sample_rate * duration_seconds)
    amplitude = 16000

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(frames):
            envelope = 1.0 - (i / frames)
            sample = int(amplitude * envelope * math.sin(2 * math.pi * frequency * i / sample_rate))
            wav_file.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))

    return path
