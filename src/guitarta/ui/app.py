import threading
from pathlib import Path
from typing import List, Optional

import flet as ft
import flet_video as fvideo

from guitarta.models import Category, Note, TempoMarker
from guitarta.paths import database_path, media_dir
from guitarta.services.downloader import DownloadError, YouTubeDownloader
from guitarta.services.repository import Repository


BG = "#0F0E0C"
PANEL = "#191714"
PANEL_2 = "#242019"
SIDEBAR_BG = "#F4E3C4"
SIDEBAR_PANEL = "#E8D0A5"
SIDEBAR_TEXT = "#201A12"
SIDEBAR_MUTED = "#6F604A"
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
        self.loop_timer: Optional[threading.Timer] = None
        self.loop_active = False
        self.restore_app_fullscreen = False
        self.dialog_category_name = "기타"

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
        self.page.on_keyboard_event = self._handle_keyboard_event

        self.new_title_input = self._text_field("새 노트 제목", width=250)
        self.url_input = self._text_field("유튜브 링크", width=430)
        self.category_input = self._text_field("직접 입력", width=220, value="")
        self.category_picker = ft.Column(spacing=6)
        self.download_status = ft.Text("", color=MUTED, size=12)
        self.note_dialog_mode = "create"
        self.note_dialog = self._note_settings_dialog()
        self.delete_dialog = self._delete_note_dialog()
        self.video_status = ft.Text("", color=MUTED, size=12)
        self.category_dropdown = ft.Dropdown(
            label="카테고리",
            width=320,
            dense=True,
            menu_width=320,
            max_menu_height=260,
            border_color="#BCA77C",
            focused_border_color=SIDEBAR_TEXT,
            bgcolor="#FFF2D7",
            color=SIDEBAR_TEXT,
            focused_color=SIDEBAR_TEXT,
            text_style=ft.TextStyle(color=SIDEBAR_TEXT),
            label_style=ft.TextStyle(color=SIDEBAR_MUTED),
            select_icon_enabled_color=SIDEBAR_TEXT,
            icon_enabled_color=SIDEBAR_TEXT,
            on_change=self._select_category_from_dropdown,
        )
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
        self.delete_note_button = self._danger_button("삭제", ft.Icons.DELETE_OUTLINE_ROUNDED, self._open_delete_note)

        self.video = self._make_video()
        self.rate_text = ft.Text("1.00x", color=BEIGE, size=16, weight=ft.FontWeight.BOLD)
        self.rate_slider = ft.Slider(
            min=0.1,
            max=2.0,
            divisions=38,
            value=1.0,
            active_color=ACCENT,
            inactive_color=LINE,
            on_change=self._change_rate,
        )

        self.marker_name_input = self._text_field("구간 이름", expand=True, value="반복 구간")
        self.marker_start_input = self._text_field("시작", width=105, value="00:00:00")
        self.marker_end_input = self._text_field("종료", width=105, value="00:00:00")
        self.marker_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self.loop_status = ft.Text("반복 대기", color=MUTED, size=12)

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
            bgcolor=SIDEBAR_BG,
            padding=ft.padding.symmetric(horizontal=14, vertical=16),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("GuitarTA", size=28, color=SIDEBAR_TEXT, weight=ft.FontWeight.BOLD, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                                icon_color=SIDEBAR_TEXT,
                                tooltip="사이드바 닫기",
                                on_click=self._toggle_sidebar,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.ElevatedButton(
                        text="새로운 노트 생성",
                        icon=ft.Icons.ADD_ROUNDED,
                        on_click=self._open_new_note,
                        style=ft.ButtonStyle(
                            bgcolor=SIDEBAR_TEXT,
                            color=SIDEBAR_BG,
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=ft.padding.symmetric(horizontal=12, vertical=12),
                        ),
                    ),
                    ft.Divider(color="#BCA77C"),
                    self.category_dropdown,
                    ft.Row(
                        [
                            ft.Text("노트", color=SIDEBAR_TEXT, weight=ft.FontWeight.BOLD, expand=True),
                            ft.Text("한 줄 보기", color=SIDEBAR_MUTED, size=12),
                        ],
                    ),
                    self.note_list,
                ],
                expand=True,
                spacing=10,
            ),
        )

    def _sidebar_rail(self) -> ft.Container:
        return ft.Container(
            bgcolor=SIDEBAR_BG,
            padding=ft.padding.symmetric(horizontal=6, vertical=14),
            content=ft.Column(
                [
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        icon_color=SIDEBAR_TEXT,
                        tooltip="사이드바 열기",
                        on_click=self._toggle_sidebar,
                    ),
                    ft.Text("노트", color=SIDEBAR_TEXT, size=12, rotate=ft.Rotate(1.5708)),
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
                    ft.Text("왼쪽에서 노트를 선택하세요.", color=MUTED, size=16),
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
                        ft.Text("v1.11  기타/베이스 연습 노트", color=MUTED, size=12),
                    ],
                    spacing=2,
                    expand=True,
                ),
                self._button("노트 설정", ft.Icons.TUNE_ROUNDED, self._open_note_settings),
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

        return ft.Container(
            padding=ft.padding.only(right=20),
            expand=True,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        self.selected_note.title,
                                        color=BEIGE,
                                        size=20,
                                        weight=ft.FontWeight.BOLD,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(self._category_name(self.selected_note.category_id), color=MUTED, size=12),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            self.delete_note_button,
                            self.save_note_button,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=self.video,
                                bgcolor="#050505",
                                border=ft.border.all(1, LINE),
                                border_radius=8,
                                padding=ft.padding.all(8),
                                expand=1,
                                height=560,
                            ),
                            ft.Container(content=self._practice_panel(), width=390),
                        ],
                        spacing=18,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Divider(color=LINE),
                    ft.Column(
                        [
                            ft.Text("노트 메모", color=BEIGE, size=18, weight=ft.FontWeight.BOLD),
                            self.memo_input,
                        ],
                        spacing=10,
                    ),
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=14,
            ),
        )

    def _download_panel(self) -> ft.Control:
        return ft.Container(
            bgcolor=PANEL,
            border=ft.border.all(1, LINE),
            border_radius=8,
            padding=ft.padding.all(12),
            content=ft.Column(
                [
                    ft.Text("새 노트", color=BEIGE, size=16, weight=ft.FontWeight.BOLD),
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
                spacing=8,
            ),
        )

    def _note_settings_dialog(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=True,
            bgcolor=PANEL,
            title=ft.Text("노트 설정", color=BEIGE, size=22, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=500,
                height=190,
                content=ft.Column(
                    [
                        self.new_title_input,
                        ft.Text("카테고리", color=MUTED, size=12, weight=ft.FontWeight.BOLD),
                        self.category_picker,
                        self.category_input,
                        self.url_input,
                        self.download_status,
                    ],
                    tight=True,
                    spacing=5,
                ),
            ),
            inset_padding=ft.padding.symmetric(horizontal=32, vertical=24),
            title_padding=ft.padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.padding.only(left=20, right=20, top=4, bottom=0),
            actions_padding=ft.padding.only(left=16, right=16, bottom=12, top=0),
            actions=[
                ft.TextButton("취소", on_click=self._close_note_settings),
                ft.ElevatedButton(
                    text="저장",
                    icon=ft.Icons.DOWNLOAD_ROUNDED,
                    on_click=self._download_note,
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT,
                        color=BG,
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _delete_note_dialog(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=True,
            bgcolor=PANEL,
            title=ft.Text("노트 삭제", color=BEIGE, size=20, weight=ft.FontWeight.BOLD),
            content=ft.Text("선택한 노트를 삭제할까요? 다운로드된 영상 파일은 유지됩니다.", color=TEXT),
            actions=[
                ft.TextButton("취소", on_click=lambda e: self.page.close(self.delete_dialog)),
                ft.ElevatedButton(
                    text="삭제",
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    on_click=self._delete_selected_note,
                    style=ft.ButtonStyle(
                        bgcolor=DANGER,
                        color=TEXT,
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _open_new_note(self, event: ft.ControlEvent) -> None:
        self.note_dialog_mode = "create"
        self.note_dialog.title.value = "새 노트 생성"
        self.new_title_input.value = ""
        self.dialog_category_name = "기타"
        self.category_input.value = ""
        self.url_input.value = ""
        self.url_input.label = "유튜브 링크"
        self.download_status.value = ""
        self._render_category_picker()
        self.page.open(self.note_dialog)

    def _open_note_settings(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            self._open_new_note(event)
            return
        self.note_dialog_mode = "update"
        self.note_dialog.title.value = "노트 설정"
        self.new_title_input.value = self.selected_note.title
        self.dialog_category_name = self._category_name(self.selected_note.category_id)
        self.category_input.value = ""
        self.url_input.value = ""
        self.url_input.label = "새 유튜브 링크"
        self.download_status.value = "링크를 입력하면 현재 노트의 영상만 교체됩니다."
        self._render_category_picker()
        self.page.open(self.note_dialog)

    def _close_note_settings(self, event: ft.ControlEvent) -> None:
        self.page.close(self.note_dialog)

    def _practice_panel(self) -> ft.Control:
        return ft.Container(
            border=ft.border.only(left=ft.BorderSide(1, LINE)),
            padding=ft.padding.only(left=18),
            content=ft.Column(
                [
                    ft.Text("배속", color=BEIGE, size=18, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            ft.Container(self.rate_slider, expand=True),
                            self.rate_text,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(color=LINE),
                    ft.Row(
                        [
                            ft.Text("반복 연습 구간", color=BEIGE, size=18, weight=ft.FontWeight.BOLD, expand=True),
                            self.loop_status,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.marker_name_input,
                    ft.Row(
                        [
                            ft.Text("시작", color=MUTED, width=40),
                            self.marker_start_input,
                            self._compact_button("현재 위치", ft.Icons.MY_LOCATION_ROUNDED, self._capture_position),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Text("종료", color=MUTED, width=40),
                            self.marker_end_input,
                            self._compact_button("현재 위치", ft.Icons.FLAG_ROUNDED, self._capture_end_position),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(color=LINE),
                    ft.Text("반복구간 조작", color=MUTED, size=12, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self._compact_button("추가", ft.Icons.ADD_ROUNDED, self._add_marker),
                            self._compact_button("시작", ft.Icons.REPEAT_ROUNDED, self._start_loop),
                            self._compact_button("정지", ft.Icons.STOP_ROUNDED, self._stop_loop),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(color=LINE),
                    ft.Container(self.marker_list, height=160),
                ],
                spacing=10,
            ),
        )

    def _refresh_all(self) -> None:
        self.categories = self.repo.categories()
        if self.selected_category_id is None:
            guitar = self._category_by_name("기타")
            if guitar:
                self.selected_category_id = guitar.id
        self.notes = self.repo.notes(self.selected_category_id)
        if self.selected_note:
            fresh = self.repo.note(self.selected_note.id)
            self.selected_note = fresh
            self.markers = self.repo.tempo_markers(fresh.id) if fresh else []
        self._render_sidebar()
        self._render_detail()
        self.page.update()

    def _render_sidebar(self) -> None:
        ordered_categories = self._ordered_categories()
        self.category_dropdown.options = [
            ft.dropdown.Option(
                key="all",
                text="전체",
                content=ft.Text("전체", color=SIDEBAR_TEXT, size=14, weight=ft.FontWeight.BOLD),
                text_style=ft.TextStyle(color=SIDEBAR_TEXT, size=14, weight=ft.FontWeight.BOLD),
            )
        ] + [
            ft.dropdown.Option(
                key=str(category.id),
                text=category.name,
                content=ft.Text(category.name, color=SIDEBAR_TEXT, size=14),
                text_style=ft.TextStyle(color=SIDEBAR_TEXT, size=14),
            )
            for category in ordered_categories
        ]
        self.category_dropdown.value = (
            str(self.selected_category_id) if self.selected_category_id is not None else "all"
        )
        self.note_list.controls = [
            self._note_tile(note, self.selected_note is not None and note.id == self.selected_note.id)
            for note in self.notes
        ]

    def _render_category_picker(self) -> None:
        controls = []
        for category in self._ordered_categories(include_all=False):
            selected = category.name == self.dialog_category_name
            controls.append(
                ft.Container(
                    content=ft.Text(
                        category.name,
                        color=BG if selected else TEXT,
                        size=12,
                        weight=ft.FontWeight.BOLD if selected else ft.FontWeight.NORMAL,
                    ),
                    bgcolor=ACCENT if selected else PANEL_2,
                    border=ft.border.all(1, ACCENT if selected else LINE),
                    border_radius=6,
                    padding=ft.padding.symmetric(horizontal=10, vertical=7),
                    on_click=lambda e, name=category.name: self._select_dialog_category(name),
                )
            )
        self.category_picker.controls = [
            ft.Row(controls, spacing=6, wrap=True),
        ]

    def _select_dialog_category(self, name: str) -> None:
        self.dialog_category_name = name
        self.category_input.value = ""
        self._render_category_picker()
        self.page.update()

    def _render_detail(self) -> None:
        if self.selected_note:
            self._load_video(self.selected_note)
            self._render_markers()
        self.detail_area.content = self._note_detail()

    def _render_markers(self) -> None:
        self.marker_list.controls = []
        for marker in self.markers:
            selected = self.selected_marker is not None and marker.id == self.selected_marker.id
            end_label = "끝까지" if marker.end_ms <= 0 else self._format_ms(marker.end_ms)
            label = f"{marker.name}  {self._format_ms(marker.start_ms)}-{end_label}"
            self.marker_list.controls.append(
                ft.Container(
                    bgcolor=PANEL_2 if selected else BG,
                    border=ft.border.all(1, ACCENT if selected else LINE),
                    border_radius=6,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    on_click=lambda e, m=marker: self._select_marker(m),
                    content=ft.Row(
                        [
                            ft.Text(label, color=TEXT, expand=True, size=13),
                            ft.IconButton(
                                icon=ft.Icons.REPEAT_ROUNDED,
                                icon_color=BEIGE,
                                tooltip="이 구간 반복",
                                on_click=lambda e, m=marker: self._play_loop_marker(m),
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

    def _note_tile(self, note: Note, selected: bool) -> ft.Control:
        return ft.Container(
            bgcolor="#FFF2D7" if selected else SIDEBAR_BG,
            border=ft.border.only(bottom=ft.BorderSide(1, "#D0B98A")),
            padding=ft.padding.symmetric(horizontal=8, vertical=9),
            on_click=lambda e, n=note: self._select_note(n),
            content=ft.Row(
                [
                    ft.Text(
                        note.title,
                        color=SIDEBAR_TEXT,
                        size=13,
                        weight=ft.FontWeight.BOLD if selected else ft.FontWeight.NORMAL,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(self._category_name(note.category_id), color=SIDEBAR_MUTED, size=11),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _select_category_from_dropdown(self, event: ft.ControlEvent) -> None:
        value = self.category_dropdown.value
        self._select_category(None if value in (None, "all") else int(value))

    def _select_category(self, category_id: Optional[int]) -> None:
        self.selected_category_id = category_id
        self.notes = self.repo.notes(category_id)
        self._render_sidebar()
        self.page.update()

    def _handle_keyboard_event(self, event: ft.KeyboardEvent) -> None:
        if event.key.lower() == "s" and (event.meta or event.ctrl):
            self._save_note_from_shortcut()

    def _save_note_from_shortcut(self) -> None:
        if not self.selected_note:
            return
        self._save_note(None)

    def _open_delete_note(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        self.page.open(self.delete_dialog)

    def _delete_selected_note(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            self.page.close(self.delete_dialog)
            return
        self.loop_active = False
        self._cancel_loop_timer()
        self.repo.delete_note(self.selected_note.id)
        self.selected_note = None
        self.selected_marker = None
        self.markers = []
        self.notes = self.repo.notes(self.selected_category_id)
        self.page.close(self.delete_dialog)
        self._render_sidebar()
        self._render_detail()
        self.page.update()

    def _toggle_sidebar(self, event: ft.ControlEvent) -> None:
        self.sidebar_open = not self.sidebar_open
        self.sidebar_host.visible = self.sidebar_open
        self.sidebar_divider.visible = self.sidebar_open
        self.sidebar_rail.visible = not self.sidebar_open
        self.page.update()

    def _select_note(self, note: Note) -> None:
        self.loop_active = False
        self._cancel_loop_timer()
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
        category_name = (self.category_input.value or "").strip() or self.dialog_category_name or "기타"
        if self.note_dialog_mode == "create" and not url.strip():
            self.download_status.value = "유튜브 링크를 입력하세요."
            self.page.update()
            return
        self.is_downloading = True
        self.download_status.value = "다운로드 준비 중..."
        self.page.update()

        def worker() -> None:
            try:
                category = self.repo.create_category(category_name)
                if self.note_dialog_mode == "update" and self.selected_note:
                    self.repo.update_note(
                        note_id=self.selected_note.id,
                        title=note_title.strip() or self.selected_note.title,
                        memo=self.memo_input.value or self.selected_note.memo,
                        playback_rate=float(self.rate_slider.value or self.selected_note.playback_rate),
                        category_id=category.id,
                    )
                    if url.strip():
                        result = self.downloader.download(url, self._set_download_status)
                        self.repo.update_note_media(
                            note_id=self.selected_note.id,
                            source_url=result["source_url"],
                            media_path=result["media_path"],
                        )
                    self.selected_category_id = category.id
                    self.selected_note = self.repo.note(self.selected_note.id)
                    self.download_status.value = "노트 설정이 저장되었습니다."
                else:
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
                    self.download_status.value = "노트가 추가되었습니다."
                self.url_input.value = ""
                self.new_title_input.value = ""
                self.page.close(self.note_dialog)
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
            show_controls=True,
            fill_color=BG,
            volume=100,
            on_loaded=self._on_video_loaded,
            on_enter_fullscreen=self._on_video_enter_fullscreen,
            on_exit_fullscreen=self._on_video_exit_fullscreen,
            on_error=self._on_video_error,
        )

    def _on_video_loaded(self, event: ft.ControlEvent) -> None:
        self.video_status.value = "영상이 준비되었습니다."
        self.page.update()

    def _on_video_error(self, event: ft.ControlEvent) -> None:
        detail = getattr(event, "data", "") or "알 수 없는 오류"
        self.video_status.value = f"영상 로드 오류: {detail}"
        self.page.update()

    def _on_video_enter_fullscreen(self, event: ft.ControlEvent) -> None:
        self.restore_app_fullscreen = bool(getattr(self.page.window, "full_screen", False))

    def _on_video_exit_fullscreen(self, event: ft.ControlEvent) -> None:
        if not self.restore_app_fullscreen:
            return

        def restore() -> None:
            self.page.window.full_screen = True
            self.page.update()

        timer = threading.Timer(0.2, restore)
        timer.daemon = True
        timer.start()

    def _play_video(self, event: ft.ControlEvent) -> None:
        self._call_video("play")

    def _pause_video(self, event: ft.ControlEvent) -> None:
        self._call_video("pause")
        self.loop_active = False
        self._cancel_loop_timer()

    def _seek_ms(self, position_ms: int) -> None:
        if hasattr(self.video, "seek"):
            try:
                self.video.seek(position_ms)
            except TypeError:
                self.video.seek(position_ms / 1000)
        self.page.update()

    def _change_rate(self, event: ft.ControlEvent) -> None:
        value = round(float(self.rate_slider.value or 1.0) / 0.05) * 0.05
        value = max(0.1, min(2.0, value))
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
        self.marker_start_input.value = self._format_ms(value)
        self.page.update()

    def _capture_end_position(self, event: ft.ControlEvent) -> None:
        value = self._video_position_ms()
        self.current_position_ms = value
        self.marker_end_input.value = self._format_ms(value)
        self.page.update()

    def _add_marker(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        marker = self.repo.create_tempo_marker(
            note_id=self.selected_note.id,
            name=self.marker_name_input.value or "새 구간",
            start_ms=self._timecode_to_ms(self.marker_start_input.value),
            end_ms=self._timecode_to_ms(self.marker_end_input.value),
            bpm=120,
            beats_per_bar=4,
            accent_first_beat=True,
        )
        self.selected_marker = marker
        self.markers = self.repo.tempo_markers(self.selected_note.id)
        self._render_markers()
        self.page.update()

    def _select_marker(self, marker: TempoMarker) -> None:
        self.selected_marker = marker
        self.marker_name_input.value = marker.name
        self.marker_start_input.value = self._format_ms(marker.start_ms)
        self.marker_end_input.value = self._format_ms(marker.end_ms)
        self._seek_ms(marker.start_ms)
        self._render_markers()
        self.page.update()

    def _play_loop_marker(self, marker: TempoMarker) -> None:
        self._select_marker(marker)
        self._start_loop_for_marker(marker)

    def _delete_marker(self, marker: TempoMarker) -> None:
        self.repo.delete_tempo_marker(marker.id)
        if self.selected_marker and self.selected_marker.id == marker.id:
            self.selected_marker = None
        if self.selected_note:
            self.markers = self.repo.tempo_markers(self.selected_note.id)
        self._render_markers()
        self.page.update()

    def _start_loop(self, event: ft.ControlEvent) -> None:
        marker = self.selected_marker or (self.markers[0] if self.markers else None)
        if marker:
            self.selected_marker = marker
            self._start_loop_for_marker(marker)
            return
        self._call_video("play")
        self.loop_status.value = "일반 재생"
        self.page.update()

    def _start_loop_for_marker(self, marker: TempoMarker) -> None:
        self._cancel_loop_timer()
        self.loop_active = True
        self._seek_ms(marker.start_ms)
        self._call_video("play")
        self._schedule_loop_restart(marker)
        self.loop_status.value = "반복 재생 중"
        self.page.update()

    def _stop_loop(self, event: ft.ControlEvent) -> None:
        self.loop_active = False
        self._cancel_loop_timer()
        self.loop_status.value = "반복 정지"
        self.page.update()

    def _schedule_loop_restart(self, marker: Optional[TempoMarker]) -> None:
        self._cancel_loop_timer()
        if not marker or marker.end_ms <= marker.start_ms:
            return
        rate = max(0.1, float(self.rate_slider.value or 1.0))
        seconds = ((marker.end_ms - marker.start_ms) / 1000) / rate
        self.loop_timer = threading.Timer(seconds, lambda: self._restart_loop_from_timer(marker))
        self.loop_timer.daemon = True
        self.loop_timer.start()

    def _cancel_loop_timer(self) -> None:
        if self.loop_timer:
            self.loop_timer.cancel()
            self.loop_timer = None

    def _restart_loop_from_timer(self, marker: TempoMarker) -> None:
        if not self.loop_active:
            return
        self._seek_ms(marker.start_ms)
        self._call_video("play")
        self._schedule_loop_restart(marker)
        self.loop_status.value = "반복 재생 중"
        self.page.update()

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

    def _category_by_name(self, name: str) -> Optional[Category]:
        for category in self.categories:
            if category.name == name:
                return category
        return None

    def _ordered_categories(self, include_all: bool = True) -> List[Category]:
        priority = {"기타": 0, "베이스": 1}
        ordered = sorted(
            self.categories,
            key=lambda category: (
                priority.get(category.name, 10),
                category.name,
            ),
        )
        return ordered if include_all else [category for category in ordered if category.name != "전체"]

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

    def _compact_button(self, label: str, icon: str, handler) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            text=label,
            icon=icon,
            on_click=handler,
            style=ft.ButtonStyle(
                bgcolor=ACCENT,
                color=BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
            ),
        )

    def _danger_button(self, label: str, icon: str, handler) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            text=label,
            icon=icon,
            on_click=handler,
            style=ft.ButtonStyle(
                bgcolor=DANGER,
                color=TEXT,
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
        total_ms = max(0, value)
        minutes = total_ms // 60000
        seconds = (total_ms % 60000) // 1000
        centiseconds = (total_ms % 1000) // 10
        return f"{minutes:02d}:{seconds:02d}:{centiseconds:02d}"

    @staticmethod
    def _timecode_to_ms(value: Optional[str]) -> int:
        text = (value or "").strip()
        if not text:
            return 0
        if text.isdigit():
            return int(text)
        parts = text.split(":")
        try:
            if len(parts) == 3:
                minutes = int(parts[0] or 0)
                seconds = int(parts[1] or 0)
                centiseconds = int(parts[2] or 0)
                return max(0, minutes * 60000 + seconds * 1000 + centiseconds * 10)
            if len(parts) == 2:
                minutes = int(parts[0] or 0)
                seconds = int(parts[1] or 0)
                return max(0, minutes * 60000 + seconds * 1000)
            return max(0, int(float(text) * 1000))
        except ValueError:
            return 0
