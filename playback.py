from typing import Optional, Dict, Any, List, Callable
from collections import deque
import asyncio
import time
import functools
import random
from datetime import datetime

from db import (
    pick_random_video,
    update_play_stats,
    get_video_by_id,
    mark_video_broken,
    create_playlist,
    get_playlist_items,
    log_playback_history,
    get_recent_history
)

class PlaybackManager:
    def __init__(self, controller, state_update_callback: Callable, loop: asyncio.AbstractEventLoop):
        self.ctrl = controller
        self.state_update_callback = state_update_callback
        self.loop = loop

        self.current: Optional[Dict[str, Any]] = None
        self.queue: List[Dict[str, Any]] = []

        initial_history = get_recent_history(20)
        self.history: deque[Dict[str, Any]] = deque(initial_history, maxlen=20)

        self.volume: int = 70
        self.is_paused: bool = False
        self.skip_in_progress: bool = False
        self.overlay_timer: Optional[asyncio.TimerHandle] = None
        self.last_known_pos: float = -1.0
        self.hang_counter: int = 0
        self.WATCHDOG_HANG_THRESHOLD = 3

    def broadcast_state(self):
        asyncio.run_coroutine_threadsafe(
            self.state_update_callback({
                "type": "state_update",
                "payload": self.get_full_state()
            }),
            self.loop
        )

    def broadcast_time(self, current_time: float, duration: float):
        asyncio.run_coroutine_threadsafe(
            self.state_update_callback({
                "type": "time_update",
                "payload": {"current": current_time, "total": duration}
            }),
            self.loop
        )

    def _clear_overlay(self):
        if self.ctrl:
            self.ctrl.command("osd-overlay", 1, "none", "")
        self.overlay_timer = None

    def _play_video(self, video: Dict[str, Any]):
        if self.current:
            old_video = self.current
            old_video['played_at'] = datetime.utcnow().isoformat()
            self.history.appendleft(old_video)
            self.loop.run_in_executor(None, log_playback_history, old_video['id'])

        print(f"[Playback] Now playing: {video['path']}")

        self.last_known_pos = -1.0
        self.hang_counter = 0
        self.is_paused = False

        db_gain = video.get('audio_gain')
        if db_gain is None:
            db_gain = 0.0

        print(f"[Playback] Applying audio gain: {db_gain:.2f}dB")
        af_chain = (
            f"@chroma_norm:volume=volume={db_gain:.2f}dB,"
            f"alimiter=limit=-1dB:asc=1"
        )
        self.ctrl.command("set_property", "af", af_chain)

        self.ctrl.load_file(video["path"])
        self.ctrl.command("set_property", "pause", False)

        if self.overlay_timer:
            self.overlay_timer.cancel()
            self.overlay_timer = None

        artist = video['artist'].upper().replace("{", "(").replace("}", ")")
        title = video['title'].replace("{", "(").replace("}", ")").replace("\\", "-")

        msg = (
            f"{{\\an1}}{{\\bord2}}{{\\shad1}}"
            f"{{\\fs45}}{{\\1c&HCCCCCC&}}{artist}\\N"
            f"{{\\fs70}}{{\\b1}}{{\\1c&HFFFFFF&}}{title}"
        )

        self.ctrl.command("osd-overlay", 1, "ass-events", msg)
        self.overlay_timer = self.loop.call_later(7.0, self._clear_overlay)

        update_play_stats(video["path"])
        self.current = video
        self.ctrl.set_volume(self.volume)

    def set_gain_live(self, new_gain: float):
        if self.current:
            self.current['audio_gain'] = new_gain
            print(f"[Playback] Live updating gain to {new_gain}dB")

            new_chain = (
                f"@chroma_norm:volume=volume={new_gain:.2f}dB,"
                f"alimiter=limit=-1dB:asc=1"
            )
            self.ctrl.command("set_property", "af", new_chain)

    def _play_next(self) -> Optional[Dict[str, Any]]:
        video_to_play = None
        if self.queue:
            video_to_play = self.queue.pop(0)
            print(f"[Playback] Playing next from queue: {video_to_play['title']}")
        else:
            video_to_play = pick_random_video()
            if video_to_play:
                print(f"[Playback] Playing next random: {video_to_play['title']}")
            else:
                print("[Playback] No videos available.")
                self.current = None

        if video_to_play:
            self._play_video(video_to_play)
        else:
            if self.current:
                self.current['played_at'] = datetime.utcnow().isoformat()
                self.history.appendleft(self.current)
            self.ctrl.stop()
            self.current = None

        return video_to_play

    def skip_to_next(self):
        print("[Playback] Skip requested")
        if self.current:
            self.skip_in_progress = True
        self._play_next()
        self.broadcast_state()

    def auto_next(self):
        print("[Playback] Auto-advance triggered.")
        self._play_next()
        self.broadcast_state()

    def seek(self, time_pos: float):
        if self.current:
            self.ctrl.command("seek", time_pos, "absolute")

    def add_to_queue(self, video_id: int):
        video = get_video_by_id(video_id)
        if not video or video["banned"]:
            return

        self.queue.append(video)
        print(f"[Playback] Queued: {video['title']}")

        if not self.current:
            self.auto_next()
        else:
            self.broadcast_state()
    
    def play_next(self, video_id: int):
        video = get_video_by_id(video_id)
        if not video or video["banned"]:
            return

        self.queue = [v for v in self.queue if v['id'] != video_id]

        self.queue.insert(0, video)
        print(f"[Playback] Play Next queued (moved to top): {video['title']}")

        if not self.current:
            self.auto_next()
        else:
            self.broadcast_state()

    def clear_queue(self):
        self.queue = []
        print("[Playback] Queue cleared by user.")
        self.broadcast_state()

    def load_playlist_into_queue(self, playlist_id: int, shuffle: bool = False, least_played: bool = False):
        items = get_playlist_items(playlist_id)
        if not items:
            print("[Playback] Playlist is empty.")
            return

        if least_played:
            items.sort(key=lambda x: (x.get('play_count', 0), x.get('artist', '')))
            print(f"[Playback] Loading {len(items)} items (LEAST PLAYED) from playlist {playlist_id}")
        elif shuffle:
            random.shuffle(items)
            print(f"[Playback] Loading {len(items)} items (SHUFFLED) from playlist {playlist_id}")
        else:
            print(f"[Playback] Loading {len(items)} items from playlist {playlist_id}")

        self.queue.extend(items)

        if not self.current:
            self.auto_next()
        else:
            self.broadcast_state()

    def save_current_queue_as_playlist(self, name: str):
        ids = []
        if self.current:
            ids.append(self.current["id"])
        for video in self.queue:
            ids.append(video["id"])

        if not ids:
            raise ValueError("Nothing to save")

        create_playlist(name, ids)
        print(f"[Playback] Saved playlist '{name}' with {len(ids)} items.")

    def stop(self):
        if self.current:
            self.current['played_at'] = datetime.utcnow().isoformat()
            self.history.appendleft(self.current)
        self.ctrl.stop()
        self.current = None
        self.queue = []
        self.broadcast_state()

    def pause_toggle(self):
        self.ctrl.pause_toggle()
        self.is_paused = not self.is_paused
        self.broadcast_state()

    def toggle_stats(self):
        self.ctrl.command("keypress", "I")

    def set_volume(self, value: int):
        self.volume = max(0, min(100, value))
        self.ctrl.set_volume(self.volume)
        self.broadcast_state()

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "current_video": self.current,
            "queue": self.queue,
            "history": list(self.history),
            "volume": self.volume,
            "is_paused": self.is_paused
        }

    def handle_mpv_event(self, msg: dict):
        event = msg.get("event")
        if not event: return

        if event == "end-file":
            reason = msg.get("reason") or msg.get("data", {}).get("reason")
            if self.skip_in_progress:
                self.skip_in_progress = False
                return

            if reason == "error" and self.current:
                mark_video_broken(self.current['path'])

            if reason in ("eof", "error"):
                self.auto_next()
            elif reason == "stop":
                self.current = None
                self.broadcast_state()

        elif event == "property-change" and msg.get("name") == "volume":
            new_vol = int(msg.get("data", 70))
            if self.volume != new_vol:
                self.volume = new_vol
                self.broadcast_state()

        elif event == "property-change" and msg.get("name") == "pause":
             is_paused = msg.get("data")
             if is_paused is not None:
                 self.is_paused = is_paused

    def on_mpv_reconnect(self):
        print("[Playback] MPV Reconnected. Resuming...")
        self.skip_to_next()

    async def _get_property_async(self, prop: str):
        call = functools.partial(self.ctrl.get_property, prop, timeout=0.2)
        return await self.loop.run_in_executor(None, call)

    async def housekeeping_tick(self):
        if not self.current or self.skip_in_progress:
            return

        try:
            time_pos = await self._get_property_async("time-pos")
            duration = await self._get_property_async("duration")
            is_paused_mpv = await self._get_property_async("pause")

            if isinstance(time_pos, (int, float)) and isinstance(duration, (int, float)):
                self.broadcast_time(float(time_pos), float(duration))

            if is_paused_mpv is not None:
                self.is_paused = is_paused_mpv

            if not self.is_paused:
                if time_pos == self.last_known_pos:
                    self.hang_counter += 1
                else:
                    self.hang_counter = 0
                    self.last_known_pos = time_pos if time_pos else -1.0
            else:
                if duration and duration > 0 and time_pos:
                    remaining = duration - time_pos
                    if remaining < 1.0:
                        self.skip_to_next()

            if self.hang_counter >= self.WATCHDOG_HANG_THRESHOLD:
                mark_video_broken(self.current['path'])
                self.skip_to_next()

        except Exception as e:
            print(f"[Playback Watchdog] Error: {e}")
