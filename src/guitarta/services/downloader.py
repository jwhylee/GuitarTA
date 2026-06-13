import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from yt_dlp import YoutubeDL


class DownloadError(RuntimeError):
    pass


BEST_VIDEO_FORMAT = (
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
    "best[ext=mp4][vcodec^=avc1]/"
    "best[ext=mp4]/best"
)


class YouTubeDownloader:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        url: str,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, str]:
        clean_url = url.strip()
        if not clean_url:
            raise DownloadError("유튜브 링크를 입력해주세요.")

        def hook(data: Dict[str, object]) -> None:
            if progress is None:
                return
            status = data.get("status")
            if status == "downloading":
                percent = data.get("_percent_str") or ""
                speed = data.get("_speed_str") or ""
                progress(f"다운로드 중 {percent} {speed}".strip())
            elif status == "finished":
                progress("영상 처리 중...")

        try:
            external = self._find_external_yt_dlp()
            if external:
                return self._download_with_cli(clean_url, hook, external)
            return self._download_with_options(clean_url, self._options(hook))
        except Exception as exc:
            message = str(exc)
            if "HTTP Error 403" in message:
                raise DownloadError(
                    "YouTube가 이 영상 파일 다운로드 요청을 차단했습니다. "
                    "현재 yt-dlp의 YouTube SABR/PO Token 제한으로 발생할 수 있으며, "
                    "링크 자체는 인식되지만 실제 파일 URL 접근이 거부된 상태입니다."
                ) from exc
            raise DownloadError(f"영상을 가져오지 못했습니다: {exc}") from exc

    def _options(self, hook: Callable[[Dict[str, object]], None]) -> Dict[str, object]:
        options: Dict[str, object] = {
            "format": BEST_VIDEO_FORMAT,
            "format_sort": ["res", "fps", "vcodec:avc1", "ext:mp4:m4a"],
            "merge_output_format": "mp4",
            "outtmpl": str(self.output_dir / "%(title).180s [%(id)s].%(ext)s"),
            "noplaylist": True,
            "force_ipv4": True,
            "retries": 3,
            "fragment_retries": 3,
            "http_chunk_size": 10 * 1024 * 1024,
            "http_headers": {
                "Referer": "https://www.youtube.com/",
                "Origin": "https://www.youtube.com",
            },
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
        }
        ffmpeg_location = self._find_ffmpeg_location()
        if ffmpeg_location:
            options["ffmpeg_location"] = ffmpeg_location
        return options

    def _download_with_options(self, clean_url: str, options: Dict[str, object]) -> Dict[str, str]:
        from yt_dlp import YoutubeDL

        with YoutubeDL(options) as ydl:
            before = self._media_files()
            info = ydl.extract_info(clean_url, download=True)
            media_path = self._resolve_downloaded_file(info, before, ydl)

        if not media_path.exists():
            raise DownloadError("다운로드된 영상 파일을 찾지 못했습니다.")

        return {
            "title": str(info.get("title") or "새 연습 노트"),
            "source_url": clean_url,
            "media_path": str(media_path),
        }

    def _download_with_cli(
        self,
        clean_url: str,
        progress: Callable[[Dict[str, object]], None],
        executable: Path,
    ) -> Dict[str, str]:
        before = self._media_files()
        command = [
            str(executable),
            "--newline",
            "--no-playlist",
            "-f",
            BEST_VIDEO_FORMAT,
            "--merge-output-format",
            "mp4",
            "-o",
            str(self.output_dir / "%(title).180s [%(id)s].%(ext)s"),
        ]
        ffmpeg_location = self._find_ffmpeg_location()
        if ffmpeg_location:
            command.extend(["--ffmpeg-location", ffmpeg_location])
        command.append(clean_url)

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output_lines = []
        existing_media_path: Optional[Path] = None
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            output_lines.append(line)
            existing_media_path = existing_media_path or self._existing_media_from_line(line)
            if line.startswith("[download]"):
                progress({"status": "downloading", "_percent_str": self._compact_progress(line)})
            elif "Merging formats" in line or "Deleting original file" in line:
                progress({"status": "finished"})

        exit_code = process.wait()
        if exit_code != 0:
            raise RuntimeError("\n".join(output_lines[-8:]))

        current = self._media_files()
        new_files = [path for path, mtime in current.items() if before.get(path) != mtime]
        if not new_files:
            if existing_media_path and existing_media_path.exists():
                media_path = existing_media_path
            else:
                raise DownloadError("다운로드된 영상 파일을 찾지 못했습니다.")
        else:
            media_path = max(new_files, key=lambda path: path.stat().st_mtime)

        return {
            "title": self._title_from_file(media_path),
            "source_url": clean_url,
            "media_path": str(media_path),
        }

    def _resolve_downloaded_file(
        self,
        info: Dict[str, object],
        before: Dict[Path, float],
        ydl: "YoutubeDL",
    ) -> Path:
        requested = info.get("requested_downloads")
        if isinstance(requested, list):
            for item in requested:
                if not isinstance(item, dict):
                    continue
                for key in ("filepath", "_filename", "filename"):
                    value = item.get(key)
                    if value and Path(str(value)).exists():
                        return Path(str(value))

        prepared = Path(ydl.prepare_filename(info))
        candidates = [prepared, prepared.with_suffix(".mp4")]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        video_id = str(info.get("id") or "")
        current = self._media_files()
        new_files = [path for path, mtime in current.items() if before.get(path) != mtime]
        if video_id:
            id_matches = [path for path in new_files if video_id in path.name]
            if id_matches:
                return max(id_matches, key=lambda path: path.stat().st_mtime)
        if new_files:
            return max(new_files, key=lambda path: path.stat().st_mtime)

        return prepared

    def _media_files(self) -> Dict[Path, float]:
        return {
            path: path.stat().st_mtime
            for path in self.output_dir.glob("*")
            if path.is_file() and path.suffix.lower() in {".mp4", ".m4v", ".mov", ".webm", ".mkv"}
        }

    @staticmethod
    def _find_ffmpeg_location() -> Optional[str]:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return str(Path(ffmpeg_path).parent)

        for candidate in (
            Path("/opt/homebrew/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
            Path("/usr/bin/ffmpeg"),
        ):
            if candidate.exists():
                return str(candidate.parent)
        try:
            import imageio_ffmpeg

            return str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
        except Exception:
            pass
        return None

    @staticmethod
    def _find_external_yt_dlp() -> Optional[Path]:
        candidates = (
            Path("/Users/jylee/JYLee/CS/Vibe Coding/YtCD/.venv/bin/yt-dlp"),
            Path("/opt/homebrew/bin/yt-dlp"),
            Path("/usr/local/bin/yt-dlp"),
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        found = shutil.which("yt-dlp")
        return Path(found) if found else None

    @staticmethod
    def _compact_progress(line: str) -> str:
        marker = " of "
        if marker in line:
            return line.replace("[download]", "").strip()
        return line

    @staticmethod
    def _existing_media_from_line(line: str) -> Optional[Path]:
        marker = " has already been downloaded"
        prefix = "[download] "
        if marker not in line or not line.startswith(prefix):
            return None
        path = Path(line[len(prefix): line.index(marker)])
        if path.suffix.lower() in {".mp4", ".m4v", ".mov", ".webm", ".mkv"}:
            return path
        return None

    @staticmethod
    def _title_from_file(path: Path) -> str:
        title = path.stem
        if " [" in title and title.endswith("]"):
            title = title.rsplit(" [", 1)[0]
        return title or "새 연습 노트"
