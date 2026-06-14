import shutil
import subprocess
import time
from contextlib import redirect_stderr, redirect_stdout
from math import pow
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


class AudioProcessingError(RuntimeError):
    pass


AUDIO_KINDS = {"original", "bass_removed", "guitar_removed", "drums_only"}
DEMUX_MODEL = "htdemucs_6s"
REQUIRED_STEMS = {"drums", "bass", "other", "vocals", "guitar", "piano"}


class AudioProcessor:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def prepare_note_audio(
        self,
        note_id: int,
        media_path: str,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, str]:
        source = Path(media_path).expanduser()
        if not source.exists():
            raise AudioProcessingError(f"영상 파일을 찾을 수 없습니다: {source}")

        paths = self._note_paths(note_id)
        paths["note_dir"].mkdir(parents=True, exist_ok=True)

        if not self._is_current(paths["original"], source):
            self._report(progress, "원본 음원 추출 중...")
            self._extract_audio(source, paths["original"])
        else:
            self._report(progress, "원본 음원 준비됨")

        if not self._outputs_current(paths):
            self._report(progress, "Demucs stem 분리 중...")
            stems = self._split_stems(paths["original"], paths["stems_dir"], progress)

            self._report(progress, "베이스 제거 음원 생성 중...")
            self._mix_stems(
                [path for name, path in stems.items() if name != "bass"],
                paths["bass_removed"],
            )

            self._report(progress, "기타 제거 음원 생성 중...")
            self._mix_stems(
                [path for name, path in stems.items() if name != "guitar"],
                paths["guitar_removed"],
            )

            self._report(progress, "드럼 단독 음원 생성 중...")
            self._copy_stem(stems["drums"], paths["drums_only"])

        self._report(progress, "오디오 준비 완료")
        return {
            "original_audio_path": str(paths["original"]),
            "bass_removed_audio_path": str(paths["bass_removed"]),
            "guitar_removed_audio_path": str(paths["guitar_removed"]),
            "drums_only_audio_path": str(paths["drums_only"]),
        }

    def playback_media_path(
        self,
        note_id: int,
        video_path: str,
        audio_path: str,
        audio_kind: str,
        pitch_semitones: int = 0,
    ) -> Path:
        clean_pitch = max(-9, min(9, int(pitch_semitones)))
        if audio_kind == "original" and clean_pitch == 0:
            return Path(video_path).expanduser()
        if audio_kind not in AUDIO_KINDS:
            raise AudioProcessingError(f"지원하지 않는 음원 선택입니다: {audio_kind}")

        video = Path(video_path).expanduser()
        audio = Path(audio_path).expanduser()
        if not video.exists():
            raise AudioProcessingError(f"영상 파일을 찾을 수 없습니다: {video}")
        if not audio.exists():
            raise AudioProcessingError(f"선택한 음원 파일을 찾을 수 없습니다: {audio}")

        output = self._playback_output_path(note_id, audio_kind, clean_pitch)
        output.parent.mkdir(parents=True, exist_ok=True)
        if self._is_current(output, video, audio):
            return output

        self._mux_video_with_audio(video, audio, output, clean_pitch)
        return output

    def cached_playback_media_path(
        self,
        note_id: int,
        video_path: str,
        audio_path: str,
        audio_kind: str,
        pitch_semitones: int = 0,
    ) -> Optional[Path]:
        clean_pitch = max(-9, min(9, int(pitch_semitones)))
        video = Path(video_path).expanduser()
        if audio_kind == "original" and clean_pitch == 0:
            return video if video.exists() else None

        audio = Path(audio_path).expanduser()
        output = self._playback_output_path(note_id, audio_kind, clean_pitch)
        if self._is_current(output, video, audio):
            return output
        return None

    def audio_path_for_kind(self, note, audio_kind: str) -> str:
        if audio_kind == "bass_removed":
            return note.bass_removed_audio_path
        if audio_kind == "guitar_removed":
            return note.guitar_removed_audio_path
        if audio_kind == "drums_only":
            return note.drums_only_audio_path
        return note.original_audio_path

    def assets_need_refresh(self, note) -> bool:
        paths = self._note_paths(note.id)
        expected_paths = {
            "original": paths["original"],
            "bass_removed": paths["bass_removed"],
            "guitar_removed": paths["guitar_removed"],
            "drums_only": paths["drums_only"],
        }
        for audio_kind, expected_path in expected_paths.items():
            current_path = self.audio_path_for_kind(note, audio_kind)
            if Path(current_path or "").expanduser() != expected_path:
                return True
            if not self._existing_path(current_path):
                return True
        return False

    def _note_paths(self, note_id: int) -> Dict[str, Path]:
        note_dir = self.output_dir / f"note_{note_id}"
        return {
            "note_dir": note_dir,
            "stems_dir": note_dir / "stems",
            "original": note_dir / "original.wav",
            "bass_removed": note_dir / "no_bass.wav",
            "guitar_removed": note_dir / "no_guitar.wav",
            "drums_only": note_dir / "drums.wav",
        }

    def _outputs_current(self, paths: Dict[str, Path]) -> bool:
        source = paths["original"]
        return all(
            self._is_current(paths[key], source)
            for key in ("bass_removed", "guitar_removed", "drums_only")
        )

    def _extract_audio(self, source: Path, output: Path) -> None:
        self._run(
            [
                self._ffmpeg(),
                "-y",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "2",
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                str(output),
            ]
        )

    def _split_stems(
        self,
        audio_path: Path,
        output_dir: Path,
        progress: Optional[Callable[[str], None]],
    ) -> Dict[str, Path]:
        if not self._demucs_available():
            raise AudioProcessingError(
                "Demucs를 찾지 못했습니다. Python 3.10 이상 환경에서 `pip install demucs`로 설치하세요."
            )

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._run_demucs(audio_path, output_dir, progress)

        stems = self._find_stems(output_dir)
        missing = sorted(REQUIRED_STEMS.difference(stems))
        if missing:
            raise AudioProcessingError(
                f"Demucs 결과에서 필요한 stem을 찾지 못했습니다: {', '.join(missing)}"
            )
        return stems

    def _find_stems(self, output_dir: Path) -> Dict[str, Path]:
        stems: Dict[str, Path] = {}
        for path in output_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".wav", ".flac", ".mp3", ".m4a"}:
                name = path.stem.lower()
                if name in REQUIRED_STEMS:
                    stems[name] = path
        return stems

    def _mix_stems(self, stems: List[Path], output: Path) -> None:
        if not stems:
            raise AudioProcessingError("믹싱할 stem이 없습니다.")
        command = [self._ffmpeg(), "-y"]
        for stem in stems:
            command.extend(["-i", str(stem)])

        inputs = "".join(f"[{index}:a]" for index in range(len(stems)))
        filter_complex = (
            f"{inputs}amix=inputs={len(stems)}:duration=longest:normalize=0,"
            "alimiter=limit=0.95[a]"
        )
        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[a]",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(output),
            ]
        )
        self._run(command)

    def _copy_stem(self, stem: Path, output: Path) -> None:
        self._run(
            [
                self._ffmpeg(),
                "-y",
                "-i",
                str(stem),
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(output),
            ]
        )

    def _mux_video_with_audio(
        self,
        video: Path,
        audio: Path,
        output: Path,
        pitch_semitones: int,
    ) -> None:
        command = [
            self._ffmpeg(),
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
        ]
        filter_complex = self._playback_audio_filter(pitch_semitones)
        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "0:v:0",
                "-map",
                "[a]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(output),
            ]
        )
        self._run(command)

    @staticmethod
    def _playback_audio_filter(pitch_semitones: int) -> str:
        if pitch_semitones == 0:
            return "[1:a]asetpts=PTS-STARTPTS,aresample=44100:first_pts=0[a]"

        factor = pow(2, pitch_semitones / 12)
        sample_rate = int(round(44100 * factor))
        return (
            f"[1:a]asetpts=PTS-STARTPTS,aresample=44100:first_pts=0,"
            f"asetrate={sample_rate},aresample=44100,atempo={1 / factor:.6f}[a]"
        )

    def _playback_output_path(self, note_id: int, audio_kind: str, pitch_semitones: int) -> Path:
        pitch_suffix = ""
        if pitch_semitones != 0:
            pitch_suffix = f"_pitch_{pitch_semitones:+d}".replace("+", "p").replace("-", "m")
        return self.output_dir / f"note_{note_id}" / f"playback_{audio_kind}{pitch_suffix}.mp4"

    def _run(
        self,
        command: Iterable[str],
        progress: Optional[Callable[[str], None]] = None,
    ) -> None:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output: List[str] = []
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            output.append(line)
            if progress is not None and len(output) % 8 == 0:
                progress(line)
        exit_code = process.wait()
        if exit_code != 0:
            detail = "\n".join(output[-10:])
            raise AudioProcessingError(detail or "오디오 처리 명령이 실패했습니다.")

    def _run_demucs(
        self,
        audio_path: Path,
        output_dir: Path,
        progress: Optional[Callable[[str], None]],
    ) -> None:
        try:
            from demucs.separate import main as demucs_main
        except Exception as exc:
            raise AudioProcessingError(f"Demucs를 불러오지 못했습니다: {exc}") from exc

        args = [
            "-n",
            DEMUX_MODEL,
            "-o",
            str(output_dir),
            str(audio_path),
        ]
        progress_stream = _ProgressStream(progress)
        try:
            with redirect_stdout(progress_stream), redirect_stderr(progress_stream):
                demucs_main(args)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if code != 0:
                raise AudioProcessingError(
                    progress_stream.tail() or f"Demucs가 종료 코드 {code}로 실패했습니다."
                ) from exc
        except Exception as exc:
            raise AudioProcessingError(progress_stream.tail() or str(exc)) from exc

    def _ffmpeg(self) -> str:
        for command in ("ffmpeg", "ffmpeg.exe"):
            found = shutil.which(command)
            if found:
                return found
        for candidate in (
            Path("/opt/homebrew/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
            Path("/usr/bin/ffmpeg"),
        ):
            if candidate.exists():
                return str(candidate)
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
        raise AudioProcessingError("ffmpeg를 찾지 못했습니다.")

    @staticmethod
    def _demucs_available() -> bool:
        for command in ("demucs", "demucs.exe"):
            if shutil.which(command):
                return True
        try:
            import demucs.separate  # noqa: F401
        except Exception:
            return False
        return True

    @staticmethod
    def _existing_path(value: str) -> bool:
        return bool(value) and Path(value).expanduser().exists()

    @staticmethod
    def _is_current(output: Path, *sources: Path) -> bool:
        if not output.exists():
            return False
        output_mtime = output.stat().st_mtime
        return all(source.exists() and output_mtime >= source.stat().st_mtime for source in sources)

    @staticmethod
    def _report(progress: Optional[Callable[[str], None]], text: str) -> None:
        if progress is not None:
            progress(text)


class _ProgressStream:
    def __init__(self, progress: Optional[Callable[[str], None]]) -> None:
        self.progress = progress
        self.buffer = ""
        self.lines: List[str] = []
        self.last_emit_at = 0.0
        self.emitting = False

    def write(self, text: str) -> int:
        if not text:
            return 0
        if self.emitting:
            return len(text)
        self.buffer += text
        while "\n" in self.buffer or "\r" in self.buffer:
            newline_index = self._next_separator_index()
            chunk = self.buffer[:newline_index].strip()
            self.buffer = self.buffer[newline_index + 1:]
            self._emit(chunk)
        return len(text)

    def flush(self) -> None:
        chunk = self.buffer.strip()
        if chunk:
            self._emit(chunk, force=True)
            self.buffer = ""

    def isatty(self) -> bool:
        return False

    def tail(self) -> str:
        self.flush()
        return "\n".join(self.lines[-10:])

    def _next_separator_index(self) -> int:
        indexes = [index for index in (self.buffer.find("\n"), self.buffer.find("\r")) if index >= 0]
        return min(indexes)

    def _emit(self, text: str, force: bool = False) -> None:
        if not text:
            return
        clean = " ".join(text.split())
        self.lines.append(clean)
        now = time.monotonic()
        if self.progress is not None and (force or now - self.last_emit_at >= 1.0):
            self.emitting = True
            try:
                self.progress(clean)
                self.last_emit_at = now
            finally:
                self.emitting = False
