# CHROMA: Raspberry Pi 5 Video Jukebox

CHROMA is a dedicated, headless video appliance designed for the Raspberry Pi 5. It turns the device into a "set-and-forget" video player that outputs directly to a TV or Monitor via HDMI using raw DRM/KMS (no desktop environment required).

The system is designed with a "broadcast" philosophy: silence is failure. It will always try to ensure a video is playing, managing a queue of user-selected tracks and falling back to a random shuffle of the local library when the queue is empty.

## Key Features

*   **Headless Appliance Architecture:** Runs on Raspberry Pi OS Lite without X11 or Wayland. MPV renders directly to the display hardware.
*   **Redundant Playback Logic:** Includes a watchdog that detects frozen players, stuck buffers, or paused states at the end of files to force the next track.
*   **Web-Based Dashboard:** A desktop-optimized control panel for managing the queue, searching the library, and creating playlists.
*   **On-Screen Display (OSD):** Pro-style "Now Playing" overlays (Artist - Title) rendered directly on the video output.
*   **Ban System:** Persistently ban specific tracks from random rotation without deleting the files.
*   **Hardware Stats:** One-click overlay of dropped frames, CPU usage, and decoder health.

## System Requirements

*   **Hardware:** Raspberry Pi 5 (NVMe boot recommended for indexing speed).
*   **Display:** 1080p or 4K TV/Monitor.
*   **OS:** Raspberry Pi OS Lite (Bookworm or newer).
*   **Media:** Local .mkv files organized as `Artist - Title.mkv`.

## Architecture

The system consists of two main systemd services:

1.  **mpv-jukebox:** Wraps the MPV media player in a specialized shell. It listens on a Unix socket for JSON IPC commands. It forces specific video modes (1080p60) to prevent HDMI handshake judder on 4K TVs.
2.  **jukebox-api:** A Python FastAPI backend that manages the SQLite database, playback logic, playlist management, and serves the frontend.

## Installation

1.  **System Prep:**
    Ensure `/boot/firmware/cmdline.txt` forces the correct video mode to prevent 30Hz fallback on 4K screens:
    `video=HDMI-A-1:1920x1080@60`

2.  **Dependencies:**
    ```bash
    sudo apt install mpv python3-venv
    ```

3.  **Setup Environment:**
    ```bash
    cd /opt/jukebox
    python3 -m venv venv
    source venv/bin/activate
    pip install fastapi uvicorn python-mpv-jsonipc
    ```

4.  **Install Services:**
    Copy the unit files from `./skeleton/` to `/etc/systemd/system/`, reload the daemon, and enable them.

## Web Interface Controls

Access the dashboard via `http://<pi-ip-address>:8000`.

### Keyboard Shortcuts
When the web interface is focused, the following shortcuts act as a remote control:

*   **Space:** Skip to Next (Intentionally not Play/Pause to encourage flow).
*   **Arrow Up/Down:** Volume +/- 5%.
*   **Arrow Left/Right:** Seek +/- 10 seconds.
*   **S:** Toggle Hardware Stats Overlay.

### Playlist Management
*   **Queue:** Drag and drop is not currently supported; use the "Queue" button in the library.
*   **Save Queue:** Converts the current play queue into a saved playlist.
*   **Ban:** Immediately skips the current song and marks it as banned in the database. It will not play again in random shuffle.

## Troubleshooting

**Video is choppy / Dropped frames:**
Check the "Stats" overlay (Press 'S'). If the display FPS matches the video FPS (usually 23.976 or 24), the TV might be in 30Hz mode. Ensure the kernel command line argument `video=HDMI-A-1:1920x1080@60` is applied.

**Player hangs at the end of a song:**
This is handled by the internal Watchdog. MPV is configured with `--keep-open=yes` to prevent the screen from flashing black between videos. The backend monitors the time-position; if the video is paused within 1.0 seconds of the end, it forces a skip.

## License

MIT License.