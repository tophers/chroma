import json
import socket
import threading
import time
from typing import Callable, List, Optional, Any

class PendingRequest:
    def __init__(self):
        self.event = threading.Event()
        self.response_data: Any = None
        self.error: Optional[str] = None

class MPVController:

    def __init__(
        self,
        socket_path="/tmp/mpv-music.sock",
        on_reconnect: Optional[Callable] = None,
    ):
        self.socket_path = socket_path
        self.sock: Optional[socket.socket] = None
        self.listeners: List[Callable] = []
        self.on_reconnect_callback = on_reconnect

        self._main_thread = None
        self._is_running = threading.Event()
        self._is_first_connect = True

        self._request_id_counter = 0
        self._lock = threading.Lock()
        self._pending_requests: dict[int, PendingRequest] = {}

    def connect(self):
        if self._main_thread is not None and self._main_thread.is_alive():
            return

        print("[MPV] Starting controller thread.")
        self._is_running.set()
        self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._main_thread.start()

    def _main_loop(self):
        while self._is_running.is_set():
            if self.sock is None:
                self._connect_internal()

            if self.sock:
                self._listen_for_events()

            print("[MPV] Disconnected. Will attempt to reconnect...")
            self.sock = None
            time.sleep(2)

    def _connect_internal(self):
        print("[MPV] Attempting to connect to socket...")
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(self.socket_path)
            print("[MPV] Connected successfully.")
            self.observe_property("volume")
            self.observe_property("pause") 

            if self.on_reconnect_callback:
                if not self._is_first_connect:
                    print("[MPV] Triggering on-reconnect callback.")
                    self.on_reconnect_callback()
                else:
                    self._is_first_connect = False

        except (FileNotFoundError, ConnectionRefusedError):
            if self.sock:
                self.sock.close()
            self.sock = None
        except Exception as e:
            print(f"[MPV] Unexpected error during connection: {e}")
            if self.sock:
                self.sock.close()
            self.sock = None

    def _listen_for_events(self):
        if not self.sock:
            return

        buf = b""
        while self._is_running.is_set():
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    print("[MPV] Socket received empty data, closing connection.")
                    break
            except (OSError, socket.timeout) as e:
                print(f"[MPV] Socket error: {e}. Connection lost.")
                break

            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                    self._dispatch_message(msg)
                except json.JSONDecodeError:
                    continue

        if self.sock:
            self.sock.close()


    def _dispatch_message(self, msg: dict):
        request_id = msg.get("request_id")

        if request_id and request_id in self._pending_requests:
            pending = self._pending_requests[request_id]
            if msg.get("error") != "success":
                pending.error = msg.get("error", "Unknown error")
            else:
                pending.response_data = msg.get("data")
            pending.event.set()
            return

        for fn in list(self.listeners):
            try:
                fn(msg)
            except Exception as e:
                print(f"[MPV] Error in event listener: {e}")

    def on_event(self, callback: Callable):
        self.listeners.append(callback)

    def command(self, *args) -> Optional[int]:
        if not self.sock:
            return None

        with self._lock:
            self._request_id_counter += 1
            request_id = self._request_id_counter
            payload = {"command": list(args), "request_id": request_id}
            data = (json.dumps(payload) + "\n").encode("utf-8")

            try:
                self.sock.sendall(data)
                return request_id
            except OSError as e:
                print(f"[MPV] Failed to send command: {e}")
                return None

    def get_property(self, prop_name: str, timeout: float = 2.0) -> Any:
        pending = PendingRequest()

        with self._lock:
            self._request_id_counter += 1
            request_id = self._request_id_counter
            self._pending_requests[request_id] = pending
            payload = {"command": ["get_property", prop_name], "request_id": request_id}
            data = (json.dumps(payload) + "\n").encode("utf-8")
            
            if not self.sock:
                del self._pending_requests[request_id]
                return None

            try:
                self.sock.sendall(data)
            except OSError:
                del self._pending_requests[request_id]
                return None

        event_was_set = pending.event.wait(timeout)

        if request_id in self._pending_requests:
            del self._pending_requests[request_id]

        if not event_was_set or pending.error:
            return None

        return pending.response_data

    def load_file(self, path: str):
        self.command("loadfile", path, "replace")

    def pause_toggle(self):
        self.command("cycle", "pause")

    def stop(self):
        self.command("stop")

    def set_volume(self, value: int):
        self.command("set_property", "volume", max(0, min(100, value)))

    def observe_property(self, prop_name: str):
        self.command("observe_property", 1, prop_name)
