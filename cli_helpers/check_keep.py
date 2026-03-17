import os
from pathlib import Path

SOURCE_DIR = Path.home() / "keep"
TARGET_DIR = Path("/opt/videos")

def check_files():
    print(f"--- Checking {SOURCE_DIR} against {TARGET_DIR} ---\n")

    if not SOURCE_DIR.exists():
        print(f"Error: Source directory not found at {SOURCE_DIR}")
        return
    if not TARGET_DIR.exists():
        print(f"Error: Target directory not found at {TARGET_DIR}")
        return

    target_files = {f.name for f in TARGET_DIR.iterdir() if f.is_file()}

    missing_in_target = []
    already_exist = []

    for f in SOURCE_DIR.iterdir():
        if f.is_file():
            if f.name in target_files:
                already_exist.append(f.name)
            else:
                missing_in_target.append(f.name)

    if already_exist:
        print(f"✅ FOUND in target ({len(already_exist)} files):")
        #     print(f"  - {name}")
        
    print(f"\n❌ MISSING in target ({len(missing_in_target)} files):")
    for name in sorted(missing_in_target):
        print(f"  [MISSING] {name}")

    print("\n--- Done ---")

if __name__ == "__main__":
    check_files()