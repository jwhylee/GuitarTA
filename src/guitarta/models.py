from dataclasses import dataclass
from typing import Optional


@dataclass
class Category:
    id: int
    name: str
    created_at: str


@dataclass
class Note:
    id: int
    title: str
    source_url: str
    media_path: str
    original_audio_path: str
    bass_removed_audio_path: str
    guitar_removed_audio_path: str
    drums_only_audio_path: str
    selected_audio_kind: str
    audio_pitch_semitones: int
    category_id: Optional[int]
    memo: str
    playback_rate: float
    created_at: str
    updated_at: str


@dataclass
class TempoMarker:
    id: int
    note_id: int
    name: str
    start_ms: int
    end_ms: int
    bpm: int
    beats_per_bar: int
    accent_first_beat: bool
    created_at: str
