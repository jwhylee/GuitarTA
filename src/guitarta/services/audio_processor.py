import shutil
import subprocess
import sys
from math import pow
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


class AudioProcessingError(RuntimeError):
    pass


AUDIO_KINDS = {"original", "bass_removed", "guitar_removed", "drums_only"}
DEMUX_MODEL = "htdemucs_6s"
DRUMS_BALANCE_VERSION = "2"
DRUMS_CENTER_FILTER = "pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1"


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

        note_dir = self.output_dir / f"note_{note_id}"
        stems_dir = note_dir / "stems"
        note_dir.mkdir(parents=True, exist_ok=True)

        original = note_dir / "original.wav"
        bass_removed = note_dir / "bass_removed.wav"
        guitar_removed = note_dir / "guitar_removed.wav"
        drums_only = note_dir / "drums_only.wav"
        drums_balance_marker = note_dir / ".drums_only_balance_version"

        if self._is_current(original, source):
            self._report(progress, "원본 음원 준비됨")
        else:
            self._report(progress, "원본 음원 추출 중...")
            self._extract_audio(source, original)

        needs_stems = (
            not self._is_current(bass_removed, source)
            or not self._is_current(guitar_removed, source)
            or not self._is_current(drums_only, source)
        )
        if needs_stems:
            self._report(progress, "Demucs stem 생성 중...")
            stems = self._separate_stems(original, stems_dir, progress)
            self._report(progress, "베이스 제거 음원 생성 중...")
            self._mix_without(stems, "bass", bass_removed)
            self._report(progress, "기타 제거 음원 생성 중...")
            self._mix_without(stems, "guitar", guitar_removed)
            self._report(progress, "드럼 단독 음원 생성 중...")
            self._use_single_stem(stems, "drums", drums_only, center_stereo=True)
            drums_balance_marker.write_text(DRUMS_BALANCE_VERSION)
        elif self._marker_value(drums_balance_marker) != DRUMS_BALANCE_VERSION:
            self._report(progress, "드럼 단독 좌우 밸런스 보정 중...")
            self._center_stereo_file(drums_only)
            drums_balance_marker.write_text(DRUMS_BALANCE_VERSION)

        self._report(progress, "오디오 준비 완료")
        return {
            "original_audio_path": str(original),
            "bass_removed_audio_path": str(bass_removed),
            "guitar_removed_audio_path": str(guitar_removed),
            "drums_only_audio_path": str(drums_only),
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

        pitch_suffix = "" if clean_pitch == 0 else f"_pitch_{clean_pitch:+d}".replace("+", "p").replace("-", "m")
        output = self.output_dir / f"note_{note_id}" / f"playback_{audio_kind}{pitch_suffix}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        if self._is_current(output, video) and self._is_current(output, audio):
            return output

        ffmpeg = self._ffmpeg()
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
        ]
        if clean_pitch != 0:
            factor = pow(2, clean_pitch / 12)
            sample_rate = int(round(44100 * factor))
            filter_complex = (
                f"[1:a]aresample=44100,asetrate={sample_rate},"
                f"aresample=44100,atempo={1 / factor:.6f}[a]"
            )
            command.extend(
                [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "0:v:0",
                    "-map",
                    "[a]",
                ]
            )
        else:
            command.extend(
                [
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                ]
            )
        command.extend(
            [
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
        return output

    def audio_path_for_kind(self, note, audio_kind: str) -> str:
        if audio_kind == "bass_removed":
            return note.bass_removed_audio_path
        if audio_kind == "guitar_removed":
            return note.guitar_removed_audio_path
        if audio_kind == "drums_only":
            return note.drums_only_audio_path
        return note.original_audio_path

    def _extract_audio(self, source: Path, output: Path) -> None:
        ffmpeg = self._ffmpeg()
        command = [
            ffmpeg,
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
        self._run(command)

    def _separate_stems(
        self,
        audio_path: Path,
        output_dir: Path,
        progress: Optional[Callable[[str], None]],
    ) -> Dict[str, Path]:
        if not self._demucs_available():
            raise AudioProcessingError(
                "demucs-mlx 실행 파일을 찾지 못했습니다. "
                "Python 3.10 이상 환경에서 `pip install 'demucs-mlx[convert]'`로 설치하세요."
            )

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "guitarta.services.mlx_demucs_runner",
            str(audio_path),
            "-n",
            DEMUX_MODEL,
            "-o",
            str(output_dir),
        ]
        self._run(command, progress=progress)
        stems = self._find_stems(output_dir)
        required = {"bass", "guitar", "drums"}
        missing = sorted(required.difference(stems))
        if missing:
            raise AudioProcessingError(
                f"Demucs 결과에서 필요한 stem을 찾지 못했습니다: {', '.join(missing)}"
            )
        return stems

    def _use_single_stem(
        self,
        stems: Dict[str, Path],
        stem_name: str,
        output: Path,
        center_stereo: bool = False,
    ) -> None:
        source = stems.get(stem_name)
        if source is None:
            raise AudioProcessingError(f"{stem_name} 단독 음원을 만들 stem이 없습니다.")
        if center_stereo:
            self._run(
                [
                    self._ffmpeg(),
                    "-y",
                    "-i",
                    str(source),
                    "-af",
                    DRUMS_CENTER_FILTER,
                    "-c:a",
                    "pcm_s16le",
                    str(output),
                ]
            )
            return
        self._run([self._ffmpeg(), "-y", "-i", str(source), "-c:a", "pcm_s16le", str(output)])

    def _center_stereo_file(self, path: Path) -> None:
        if not path.exists():
            return
        temp = path.with_suffix(".balanced.tmp.wav")
        self._run(
            [
                self._ffmpeg(),
                "-y",
                "-i",
                str(path),
                "-af",
                DRUMS_CENTER_FILTER,
                "-c:a",
                "pcm_s16le",
                str(temp),
            ]
        )
        temp.replace(path)

    @staticmethod
    def _marker_value(path: Path) -> str:
        try:
            return path.read_text().strip()
        except OSError:
            return ""

    def _mix_without(self, stems: Dict[str, Path], excluded_stem: str, output: Path) -> None:
        included = [path for name, path in sorted(stems.items()) if name != excluded_stem]
        if not included:
            raise AudioProcessingError(f"{excluded_stem} 제외 음원을 만들 stem이 없습니다.")
        if len(included) == 1:
            self._run([self._ffmpeg(), "-y", "-i", str(included[0]), "-c:a", "pcm_s16le", str(output)])
            return

        labels = "".join(f"[{index}:a]" for index in range(len(included)))
        filter_complex = f"{labels}amix=inputs={len(included)}:normalize=0[a]"
        command = [self._ffmpeg(), "-y"]
        for path in included:
            command.extend(["-i", str(path)])
        command.extend(["-filter_complex", filter_complex, "-map", "[a]", "-c:a", "pcm_s16le", str(output)])
        self._run(command)

    def _find_stems(self, output_dir: Path) -> Dict[str, Path]:
        stems: Dict[str, Path] = {}
        for path in output_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a"}:
                name = path.stem.lower()
                if name in {"drums", "bass", "other", "vocals", "guitar", "piano"}:
                    stems[name] = path
        return stems

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

    def _ffmpeg(self) -> str:
        found = shutil.which("ffmpeg")
        if found:
            return found
        for candidate in (
            Path("/opt/homebrew/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
            Path("/usr/bin/ffmpeg"),
        ):
            if candidate.exists():
                return str(candidate)
        raise AudioProcessingError("ffmpeg를 찾지 못했습니다.")

    @staticmethod
    def _demucs_available() -> bool:
        for command in ("demucs-mlx", "mlx-demucs"):
            found = shutil.which(command)
            if found:
                return True
        try:
            import demucs_mlx  # noqa: F401
        except Exception:
            return False
        return True

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
