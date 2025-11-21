# /opt/jukebox/db.py

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = Path("/opt/jukebox/jukebox.db")


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def db_exists() -> bool:
    """Check if the database file exists."""
    return DB_PATH.exists()


def init_schema():
    """Create tables. Dropped year/genre, added playlists."""
    db = get_db()
    cur = db.cursor()
    
    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")
    
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            filename            TEXT NOT NULL,
            path                TEXT NOT NULL UNIQUE,
            artist              TEXT NOT NULL,
            title               TEXT NOT NULL,
            banned              INTEGER NOT NULL DEFAULT 0,
            broken              INTEGER NOT NULL DEFAULT 0,
            play_count          INTEGER NOT NULL DEFAULT 0,
            last_played         TEXT
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
        """
    )
    db.commit()
    db.close()


def pick_random_video() -> Optional[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT id, path, artist, title
        FROM videos
        WHERE banned = 0
          AND broken = 0
        ORDER BY RANDOM()
        LIMIT 1
        """
    )
    row = cur.fetchone()
    db.close()
    return dict(row) if row else None


def get_video_by_id(video_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, path, artist, title, banned FROM videos WHERE id = ?",
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
        SELECT id, artist, title
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
        SELECT id, artist, title
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


def mark_video_broken(path: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE videos SET broken = 1 WHERE path = ?", (path,))
    db.commit()
    db.close()


def set_banned_by_path(path: str, banned: bool):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE videos SET banned = ? WHERE path = ?",
        (1 if banned else 0, path),
    )
    db.commit()
    db.close()


def set_banned_by_id(video_id: int, banned: bool):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE videos SET banned = ? WHERE id = ?",
        (1 if banned else 0, video_id),
    )
    db.commit()
    db.close()


def list_banned_videos():
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT id, artist, title, filename, path
        FROM videos
        WHERE banned = 1
        ORDER BY artist, title
        """
    )
    rows = cur.fetchall()
    db.close()
    return [dict(row) for row in rows]

# --- Playlist Functions ---

def create_playlist(name: str, video_ids: List[int]):
    """Create a new playlist and populate it with video IDs."""
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO playlists (name, created_at) VALUES (?, ?)",
            (name, datetime.utcnow().isoformat())
        )
        playlist_id = cur.lastrowid
        
        # Batch insert items
        if video_ids:
            data = [(playlist_id, vid, idx) for idx, vid in enumerate(video_ids)]
            cur.executemany(
                "INSERT INTO playlist_items (playlist_id, video_id, sort_order) VALUES (?, ?, ?)",
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
    """Return actual video objects for a playlist, respecting sort order."""
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT v.id, v.path, v.artist, v.title
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
