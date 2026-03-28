import os
from pathlib import Path

# --- CONFIG ---
SOURCE_DIR = Path.home() / "keep"
TARGET_DIR = Path("/opt/music_videos")

def check_files():
    print(f"--- Checking {SOURCE_DIR} against {TARGET_DIR} ---\n")

    if not SOURCE_DIR.exists():
        print(f"Error: Source directory not found at {SOURCE_DIR}")
        return
    if not TARGET_DIR.exists():
        print(f"Error: Target directory not found at {TARGET_DIR}")
        return

    # Build a fast lookup set of the destination filenames
    target_files = {f.name for f in TARGET_DIR.iterdir() if f.is_file()}

    missing_in_target = []
    already_exist = []

    # Check each file in the source directory
    for f in SOURCE_DIR.iterdir():
        if f.is_file():
            if f.name in target_files:
                already_exist.append(f.name)
            else:
                missing_in_target.append(f.name)

    # Print Results
    if already_exist:
        print(f"✅ FOUND in target ({len(already_exist)} files):")
        # Uncomment the next two lines if you want it to print every found file
        # for name in sorted(already_exist):
        #     print(f"  - {name}")
        
    print(f"\n❌ MISSING in target ({len(missing_in_target)} files):")
    for name in sorted(missing_in_target):
        print(f"  [MISSING] {name}")

    print("\n--- Done ---")

if __name__ == "__main__":
    check_files()