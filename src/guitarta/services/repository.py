import sqlite3
from pathlib import Path
from typing import List, Optional

from guitarta.models import Category, Note, TempoMarker


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    media_path TEXT NOT NULL,
                    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                    memo TEXT NOT NULL DEFAULT '',
                    playback_rate REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tempo_markers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    start_ms INTEGER NOT NULL DEFAULT 0,
                    end_ms INTEGER NOT NULL DEFAULT 0,
                    bpm INTEGER NOT NULL DEFAULT 120,
                    beats_per_bar INTEGER NOT NULL DEFAULT 4,
                    accent_first_beat INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(tempo_markers)").fetchall()
            }
            if "end_ms" not in columns:
                conn.execute(
                    "ALTER TABLE tempo_markers ADD COLUMN end_ms INTEGER NOT NULL DEFAULT 0"
                )
            conn.execute(
                "INSERT OR IGNORE INTO categories(name) VALUES (?)",
                ("미분류",),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO categories(name) VALUES (?)",
                [("기타",), ("베이스",)],
            )

    def categories(self) -> List[Category]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        return [self._category(row) for row in rows]

    def notes(self, category_id: Optional[int] = None) -> List[Note]:
        sql = "SELECT * FROM notes"
        params = ()
        if category_id is not None:
            sql += " WHERE category_id = ?"
            params = (category_id,)
        sql += " ORDER BY updated_at DESC, id DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._note(row) for row in rows]

    def note(self, note_id: int) -> Optional[Note]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return self._note(row) if row else None

    def category_by_name(self, name: str) -> Optional[Category]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone()
        return self._category(row) if row else None

    def create_category(self, name: str) -> Category:
        clean_name = name.strip() or "미분류"
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (clean_name,))
            row = conn.execute("SELECT * FROM categories WHERE name = ?", (clean_name,)).fetchone()
        return self._category(row)

    def create_note(
        self,
        title: str,
        source_url: str,
        media_path: str,
        category_id: Optional[int],
    ) -> Note:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO notes(title, source_url, media_path, category_id)
                VALUES (?, ?, ?, ?)
                """,
                (title.strip() or "새 연습 노트", source_url, media_path, category_id),
            )
            note_id = int(cur.lastrowid)
        note = self.note(note_id)
        if note is None:
            raise RuntimeError("노트 생성에 실패했습니다.")
        return note

    def update_note(
        self,
        note_id: int,
        title: str,
        memo: str,
        playback_rate: float,
        category_id: Optional[int],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notes
                SET title = ?, memo = ?, playback_rate = ?, category_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title.strip() or "새 연습 노트", memo, playback_rate, category_id, note_id),
            )

    def update_note_media(
        self,
        note_id: int,
        source_url: str,
        media_path: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notes
                SET source_url = ?, media_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (source_url, media_path, note_id),
            )

    def delete_note(self, note_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def tempo_markers(self, note_id: int) -> List[TempoMarker]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tempo_markers WHERE note_id = ? ORDER BY start_ms, id",
                (note_id,),
            ).fetchall()
        return [self._marker(row) for row in rows]

    def create_tempo_marker(
        self,
        note_id: int,
        name: str,
        start_ms: int,
        bpm: int,
        beats_per_bar: int,
        accent_first_beat: bool,
        end_ms: int = 0,
    ) -> TempoMarker:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tempo_markers(
                    note_id, name, start_ms, end_ms, bpm, beats_per_bar, accent_first_beat
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    name.strip() or "새 구간",
                    max(0, start_ms),
                    max(0, end_ms),
                    max(20, min(300, bpm)),
                    max(1, min(16, beats_per_bar)),
                    1 if accent_first_beat else 0,
                ),
            )
            marker_id = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM tempo_markers WHERE id = ?", (marker_id,)).fetchone()
        return self._marker(row)

    def delete_tempo_marker(self, marker_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tempo_markers WHERE id = ?", (marker_id,))

    @staticmethod
    def _category(row: sqlite3.Row) -> Category:
        return Category(id=row["id"], name=row["name"], created_at=row["created_at"])

    @staticmethod
    def _note(row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"],
            title=row["title"],
            source_url=row["source_url"],
            media_path=row["media_path"],
            category_id=row["category_id"],
            memo=row["memo"],
            playback_rate=float(row["playback_rate"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _marker(row: sqlite3.Row) -> TempoMarker:
        return TempoMarker(
            id=row["id"],
            note_id=row["note_id"],
            name=row["name"],
            start_ms=row["start_ms"],
            end_ms=row["end_ms"],
            bpm=row["bpm"],
            beats_per_bar=row["beats_per_bar"],
            accent_first_beat=bool(row["accent_first_beat"]),
            created_at=row["created_at"],
        )
