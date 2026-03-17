import re
import time
import subprocess
import sqlite3
from pathlib import Path
from db import get_db, get_all_video_paths, prune_videos

VIDEO_ROOT = Path("/opt/videos")

# Strict regex: Artist - Song.mkv
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
    db = get_db()
    cur = db.cursor()

    print("[Scanner] Starting library discovery...")

    existing_paths = set(get_all_video_paths())
    found_paths = set()

    added_count = 0
    updated_count = 0

    for file in VIDEO_ROOT.rglob("*.mkv"):
        m = FILENAME_RE.match(file.name)
        if not m:
            continue

        path_str = str(file)
        found_paths.add(path_str)

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
                path_str,
                artist,
                title,
            ),
        )

        if path_str not in existing_paths:
            added_count += 1
        else:
            updated_count += 1

    db.commit()
    db.close()

    to_delete = list(existing_paths - found_paths)

    if to_delete:
        print(f"[Scanner] Pruning {len(to_delete)} missing files from DB.")
        prune_videos(to_delete)

    print(f"[Scanner] Discovery complete. Added: {added_count}, Verified: {updated_count}, Pruned: {len(to_delete)}")

def get_ffmpeg_audio_stats(file_path):
    cmd = [
        "ffmpeg",
        "-hide_banner", "-nostats",
        "-i", str(file_path),
        "-map", "0:a",
        "-filter:a", "ebur128=peak=true",
        "-f", "null",
        "-"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        lufs = None
        true_peak = None
        
        for line in result.stderr.splitlines():
            line = line.strip()
            if line.startswith("I:") and "LUFS" in line:
                parts = line.split()
                if len(parts) >= 2:
                    try: lufs = float(parts[1])
                    except: pass
            elif line.startswith("Peak:") and "dBFS" in line:
                parts = line.split()
                if len(parts) >= 2:
                    try: true_peak = float(parts[1])
                    except: pass
                    
        return lufs, true_peak
        
    except Exception as e:
        print(f"[Scanner] Error analyzing {file_path.name}: {e}")
        return None, None

def calculate_safe_gain(lufs, true_peak, target_lufs=-14.0):
    if lufs is None or true_peak is None:
        return 0.0

    raw_gain = target_lufs - lufs

    if lufs < -60.0:
        return 0.0

    max_headroom = (-1.0 - true_peak) + 2.0 
    
    final_gain = min(raw_gain, 15.0, max_headroom)
    final_gain = max(final_gain, -30.0)
    
    return round(final_gain, 2)

def run_audio_analysis(force=False):
    db = get_db()
    cur = db.cursor()
    query = """
        SELECT id, path, title, manual_override, audio_gain
        FROM videos 
        WHERE manual_override = 0 
    """
    if not force:
        query += " AND (audio_gain = 0.0 AND integrated_loudness IS NULL)"
        
    cur.execute(query)
    rows = cur.fetchall()
    
    if not rows:
        print("[Scanner] No tracks require audio analysis.")
        db.close()
        return

    print(f"--- Audio Analysis Started ---")
    print(f"Found {len(rows)} tracks to analyze.")
    
    for idx, row in enumerate(rows):
        vid_id = row['id']
        path = Path(row['path'])
        
        if not path.exists():
            print(f"Skipping missing file: {path}")
            continue
            
        print(f"[{idx+1}/{len(rows)}] Analyzing: {row['title']}...", end="", flush=True)
        
        start_t = time.time()
        lufs, tp = get_ffmpeg_audio_stats(path)
        duration = time.time() - start_t
        
        if lufs is not None:
            gain = calculate_safe_gain(lufs, tp)
            cur.execute("""
                UPDATE videos 
                SET audio_gain = ?, integrated_loudness = ?, true_peak = ?
                WHERE id = ?
            """, (gain, lufs, tp, vid_id))
            db.commit() 
            
            print(f" Done ({duration:.1f}s). I={lufs} TP={tp} -> Gain={gain}dB")
        else:
            print(" Failed to parse stats.")
            
        time.sleep(1.0)

    db.close()
    print("--- Audio Analysis Complete ---")


def run_full_scan():
    scan_library()
    run_audio_analysis()


if __name__ == "__main__":
    run_full_scan()
