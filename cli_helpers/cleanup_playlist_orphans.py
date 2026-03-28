import sqlite3
from pathlib import Path

DB_PATH = Path("/opt/jukebox/jukebox.db")

def cleanup_orphans():
    print("--- Starting Database Cleanup ---")
    
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Clean orphaned playlist items
    cur.execute("""
        DELETE FROM playlist_items 
        WHERE playlist_id NOT IN (SELECT id FROM playlists)
    """)
    playlists_cleaned = cur.rowcount
    
    # 2. Clean orphaned playback history (if any videos were pruned)
    cur.execute("""
        DELETE FROM playback_history 
        WHERE video_id NOT IN (SELECT id FROM videos)
    """)
    history_cleaned = cur.rowcount

    conn.commit()
    conn.close()

    print(f"Removed {playlists_cleaned} orphaned playlist items.")
    print(f"Removed {history_cleaned} orphaned playback history records.")
    print("--- Cleanup Complete ---")

if __name__ == "__main__":
    cleanup_orphans()