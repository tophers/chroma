# CHROMA: Raspberry Pi 5 Video Jukebox (v1.4)

CHROMA is a dedicated, headless video appliance designed for the Raspberry Pi 5. It turns the device into a "set-and-forget" video player that outputs directly to a TV or Monitor via HDMI using raw DRM/KMS (no desktop environment required).

The system is designed with a "broadcast" philosophy: **silence is failure.** It ensures a video is always playing by managing a user-selected queue and falling back to a "Weighted Neglect" random shuffle of the local library when the queue is empty.

## Key Features

* **Headless Appliance Architecture:** Runs on Raspberry Pi OS Lite without X11 or Wayland. MPV renders directly to the display hardware.
* **Loudness Normalization (New):** Automatically analyzes library audio to target -14.0 LUFS, ensuring consistent volume across all videos without manual adjustment.
* **Redundant Playback Logic:** Includes a watchdog that detects frozen players, stuck buffers, or stuck end-of-file states to force the next track.
* **Web-Based Dashboard & Touch Remote:** Desktop-optimized control panel for management, plus a new mobile-friendly "Touch Remote" interface.
* **On-Screen Display (OSD):** Pro-style "Now Playing" overlays (Artist - Title) rendered directly on the video output.
* **Weighted Shuffle:** Intelligent randomization that prioritizes videos with lower play counts and older "last played" timestamps.
* **Ban System:** Persistently ban specific tracks from rotation without deleting files.

## System Requirements

* **Hardware:** Raspberry Pi 5 (NVMe boot recommended for indexing speed).
* **Display:** 1080p or 4K TV/Monitor.
* **OS:** Raspberry Pi OS Lite (Bookworm or newer).
* **Media:** Local `.mkv`, `.mp4`, or `.avi` files organized as `Artist - Song.mkv`.

## Architecture

The system consists of two main systemd services located in `/opt/jukebox`:

1.  **mpv-jukebox:** Wraps the MPV media player. It listens on a Unix socket for JSON IPC commands and renders via DRM/KMS.
2.  **jukebox-api:** A Python FastAPI backend managing the SQLite (WAL mode) database, playback logic, and the event-driven "Chroma Core" frontend.

## Installation & Setup

1.  **System Prep:**
    Ensure `/boot/firmware/cmdline.txt` forces the correct video mode:
    `video=HDMI-A-1:1920x1080@60`

2.  **Dependencies:**
    ```bash
    sudo apt install mpv ffmpeg python3-venv sqlite3
    ```

3.  **Setup Environment:**
    ```bash
    cd /opt/jukebox
    python3 -m venv venv
    source venv/bin/activate
    pip install fastapi uvicorn python-mpv-jsonipc
    ```

4.  **Database Migration (v1.3):**
    If upgrading, run the migration script to enable loudness features:
    ```bash
    python3 cli_helpers/migrate_v1_3.py
    ```

## Audio Normalization

CHROMA now performs a two-pass audio analysis:
1.  **Scan:** The `scanner.py` uses `ffmpeg`'s ebur128 filter to measure integrated loudness and true peak.
2.  **Apply:** During playback, a dynamic `af` (audio filter) chain is sent to MPV:
    * **Gain:** Calculated to hit -14.0 LUFS with a "Soft Clamp" to protect transients.
    * **Limiter:** A hard limiter at -1dB prevents clipping.
3.  **Manual Override:** You can manually adjust and "lock" the gain for a specific track via the API/UI.

## Web Interface Controls

Access the dashboard via `http://<pi-ip-address>:8000` or the remote via `http://<pi-ip-address>:8000/touch`.

### Keyboard Shortcuts
* **Space:** Skip to Next.
* **Arrow Up/Down:** Volume +/- 5%.
* **Arrow Left/Right:** Seek +/- 10 seconds.
* **S:** Toggle Hardware/Playback Stats Overlay.

### Management Tools
* **`scanner.py`:** Run this to discover new files and perform audio analysis.
* **`find_missing.py`:** Identifies discrepancies between the filesystem and the database.
* **`fuzzy_search_duplicates.py`:** Uses string similarity to find potential duplicate videos.

## Troubleshooting

**Database is Locked:**
The system now uses SQLite WAL mode. Ensure all scripts are importing `get_db` from `db.py` to maintain consistent PRAGMA settings.

**Audio is too quiet/loud:**
Check if the video has a `manual_override` set in the database. You can force a re-analysis of the library by running `python3 scanner.py` which will fill in missing LUFS data.

## License

MIT License.
