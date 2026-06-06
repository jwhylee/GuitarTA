import threading
from pathlib import Path
from typing import List, Optional

import flet as ft
import flet_audio as fta
import flet_video as fvideo

from guitarta.models import Category, Note, TempoMarker
from guitarta.paths import audio_dir, database_path, media_dir
from guitarta.services.downloader import DownloadError, YouTubeDownloader
from guitarta.services.metronome import Metronome, ensure_click_wav
from guitarta.services.repository import Repository


BG = "#0F0E0C"
PANEL = "#191714"
PANEL_2 = "#242019"
BEIGE = "#F4E3C4"
BEIGE_2 = "#E8D0A5"
TEXT = "#FFF7EA"
MUTED = "#A99E8B"
LINE = "#473E31"
ACCENT = "#F0C982"
DANGER = "#D96855"


class GuitarTAApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.repo = Repository(database_path())
        self.downloader = YouTubeDownloader(media_dir())
        self.selected_category_id: Optional[int] = None
        self.selected_note: Optional[Note] = None
        self.selected_marker: Optional[TempoMarker] = None
        self.current_position_ms = 0
        self.is_downloading = False
        self.sidebar_open = True

        normal_click = ensure_click_wav(audio_dir() / "click.wav", 1250)
        accent_click = ensure_click_wav(audio_dir() / "accent.wav", 1800)
        self.click_audio = fta.Audio(src=str(normal_click), autoplay=False)
        self.accent_audio = fta.Audio(src=str(accent_click), autoplay=False)
        self.metronome = Metronome(self._play_tick)

        self.categories: List[Category] = []
        self.notes: List[Note] = []
        self.markers: List[TempoMarker] = []

    def build(self) -> None:
        self.page.title = "GuitarTA"
        self.page.window_width = 1360
        self.page.window_height = 840
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = BG
        self.page.padding = 0
        self.page.overlay.extend([self.click_audio, self.accent_audio])

        self.new_title_input = self._text_field("새 노트 제목", expand=True)
        self.url_input = self._text_field("유튜브 링크", expand=True)
        self.category_input = self._text_field("카테고리", width=150, value="미분류")
        self.download_status = ft.Text("", color=MUTED, size=12)
        self.video_status = ft.Text("", color=MUTED, size=12)
        self.category_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self.note_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        self.title_input = self._text_field("노트 제목", expand=True)
        self.memo_input = ft.TextField(
            label="연습 메모",
            multiline=True,
            min_lines=5,
            max_lines=8,
            border_color=LINE,
            focused_border_color=ACCENT,
            bgcolor=PANEL_2,
            color=TEXT,
            label_style=ft.TextStyle(color=MUTED),
        )
        self.note_category_input = self._text_field("카테고리", width=160)
        self.save_note_button = self._button("저장", ft.Icons.SAVE_OUTLINED, self._save_note)

        self.video = self._make_video()
        self.play_button = self._button("재생", ft.Icons.PLAY_ARROW_ROUNDED, self._play_video)
        self.pause_button = self._button("일시정지", ft.Icons.PAUSE_ROUNDED, self._pause_video)
        self.position_input = self._text_field("이동 초", width=90, value="0")
        self.seek_button = self._button("이동", ft.Icons.SKIP_NEXT_ROUNDED, self._seek_video)
        self.rate_text = ft.Text("1.00x", color=BEIGE, size=16, weight=ft.FontWeight.BOLD)
        self.rate_slider = ft.Slider(
            min=0.5,
            max=2.0,
            divisions=30,
            value=1.0,
            active_color=ACCENT,
            inactive_color=LINE,
            on_change=self._change_rate,
        )

        self.marker_name_input = self._text_field("구간 이름", expand=True, value="새 구간")
        self.marker_start_input = self._text_field("시작 ms", width=110, value="0")
        self.bpm_input = self._text_field("BPM", width=90, value="120")
        self.beats_input = self._text_field("박자", width=80, value="4")
        self.accent_checkbox = ft.Checkbox(
            label="첫 박 강조",
            value=True,
            active_color=ACCENT,
            check_color=BG,
            label_style=ft.TextStyle(color=TEXT),
        )
        self.marker_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self.metronome_status = ft.Text("정지", color=MUTED, size=12)

        self.sidebar_host = ft.Container(content=self._sidebar(), width=360)
        self.sidebar_divider = ft.VerticalDivider(width=1, color=LINE)
        self.sidebar_rail = ft.Container(content=self._sidebar_rail(), width=54, visible=False)
        self.page.add(
            ft.Row(
                [
                    self.sidebar_host,
                    self.sidebar_divider,
                    self.sidebar_rail,
                    self._main_area(),
                ],
                expand=True,
                spacing=0,
            )
        )
        self._refresh_all()

    def _sidebar(self) -> ft.Container:
        return ft.Container(
            bgcolor=PANEL,
            padding=ft.padding.all(18),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("GuitarTA", size=28, color=BEIGE, weight=ft.FontWeight.BOLD, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                                icon_color=BEIGE,
                                tooltip="사이드바 닫기",
                                on_click=self._toggle_sidebar,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text("기타와 베이스 연습 노트", size=13, color=MUTED),
                    ft.Divider(color=LINE),
                    ft.Text("카테고리", color=BEIGE_2, weight=ft.FontWeight.BOLD),
                    ft.Container(self.category_list, height=180),
                    ft.Text("노트", color=BEIGE_2, weight=ft.FontWeight.BOLD),
                    self.note_list,
                ],
                expand=True,
                spacing=12,
            ),
        )

    def _sidebar_rail(self) -> ft.Container:
        return ft.Container(
            bgcolor=PANEL,
            padding=ft.padding.symmetric(horizontal=6, vertical=14),
            content=ft.Column(
                [
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        icon_color=BEIGE,
                        tooltip="사이드바 열기",
                        on_click=self._toggle_sidebar,
                    ),
                    ft.Text("노트", color=BEIGE, size=12, rotate=ft.Rotate(1.5708)),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=22,
            ),
        )

    def _main_area(self) -> ft.Container:
        empty = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.MUSIC_VIDEO_ROUNDED, color=LINE, size=58),
                    ft.Text("노트를 선택하거나 위 입력창에 유튜브 링크를 추가하세요.", color=MUTED, size=16),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )
        self.detail_area = ft.Container(content=empty, expand=True)
        return ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.all(20),
            content=ft.Column(
                [
                    self._top_bar(),
                    self._download_panel(),
                    self.detail_area,
                ],
                expand=True,
                spacing=16,
            ),
        )

    def _top_bar(self) -> ft.Control:
        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("GuitarTA", color=BEIGE, size=26, weight=ft.FontWeight.BOLD),
                        ft.Text("v1.3  기타/베이스 연습 노트", color=MUTED, size=12),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _note_detail(self) -> ft.Control:
        if not self.selected_note:
            return ft.Container(
                content=ft.Text("다운로드한 영상이 이 영역에 표시됩니다.", color=MUTED, size=16),
                alignment=ft.alignment.center,
                expand=True,
            )

        self.title_input.value = self.selected_note.title
        self.memo_input.value = self.selected_note.memo
        self.note_category_input.value = self._category_name(self.selected_note.category_id)
        self.rate_slider.value = self.selected_note.playback_rate
        self.rate_text.value = f"{self.selected_note.playback_rate:.2f}x"

        return ft.Column(
            [
                ft.Row(
                    [
                        self.title_input,
                        self.note_category_input,
                        self.save_note_button,
                    ],
                    spacing=10,
                ),
                ft.Container(
                    content=self.video,
                    bgcolor="#050505",
                    border=ft.border.all(1, LINE),
                    border_radius=8,
                    padding=ft.padding.all(8),
                    height=430,
                ),
                self.video_status,
                ft.Row(
                    [
                        self.play_button,
                        self.pause_button,
                        self.position_input,
                        self.seek_button,
                        ft.Container(width=16),
                        ft.Text("배속", color=MUTED),
                        ft.Container(self.rate_slider, width=280),
                        self.rate_text,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Container(
                            bgcolor=PANEL,
                            border=ft.border.all(1, LINE),
                            border_radius=8,
                            padding=ft.padding.all(14),
                            content=ft.Column(
                                [
                                    ft.Text("노트 메모", color=BEIGE, size=18, weight=ft.FontWeight.BOLD),
                                    self.memo_input,
                                ],
                                spacing=10,
                            ),
                            expand=1,
                        ),
                        ft.Container(self._metronome_panel(), width=410),
                    ],
                    expand=True,
                    spacing=16,
                ),
            ],
            expand=True,
            spacing=14,
        )

    def _download_panel(self) -> ft.Control:
        return ft.Container(
            bgcolor=PANEL,
            border=ft.border.all(1, LINE),
            border_radius=8,
            padding=ft.padding.all(14),
            content=ft.Column(
                [
                    ft.Text("새 연습 영상", color=BEIGE, size=18, weight=ft.FontWeight.BOLD),
                    ft.Row([self.new_title_input, self.category_input], spacing=10),
                    ft.Row(
                        [
                            self.url_input,
                            self._button("다운로드", ft.Icons.DOWNLOAD_ROUNDED, self._download_note),
                        ],
                        spacing=10,
                    ),
                    self.download_status,
                ],
                spacing=10,
            ),
        )

    def _metronome_panel(self) -> ft.Control:
        return ft.Container(
            bgcolor=PANEL,
            border=ft.border.all(1, LINE),
            border_radius=8,
            padding=ft.padding.all(14),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("메트로놈 구간", color=BEIGE, size=18, weight=ft.FontWeight.BOLD),
                            self.metronome_status,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row([self.marker_name_input], spacing=8),
                    ft.Row(
                        [
                            self.marker_start_input,
                            self._button("현재 위치", ft.Icons.MY_LOCATION_ROUNDED, self._capture_position),
                        ],
                        spacing=8,
                    ),
                    ft.Row([self.bpm_input, self.beats_input, self.accent_checkbox], spacing=8),
                    ft.Row(
                        [
                            self._button("구간 추가", ft.Icons.ADD_ROUNDED, self._add_marker),
                            self._button("시작", ft.Icons.GRAPHIC_EQ_ROUNDED, self._start_metronome),
                            self._button("정지", ft.Icons.STOP_ROUNDED, self._stop_metronome),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(color=LINE),
                    self.marker_list,
                ],
                expand=True,
                spacing=10,
            ),
        )

    def _refresh_all(self) -> None:
        self.categories = self.repo.categories()
        self.notes = self.repo.notes(self.selected_category_id)
        if self.selected_note:
            fresh = self.repo.note(self.selected_note.id)
            self.selected_note = fresh
            self.markers = self.repo.tempo_markers(fresh.id) if fresh else []
        self._render_sidebar()
        self._render_detail()
        self.page.update()

    def _render_sidebar(self) -> None:
        self.category_list.controls = [
            self._category_tile(None, "전체", self.selected_category_id is None)
        ] + [
            self._category_tile(category.id, category.name, category.id == self.selected_category_id)
            for category in self.categories
        ]
        self.note_list.controls = [
            self._note_tile(note, self.selected_note is not None and note.id == self.selected_note.id)
            for note in self.notes
        ]

    def _render_detail(self) -> None:
        if self.selected_note:
            self._load_video(self.selected_note)
            self._render_markers()
        self.detail_area.content = self._note_detail()

    def _render_markers(self) -> None:
        self.marker_list.controls = []
        for marker in self.markers:
            selected = self.selected_marker is not None and marker.id == self.selected_marker.id
            label = f"{marker.name}  {self._format_ms(marker.start_ms)}  {marker.bpm} BPM"
            self.marker_list.controls.append(
                ft.Container(
                    bgcolor=PANEL_2 if selected else BG,
                    border=ft.border.all(1, ACCENT if selected else LINE),
                    border_radius=6,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Row(
                        [
                            ft.Text(label, color=TEXT, expand=True, size=13),
                            ft.IconButton(
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                icon_color=BEIGE,
                                tooltip="이 구간 선택",
                                on_click=lambda e, m=marker: self._select_marker(m),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=DANGER,
                                tooltip="구간 삭제",
                                on_click=lambda e, m=marker: self._delete_marker(m),
                            ),
                        ],
                        spacing=4,
                    ),
                )
            )

    def _category_tile(self, category_id: Optional[int], label: str, selected: bool) -> ft.Control:
        return ft.Container(
            bgcolor=PANEL_2 if selected else None,
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            on_click=lambda e: self._select_category(category_id),
            content=ft.Text(label, color=BEIGE if selected else TEXT, size=14),
        )

    def _note_tile(self, note: Note, selected: bool) -> ft.Control:
        return ft.Container(
            bgcolor=PANEL_2 if selected else None,
            border=ft.border.all(1, ACCENT if selected else LINE),
            border_radius=6,
            padding=ft.padding.all(10),
            on_click=lambda e, n=note: self._select_note(n),
            content=ft.Column(
                [
                    ft.Text(note.title, color=BEIGE if selected else TEXT, size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(self._category_name(note.category_id), color=MUTED, size=12),
                ],
                spacing=3,
            ),
        )

    def _select_category(self, category_id: Optional[int]) -> None:
        self.selected_category_id = category_id
        self.notes = self.repo.notes(category_id)
        self._render_sidebar()
        self.page.update()

    def _toggle_sidebar(self, event: ft.ControlEvent) -> None:
        self.sidebar_open = not self.sidebar_open
        self.sidebar_host.visible = self.sidebar_open
        self.sidebar_divider.visible = self.sidebar_open
        self.sidebar_rail.visible = not self.sidebar_open
        self.page.update()

    def _select_note(self, note: Note) -> None:
        self.selected_note = self.repo.note(note.id)
        self.selected_marker = None
        self.markers = self.repo.tempo_markers(note.id)
        self._render_detail()
        self._render_sidebar()
        self.page.update()

    def _download_note(self, event: ft.ControlEvent) -> None:
        if self.is_downloading:
            return
        url = self.url_input.value or ""
        note_title = self.new_title_input.value or ""
        category_name = self.category_input.value or "미분류"
        self.is_downloading = True
        self.download_status.value = "다운로드 준비 중..."
        self.page.update()

        def worker() -> None:
            try:
                category = self.repo.create_category(category_name)
                result = self.downloader.download(url, self._set_download_status)
                note = self.repo.create_note(
                    title=note_title.strip() or result["title"],
                    source_url=result["source_url"],
                    media_path=result["media_path"],
                    category_id=category.id,
                )
                self.selected_category_id = category.id
                self.selected_note = note
                self.selected_marker = None
                self.url_input.value = ""
                self.new_title_input.value = ""
                self.download_status.value = "노트가 추가되었습니다."
            except DownloadError as exc:
                self.download_status.value = str(exc)
            finally:
                self.is_downloading = False
                self.categories = self.repo.categories()
                self.notes = self.repo.notes(self.selected_category_id)
                self.markers = self.repo.tempo_markers(self.selected_note.id) if self.selected_note else []
                self._render_sidebar()
                self._render_detail()
                self.page.update()

        threading.Thread(target=worker, daemon=True).start()

    def _set_download_status(self, text: str) -> None:
        self.download_status.value = text
        self.page.update()

    def _save_note(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        category = self.repo.create_category(self.note_category_input.value or "미분류")
        self.repo.update_note(
            note_id=self.selected_note.id,
            title=self.title_input.value or "",
            memo=self.memo_input.value or "",
            playback_rate=float(self.rate_slider.value or 1.0),
            category_id=category.id,
        )
        self.selected_category_id = category.id
        self.selected_note = self.repo.note(self.selected_note.id)
        self._refresh_all()

    def _load_video(self, note: Note) -> None:
        path = Path(note.media_path).expanduser()
        if not path.exists():
            self.video = self._make_video()
            self.video_status.value = f"영상 파일을 찾을 수 없습니다: {path}"
            return

        media = fvideo.VideoMedia(path.resolve().as_uri())
        self.video = self._make_video([media])
        self.video.playback_rate = note.playback_rate
        self.video_status.value = f"영상 준비 중: {path.name}"

    def _make_video(self, playlist: Optional[List[fvideo.VideoMedia]] = None) -> fvideo.Video:
        return fvideo.Video(
            expand=True,
            playlist=playlist or [],
            aspect_ratio=16 / 9,
            autoplay=False,
            fill_color=BG,
            volume=100,
            on_loaded=self._on_video_loaded,
            on_error=self._on_video_error,
        )

    def _on_video_loaded(self, event: ft.ControlEvent) -> None:
        self.video_status.value = "영상이 준비되었습니다."
        self.page.update()

    def _on_video_error(self, event: ft.ControlEvent) -> None:
        detail = getattr(event, "data", "") or "알 수 없는 오류"
        self.video_status.value = f"영상 로드 오류: {detail}"
        self.page.update()

    def _play_video(self, event: ft.ControlEvent) -> None:
        self._call_video("play")
        if self.selected_marker:
            self._start_metronome(event)

    def _pause_video(self, event: ft.ControlEvent) -> None:
        self._call_video("pause")
        self._stop_metronome(event)

    def _seek_video(self, event: ft.ControlEvent) -> None:
        seconds = self._int_value(self.position_input.value, 0)
        self.current_position_ms = max(0, seconds * 1000)
        self._seek_ms(self.current_position_ms)

    def _seek_ms(self, position_ms: int) -> None:
        if hasattr(self.video, "seek"):
            try:
                self.video.seek(position_ms)
            except TypeError:
                self.video.seek(position_ms / 1000)
        self.page.update()

    def _change_rate(self, event: ft.ControlEvent) -> None:
        value = round(float(self.rate_slider.value or 1.0) / 0.05) * 0.05
        value = max(0.5, min(2.0, value))
        self.rate_slider.value = value
        self.rate_text.value = f"{value:.2f}x"
        self.video.playback_rate = value
        if self.selected_note:
            self.repo.update_note(
                self.selected_note.id,
                self.title_input.value or self.selected_note.title,
                self.memo_input.value or "",
                value,
                self.selected_note.category_id,
            )
        self.page.update()

    def _capture_position(self, event: ft.ControlEvent) -> None:
        value = self._video_position_ms()
        self.current_position_ms = value
        self.marker_start_input.value = str(value)
        self.page.update()

    def _add_marker(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        marker = self.repo.create_tempo_marker(
            note_id=self.selected_note.id,
            name=self.marker_name_input.value or "새 구간",
            start_ms=self._int_value(self.marker_start_input.value, 0),
            bpm=self._int_value(self.bpm_input.value, 120),
            beats_per_bar=self._int_value(self.beats_input.value, 4),
            accent_first_beat=bool(self.accent_checkbox.value),
        )
        self.selected_marker = marker
        self.markers = self.repo.tempo_markers(self.selected_note.id)
        self._render_markers()
        self.page.update()

    def _select_marker(self, marker: TempoMarker) -> None:
        self.selected_marker = marker
        self.marker_name_input.value = marker.name
        self.marker_start_input.value = str(marker.start_ms)
        self.bpm_input.value = str(marker.bpm)
        self.beats_input.value = str(marker.beats_per_bar)
        self.accent_checkbox.value = marker.accent_first_beat
        self._seek_ms(marker.start_ms)
        self._render_markers()
        self.page.update()

    def _delete_marker(self, marker: TempoMarker) -> None:
        self.repo.delete_tempo_marker(marker.id)
        if self.selected_marker and self.selected_marker.id == marker.id:
            self.selected_marker = None
        if self.selected_note:
            self.markers = self.repo.tempo_markers(self.selected_note.id)
        self._render_markers()
        self.page.update()

    def _start_metronome(self, event: ft.ControlEvent) -> None:
        marker = self.selected_marker
        bpm = marker.bpm if marker else self._int_value(self.bpm_input.value, 120)
        beats = marker.beats_per_bar if marker else self._int_value(self.beats_input.value, 4)
        accent = marker.accent_first_beat if marker else bool(self.accent_checkbox.value)
        if marker:
            self._seek_ms(marker.start_ms)
        self.metronome.start(bpm, beats, accent)
        self.metronome_status.value = f"{bpm} BPM 재생 중"
        self.page.update()

    def _stop_metronome(self, event: ft.ControlEvent) -> None:
        self.metronome.stop()
        self.metronome_status.value = "정지"
        self.page.update()

    def _play_tick(self, accent: bool) -> None:
        audio = self.accent_audio if accent else self.click_audio
        try:
            audio.play()
        except Exception:
            pass

    def _call_video(self, method_name: str) -> None:
        method = getattr(self.video, method_name, None)
        if callable(method):
            method()
        self.page.update()

    def _video_position_ms(self) -> int:
        for attr in ("position", "current_position"):
            value = getattr(self.video, attr, None)
            if isinstance(value, (int, float)):
                return int(value)
        method = getattr(self.video, "get_current_position", None)
        if callable(method):
            try:
                return int(method())
            except Exception:
                return self.current_position_ms
        return self.current_position_ms

    def _category_name(self, category_id: Optional[int]) -> str:
        for category in self.categories:
            if category.id == category_id:
                return category.name
        return "미분류"

    def _text_field(self, label: str, width: Optional[int] = None, expand: bool = False, value: str = "") -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            width=width,
            expand=expand,
            dense=True,
            border_color=LINE,
            focused_border_color=ACCENT,
            bgcolor=PANEL_2,
            color=TEXT,
            cursor_color=ACCENT,
            label_style=ft.TextStyle(color=MUTED),
        )

    def _button(self, label: str, icon: str, handler) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            text=label,
            icon=icon,
            on_click=handler,
            style=ft.ButtonStyle(
                bgcolor=ACCENT,
                color=BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
            ),
        )

    @staticmethod
    def _int_value(value: Optional[str], default: int) -> int:
        try:
            return int(float(value or default))
        except ValueError:
            return default

    @staticmethod
    def _format_ms(value: int) -> str:
        seconds = max(0, value) // 1000
        minutes = seconds // 60
        return f"{minutes:02d}:{seconds % 60:02d}"
