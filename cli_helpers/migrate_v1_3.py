import sqlite3
from pathlib import Path

DB_PATH = Path("/opt/jukebox/jukebox.db")

def migrate():
    print(f"--- Starting Migration for v1.3 (Loudness) ---")
    
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("-> Enabling WAL mode...")
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;") 
    new_columns = [
        ("audio_gain",          "REAL DEFAULT 0.0"),
        ("integrated_loudness", "REAL"),
        ("true_peak",           "REAL"),
        ("manual_override",     "INTEGER DEFAULT 0"), # INT for BOOLEAN
        ("analysis_version",    "INTEGER DEFAULT 1")
    ]

    cur.execute("PRAGMA table_info(videos)")
    existing_columns = [row[1] for row in cur.fetchall()]

    for col_name, col_def in new_columns:
        if col_name not in existing_columns:
            print(f"-> Adding column: {col_name}")
            try:
                cur.execute(f"ALTER TABLE videos ADD COLUMN {col_name} {col_def}")
            except Exception as e:
                print(f"   ERROR adding {col_name}: {e}")
        else:
            print(f"-> Column '{col_name}' already exists. Skipping.")

    conn.commit()
    conn.close()
    print("--- Migration Complete. Your playlists are safe. ---")

if __name__ == "__main__":
    migrate()