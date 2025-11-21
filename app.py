# /opt/jukebox/app.py

import asyncio
from pathlib import Path
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mpv_controller import MPVController
from db import (
    init_schema,
    db_exists,
    set_banned_by_path,
    set_banned_by_id,
    list_banned_videos,
    get_all_videos,
    search_videos,
    get_playlists,
    delete_playlist
)
from scanner import scan_library
from playback import PlaybackManager

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()
ctrl: MPVController | None = None
playback: PlaybackManager | None = None
loop: asyncio.AbstractEventLoop | None = None

# --- Background Task ---

async def housekeeping_loop(playback_manager: PlaybackManager):
    print("[Housekeeping] Loop started.")
    while True:
        await asyncio.sleep(1)
        if playback_manager:
            await playback_manager.housekeeping_tick()

# --- Startup ---

@app.on_event("startup")
async def startup_event():
    global ctrl, playback, loop
    loop = asyncio.get_running_loop()

    print("[Startup] Checking database...")
    if not db_exists():
        print("[Startup] DB missing. Initializing schema and scanning...")
        init_schema()
        await asyncio.to_thread(scan_library)
    else:
        print("[Startup] DB exists. Skipping auto-scan.")

    # Init Playback
    playback = PlaybackManager(None, state_update_callback=manager.broadcast, loop=loop)

    print("[Startup] Connecting to MPV...")
    ctrl = MPVController(on_reconnect=playback.on_mpv_reconnect)

    # Link the controller to the playback manager
    playback.ctrl = ctrl

    # Register the event listener
    ctrl.on_event(playback.handle_mpv_event)

    ctrl.connect()

    # Start Housekeeping
    loop.create_task(housekeeping_loop(playback))

    # Give MPV a sec then start
    await asyncio.sleep(1)
    playback.auto_next()

# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# --- UI ---

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- API Models ---

class VolumeReq(BaseModel):
    volume: int

class SeekReq(BaseModel):
    time: float

class CreatePlaylistReq(BaseModel):
    name: str

# --- API Endpoints (Threadpool) ---

@app.get("/api/initial-state")
def api_initial_state():
    if not playback: return {}
    return playback.get_full_state()

@app.post("/api/library/scan")
def api_scan():
    scan_library()
    return {"ok": True}

@app.get("/api/videos")
def api_get_videos():
    return {"videos": get_all_videos()}

@app.get("/api/search")
def api_search_videos(q: str):
    if not q or len(q) < 2: return {"videos": []}
    return {"videos": search_videos(q)}

@app.post("/api/queue/add/{video_id}")
def api_queue_add(video_id: int):
    if playback: playback.add_to_queue(video_id)
    return {"ok": True}

@app.post("/api/volume")
def api_set_volume(data: VolumeReq):
    if playback: playback.set_volume(data.volume)
    return {"ok": True}

@app.post("/api/seek")
def api_seek(data: SeekReq):
    if playback: playback.seek(data.time)
    return {"ok": True}

@app.post("/api/next")
def api_next():
    if playback: playback.skip_to_next()
    return {"ok": True}

@app.post("/api/pause")
def api_pause():
    if playback: playback.pause_toggle()
    return {"ok": True}

@app.post("/api/stop")
def api_stop():
    if playback: playback.stop()
    return {"ok": True}

@app.post("/api/stats")
def api_stats():
    if playback: playback.toggle_stats()
    return {"ok": True}

@app.post("/api/ban")
def api_ban():
    if playback and playback.current:
        path = playback.current["path"]
        set_banned_by_path(path, True)
        playback.skip_to_next()
    return {"ok": True}

@app.get("/api/banned")
def api_banned():
    return {"banned": list_banned_videos()}

@app.post("/api/unban/{video_id}")
def api_unban_by_id(video_id: int):
    set_banned_by_id(video_id, False)
    return {"ok": True}

# --- Playlist API ---

@app.get("/api/playlists")
def api_list_playlists():
    return {"playlists": get_playlists()}

@app.post("/api/playlists/create")
def api_create_playlist(req: CreatePlaylistReq):
    if not playback: raise HTTPException(503, "Not initialized")
    try:
        playback.save_current_queue_as_playlist(req.name)
        return {"ok": True}
    except ValueError:
        raise HTTPException(400, "Queue is empty")

@app.post("/api/playlists/{pid}/load")
def api_load_playlist(pid: int):
    if playback: playback.load_playlist_into_queue(pid)
    return {"ok": True}

@app.delete("/api/playlists/{pid}")
def api_delete_playlist(pid: int):
    delete_playlist(pid)
    return {"ok": True}
