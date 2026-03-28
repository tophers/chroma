# /opt/jukebox/scanner.py

import re
import time
import subprocess
import sqlite3
from pathlib import Path

# Keep your existing DB imports
from db import get_db, get_all_video_paths, prune_videos

VIDEO_ROOT = Path("/opt/music_videos")

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


# --- PHASE 1: FILE DISCOVERY (Existing Logic) ---

def scan_library():
    """
    1. Crawl VIDEO_ROOT for .mkv files.
    2. Upsert valid files into DB.
    3. Remove files from DB that are no longer on disk (Prune).
    """
    db = get_db()
    cur = db.cursor()

    print("[Scanner] Starting library discovery...")

    # 1. Get a snapshot of what is currently in the DB
    existing_paths = set(get_all_video_paths())
    found_paths = set()

    added_count = 0
    updated_count = 0

    # 2. Walk filesystem
    for file in VIDEO_ROOT.rglob("*.mkv"):
        m = FILENAME_RE.match(file.name)
        if not m:
            # Silent skip for non-matching files
            continue

        path_str = str(file)
        found_paths.add(path_str)

        meta = m.groupdict()
        artist = meta["artist"].strip()
        title = meta["title"].strip()

        # Update metadata if filename case changed, or insert new
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

    # 3. Prune
    to_delete = list(existing_paths - found_paths)

    if to_delete:
        print(f"[Scanner] Pruning {len(to_delete)} missing files from DB.")
        prune_videos(to_delete)

    print(f"[Scanner] Discovery complete. Added: {added_count}, Verified: {updated_count}, Pruned: {len(to_delete)}")


# --- PHASE 2: AUDIO ANALYSIS (New Logic) ---

def get_ffmpeg_audio_stats(file_path):
    """
    Runs a specialized ffmpeg pass to measure loudness and true peak.
    Returns: (integrated_lufs, true_peak_db) or (None, None) on failure.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner", "-nostats",
        "-i", str(file_path),
        "-map", "0:a",
        "-filter:a", "ebur128=peak=true", # peak=true is CRITICAL
        "-f", "null",
        "-"
    ]
    
    try:
        # Capture stderr because that's where stats are printed
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        lufs = None
        true_peak = None
        
        for line in result.stderr.splitlines():
            line = line.strip()
            if line.startswith("I:") and "LUFS" in line:
                # Example: "I:         -23.4 LUFS"
                parts = line.split()
                if len(parts) >= 2:
                    try: lufs = float(parts[1])
                    except: pass
            elif line.startswith("Peak:") and "dBFS" in line:
                # Example: "Peak:        -1.5 dBFS"
                parts = line.split()
                if len(parts) >= 2:
                    try: true_peak = float(parts[1])
                    except: pass
                    
        return lufs, true_peak
        
    except Exception as e:
        print(f"[Scanner] Error analyzing {file_path.name}: {e}")
        return None, None


def calculate_safe_gain(lufs, true_peak, target_lufs=-14.0):
    """
    Calculates gain with a 'Soft Clamp' to prevent over-limiting.
    """
    if lufs is None or true_peak is None:
        return 0.0

    # 1. Raw Calculation (Target - Measured)
    raw_gain = target_lufs - lufs

    # 2. Silence Protection (Don't boost empty noise)
    if lufs < -60.0:
        return 0.0

    # 3. Soft Clamp Logic
    # We want the final peak to be around -1.0 dB.
    # If the True Peak is currently -2.0 dB, we technically only have 1.0 dB of headroom.
    # However, we have a limiter, so we can push it slightly.
    # Rule: Allow the limiter to eat up to 2.0 dB of transients.
    max_headroom = (-1.0 - true_peak) + 2.0 
    
    # 4. Hard Caps (Sanity Check)
    # Never boost more than +15dB, never cut more than -30dB
    final_gain = min(raw_gain, 15.0, max_headroom)
    final_gain = max(final_gain, -30.0)
    
    return round(final_gain, 2)


def run_audio_analysis(force=False):
    """
    Iterates over the DB, finds tracks needing analysis, and updates them.
    """
    db = get_db()
    cur = db.cursor()
    
    # Query: Find tracks not locked by user AND (missing gain OR forced)
    query = """
        SELECT id, path, title, manual_override, audio_gain
        FROM videos 
        WHERE manual_override = 0 
    """
    if not force:
        # If not forcing, only select rows where we haven't done analysis yet
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
            
            # Write to DB immediately (WAL mode handles concurrency)
            cur.execute("""
                UPDATE videos 
                SET audio_gain = ?, integrated_loudness = ?, true_peak = ?
                WHERE id = ?
            """, (gain, lufs, tp, vid_id))
            db.commit() 
            
            print(f" Done ({duration:.1f}s). I={lufs} TP={tp} -> Gain={gain}dB")
        else:
            print(" Failed to parse stats.")
            
        # Sleep slightly to let the Pi cool down / handle other requests
        time.sleep(1.0)

    db.close()
    print("--- Audio Analysis Complete ---")


def run_full_scan():
    """Helper to run both discovery and analysis."""
    scan_library()
    run_audio_analysis()


if __name__ == "__main__":
    # If run from command line: python3 scanner.py
    run_full_scan()
