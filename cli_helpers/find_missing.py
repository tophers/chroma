import os
import sqlite3

VIDEO_DIR = "/opt/videos"
DB_PATH = "../chroma.db"

def get_db_info(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        for col in columns:
            if col.lower() in ['filename', 'file_name', 'path', 'filepath']:
                return table, col
    return None, None

def find_the_gap():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    fs_files = set(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(('.mkv', '.mp4', '.avi')))
    
    conn = sqlite3.connect(DB_PATH)
    table, col = get_db_info(conn)
    
    if not table:
        print("Could not automatically find the video table. Tables found:", tables)
        conn.close()
        return

    print(f"Checking table: {table} (Column: {col})")
    cursor = conn.cursor()
    cursor.execute(f"SELECT {col} FROM {table}")
    db_files = set(os.path.basename(row[0]) for row in cursor.fetchall())
    conn.close()

    missing_from_db = fs_files - db_files
    orphans_in_db = db_files - fs_files

    print(f"\n--- Statistics ---")
    print(f"FS Videos: {len(fs_files)}")
    print(f"DB Entries: {len(db_files)}")
    print(f"Gap:        {len(fs_files) - len(db_files)}")
    print(f"------------------\n")

    if missing_from_db:
        print(f"Found {len(missing_from_db)} files in storage but NOT in DB:")
        for f in sorted(missing_from_db):
            print(f" [MISSING] {f}")
    
    if orphans_in_db:
        print(f"\nFound {len(orphans_in_db)} DB entries with NO physical file:")
        for f in sorted(orphans_in_db):
            print(f" [ORPHAN]  {f}")

if __name__ == "__main__":
    find_the_gap()