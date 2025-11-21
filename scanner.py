# /opt/jukebox/scanner.py

import re
from pathlib import Path

from db import get_db

VIDEO_ROOT = Path("/opt/music_videos")

# Strict regex: Artist - Song.mkv, metadata rabbit holes are not for me. 
FILENAME_RE = re.compile(
    r"""
    ^
    (?P<artist>.+?)
    \s*-\s*
    (?P<title>.+?)
    \.mkv
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)


def scan_library():
    """
    Crawl VIDEO_ROOT for .mkv files, parse filenames, and upsert into DB.
    Drops support for mp4 or complex naming.
    """
    db = get_db()
    cur = db.cursor()
    
    print("[Scanner] Starting library scan...")
    count = 0

    for file in VIDEO_ROOT.rglob("*.mkv"):
        m = FILENAME_RE.match(file.name)
        if not m:
            print(f"[Scanner] Skipping invalid format: {file.name}")
            continue

        meta = m.groupdict()
        artist = meta["artist"].strip()
        title = meta["title"].strip()

        cur.execute(
            """
            INSERT INTO videos (filename, path, artist, title)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                artist = excluded.artist,
                title  = excluded.title
            """,
            (
                file.name,
                str(file),
                artist,
                title,
            ),
        )
        count += 1

    db.commit()
    db.close()
    print(f"[Scanner] Scan complete. Processed {count} videos.")
