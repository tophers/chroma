import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mpv_controller import MPVController
from db import (
    init_schema, db_exists, set_banned_by_path, set_banned_by_id,
    list_banned_videos, get_all_videos, search_videos,
    get_playlists, delete_playlist, add_to_playlist,
    remove_from_playlist, get_playlist_items, set_manual_gain
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

async def housekeeping_loop(playback_manager: PlaybackManager):
    print("[Housekeeping] Loop started.")
    while True:
        await asyncio.sleep(1)
        if playback_manager:
            await playback_manager.housekeeping_tick()

@app.on_event("startup")
async def startup_event():
    global ctrl, playback, loop
    loop = asyncio.get_running_loop()
    if not db_exists():
        init_schema()
        await asyncio.to_thread(scan_library)
    else:
        init_schema()
    playback = PlaybackManager(None, state_update_callback=manager.broadcast, loop=loop)
    ctrl = MPVController(on_reconnect=playback.on_mpv_reconnect)
    playback.ctrl = ctrl
    ctrl.on_event(playback.handle_mpv_event)
    ctrl.connect()
    loop.create_task(housekeeping_loop(playback))
    await asyncio.sleep(1)
    playback.auto_next()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class VolumeReq(BaseModel):
    volume: int
class SeekReq(BaseModel):
    time: float
class CreatePlaylistReq(BaseModel):
    name: str
class PlaylistItemReq(BaseModel):
    video_id: int
class GainReq(BaseModel):
    gain: float

@app.get("/api/initial-state")
def api_initial_state():
    if not playback: return {}
    return playback.get_full_state()

@app.get("/api/current")

def api_current():
    current = playback.current if playback else None
    paused = playback.is_paused if playback else False

    return {
        "has_media": current is not None,
        "is_paused": paused,
        "is_playing": current is not None and not paused,
        "id": current.get("id") if current else None,
        "title": current.get("title") if current else None,
        "artist": current.get("artist") if current else None,
        "path": current.get("path") if current else None,
    }

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

@app.post("/api/queue/play_next/{video_id}")
def api_queue_play_next(video_id: int):
    if playback: playback.play_next(video_id)
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
def api_ban_current():
    if playback and playback.current:
        set_banned_by_path(playback.current["path"], True)
        playback.skip_to_next()
    return {"ok": True}

@app.post("/api/ban/{video_id}")
def api_ban_by_id(video_id: int):
    set_banned_by_id(video_id, True)
    if playback and playback.current and playback.current['id'] == video_id:
        playback.skip_to_next()
    return {"ok": True}

@app.get("/api/banned")
def api_banned():
    return {"banned": list_banned_videos()}

@app.post("/api/unban/{video_id}")
def api_unban_by_id(video_id: int):
    set_banned_by_id(video_id, False)
    return {"ok": True}

@app.post("/api/videos/{video_id}/gain")
def api_set_video_gain(video_id: int, req: GainReq):
    set_manual_gain(video_id, req.gain)
    if playback and playback.current and playback.current.get('id') == video_id:
        playback.set_gain_live(req.gain)
        
    return {"ok": True}

@app.get("/api/playlists")
def api_list_playlists():
    playlists = get_playlists()
    for p in playlists:
        p['items'] = get_playlist_items(p['id'])
    return {"playlists": playlists}

@app.post("/api/playlists/create")
def api_create_playlist(req: CreatePlaylistReq):
    if not playback: raise HTTPException(503, "Not initialized")
    try:
        playback.save_current_queue_as_playlist(req.name)
        return {"ok": True}
    except ValueError:
        raise HTTPException(400, "Queue is empty")

@app.post("/api/playlists/{pid}/load")
def api_load_playlist(pid: int, shuffle: bool = False, least_played: bool = False):
    if playback: playback.load_playlist_into_queue(pid, shuffle=shuffle, least_played=least_played)
    return {"ok": True}

@app.delete("/api/playlists/{pid}")
def api_delete_playlist(pid: int):
    delete_playlist(pid)
    return {"ok": True}

@app.post("/api/playlists/{pid}/add")
def api_playlist_add_item(pid: int, req: PlaylistItemReq):
    added = add_to_playlist(pid, req.video_id)
    return {"ok": True, "added": added}

@app.post("/api/queue/clear")
def api_clear_queue():
    if playback:
        playback.clear_queue()
    return {"ok": True}

@app.post("/api/playlists/{pid}/remove")
def api_playlist_remove_item(pid: int, req: PlaylistItemReq):
    remove_from_playlist(pid, req.video_id)
    return {"ok": True}
