import difflib
from pathlib import Path

VIDEO_DIR = Path("/opt/videos")
MATCH_THRESHOLD = 0.85  # 85% similarity threshold

def find_fuzzy_duplicates():
    print(f"--- Starting Fuzzy Duplicate Scan ---")
    if not VIDEO_DIR.exists():
        print(f"Error: Directory not found at {VIDEO_DIR}")
        return

    extensions = {'.mkv', '.mp4', '.avi'}
    files = [f for f in VIDEO_DIR.iterdir() if f.is_file() and f.suffix.lower() in extensions]
    
    file_map = {f.stem.lower(): f.name for f in files}
    stems = list(file_map.keys())
    
    print(f"Found {len(stems)} videos. Comparing filenames (this might take a moment)...\n")
    
    found_dupes = set()
    
    for i, stem1 in enumerate(stems):
        for j in range(i + 1, len(stems)):
            stem2 = stems[j]
            
            if abs(len(stem1) - len(stem2)) > 10:
                continue
                
            ratio = difflib.SequenceMatcher(None, stem1, stem2).ratio()
            
            if ratio >= MATCH_THRESHOLD:
                match_pair = tuple(sorted([file_map[stem1], file_map[stem2]]))
                
                if match_pair not in found_dupes:
                    found_dupes.add(match_pair)
                    print(f"[Match {ratio*100:.1f}%]")
                    print(f"  1. {match_pair[0]}")
                    print(f"  2. {match_pair[1]}\n")

    if not found_dupes:
        print("No fuzzy duplicates found! Your library is clean.")
    else:
        print(f"Total potential duplicate pairs found: {len(found_dupes)}")
    print("--- Scan Complete ---")

if __name__ == "__main__":
    find_fuzzy_duplicates()