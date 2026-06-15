import inspect
import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import flet as ft
import flet_video as fvideo

from guitarta.models import Category, Note, TempoMarker
from guitarta.paths import audio_dir, database_path, media_dir
from guitarta.services.audio_processor import AudioProcessingError, AudioProcessor
from guitarta.services.downloader import DownloadError, YouTubeDownloader
from guitarta.services.repository import Repository


def _install_flet_compat() -> None:
    if not hasattr(ft.padding, "all"):
        ft.padding.all = lambda value: ft.Padding(value, value, value, value)
    if not hasattr(ft.padding, "symmetric"):
        ft.padding.symmetric = lambda horizontal=0, vertical=0: ft.Padding(
            horizontal,
            vertical,
            horizontal,
            vertical,
        )
    if not hasattr(ft.padding, "only"):
        ft.padding.only = lambda left=0, top=0, right=0, bottom=0: ft.Padding(
            left,
            top,
            right,
            bottom,
        )
    if not hasattr(ft.border, "all"):
        ft.border.all = lambda width=1, color=None: ft.Border(
            top=ft.BorderSide(width, color),
            right=ft.BorderSide(width, color),
            bottom=ft.BorderSide(width, color),
            left=ft.BorderSide(width, color),
        )
    if not hasattr(ft.border, "only"):
        ft.border.only = lambda left=None, top=None, right=None, bottom=None: ft.Border(
            left=left or ft.BorderSide(0, ft.Colors.BLACK),
            top=top or ft.BorderSide(0, ft.Colors.BLACK),
            right=right or ft.BorderSide(0, ft.Colors.BLACK),
            bottom=bottom or ft.BorderSide(0, ft.Colors.BLACK),
        )
    if not hasattr(ft.alignment, "center"):
        ft.alignment.center = ft.Alignment(0, 0)
    if not hasattr(ft.alignment, "center_left"):
        ft.alignment.center_left = ft.Alignment(-1, 0)
    if not hasattr(ft.alignment, "center_right"):
        ft.alignment.center_right = ft.Alignment(1, 0)


_install_flet_compat()


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
CATEGORY_ADD_CONTROL_HEIGHT = 40
VIDEO_PANEL_HEIGHT = 500
NOTE_BOTTOM_HEIGHT = 190
MEMO_INPUT_HEIGHT = NOTE_BOTTOM_HEIGHT - 30
MARKER_LABEL_WIDTH = 44
MARKER_FIELD_PAD_V = 10
MARKER_TIME_FIELD_WIDTH = 112
MARKER_ACTION_BUTTON_WIDTH = 100
MARKER_ACTION_BUTTON_HEIGHT = 33
FULLSCREEN_RESTORE_RECHECK_SECONDS = (0.03, 0.1, 0.25)
DROPDOWN_OPTION_HEIGHT = 48
DROPDOWN_MENU_MAX_HEIGHT = 260
AUDIO_KIND_LABELS = {
    "original": "원본",
    "bass_removed": "베이스 제거",
    "guitar_removed": "기타 제거",
    "drums_only": "드럼 단독",
}
SIDEBAR_TOOL_BUTTON_HEIGHT = 58
SCALE_BOARD_WIDTH = 960
SCALE_BOARD_IMAGE_WIDTH = 930
SCALE_BOARD_CONTENT_X = 15
SCALE_OPEN_STRING_X_RATIO = 0.3
SCALE_PRESS_RATIO = 0.68
SCALE_FRET_NUMBER_HEIGHT = 54
SCALE_NUMBER_FRETS = [3, 5, 7, 9, 12, 15, 17, 19, 21]
CHROMATIC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SHARP_TO_FLAT = {"C#": "D♭", "D#": "E♭", "F#": "G♭", "G#": "A♭", "A#": "B♭"}
INTERVAL_LABELS = {
    0: "1",
    1: "♭2",
    2: "2",
    3: "♭3",
    4: "3",
    5: "4",
    6: "♯4",
    7: "5",
    8: "♭6",
    9: "6",
    10: "♭7",
    11: "7",
}
SCALE_CATEGORY_LABELS = {
    "major": "메이저",
    "minor": "마이너",
    "pent": "펜타/블루스",
    "modes": "모드",
    "exotic": "특이 스케일",
}
SCALE_LIBRARY = {
    "major": [
        {"id": "major", "name": "메이저 스케일", "intervals": [0, 2, 4, 5, 7, 9, 11], "desc": "가장 기본적인 장조 스케일."},
    ],
    "minor": [
        {"id": "nat_minor", "name": "내추럴 마이너 (Aeolian)", "intervals": [0, 2, 3, 5, 7, 8, 10], "desc": "기본 단조 스케일."},
        {"id": "harm_minor", "name": "하모닉 마이너", "intervals": [0, 2, 3, 5, 7, 8, 11], "desc": "7음을 반음 올린 단조."},
        {"id": "mel_minor", "name": "멜로딕 마이너 (재즈)", "intervals": [0, 2, 3, 5, 7, 9, 11], "desc": "재즈에서 많이 쓰는 상행 멜로딕 마이너."},
    ],
    "pent": [
        {"id": "maj_pent", "name": "메이저 펜타토닉", "intervals": [0, 2, 4, 7, 9], "desc": "메이저의 4, 7을 뺀 5음 스케일."},
        {"id": "min_pent", "name": "마이너 펜타토닉", "intervals": [0, 3, 5, 7, 10], "desc": "록, 블루스, 발라드의 기본 5음 스케일."},
        {"id": "blues", "name": "블루스 스케일", "intervals": [0, 3, 5, 6, 7, 10], "desc": "마이너 펜타토닉에 블루노트를 더한 스케일."},
    ],
    "modes": [
        {"id": "ionian", "name": "Ionian (1번 모드)", "intervals": [0, 2, 4, 5, 7, 9, 11], "desc": "메이저 스케일과 같은 모드."},
        {"id": "dorian", "name": "Dorian (2번)", "intervals": [0, 2, 3, 5, 7, 9, 10], "desc": "밝은 6도를 가진 마이너 모드."},
        {"id": "phrygian", "name": "Phrygian (3번)", "intervals": [0, 1, 3, 5, 7, 8, 10], "desc": "플라멩코 느낌의 어두운 모드."},
        {"id": "lydian", "name": "Lydian (4번)", "intervals": [0, 2, 4, 6, 7, 9, 11], "desc": "♯4가 들어간 메이저 모드."},
        {"id": "mixolydian", "name": "Mixolydian (5번)", "intervals": [0, 2, 4, 5, 7, 9, 10], "desc": "♭7을 가진 메이저 모드."},
        {"id": "aeolian", "name": "Aeolian (6번)", "intervals": [0, 2, 3, 5, 7, 8, 10], "desc": "내추럴 마이너와 같은 모드."},
        {"id": "locrian", "name": "Locrian (7번)", "intervals": [0, 1, 3, 5, 6, 8, 10], "desc": "♭2, ♭5가 들어간 불안정한 모드."},
    ],
    "exotic": [
        {"id": "wholetone", "name": "홀톤 스케일", "intervals": [0, 2, 4, 6, 8, 10], "desc": "모든 음 간격이 전음인 6음 스케일."},
        {"id": "dim_wh", "name": "디미니시드 (홀하프)", "intervals": [0, 2, 3, 5, 6, 8, 9, 11], "desc": "전음-반음이 반복되는 8음 스케일."},
        {"id": "dim_hw", "name": "디미니시드 (하프홀)", "intervals": [0, 1, 3, 4, 6, 7, 9, 10], "desc": "반음-전음이 반복되는 8음 스케일."},
        {"id": "hungarian", "name": "헝가리안 마이너", "intervals": [0, 2, 3, 6, 7, 8, 11], "desc": "하모닉 마이너에 ♯4를 더한 색채."},
        {"id": "phrygian_dom", "name": "Phrygian Dominant", "intervals": [0, 1, 4, 5, 7, 8, 10], "desc": "하모닉 마이너의 5번 모드."},
        {"id": "chromatic", "name": "크로매틱", "intervals": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], "desc": "12음 전체."},
    ],
}
SCALE_INSTRUMENTS = {
    "guitar": {
        "label": "기타",
        "image": "guitar_fretboard_22.png",
        "image_size": (4570, 1050),
        "board_left": 85.5,
        "board_right": 4484,
        "string_y": [95, 256, 418, 580, 741, 902],
        "tuning": [64, 59, 55, 50, 45, 40],
        "max_fret": 22,
    },
    "bass": {
        "label": "베이스",
        "image": "bass_fretboard_20.png",
        "image_size": (4570, 790),
        "board_left": 85.5,
        "board_right": 4484,
        "string_y": [96, 278, 459, 642],
        "tuning": [43, 38, 33, 28],
        "max_fret": 20,
    },
}


class GuitarTAApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.repo = Repository(database_path())
        self.downloader = YouTubeDownloader(media_dir())
        self.audio_processor = AudioProcessor(audio_dir())
        self.selected_category_id: Optional[int] = None
        self.selected_note: Optional[Note] = None
        self.selected_marker: Optional[TempoMarker] = None
        self.current_position_ms = 0
        self.is_downloading = False
        self.sidebar_open = True
        self.loop_timer: Optional[threading.Timer] = None
        self.loop_active = False
        self.loop_last_restart_at = 0.0
        self.restore_app_fullscreen = False
        self.video_fullscreen_active = False
        self.video_focus_mode = False
        self.dialog_category_name = "기타"
        self.audio_assets_preparing = set()
        self.playback_assets_preparing = set()
        self.video_volume = 100
        self.audio_pitch_semitones = 0
        self.video_playing = False
        self.dialog_open = False
        self.text_entry_active = False
        self.active_detail_view = "notes"
        self.scale_instrument = "guitar"
        self.scale_root = "C"
        self.scale_category = "major"
        self.scale_id = "major"
        self.scale_accidental = "sharp"
        self.scale_show_notes = True
        self.scale_highlight_root = True

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
        if getattr(self.page, "window", None) is not None:
            self.page.window.on_event = self._handle_window_event

        self.new_title_input = self._text_field(
            "새 노트 제목",
            width=230,
            on_change=self._auto_save_note_dialog_metadata,
        )
        self.url_input = self._text_field("유튜브 링크", height=54)
        self.add_category_input = self._bare_text_field(width=320)
        self.download_status = ft.Text("", color=MUTED, size=12)
        self.download_status.visible = False
        self.note_dialog_mode = "create"
        self.note_category_dropdown = self._category_dropdown(
            label="카테고리",
            width=180,
            include_all=False,
            on_change=self._select_note_dialog_category,
        )
        self.note_dialog = self._note_settings_dialog()
        self.delete_dialog = self._delete_note_dialog()
        self.category_dialog = self._category_dialog()
        self.video_status = ft.Text("", color=MUTED, size=12)
        self.category_dropdown = self._category_dropdown(
            label="카테고리",
            width=320,
            include_all=True,
            on_change=self._select_category_from_dropdown,
            sidebar=True,
        )
        self.note_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        self.title_input = self._text_field("노트 제목", expand=True)
        self.memo_input = ft.TextField(
            label="연습 메모",
            multiline=True,
            min_lines=5,
            max_lines=5,
            expand=True,
            height=MEMO_INPUT_HEIGHT,
            border_color=LINE,
            focused_border_color=ACCENT,
            bgcolor=PANEL_2,
            color=TEXT,
            label_style=ft.TextStyle(color=MUTED),
            on_change=self._auto_save_note,
            on_focus=lambda event: self._set_text_entry_active(True),
            on_blur=lambda event: self._set_text_entry_active(False),
        )
        self.audio_status = ft.Text("", color=MUTED, size=12)
        self.audio_kind_dropdown = self._audio_kind_dropdown()
        self.volume_text = ft.Text("100%", color=BEIGE, size=13, weight=ft.FontWeight.BOLD)
        self.volume_slider = ft.Slider(
            min=0,
            max=100,
            divisions=20,
            value=self.video_volume,
            active_color=ACCENT,
            inactive_color=LINE,
            on_change=self._change_volume,
        )
        self.pitch_text = ft.Text("0키", color=BEIGE, size=13, weight=ft.FontWeight.BOLD)
        self.pitch_slider = ft.Slider(
            min=-9,
            max=9,
            divisions=18,
            value=self.audio_pitch_semitones,
            active_color=ACCENT,
            inactive_color=LINE,
            on_change=self._preview_pitch,
            on_change_end=self._change_pitch,
        )
        self.note_settings_button = self._button("노트 설정", ft.Icons.TUNE_ROUNDED, self._open_note_settings)
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

        self.marker_name_input = self._marker_text_field("구간 제목", on_change=self._auto_save_selected_marker)
        self.marker_start_input = self._marker_time_field("시작 시간")
        self.marker_end_input = self._marker_time_field("종료 시간")
        self.marker_list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self.loop_status = ft.Text("반복 대기", color=MUTED, size=12)

        self.sidebar_host = ft.Container(content=self._sidebar(), width=360)
        self.sidebar_divider = ft.VerticalDivider(width=1, color=LINE)
        self.sidebar_rail = ft.Container(content=self._sidebar_rail(), width=54, visible=False)
        self.main_area_host = self._main_area()
        self.page.add(
            ft.Row(
                [
                    self.sidebar_host,
                    self.sidebar_divider,
                    self.sidebar_rail,
                    self.main_area_host,
                ],
                expand=True,
                spacing=0,
            )
        )
        self._refresh_all()
        self._prepare_missing_audio_assets()

    def _sidebar(self) -> ft.Container:
        return ft.Container(
            bgcolor=SIDEBAR_BG,
            padding=ft.padding.symmetric(horizontal=14, vertical=16),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("GuitarTA", size=28, color=SIDEBAR_TEXT, weight=ft.FontWeight.BOLD),
                            ft.Text("v3.0", color=SIDEBAR_MUTED, size=12, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                                icon_color=SIDEBAR_TEXT,
                                tooltip="사이드바 닫기",
                                on_click=self._toggle_sidebar,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "새로운 노트 생성",
                                icon=ft.Icons.ADD_ROUNDED,
                                on_click=self._open_new_note,
                                expand=True,
                                style=ft.ButtonStyle(
                                    bgcolor=SIDEBAR_TEXT,
                                    color=SIDEBAR_BG,
                                    shape=ft.RoundedRectangleBorder(radius=6),
                                    padding=ft.padding.symmetric(horizontal=12, vertical=12),
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED,
                                icon_color=SIDEBAR_TEXT,
                                tooltip="카테고리 추가",
                                on_click=self._open_category_dialog,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(color="#BCA77C"),
                    self.category_dropdown,
                    ft.Divider(color="#BCA77C"),
                    self.note_list,
                    ft.Divider(color="#BCA77C"),
                    self._sidebar_tools_panel(),
                ],
                expand=True,
                spacing=10,
            ),
        )

    def _sidebar_tools_panel(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self._sidebar_tool_button("스케일 연습", ft.Icons.FLAG_ROUNDED, self._open_scale_practice),
                            self._sidebar_tool_button("음정 트레이닝", ft.Icons.MY_LOCATION_ROUNDED),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        [
                            self._sidebar_tool_button("튜너", ft.Icons.TUNE_ROUNDED),
                            self._sidebar_tool_button("메트로놈", ft.Icons.REPEAT_ROUNDED),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=8,
            ),
        )

    def _sidebar_tool_button(self, label: str, icon: str, handler=None) -> ft.Container:
        return ft.Container(
            expand=True,
            height=SIDEBAR_TOOL_BUTTON_HEIGHT,
            bgcolor="#FFF2D7",
            border=ft.border.all(1, "#BCA77C"),
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=8, vertical=8),
            alignment=ft.alignment.center,
            tooltip=label if handler else f"{label} 준비 중",
            on_click=handler or self._noop_sidebar_tool,
            content=ft.Column(
                [
                    ft.Icon(icon, color=SIDEBAR_TEXT, size=18),
                    ft.Text(
                        label,
                        color=SIDEBAR_TEXT,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                tight=True,
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

    def _noop_sidebar_tool(self, event: ft.ControlEvent) -> None:
        return None

    def _open_scale_practice(self, event: ft.ControlEvent) -> None:
        self.active_detail_view = "scale"
        if self.video_focus_mode:
            self._set_video_focus_mode(False, update=False)
        self.detail_area.content = self._scale_practice_view()
        self.page.update()

    def _scale_practice_view(self) -> ft.Control:
        scale = self._current_scale()
        if scale is None:
            return ft.Container(
                content=ft.Text("스케일을 불러올 수 없습니다.", color=MUTED, size=16),
                alignment=ft.alignment.center,
                expand=True,
            )
        notes = self._scale_note_names(scale)
        degrees = [INTERVAL_LABELS.get(interval, str(interval)) for interval in scale["intervals"]]
        return ft.Container(
            expand=True,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("스케일 연습", color=BEIGE, size=22, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"{self._pc_label(self.scale_root)} {scale['name']}",
                                        color=MUTED,
                                        size=13,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            self._scale_toggle("음정 보기", self.scale_show_notes, self._toggle_scale_note_names),
                            self._scale_toggle("루트 강조", self.scale_highlight_root, self._toggle_scale_root_highlight),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._scale_controls(),
                    self._scale_info_panel(scale, notes, degrees),
                    self._scale_fretboard(),
                ],
                expand=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    def _scale_controls(self) -> ft.Control:
        return ft.Container(
            bgcolor=PANEL,
            border=ft.border.all(1, LINE),
            border_radius=8,
            padding=ft.padding.all(12),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self._scale_instrument_button("guitar", ft.Icons.MUSIC_NOTE_ROUNDED),
                            self._scale_instrument_button("bass", ft.Icons.GRAPHIC_EQ_ROUNDED),
                            self._scale_dropdown(
                                "루트",
                                self.scale_root,
                                [(pc, self._pc_label(pc)) for pc in CHROMATIC],
                                self._set_scale_root,
                                width=110,
                            ),
                            self._scale_dropdown(
                                "표기",
                                self.scale_accidental,
                                [("sharp", "♯"), ("flat", "♭")],
                                self._set_scale_accidental,
                                width=96,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            self._scale_dropdown(
                                "카테고리",
                                self.scale_category,
                                [(key, label) for key, label in SCALE_CATEGORY_LABELS.items()],
                                self._set_scale_category,
                                width=180,
                            ),
                            self._scale_dropdown(
                                "스케일",
                                self.scale_id,
                                [(item["id"], item["name"]) for item in SCALE_LIBRARY[self.scale_category]],
                                self._set_scale_id,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=10,
            ),
        )

    def _scale_info_panel(self, scale: Dict, notes: List[str], degrees: List[str]) -> ft.Control:
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(scale["name"], color=BEIGE, size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(scale.get("desc", ""), color=MUTED, size=12, expand=True),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text("구성음", color=MUTED, size=12, width=48),
                        ft.Row(
                            [
                                self._scale_note_text(note, idx == 0)
                                for idx, note in enumerate(notes)
                            ],
                            spacing=12,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text("도수", color=MUTED, size=12, width=48),
                        ft.Text("  ".join(degrees), color=TEXT, size=13),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(color=LINE),
            ],
            spacing=8,
        )

    def _scale_fretboard(self) -> ft.Control:
        inst = SCALE_INSTRUMENTS[self.scale_instrument]
        image_w, image_h = inst["image_size"]
        image_scale = SCALE_BOARD_IMAGE_WIDTH / image_w
        image_display_h = round(image_h * image_scale)
        board_h = image_display_h + SCALE_FRET_NUMBER_HEIGHT
        controls = [
            ft.Image(
                src=inst["image"],
                left=SCALE_BOARD_CONTENT_X,
                top=0,
                width=SCALE_BOARD_IMAGE_WIDTH,
                height=image_display_h,
                fit=ft.BoxFit.CONTAIN,
            )
        ]
        controls.extend(self._scale_fret_markers(inst, image_scale))
        controls.extend(self._scale_fret_numbers(inst, image_scale, image_display_h))
        return ft.Container(
            width=SCALE_BOARD_WIDTH,
            height=board_h,
            bgcolor="#000000",
            border_radius=8,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(
                controls=controls,
                width=SCALE_BOARD_WIDTH,
                height=board_h,
            ),
        )

    def _scale_fret_markers(self, inst: Dict, image_scale: float) -> List[ft.Control]:
        scale = self._current_scale()
        if scale is None:
            return []
        root_idx = CHROMATIC.index(self.scale_root)
        scale_pcs = {
            CHROMATIC[(root_idx + interval) % 12]
            for interval in scale["intervals"]
        }
        markers: List[ft.Control] = []
        for string_idx, open_midi in enumerate(inst["tuning"]):
            for fret in range(0, inst["max_fret"] + 1):
                midi = open_midi + fret
                pc = CHROMATIC[midi % 12]
                if pc not in scale_pcs:
                    continue
                is_root = pc == self.scale_root
                x, y = self._scale_marker_position(inst, fret, string_idx)
                size = 26 if is_root and self.scale_highlight_root else 22
                markers.append(
                    ft.Container(
                        left=SCALE_BOARD_CONTENT_X + x * image_scale - size / 2,
                        top=y * image_scale - size / 2,
                        width=size,
                        height=size,
                        bgcolor=ACCENT if is_root and self.scale_highlight_root else "#FFF7EA",
                        border=ft.border.all(2 if is_root and self.scale_highlight_root else 1, "#2A2118"),
                        border_radius=50,
                        alignment=ft.alignment.center,
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=5,
                            color="#66000000",
                            offset=ft.Offset(0, 1),
                        ),
                        content=(
                            ft.Text(
                                self._pc_label(pc),
                                color=BG,
                                size=10 if len(self._pc_label(pc)) == 1 else 9,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                            )
                            if self.scale_show_notes
                            else None
                        ),
                    )
                )
        return markers

    def _scale_fret_numbers(self, inst: Dict, image_scale: float, image_display_h: int) -> List[ft.Control]:
        numbers: List[ft.Control] = []
        for fret in SCALE_NUMBER_FRETS:
            if fret > int(inst["max_fret"]):
                continue
            x = self._scale_fret_mid_x(inst, fret)
            numbers.append(
                ft.Container(
                    left=SCALE_BOARD_CONTENT_X + x * image_scale - 12,
                    top=image_display_h + 18,
                    width=24,
                    height=20,
                    alignment=ft.alignment.center,
                    content=ft.Text(
                        str(fret),
                        color=MUTED,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                )
            )
        return numbers

    def _scale_marker_position(self, inst: Dict, fret: int, string_idx: int) -> Tuple[float, float]:
        y = inst["string_y"][string_idx]
        if fret == 0:
            return float(inst["board_left"]) * SCALE_OPEN_STRING_X_RATIO, float(y)
        return self._scale_fret_press_x(inst, fret), float(y)

    def _scale_fret_press_x(self, inst: Dict, fret: int) -> float:
        prev_x = self._scale_fret_line_x(inst, fret - 1)
        next_x = self._scale_fret_line_x(inst, fret)
        return prev_x + (next_x - prev_x) * SCALE_PRESS_RATIO

    def _scale_fret_mid_x(self, inst: Dict, fret: int) -> float:
        prev_x = self._scale_fret_line_x(inst, fret - 1)
        next_x = self._scale_fret_line_x(inst, fret)
        return (prev_x + next_x) / 2

    def _scale_fret_line_x(self, inst: Dict, fret_no: int) -> float:
        board_left = float(inst["board_left"])
        if fret_no <= 0:
            return board_left
        board_len = float(inst["board_right"] - inst["board_left"])
        max_fret = int(inst["max_fret"])
        normalized = (1 - 2 ** (-fret_no / 12)) / (1 - 2 ** (-max_fret / 12))
        return board_left + board_len * normalized

    def _scale_instrument_button(self, instrument: str, icon: str) -> ft.Container:
        selected = self.scale_instrument == instrument
        return ft.Container(
            width=112,
            height=44,
            bgcolor=ACCENT if selected else PANEL_2,
            border=ft.border.all(1, ACCENT if selected else LINE),
            border_radius=6,
            alignment=ft.alignment.center,
            on_click=lambda event, value=instrument: self._set_scale_instrument(value),
            content=ft.Row(
                [
                    ft.Icon(icon, color=BG if selected else BEIGE, size=18),
                    ft.Text(
                        SCALE_INSTRUMENTS[instrument]["label"],
                        color=BG if selected else BEIGE,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _scale_dropdown(self, label: str, value: str, options: List[Tuple[str, str]], on_change, width: Optional[int] = None, expand: bool = False) -> ft.Dropdown:
        params = inspect.signature(ft.Dropdown).parameters
        kwargs = {
            "label": label,
            "value": value,
            "width": width,
            "expand": expand,
            "dense": True,
            "bgcolor": PANEL_2,
            "color": TEXT,
            "border_color": LINE,
            "focused_border_color": ACCENT,
            "label_style": ft.TextStyle(color=MUTED),
            "text_style": ft.TextStyle(color=TEXT),
            "options": [
                ft.dropdown.Option(
                    key=key,
                    text=text,
                    content=ft.Text(text, color=TEXT, size=13),
                )
                for key, text in options
            ],
        }
        kwargs["menu_height" if "menu_height" in params else "max_menu_height"] = self._dropdown_menu_height(len(options))
        kwargs["on_select" if "on_select" in params else "on_change"] = on_change
        return ft.Dropdown(**{key: value for key, value in kwargs.items() if key in params})

    def _scale_toggle(self, label: str, value: bool, handler) -> ft.Switch:
        return ft.Switch(
            label=label,
            value=value,
            active_color=ACCENT,
            label_text_style=ft.TextStyle(color=BEIGE, size=12),
            on_change=handler,
        )

    def _scale_note_text(self, note: str, root: bool) -> ft.Text:
        return ft.Text(
            note,
            color=ACCENT if root else TEXT,
            size=15,
            weight=ft.FontWeight.BOLD,
        )

    def _current_scale(self) -> Optional[Dict]:
        scales = SCALE_LIBRARY.get(self.scale_category, [])
        if not scales:
            return None
        for scale in scales:
            if scale["id"] == self.scale_id:
                return scale
        self.scale_id = scales[0]["id"]
        return scales[0]

    def _scale_note_names(self, scale: Dict) -> List[str]:
        root_idx = CHROMATIC.index(self.scale_root)
        return [
            self._pc_label(CHROMATIC[(root_idx + interval) % 12])
            for interval in scale["intervals"]
        ]

    def _pc_label(self, pc: str) -> str:
        return SHARP_TO_FLAT.get(pc, pc) if self.scale_accidental == "flat" else pc

    def _refresh_scale_practice(self) -> None:
        if self.active_detail_view == "scale":
            self.detail_area.content = self._scale_practice_view()
            self.page.update()

    def _set_scale_instrument(self, instrument: str) -> None:
        if instrument not in SCALE_INSTRUMENTS:
            return
        self.scale_instrument = instrument
        self._refresh_scale_practice()

    def _set_scale_root(self, event: ft.ControlEvent) -> None:
        if event.control.value in CHROMATIC:
            self.scale_root = event.control.value
            self._refresh_scale_practice()

    def _set_scale_accidental(self, event: ft.ControlEvent) -> None:
        self.scale_accidental = "flat" if event.control.value == "flat" else "sharp"
        self._refresh_scale_practice()

    def _set_scale_category(self, event: ft.ControlEvent) -> None:
        category = event.control.value
        if category not in SCALE_LIBRARY:
            return
        self.scale_category = category
        self.scale_id = SCALE_LIBRARY[category][0]["id"]
        self._refresh_scale_practice()

    def _set_scale_id(self, event: ft.ControlEvent) -> None:
        scale_id = event.control.value
        if any(scale["id"] == scale_id for scale in SCALE_LIBRARY.get(self.scale_category, [])):
            self.scale_id = scale_id
            self._refresh_scale_practice()

    def _toggle_scale_note_names(self, event: ft.ControlEvent) -> None:
        self.scale_show_notes = bool(event.control.value)
        self._refresh_scale_practice()

    def _toggle_scale_root_highlight(self, event: ft.ControlEvent) -> None:
        self.scale_highlight_root = bool(event.control.value)
        self._refresh_scale_practice()

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
                    self.detail_area,
                ],
                expand=True,
                spacing=0,
            ),
        )

    def _note_detail(self) -> ft.Control:
        if not self.selected_note:
            return ft.Container(
                content=ft.Text("다운로드한 영상이 이 영역에 표시됩니다.", color=MUTED, size=16),
                alignment=ft.alignment.center,
                expand=True,
            )

        if self.video_focus_mode:
            return self._video_focus_detail()

        self.title_input.value = self.selected_note.title
        self.memo_input.value = self.selected_note.memo
        self.rate_slider.value = self.selected_note.playback_rate
        self.rate_text.value = f"{self.selected_note.playback_rate:.2f}x"
        self._render_audio_selector()

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
                            ft.Row(
                                [
                                    self.note_settings_button,
                                    self.delete_note_button,
                                ],
                                spacing=10,
                            ),
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
                                height=VIDEO_PANEL_HEIGHT,
                            ),
                            ft.Container(content=self._practice_panel(), width=390, height=VIDEO_PANEL_HEIGHT),
                        ],
                        spacing=18,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Divider(color=LINE),
                    ft.Container(
                        height=NOTE_BOTTOM_HEIGHT,
                        content=ft.Row(
                            [
                                self._audio_selection_panel(),
                                ft.Container(width=1, height=NOTE_BOTTOM_HEIGHT, bgcolor=LINE),
                                ft.Column(
                                    [
                                        ft.Text("노트 메모", color=BEIGE, size=18, weight=ft.FontWeight.BOLD),
                                        self.memo_input,
                                    ],
                                    spacing=8,
                                    expand=True,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                ),
                            ],
                            spacing=16,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                    ),
                ],
                expand=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    def _video_focus_detail(self) -> ft.Control:
        return ft.Container(
            expand=True,
            bgcolor="#050505",
            padding=ft.padding.all(10),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                self.selected_note.title if self.selected_note else "영상 확대",
                                color=BEIGE,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                expand=True,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=self.video,
                        bgcolor="#050505",
                        expand=True,
                    ),
                ],
                expand=True,
                spacing=8,
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
                    ft.Row([self.new_title_input, self.note_category_dropdown], spacing=10),
                    ft.Row(
                        [
                            ft.Container(self.url_input, expand=True),
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
            title=ft.Text("노트 설정", color=BEIGE, size=20, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Divider(color=LINE),
                        ft.Row([self.new_title_input, self.note_category_dropdown], spacing=10),
                        ft.Container(self.url_input, width=420),
                        self.download_status,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            inset_padding=ft.padding.symmetric(horizontal=32, vertical=24),
            title_padding=ft.padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.padding.only(left=20, right=20, top=4, bottom=2),
            actions_padding=ft.padding.only(left=16, right=16, bottom=12, top=4),
            actions=[
                ft.TextButton("취소", on_click=self._close_note_settings),
                ft.ElevatedButton(
                    "저장",
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

    def _category_dialog(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=True,
            bgcolor=PANEL,
            title=ft.Row(
                [
                    ft.Text("카테고리 관리", color=BEIGE, size=20, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_color=BEIGE,
                        tooltip="닫기",
                        on_click=self._close_category_dialog,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=self._category_dialog_content(),
            actions=[],
        )

    def _category_dialog_content(self) -> ft.Container:
        self.add_category_input = self._bare_text_field(expand=True, height=CATEGORY_ADD_CONTROL_HEIGHT)
        return ft.Container(
            width=360,
            content=ft.Column(
                [
                    ft.Text("카테고리 추가", color=MUTED, size=12, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self.add_category_input,
                            self._category_add_button(),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(color=LINE),
                    ft.Text("카테고리 삭제", color=MUTED, size=12, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        height=140,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(category.name, color=TEXT, expand=True),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                            icon_color=DANGER,
                                            tooltip="카테고리 삭제",
                                            on_click=lambda e, c=category: self._delete_category(c),
                                        ),
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                )
                                for category in self._deletable_categories()
                            ],
                            spacing=2,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        )

    def _delete_note_dialog(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=True,
            bgcolor=PANEL,
            title=ft.Text("노트 삭제", color=BEIGE, size=20, weight=ft.FontWeight.BOLD),
            content=ft.Text("선택한 노트를 삭제할까요? 다운로드된 영상 파일은 유지됩니다.", color=TEXT),
            actions=[
                ft.TextButton("취소", on_click=self._close_delete_note),
                ft.ElevatedButton(
                    "삭제",
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
        self.active_detail_view = "notes"
        self.note_dialog_mode = "create"
        self.note_dialog.title.value = "새 노트 생성"
        self.new_title_input.value = ""
        self.dialog_category_name = "기타"
        self._render_note_category_dropdown()
        self.note_category_dropdown.value = self._category_key_by_name("기타")
        self.url_input.value = ""
        self.url_input.label = "유튜브 링크"
        self._set_download_status("", update=False)
        self._open_dialog(self.note_dialog)

    def _open_note_settings(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            self._open_new_note(event)
            return
        self.note_dialog_mode = "update"
        self.note_dialog.title.value = "노트 설정"
        self.new_title_input.value = self.selected_note.title
        self.dialog_category_name = self._category_name(self.selected_note.category_id)
        self._render_note_category_dropdown()
        self.note_category_dropdown.value = self._category_key_by_name(self.dialog_category_name)
        self.url_input.value = ""
        self.url_input.label = "새 유튜브 링크"
        self._set_download_status("", update=False)
        self._open_dialog(self.note_dialog)

    def _close_note_settings(self, event: ft.ControlEvent) -> None:
        self._close_dialog(self.note_dialog)

    def _practice_panel(self) -> ft.Control:
        return ft.Container(
            height=VIDEO_PANEL_HEIGHT,
            border=ft.border.only(left=ft.BorderSide(1, LINE)),
            padding=ft.padding.only(left=18),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("배속", color=BEIGE, size=16, weight=ft.FontWeight.BOLD),
                            ft.Container(self.rate_slider, expand=True),
                            self.rate_text,
                        ],
                        spacing=8,
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
                    ft.Row(
                        [self.marker_name_input],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=4),
                    self._marker_field_row(
                        "시작",
                        self.marker_start_input,
                        self._marker_time_controls(
                            self.marker_start_input,
                            ft.Icons.MY_LOCATION_ROUNDED,
                            self._capture_position,
                        ),
                    ),
                    self._marker_field_row(
                        "종료",
                        self.marker_end_input,
                        self._marker_time_controls(
                            self.marker_end_input,
                            ft.Icons.FLAG_ROUNDED,
                            self._capture_end_position,
                        ),
                    ),
                    ft.Divider(color=LINE),
                    ft.Text("반복구간 조작", color=MUTED, size=12, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self._compact_button("추가", ft.Icons.ADD_ROUNDED, self._add_marker, expand=True),
                            self._compact_button("시작", ft.Icons.REPEAT_ROUNDED, self._start_loop, expand=True),
                            self._compact_button("정지", ft.Icons.STOP_ROUNDED, self._stop_loop, expand=True),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(color=LINE),
                    ft.Container(self.marker_list, height=160),
                ],
                spacing=8,
            ),
        )

    def _audio_selection_panel(self) -> ft.Control:
        return ft.Container(
            width=250,
            content=ft.Column(
                [
                    ft.Text("음원 선택", color=BEIGE, size=18, weight=ft.FontWeight.BOLD),
                    self.audio_kind_dropdown,
                    ft.Row(
                        [
                            ft.Text("볼륨", color=MUTED, size=12, width=38),
                            ft.Container(self.volume_slider, expand=True),
                            self.volume_text,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Text("피치", color=MUTED, size=12, width=38),
                            ft.Container(self.pitch_slider, expand=True),
                            self.pitch_text,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=6,
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
        self._apply_dropdown_options(
            self.category_dropdown,
            self._category_options(include_all=True, sidebar=True),
        )
        self.category_dropdown.value = (
            str(self.selected_category_id) if self.selected_category_id is not None else "all"
        )
        self.note_list.controls = [
            self._note_tile(note, self.selected_note is not None and note.id == self.selected_note.id)
            for note in self.notes
        ]

    def _render_note_category_dropdown(self) -> None:
        self._apply_dropdown_options(
            self.note_category_dropdown,
            self._category_options(include_all=False, sidebar=False),
        )

    def _select_note_dialog_category(self, event: ft.ControlEvent) -> None:
        key = self.note_category_dropdown.value
        category = self._category_by_id(int(key)) if key else None
        self.dialog_category_name = category.name if category else "기타"
        self._auto_save_note_dialog_metadata()

    def _render_detail(self) -> None:
        if self.active_detail_view == "scale":
            self.detail_area.content = self._scale_practice_view()
            return
        if not self.selected_note and self.video_focus_mode:
            self._set_video_focus_mode(False, update=False)
        if self.selected_note:
            self._sync_note_controls(self.selected_note)
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

    def _render_audio_selector(self) -> None:
        if not self.selected_note:
            return
        selected = self._selected_audio_kind(self.selected_note)
        pitch = self._audio_pitch(self.selected_note)
        self.audio_pitch_semitones = pitch
        self.pitch_slider.value = pitch
        self.pitch_text.value = self._pitch_label(pitch)
        self._apply_dropdown_options(
            self.audio_kind_dropdown,
            self._audio_kind_options(self.selected_note),
        )
        self.audio_kind_dropdown.value = selected
        volume = self._audio_volume(self.selected_note)
        self.video_volume = volume
        self.volume_slider.value = volume
        self.volume_text.value = f"{volume}%"
        if self.selected_note.id in self.audio_assets_preparing:
            self.audio_status.value = "제거 음원 생성 중..."
        elif self._all_audio_assets_ready(self.selected_note):
            self.audio_status.value = ""
        else:
            self.audio_status.value = ""

    def _sync_note_controls(self, note: Note) -> None:
        self.video_volume = self._audio_volume(note)
        self.volume_slider.value = self.video_volume
        self.volume_text.value = f"{self.video_volume}%"
        pitch = self._audio_pitch(note)
        self.audio_pitch_semitones = pitch
        self.pitch_slider.value = pitch
        self.pitch_text.value = self._pitch_label(pitch)
        self.rate_slider.value = note.playback_rate
        self.rate_text.value = f"{note.playback_rate:.2f}x"

    def _select_audio_from_dropdown(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        audio_kind = self.audio_kind_dropdown.value or "original"
        self._select_audio_kind(audio_kind)

    def _select_audio_kind(self, audio_kind: str) -> None:
        if not self.selected_note:
            return
        current_kind = self._selected_audio_kind(self.selected_note)
        if audio_kind != "original" and not self._audio_asset_ready(self.selected_note, audio_kind):
            self._start_note_audio_preparation(self.selected_note)
            self.audio_kind_dropdown.value = current_kind
            self._render_audio_selector()
            self.page.update()
            return
        self.repo.update_note_audio_kind(self.selected_note.id, audio_kind)
        self.selected_note = self.repo.note(self.selected_note.id)
        if self.selected_note:
            self._load_video(self.selected_note)
            self._render_audio_selector()
            self.detail_area.content = self._note_detail()
        self.page.update()

    def _note_tile(self, note: Note, selected: bool) -> ft.Control:
        return ft.Container(
            bgcolor="#FFF2D7" if selected else SIDEBAR_BG,
            border_radius=6 if selected else 0,
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

    def _open_category_dialog(self, event: ft.ControlEvent) -> None:
        self.add_category_input.value = ""
        self.category_dialog = self._category_dialog()
        self._open_dialog(self.category_dialog)

    def _add_category(self, event: ft.ControlEvent) -> None:
        name = (self.add_category_input.value or "").strip()
        if not name:
            return
        self.repo.create_category(name)
        self.categories = self.repo.categories()
        self._render_sidebar()
        self._render_note_category_dropdown()
        self._refresh_category_dialog()
        self.page.update()

    def _delete_category(self, category: Category) -> None:
        self.repo.delete_category(category.id)
        if self.selected_category_id == category.id:
            self.selected_category_id = None
        if self.selected_note and self.selected_note.category_id == category.id:
            self.selected_note = self.repo.note(self.selected_note.id)
        self.categories = self.repo.categories()
        self.notes = self.repo.notes(self.selected_category_id)
        self._render_sidebar()
        self._render_note_category_dropdown()
        self._refresh_category_dialog()
        self.page.update()

    def _refresh_category_dialog(self) -> None:
        if self.category_dialog:
            self.category_dialog.content = self._category_dialog_content()

    def _close_category_dialog(self, event: ft.ControlEvent) -> None:
        self._close_dialog(self.category_dialog)
        self.page.update()

    def _handle_keyboard_event(self, event: ft.KeyboardEvent) -> None:
        key = str(getattr(event, "key", "") or "").lower()
        meta = bool(getattr(event, "meta", False))
        ctrl = bool(getattr(event, "ctrl", False))
        alt = bool(getattr(event, "alt", False))
        if self.video_focus_mode and key in {"escape", "esc"}:
            self._set_video_focus_mode(False)
            return
        if key == "f" and meta and ctrl:
            self._set_window_fullscreen(not self._window_is_fullscreen())
            self.page.update()
            return
        if key == "s" and (meta or ctrl):
            self._save_note_from_shortcut()
            return
        if (
            self.selected_note
            and self._is_space_key(event)
            and not (meta or ctrl or alt)
            and not self.dialog_open
            and not self.text_entry_active
        ):
            self._toggle_video_playback()

    def _save_note_from_shortcut(self) -> None:
        if not self.selected_note:
            return
        self._save_note(None)

    def _open_delete_note(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        self.delete_dialog = self._delete_note_dialog()
        self._open_dialog(self.delete_dialog)

    def _close_delete_note(self, event: ft.ControlEvent) -> None:
        self._close_dialog(self.delete_dialog)
        self.page.update()

    def _delete_selected_note(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            self._close_delete_note(event)
            return
        self.loop_active = False
        self._cancel_loop_timer()
        self.repo.delete_note(self.selected_note.id)
        self.selected_note = None
        self.selected_marker = None
        self.markers = []
        self._reset_marker_form()
        self.notes = self.repo.notes(self.selected_category_id)
        self._close_dialog(self.delete_dialog)
        self._render_sidebar()
        self._render_detail()
        self.page.update()

    def _toggle_sidebar(self, event: ft.ControlEvent) -> None:
        if self.video_focus_mode:
            return
        self.sidebar_open = not self.sidebar_open
        self.sidebar_host.visible = self.sidebar_open
        self.sidebar_divider.visible = self.sidebar_open
        self.sidebar_rail.visible = not self.sidebar_open
        self.page.update()

    def _toggle_video_focus(self, event: ft.ControlEvent) -> None:
        self._set_video_focus_mode(not self.video_focus_mode)

    def _set_video_focus_mode(self, enabled: bool, update: bool = True) -> None:
        if enabled and not self.selected_note:
            return
        restore_position_ms = self._video_position_ms()
        restore_playing = self.video_playing or self.loop_active
        self.video_focus_mode = enabled
        if hasattr(self.video, "controls"):
            self.video.controls = self._video_controls(expanded=enabled)
        self.sidebar_host.visible = False if enabled else self.sidebar_open
        self.sidebar_divider.visible = False if enabled else self.sidebar_open
        self.sidebar_rail.visible = False if enabled else not self.sidebar_open
        self.main_area_host.padding = ft.padding.all(0 if enabled else 20)
        self.detail_area.content = self._note_detail()
        if update:
            self.page.update()
            self._restore_video_after_focus_change(restore_position_ms, restore_playing)

    def _restore_video_after_focus_change(self, position_ms: int, should_play: bool) -> None:
        fixed_position_ms = max(0, int(position_ms))
        self.current_position_ms = fixed_position_ms

        def restore() -> None:
            if should_play:
                self._play_from_ms(fixed_position_ms)
                if self.loop_active and self.selected_marker:
                    self._schedule_loop_restart(self.selected_marker, fixed_position_ms)
                return
            self._seek_ms(fixed_position_ms)

        restore()
        for delay in (0.05, 0.18):
            timer = threading.Timer(delay, restore)
            timer.daemon = True
            timer.start()

    def _open_dialog(self, dialog: ft.AlertDialog) -> None:
        self.dialog_open = True
        self.text_entry_active = False
        if hasattr(self.page, "open"):
            self.page.open(dialog)
            return
        if hasattr(self.page, "show_dialog"):
            self.page.show_dialog(dialog)
            return
        dialog.open = True
        self.page.update()

    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        self.dialog_open = False
        self.text_entry_active = False
        dialog.open = False
        if hasattr(self.page, "close"):
            self.page.close(dialog)
            return
        if hasattr(self.page, "pop_dialog"):
            self.page.pop_dialog()
            return
        self.page.update()

    def _select_note(self, note: Note) -> None:
        self.active_detail_view = "notes"
        self.loop_active = False
        self._cancel_loop_timer()
        self.selected_note = self.repo.note(note.id)
        self.selected_marker = None
        self.markers = self.repo.tempo_markers(note.id)
        self._reset_marker_form()
        self._render_detail()
        self._render_sidebar()
        self.page.update()

    def _download_note(self, event: ft.ControlEvent) -> None:
        if self.is_downloading:
            return
        url = self.url_input.value or ""
        note_title = self.new_title_input.value or ""
        category_name = self._note_dialog_category_name()
        if self.note_dialog_mode == "create" and not url.strip():
            self._set_download_status("유튜브 링크를 입력하세요.", update=False)
            self.page.update()
            return
        self.is_downloading = True
        self._set_download_status("다운로드 준비 중...", update=False)
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
                        assets = self.audio_processor.prepare_note_audio(
                            self.selected_note.id,
                            result["media_path"],
                            self._set_download_status,
                        )
                        self.repo.update_note_audio_assets(
                            self.selected_note.id,
                            assets["original_audio_path"],
                            assets["bass_removed_audio_path"],
                            assets["guitar_removed_audio_path"],
                            assets["drums_only_audio_path"],
                        )
                    self.selected_note = self.repo.note(self.selected_note.id)
                    self._set_download_status("노트 설정이 저장되었습니다.", update=False)
                else:
                    result = self.downloader.download(url, self._set_download_status)
                    note = self.repo.create_note(
                        title=note_title.strip() or result["title"],
                        source_url=result["source_url"],
                        media_path=result["media_path"],
                        category_id=category.id,
                    )
                    self.selected_note = note
                    self.selected_marker = None
                    assets = self.audio_processor.prepare_note_audio(
                        note.id,
                        result["media_path"],
                        self._set_download_status,
                    )
                    self.repo.update_note_audio_assets(
                        note.id,
                        assets["original_audio_path"],
                        assets["bass_removed_audio_path"],
                        assets["guitar_removed_audio_path"],
                        assets["drums_only_audio_path"],
                    )
                    note = self.repo.note(note.id) or note
                    self.selected_note = note
                    self._set_download_status("노트가 추가되었습니다.", update=False)
                self.url_input.value = ""
                self.new_title_input.value = ""
                self._close_dialog(self.note_dialog)
            except DownloadError as exc:
                self._set_download_status(str(exc), update=False)
            except AudioProcessingError as exc:
                self._set_download_status(f"영상은 저장됐지만 제거 음원 생성에 실패했습니다: {exc}", update=False)
            finally:
                self.is_downloading = False
                self.categories = self.repo.categories()
                self.notes = self.repo.notes(self.selected_category_id)
                self.markers = self.repo.tempo_markers(self.selected_note.id) if self.selected_note else []
                self._render_sidebar()
                self._render_detail()
                self.page.update()

        threading.Thread(target=worker, daemon=True).start()

    def _set_download_status(self, text: str, update: bool = True) -> None:
        self.download_status.value = text
        self.download_status.visible = bool(text)
        if update:
            self.page.update()

    def _prepare_missing_audio_assets(self) -> None:
        pending_notes = [
            note for note in self.repo.notes()
            if not self._all_audio_assets_ready(note) or self.audio_processor.assets_need_refresh(note)
        ]
        if not pending_notes:
            return

        def worker() -> None:
            for note in pending_notes:
                if note.id in self.audio_assets_preparing:
                    continue
                self._prepare_note_audio_assets_blocking(note)

        threading.Thread(target=worker, daemon=True).start()

    def _start_note_audio_preparation(self, note: Note) -> None:
        if note.id in self.audio_assets_preparing:
            return
        self.audio_assets_preparing.add(note.id)
        threading.Thread(
            target=lambda: self._prepare_note_audio_assets_blocking(note, marked=True),
            daemon=True,
        ).start()

    def _prepare_note_audio_assets_blocking(self, note: Note, marked: bool = False) -> None:
        if not marked:
            if note.id in self.audio_assets_preparing:
                return
            self.audio_assets_preparing.add(note.id)
        try:
            assets = self.audio_processor.prepare_note_audio(
                note.id,
                note.media_path,
                lambda text: self._set_audio_status(note.id, text),
            )
            self.repo.update_note_audio_assets(
                note.id,
                assets["original_audio_path"],
                assets["bass_removed_audio_path"],
                assets["guitar_removed_audio_path"],
                assets["drums_only_audio_path"],
            )
        except AudioProcessingError as exc:
            self._set_audio_status(note.id, f"제거 음원 생성 실패: {exc}")
        finally:
            self.audio_assets_preparing.discard(note.id)
            if self.selected_note and self.selected_note.id == note.id:
                self.selected_note = self.repo.note(note.id)
                if self.selected_note:
                    self._render_audio_selector()
                    self._load_video(self.selected_note)
            self.notes = self.repo.notes(self.selected_category_id)
            self._render_sidebar()
            self.page.update()

    def _set_audio_status(self, note_id: int, text: str) -> None:
        if self.selected_note and self.selected_note.id == note_id:
            self.audio_status.value = text
            self.page.update()

    def _window_is_fullscreen(self) -> bool:
        window = getattr(self.page, "window", None)
        for target, attr in ((window, "full_screen"), (self.page, "window_full_screen")):
            if target is not None and hasattr(target, attr):
                return bool(getattr(target, attr))
        return False

    def _set_window_fullscreen(self, value: bool) -> None:
        window = getattr(self.page, "window", None)
        for target, attr in ((window, "full_screen"), (self.page, "window_full_screen")):
            if target is not None and hasattr(target, attr):
                setattr(target, attr, value)
                return

    def _selected_audio_kind(self, note: Note) -> str:
        if note.selected_audio_kind in {"original", "bass_removed", "guitar_removed", "drums_only"}:
            return note.selected_audio_kind
        return "original"

    @staticmethod
    def _audio_pitch(note: Note) -> int:
        return max(-9, min(9, int(getattr(note, "audio_pitch_semitones", 0) or 0)))

    @staticmethod
    def _audio_volume(note: Note) -> int:
        value = getattr(note, "audio_volume", 100)
        if value is None:
            value = 100
        return max(0, min(100, int(value)))

    def _audio_asset_ready(self, note: Note, audio_kind: str) -> bool:
        if audio_kind == "original":
            return bool(note.original_audio_path) and Path(note.original_audio_path).expanduser().exists()
        if audio_kind == "bass_removed":
            return bool(note.bass_removed_audio_path) and Path(note.bass_removed_audio_path).expanduser().exists()
        if audio_kind == "guitar_removed":
            return bool(note.guitar_removed_audio_path) and Path(note.guitar_removed_audio_path).expanduser().exists()
        if audio_kind == "drums_only":
            return bool(note.drums_only_audio_path) and Path(note.drums_only_audio_path).expanduser().exists()
        return False

    def _all_audio_assets_ready(self, note: Note) -> bool:
        return all(
            self._audio_asset_ready(note, audio_kind)
            for audio_kind in ("original", "bass_removed", "guitar_removed", "drums_only")
        )

    def _save_note(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        category = self.repo.create_category(self._category_name(self.selected_note.category_id) or "기타")
        self.repo.update_note(
            note_id=self.selected_note.id,
            title=self.title_input.value or "",
            memo=self.memo_input.value or "",
            playback_rate=float(self.rate_slider.value or 1.0),
            category_id=category.id,
        )
        self.selected_note = self.repo.note(self.selected_note.id)
        self._refresh_all()

    def _auto_save_note(self, event: Optional[ft.ControlEvent] = None) -> None:
        if not self.selected_note:
            return
        self.repo.update_note(
            note_id=self.selected_note.id,
            title=self.selected_note.title,
            memo=self.memo_input.value or "",
            playback_rate=float(self.rate_slider.value or self.selected_note.playback_rate),
            category_id=self.selected_note.category_id,
        )
        fresh = self.repo.note(self.selected_note.id)
        if fresh:
            self.selected_note = fresh

    def _auto_save_note_dialog_metadata(self, event: Optional[ft.ControlEvent] = None) -> None:
        if self.note_dialog_mode != "update" or not self.selected_note:
            return
        category = self.repo.create_category(self.dialog_category_name or "기타")
        self.repo.update_note(
            note_id=self.selected_note.id,
            title=self.new_title_input.value or self.selected_note.title,
            memo=self.memo_input.value or self.selected_note.memo,
            playback_rate=float(self.rate_slider.value or self.selected_note.playback_rate),
            category_id=category.id,
        )
        fresh = self.repo.note(self.selected_note.id)
        if fresh:
            self.selected_note = fresh
            self.notes = self.repo.notes(self.selected_category_id)
            self._render_sidebar()
            self.page.update()

    def _reset_marker_form(self) -> None:
        self.marker_name_input.value = ""
        self.marker_start_input.value = "00:00"
        self.marker_end_input.value = "00:00"

    def _auto_save_selected_marker(self, event: Optional[ft.ControlEvent] = None) -> None:
        if not self.selected_note or not self.selected_marker:
            return
        self.repo.update_tempo_marker(
            marker_id=self.selected_marker.id,
            name=self.marker_name_input.value or self.selected_marker.name,
            start_ms=self._timecode_to_ms(self.marker_start_input.value),
            end_ms=self._timecode_to_ms(self.marker_end_input.value),
            bpm=self.selected_marker.bpm,
            beats_per_bar=self.selected_marker.beats_per_bar,
            accent_first_beat=self.selected_marker.accent_first_beat,
        )
        self.markers = self.repo.tempo_markers(self.selected_note.id)
        self.selected_marker = next(
            (marker for marker in self.markers if marker.id == self.selected_marker.id),
            self.selected_marker,
        )
        self._render_markers()
        self.page.update()

    def _load_video(self, note: Note) -> None:
        path = self._playback_media_for_note(note)
        if not path.exists():
            self.video = self._make_video()
            self.video_status.value = f"영상 파일을 찾을 수 없습니다: {path}"
            return

        media = fvideo.VideoMedia(path.resolve().as_uri())
        self.video = self._make_video([media])
        self.video.playback_rate = note.playback_rate
        self.video.volume = self.video_volume
        self.video_status.value = f"영상 준비 중: {path.name}"

    def _playback_media_for_note(self, note: Note) -> Path:
        selected_kind = self._selected_audio_kind(note)
        pitch = self._audio_pitch(note)
        fallback = Path(note.media_path).expanduser()
        if selected_kind == "original" and pitch == 0:
            return fallback

        audio_path = self.audio_processor.audio_path_for_kind(note, selected_kind)
        if selected_kind == "original" and not audio_path:
            audio_path = note.media_path
        if not audio_path or not Path(audio_path).expanduser().exists():
            self._start_note_audio_preparation(note)
            self.video_status.value = "선택한 음원이 아직 준비되지 않아 원본으로 재생합니다."
            return fallback

        cached_path = self.audio_processor.cached_playback_media_path(
            note.id,
            note.media_path,
            audio_path,
            selected_kind,
            pitch,
        )
        if cached_path:
            return cached_path

        self._start_playback_media_preparation(note, selected_kind, pitch, audio_path)
        self.video_status.value = "선택 음원 재생 파일 준비 중... 원본으로 먼저 표시합니다."
        return fallback

    def _start_playback_media_preparation(
        self,
        note: Note,
        audio_kind: str,
        pitch: int,
        audio_path: str,
    ) -> None:
        key = (note.id, audio_kind, pitch)
        if key in self.playback_assets_preparing:
            return
        self.playback_assets_preparing.add(key)

        def worker() -> None:
            try:
                self.audio_processor.playback_media_path(
                    note.id,
                    note.media_path,
                    audio_path,
                    audio_kind,
                    pitch,
                )
            except AudioProcessingError as exc:
                if self.selected_note and self.selected_note.id == note.id:
                    self.video_status.value = f"선택 음원 준비 실패: {exc}"
            finally:
                self.playback_assets_preparing.discard(key)
                if (
                    self.selected_note
                    and self.selected_note.id == note.id
                    and self._selected_audio_kind(self.selected_note) == audio_kind
                    and self._audio_pitch(self.selected_note) == pitch
                ):
                    self._load_video(self.selected_note)
                    self.detail_area.content = self._note_detail()
                self.page.update()

        threading.Thread(target=worker, daemon=True).start()

    def _make_video(self, playlist: Optional[List[fvideo.VideoMedia]] = None) -> fvideo.Video:
        params = inspect.signature(fvideo.Video).parameters
        kwargs = {
            "expand": True,
            "playlist": playlist or [],
            "aspect_ratio": 16 / 9,
            "autoplay": False,
            "controls": self._video_controls(expanded=self.video_focus_mode),
            "fill_color": BG,
            "volume": self.video_volume,
            "on_enter_fullscreen": self._on_video_enter_fullscreen,
            "on_exit_fullscreen": self._on_video_exit_fullscreen,
            "on_error": self._on_video_error,
            "on_position_change": self._on_video_position_change,
        }
        kwargs["on_load" if "on_load" in params else "on_loaded"] = self._on_video_loaded
        return fvideo.Video(**{key: value for key, value in kwargs.items() if key in params})

    def _video_controls(self, expanded: bool = False) -> fvideo.AdaptiveVideoControls:
        desktop_controls = fvideo.MaterialDesktopVideoControls(
            toggle_fullscreen_on_double_press=False,
            automatically_imply_skip_next_button=False,
            automatically_imply_skip_previous_button=False,
            bottom_button_bar=[
                fvideo.VideoPlayOrPauseButton(),
                fvideo.VideoVolumeButton(),
                fvideo.VideoPositionIndicator(),
                fvideo.VideoSpacer(),
                self._video_control_focus_button(expanded=expanded),
            ],
        )
        touch_controls = fvideo.MaterialVideoControls(
            automatically_imply_skip_next_button=False,
            automatically_imply_skip_previous_button=False,
            bottom_button_bar=[
                fvideo.VideoPositionIndicator(),
                fvideo.VideoSpacer(),
                self._video_control_focus_button(expanded=expanded),
            ],
        )
        return fvideo.AdaptiveVideoControls(
            material=touch_controls,
            material_desktop=desktop_controls,
        )

    def _on_video_loaded(self, event: ft.ControlEvent) -> None:
        self.video_status.value = "영상이 준비되었습니다."
        self.page.update()

    def _on_video_error(self, event: ft.ControlEvent) -> None:
        detail = getattr(event, "data", "") or "알 수 없는 오류"
        self.video_status.value = f"영상 로드 오류: {detail}"
        self.page.update()

    def _on_video_position_change(self, event: ft.ControlEvent) -> None:
        value = self._coerce_position_ms(getattr(event, "data", None))
        if value is not None:
            self.current_position_ms = value
            self._enforce_active_loop_position(value)

    def _on_video_enter_fullscreen(self, event: ft.ControlEvent) -> None:
        self.video_fullscreen_active = True
        self.restore_app_fullscreen = self._window_is_fullscreen()
        if hasattr(self.video, "fullscreen"):
            self.video.fullscreen = True

    def _on_video_exit_fullscreen(self, event: ft.ControlEvent) -> None:
        self.video_fullscreen_active = True
        if not self.restore_app_fullscreen:
            self.video_fullscreen_active = False
            return

        if hasattr(self.video, "fullscreen"):
            self.video.fullscreen = False
        self._schedule_window_fullscreen_restore()

    def _handle_window_event(self, event) -> None:
        raw_event_type = getattr(event, "type", "") or ""
        event_type = str(getattr(raw_event_type, "value", raw_event_type))
        if (
            self.video_fullscreen_active
            and self.restore_app_fullscreen
            and "leave-full-screen" in event_type
        ):
            self._schedule_window_fullscreen_restore()

    def _schedule_window_fullscreen_restore(self) -> None:
        self._restore_window_fullscreen_once()
        for delay in FULLSCREEN_RESTORE_RECHECK_SECONDS:
            timer = threading.Timer(delay, self._restore_window_fullscreen_once)
            timer.daemon = True
            timer.start()
        clear_delay = max(FULLSCREEN_RESTORE_RECHECK_SECONDS) + 0.05
        clear_timer = threading.Timer(clear_delay, self._clear_video_fullscreen_restore)
        clear_timer.daemon = True
        clear_timer.start()

    def _restore_window_fullscreen_once(self) -> None:
        if not self.restore_app_fullscreen:
            return
        self._set_window_fullscreen(True)
        self.page.update()

    def _clear_video_fullscreen_restore(self) -> None:
        self.video_fullscreen_active = False

    def _play_video(self, event: ft.ControlEvent) -> None:
        self._call_video("play")
        self.video_playing = True

    def _pause_video(self, event: ft.ControlEvent) -> None:
        self._call_video("pause")
        self.video_playing = False
        self.loop_active = False
        self._cancel_loop_timer()

    def _seek_ms(self, position_ms: int) -> None:
        if hasattr(self.video, "seek"):
            method = getattr(self.video, "seek")
            try:
                self._run_control_method(method, position_ms)
            except TypeError:
                self._run_control_method(method, position_ms / 1000)
            self.current_position_ms = max(0, int(position_ms))
        self.page.update()

    def _change_rate(self, event: ft.ControlEvent) -> None:
        value = round(float(self.rate_slider.value or 1.0) / 0.05) * 0.05
        value = max(0.1, min(2.0, value))
        self.rate_slider.value = value
        self.rate_text.value = f"{value:.2f}x"
        self.video.playback_rate = value
        if self.selected_note:
            self._auto_save_note()
        self.page.update()

    def _change_volume(self, event: ft.ControlEvent) -> None:
        value = max(0, min(100, int(round(float(self.volume_slider.value or 0)))))
        self.video_volume = value
        self.volume_slider.value = value
        self.volume_text.value = f"{value}%"
        self.video.volume = value
        if self.selected_note:
            self.repo.update_note_audio_volume(self.selected_note.id, value)
            self.selected_note = self.repo.note(self.selected_note.id)
        self.page.update()

    def _preview_pitch(self, event: ft.ControlEvent) -> None:
        value = self._pitch_slider_value()
        self.pitch_slider.value = value
        self.pitch_text.value = self._pitch_label(value)
        self.page.update()

    def _change_pitch(self, event: ft.ControlEvent) -> None:
        if not self.selected_note:
            return
        value = self._pitch_slider_value()
        self.audio_pitch_semitones = value
        self.pitch_slider.value = value
        self.pitch_text.value = self._pitch_label(value)
        self.repo.update_note_audio_pitch(self.selected_note.id, value)
        self.selected_note = self.repo.note(self.selected_note.id)
        if self.selected_note:
            self._load_video(self.selected_note)
            self.detail_area.content = self._note_detail()
        self.page.update()

    def _capture_position(self, event: ft.ControlEvent) -> None:
        self._capture_marker_position(self.marker_start_input)

    def _capture_end_position(self, event: ft.ControlEvent) -> None:
        self._capture_marker_position(self.marker_end_input)

    def _capture_marker_position(self, field: ft.TextField) -> None:
        self._set_marker_position(field, self._video_position_ms())

    def _set_marker_position(self, field: ft.TextField, value: Optional[int]) -> None:
        value = self.current_position_ms if value is None else value
        self.current_position_ms = value
        field.value = self._format_ms(value)
        self._auto_save_selected_marker()
        self.page.update()

    def _adjust_marker_time(self, field: ft.TextField, delta_ms: int) -> None:
        value = max(0, self._timecode_to_ms(field.value) + delta_ms)
        field.value = self._format_ms(value)
        self._auto_save_selected_marker()
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
        self.selected_marker = marker
        self.loop_active = True
        self.loop_last_restart_at = 0.0
        self.video_playing = True
        self._play_from_ms(marker.start_ms)
        self._schedule_loop_restart(marker)
        self.loop_status.value = "반복 재생 중"
        self.page.update()

    def _stop_loop(self, event: ft.ControlEvent) -> None:
        self.loop_active = False
        self.video_playing = False
        self._call_video("pause")
        self._cancel_loop_timer()
        self.loop_status.value = "반복 정지"
        self.page.update()

    def _schedule_loop_restart(self, marker: Optional[TempoMarker], position_ms: Optional[int] = None) -> None:
        self._cancel_loop_timer()
        if not marker or marker.end_ms <= marker.start_ms:
            return
        rate = max(0.1, float(self.rate_slider.value or 1.0))
        start_ms = marker.start_ms if position_ms is None else max(marker.start_ms, min(marker.end_ms, position_ms))
        seconds = ((marker.end_ms - start_ms) / 1000) / rate
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
        self.loop_last_restart_at = time.monotonic()
        self.video_playing = True
        self._play_from_ms(marker.start_ms)
        self._schedule_loop_restart(marker)
        self.loop_status.value = "반복 재생 중"
        self.page.update()

    def _enforce_active_loop_position(self, position_ms: int) -> None:
        marker = self.selected_marker
        if not self.loop_active or not marker or marker.end_ms <= marker.start_ms:
            return
        if position_ms < marker.end_ms:
            return
        now = time.monotonic()
        if now - self.loop_last_restart_at < 0.3:
            return
        self.loop_last_restart_at = now
        self.video_playing = True
        self._play_from_ms(marker.start_ms)
        self._schedule_loop_restart(marker)
        self.loop_status.value = "반복 재생 중"
        self.page.update()

    def _call_video(self, method_name: str) -> None:
        method = getattr(self.video, method_name, None)
        if callable(method):
            self._run_control_method(method)
        self.page.update()

    def _toggle_video_playback(self) -> None:
        if self.video_playing:
            self._pause_video(None)
            return
        self.loop_active = False
        self._cancel_loop_timer()
        self._play_video(None)

    def _run_control_method(self, method, *args) -> None:
        if inspect.iscoroutinefunction(method):
            if hasattr(self.page, "run_task"):
                self.page.run_task(method, *args)
            else:
                asyncio.run(method(*args))
            return
        result = method(*args)
        if inspect.isawaitable(result):
            async def runner():
                return await result

            if hasattr(self.page, "run_task"):
                self.page.run_task(runner)
            else:
                asyncio.run(runner())

    def _play_from_ms(self, position_ms: int) -> None:
        self.current_position_ms = max(0, int(position_ms))
        seek = getattr(self.video, "seek", None)
        play = getattr(self.video, "play", None)
        if not callable(play):
            return
        self.video_playing = True

        async def runner() -> None:
            if callable(seek):
                try:
                    result = seek(position_ms)
                except TypeError:
                    result = seek(position_ms / 1000)
                if inspect.isawaitable(result):
                    await result
            result = play()
            if inspect.isawaitable(result):
                await result

        if inspect.iscoroutinefunction(play) or inspect.iscoroutinefunction(seek):
            if hasattr(self.page, "run_task"):
                self.page.run_task(runner)
            else:
                asyncio.run(runner())
            return
        if callable(seek):
            try:
                seek(position_ms)
            except TypeError:
                seek(position_ms / 1000)
        play()

    def _video_position_ms(self) -> int:
        for attr in ("position", "current_position"):
            value = getattr(self.video, attr, None)
            position_ms = self._coerce_position_ms(value)
            if position_ms is not None:
                return position_ms
        return self.current_position_ms

    @staticmethod
    def _is_space_key(event: ft.KeyboardEvent) -> bool:
        key = str(getattr(event, "key", "") or "").lower()
        return key in {" ", "space", "spacebar"}

    def _coerce_position_ms(self, value) -> Optional[int]:
        in_milliseconds = getattr(value, "in_milliseconds", None)
        if callable(in_milliseconds):
            return max(0, int(in_milliseconds()))
        if isinstance(in_milliseconds, (int, float)):
            return max(0, int(in_milliseconds))
        if isinstance(value, (int, float)):
            return max(0, int(value))
        text = str(value or "").strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)
        if ":" in text:
            return self._timecode_to_ms(text)
        try:
            return max(0, int(float(text)))
        except ValueError:
            return None

    def _category_name(self, category_id: Optional[int]) -> str:
        for category in self.categories:
            if category.id == category_id:
                return category.name
        return "미분류"

    def _note_dialog_category_name(self) -> str:
        key = self.note_category_dropdown.value
        category = self._category_by_id(int(key)) if key else None
        return category.name if category else "기타"

    def _category_by_id(self, category_id: int) -> Optional[Category]:
        for category in self.categories:
            if category.id == category_id:
                return category
        return None

    def _category_by_name(self, name: str) -> Optional[Category]:
        for category in self.categories:
            if category.name == name:
                return category
        return None

    def _category_key_by_name(self, name: str) -> Optional[str]:
        category = self._category_by_name(name)
        if category:
            return str(category.id)
        fallback = self._category_by_name("기타")
        return str(fallback.id) if fallback else None

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

    def _deletable_categories(self) -> List[Category]:
        protected = {"기타", "베이스", "미분류"}
        return [category for category in self._ordered_categories(include_all=False) if category.name not in protected]

    def _category_options(self, include_all: bool, sidebar: bool) -> List[ft.dropdown.Option]:
        options: List[ft.dropdown.Option] = []
        text_color = SIDEBAR_TEXT if sidebar else TEXT
        if include_all:
            options.append(
                ft.dropdown.Option(
                    key="all",
                    text="전체",
                    content=ft.Text("전체", color=SIDEBAR_TEXT, size=14, weight=ft.FontWeight.BOLD),
                )
            )
        for category in self._ordered_categories(include_all=False):
            options.append(
                ft.dropdown.Option(
                    key=str(category.id),
                    text=category.name,
                    content=ft.Text(category.name, color=text_color, size=14),
                )
            )
        return options

    def _audio_kind_options(self, note: Note) -> List[ft.dropdown.Option]:
        options: List[ft.dropdown.Option] = []
        for key, label in AUDIO_KIND_LABELS.items():
            ready = key == "original" or self._audio_asset_ready(note, key)
            display = label if ready else f"{label} (생성 전)"
            color = TEXT if ready else MUTED
            options.append(
                ft.dropdown.Option(
                    key=key,
                    text=display,
                    content=ft.Text(display, color=color, size=14),
                )
            )
        return options

    def _audio_kind_dropdown(self) -> ft.Dropdown:
        dropdown = self._category_dropdown(
            label="음원",
            width=210,
            include_all=False,
            on_change=self._select_audio_from_dropdown,
        )
        dropdown.value = "original"
        self._apply_dropdown_options(
            dropdown,
            [
                ft.dropdown.Option(
                    key=key,
                    text=label,
                    content=ft.Text(label, color=TEXT, size=14),
                )
                for key, label in AUDIO_KIND_LABELS.items()
            ],
        )
        return dropdown

    def _category_dropdown(self, label: str, width: int, include_all: bool, on_change, sidebar: bool = False) -> ft.Dropdown:
        params = inspect.signature(ft.Dropdown).parameters
        kwargs = {
            "label": label,
            "width": width,
            "dense": True,
            "menu_width": width,
            "border_color": "#BCA77C" if sidebar else LINE,
            "focused_border_color": SIDEBAR_TEXT if sidebar else ACCENT,
            "bgcolor": "#FFF2D7" if sidebar else PANEL_2,
            "color": SIDEBAR_TEXT if sidebar else TEXT,
            "text_style": ft.TextStyle(color=SIDEBAR_TEXT if sidebar else TEXT),
            "label_style": ft.TextStyle(color=SIDEBAR_MUTED if sidebar else MUTED),
            "options": [],
        }
        kwargs["menu_height" if "menu_height" in params else "max_menu_height"] = self._dropdown_menu_height(0)
        kwargs["on_select" if "on_select" in params else "on_change"] = on_change
        if "on_focus" in params:
            kwargs["on_focus"] = lambda event: self._set_text_entry_active(True)
        if "on_blur" in params:
            kwargs["on_blur"] = lambda event: self._set_text_entry_active(False)
        if "focused_color" in params:
            kwargs["focused_color"] = SIDEBAR_TEXT if sidebar else TEXT
        if "select_icon_enabled_color" in params:
            kwargs["select_icon_enabled_color"] = SIDEBAR_TEXT if sidebar else TEXT
        if "icon_enabled_color" in params:
            kwargs["icon_enabled_color"] = SIDEBAR_TEXT if sidebar else TEXT
        return ft.Dropdown(**{key: value for key, value in kwargs.items() if key in params})

    def _apply_dropdown_options(self, dropdown: ft.Dropdown, options: List[ft.dropdown.Option]) -> None:
        dropdown.options = options
        height = self._dropdown_menu_height(len(options))
        params = inspect.signature(ft.Dropdown).parameters
        if "menu_height" in params:
            dropdown.menu_height = height
        elif "max_menu_height" in params:
            dropdown.max_menu_height = height

    @staticmethod
    def _dropdown_menu_height(option_count: int) -> int:
        return min(
            DROPDOWN_MENU_MAX_HEIGHT,
            max(DROPDOWN_OPTION_HEIGHT, option_count * DROPDOWN_OPTION_HEIGHT),
        )

    def _set_text_entry_active(self, active: bool) -> None:
        self.text_entry_active = active

    def _pitch_slider_value(self) -> int:
        return max(-9, min(9, int(round(float(self.pitch_slider.value or 0)))))

    @staticmethod
    def _pitch_label(value: int) -> str:
        if value > 0:
            return f"+{value}키"
        return f"{value}키"

    def _text_field(
        self,
        label: str,
        width: Optional[int] = None,
        expand: bool = False,
        value: str = "",
        height: Optional[int] = None,
        on_change=None,
    ) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            width=width,
            expand=expand,
            height=height,
            dense=True,
            border_color=LINE,
            focused_border_color=ACCENT,
            bgcolor=PANEL_2,
            color=TEXT,
            cursor_color=ACCENT,
            label_style=ft.TextStyle(color=MUTED),
            on_change=on_change,
            on_focus=lambda event: self._set_text_entry_active(True),
            on_blur=lambda event: self._set_text_entry_active(False),
        )

    def _marker_text_field(self, hint_text: str, value: str = "", on_change=None) -> ft.TextField:
        return ft.TextField(
            value=value,
            hint_text=hint_text,
            expand=True,
            dense=True,
            text_size=14,
            border_color=LINE,
            focused_border_color=ACCENT,
            bgcolor=PANEL_2,
            color=TEXT,
            cursor_color=ACCENT,
            hint_style=ft.TextStyle(color=MUTED, size=13),
            content_padding=ft.padding.symmetric(horizontal=12, vertical=MARKER_FIELD_PAD_V),
            on_change=on_change,
            on_focus=lambda event: self._set_text_entry_active(True),
            on_blur=lambda event: self._set_text_entry_active(False),
        )

    def _marker_time_field(self, hint_text: str) -> ft.TextField:
        return ft.TextField(
            value="00:00",
            hint_text=hint_text,
            width=MARKER_TIME_FIELD_WIDTH,
            dense=True,
            text_size=14,
            border_color=LINE,
            focused_border_color=ACCENT,
            bgcolor=PANEL_2,
            color=TEXT,
            cursor_color=ACCENT,
            read_only=True,
            hint_style=ft.TextStyle(color=MUTED, size=13),
            content_padding=ft.padding.symmetric(horizontal=12, vertical=MARKER_FIELD_PAD_V),
        )

    def _marker_field_row(self, label: str, field: ft.Control, trailing: ft.Control) -> ft.Row:
        return ft.Row(
            [
                ft.Container(
                    width=MARKER_LABEL_WIDTH,
                    alignment=ft.alignment.center_left,
                    content=ft.Text(label, color=MUTED, size=13),
                ),
                ft.Container(expand=True),
                field,
                trailing,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _marker_action_button(self, label: str, icon: str, handler) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(icon, color=BG, size=16),
                    ft.Text(label, color=BG, size=13, weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=handler,
            width=MARKER_ACTION_BUTTON_WIDTH,
            height=MARKER_ACTION_BUTTON_HEIGHT,
            elevation=0,
            style=ft.ButtonStyle(
                bgcolor=ACCENT,
                color=BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.padding.all(0),
            ),
        )

    def _marker_time_controls(self, field: ft.TextField, capture_icon: str, capture_handler) -> ft.Row:
        return ft.Row(
            [
                self._marker_nudge_button("-1", lambda event, target=field: self._adjust_marker_time(target, -1000)),
                self._marker_nudge_button("+1", lambda event, target=field: self._adjust_marker_time(target, 1000)),
                self._marker_action_button("현재", capture_icon, capture_handler),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _marker_nudge_button(self, label: str, handler) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            content=ft.Text(label, color=BEIGE, size=12, weight=ft.FontWeight.BOLD),
            on_click=handler,
            width=34,
            height=MARKER_ACTION_BUTTON_HEIGHT,
            elevation=0,
            style=ft.ButtonStyle(
                bgcolor=PANEL_2,
                color=BEIGE,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.padding.all(0),
            ),
        )

    def _button(self, label: str, icon: str, handler) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            label,
            icon=icon,
            on_click=handler,
            style=ft.ButtonStyle(
                bgcolor=ACCENT,
                color=BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
            ),
        )

    def _video_focus_button(self, expanded: bool) -> ft.ElevatedButton:
        return self._button(
            "영상 축소" if expanded else "영상 확대",
            ft.Icons.FULLSCREEN_EXIT_ROUNDED if expanded else ft.Icons.FULLSCREEN_ROUNDED,
            self._toggle_video_focus,
        )

    def _video_control_focus_button(self, expanded: bool) -> ft.IconButton:
        return ft.IconButton(
            icon=ft.Icons.FULLSCREEN_EXIT_ROUNDED if expanded else ft.Icons.FULLSCREEN_ROUNDED,
            icon_color=TEXT,
            icon_size=22,
            tooltip="영상 축소" if expanded else "영상 확대",
            on_click=self._toggle_video_focus,
        )

    def _compact_button(
        self,
        label: str,
        icon: str,
        handler,
        expand: bool = False,
        height: Optional[int] = None,
    ) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            label,
            icon=icon,
            on_click=handler,
            expand=expand,
            height=height,
            style=ft.ButtonStyle(
                bgcolor=ACCENT,
                color=BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
            ),
        )

    def _bare_text_field(
        self,
        width: Optional[int] = None,
        expand: bool = False,
        value: str = "",
        height: Optional[int] = None,
    ) -> ft.TextField:
        return ft.TextField(
            value=value,
            width=width,
            expand=expand,
            height=height,
            dense=True,
            border_color=LINE,
            focused_border_color=ACCENT,
            bgcolor=PANEL_2,
            color=TEXT,
            cursor_color=ACCENT,
            on_focus=lambda event: self._set_text_entry_active(True),
            on_blur=lambda event: self._set_text_entry_active(False),
        )

    def _category_add_button(self) -> ft.Container:
        return ft.Container(
            width=86,
            height=CATEGORY_ADD_CONTROL_HEIGHT,
            bgcolor=ACCENT,
            border_radius=6,
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(horizontal=12, vertical=0),
            on_click=self._add_category,
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_ROUNDED, color=BG, size=18),
                    ft.Text("추가", color=BG, size=14, weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _danger_button(self, label: str, icon: str, handler) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            label,
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
        return f"{minutes:02d}:{seconds:02d}"

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
