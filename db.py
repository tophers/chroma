import sqlite3
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = Path("chroma.db")

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON;")
    return db

def db_exists() -> bool:
    return DB_PATH.exists()

def init_schema():
    db = get_db()
    cur = db.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT NOT NULL,
            path            TEXT NOT NULL UNIQUE,
            artist          TEXT NOT NULL,
            title           TEXT NOT NULL,
            banned          INTEGER NOT NULL DEFAULT 0,
            broken          INTEGER NOT NULL DEFAULT 0,
            play_count      INTEGER NOT NULL DEFAULT 0,
            banned_at       TEXT,
            last_played     TEXT,
            audio_gain           REAL DEFAULT 0.0,
            integrated_loudness  REAL,
            true_peak            REAL,
            manual_override      INTEGER DEFAULT 0,
            analysis_version     INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS playlists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS playlist_items (
            playlist_id INTEGER,
            video_id    INTEGER,
            sort_order  INTEGER,
            PRIMARY KEY (playlist_id, video_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS playback_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    INTEGER,
            played_at   TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()
    db.close()

def pick_random_video() -> Optional[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT id, path, artist, title, audio_gain, play_count
        FROM videos
        WHERE banned = 0
          AND broken = 0
        ORDER BY play_count ASC, last_played ASC, RANDOM()
        LIMIT 50
        """
    )
    rows = cur.fetchall()
    db.close()

    if not rows:
        return None

    candidates = [dict(row) for row in rows]
    return random.choice(candidates)


def get_video_by_id(video_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, path, artist, title, banned, audio_gain, play_count FROM videos WHERE id = ?",
        (video_id,),
    )
    row = cur.fetchone()
    db.close()
    return dict(row) if row else None

def get_all_videos() -> List[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT id, artist, title, audio_gain, play_count
        FROM videos
        WHERE banned = 0 AND broken = 0
        ORDER BY artist, title
        """
    )
    rows = cur.fetchall()
    db.close()
    return [dict(row) for row in rows]

def search_videos(query: str) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    search_term = f"%{query}%"
    cur.execute(
        """
        SELECT id, artist, title, audio_gain, play_count
        FROM videos
        WHERE banned = 0
          AND broken = 0
          AND (artist LIKE ? OR title LIKE ?)
        ORDER BY artist, title
        LIMIT 100
        """,
        (search_term, search_term),
    )
    rows = cur.fetchall()
    db.close()
    return [dict(row) for row in rows]

def update_play_stats(path: str):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        UPDATE videos
        SET play_count = play_count + 1,
            last_played = ?
        WHERE path = ?
        """,
        (datetime.utcnow().isoformat(), path),
    )
    db.commit()
    db.close()

def log_playback_history(video_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO playback_history (video_id, played_at) VALUES (?, ?)",
        (video_id, datetime.utcnow().isoformat())
    )
    db.commit()
    db.close()

def get_recent_history(limit: int = 20) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT v.id, v.path, v.artist, v.title, v.audio_gain, ph.played_at
        FROM playback_history ph
        JOIN videos v ON ph.video_id = v.id
        ORDER BY ph.id DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cur.fetchall()
    db.close()
    return [dict(row) for row in rows]

def mark_video_broken(path: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE videos SET broken = 1 WHERE path = ?", (path,))
    db.commit()
    db.close()

def set_banned_by_path(path: str, banned: bool):
    db = get_db()
    cur = db.cursor()
    now = datetime.utcnow().isoformat() if banned else None
    cur.execute(
        "UPDATE videos SET banned = ?, banned_at = ? WHERE path = ?",
        (1 if banned else 0, now, path),
    )
    db.commit()
    db.close()

def set_banned_by_id(video_id: int, banned: bool):
    db = get_db()
    cur = db.cursor()
    now = datetime.utcnow().isoformat() if banned else None
    cur.execute(
        "UPDATE videos SET banned = ?, banned_at = ? WHERE id = ?",
        (1 if banned else 0, now, video_id),
    )
    db.commit()
    db.close()

def list_banned_videos():
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT id, artist, title, filename, path, banned_at
        FROM videos
        WHERE banned = 1
        ORDER BY banned_at DESC
        """
    )
    rows = cur.fetchall()
    db.close()
    return [dict(row) for row in rows]

def get_all_video_paths() -> List[str]:
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT path FROM videos")
    rows = cur.fetchall()
    db.close()
    return [row["path"] for row in rows]

def prune_videos(paths_to_remove: List[str]):
    if not paths_to_remove:
        return
    db = get_db()
    cur = db.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.executemany("DELETE FROM videos WHERE path = ?", [(p,) for p in paths_to_remove])
    db.commit()
    db.close()

def set_manual_gain(video_id: int, gain: float):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        UPDATE videos 
        SET audio_gain = ?, manual_override = 1 
        WHERE id = ?
        """,
        (gain, video_id)
    )
    db.commit()
    db.close()

def create_playlist(name: str, video_ids: List[int]):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO playlists (name, created_at) VALUES (?, ?)",
            (name, datetime.utcnow().isoformat())
        )
        playlist_id = cur.lastrowid

        if video_ids:
            data = [(playlist_id, vid, idx) for idx, vid in enumerate(video_ids)]
            cur.executemany(
                "INSERT OR IGNORE INTO playlist_items (playlist_id, video_id, sort_order) VALUES (?, ?, ?)",
                data
            )
        db.commit()
        return playlist_id
    finally:
        db.close()

def get_playlists():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM playlists ORDER BY name")
    rows = cur.fetchall()
    db.close()
    return [dict(row) for row in rows]

def delete_playlist(playlist_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    db.commit()
    db.close()

def get_playlist_items(playlist_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT v.id, v.path, v.artist, v.title, v.audio_gain, v.play_count
        FROM playlist_items pi
        JOIN videos v ON pi.video_id = v.id
        WHERE pi.playlist_id = ?
        ORDER BY pi.sort_order ASC
        """,
        (playlist_id,)
    )
    rows = cur.fetchall()
    db.close()
    return [dict(row) for row in rows]

def add_to_playlist(playlist_id: int, video_id: int) -> bool:
    db = get_db()
    cur = db.cursor()
    added = False
    try:
        cur.execute("SELECT MAX(sort_order) as m FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
        row = cur.fetchone()
        next_order = (row['m'] + 1) if row and row['m'] is not None else 0

        cur.execute(
            "INSERT INTO playlist_items (playlist_id, video_id, sort_order) VALUES (?, ?, ?)",
            (playlist_id, video_id, next_order)
        )
        db.commit()
        added = True
    except sqlite3.IntegrityError:
        pass
    finally:
        db.close()
    
    return added

def remove_from_playlist(playlist_id: int, video_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "DELETE FROM playlist_items WHERE playlist_id = ? AND video_id = ?",
        (playlist_id, video_id)
    )
    db.commit()
    db.close()
