// /opt/jukebox/static/js/core.js

class ChromaCore extends EventTarget {
    constructor() {
        super();
        this.state = {
            current_video: null,
            queue: [],
            history: [],
            volume: 70,
            is_paused: false,
            time: { current: 0, total: 0 }
        };
    }

    async init() {
        try {
            const initialState = await this.apiRequest("GET", "/api/initial-state");
            this._updateState(initialState);
        } catch (e) {
            console.error("Failed to fetch initial state:", e);
        }
        this.connectWS();
    }

    async apiRequest(method, path, body = null) {
        const opts = { method, headers: {} };
        if (body) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        const res = await fetch(path, opts);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || res.statusText);
        return data;
    }

    connectWS() {
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const ws = new WebSocket(`${proto}//${window.location.host}/ws`);

        ws.onopen = () => this.dispatchEvent(new Event('ws-connected'));
        
        ws.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            if (msg.type === "state_update") this._updateState(msg.payload);
            if (msg.type === "time_update") this._updateTime(msg.payload);
        };

        ws.onclose = () => {
            this.dispatchEvent(new Event('ws-disconnected'));
            setTimeout(() => this.connectWS(), 5000);
        };
    }

    _updateState(newState) {
        this.state = { ...this.state, ...newState };
        this.dispatchEvent(new CustomEvent('state-changed', { detail: this.state }));
    }

    _updateTime(timePayload) {
        this.state.time = timePayload;
        this.dispatchEvent(new CustomEvent('time-changed', { detail: this.state.time }));
    }

    // --- Core Remote Actions ---
    playNext() { return this.apiRequest("POST", "/api/next"); }
    togglePause() { return this.apiRequest("POST", "/api/pause"); }
    stop() { return this.apiRequest("POST", "/api/stop"); }
    seek(time) { return this.apiRequest("POST", "/api/seek", { time }); }
    setVolume(volume) { return this.apiRequest("POST", "/api/volume", { volume }); }
    banCurrent() { return this.apiRequest("POST", "/api/ban"); }
    clearQueue() { return this.apiRequest("POST", "/api/queue/clear"); }

    // --- Queue & Search Actions ---
    search(query) { return this.apiRequest("GET", `/api/search?q=${encodeURIComponent(query)}`); }
    queueAdd(id) { return this.apiRequest("POST", `/api/queue/add/${id}`); }
    queuePlayNext(id) { return this.apiRequest("POST", `/api/queue/play_next/${id}`); }
}

// Export a single, global instance
const chroma = new ChromaCore();