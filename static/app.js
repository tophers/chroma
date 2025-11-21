// /opt/jukebox/static/app.js

const DOM = {
  status: document.getElementById("status-indicator"),
  message: document.getElementById("message"),
  nowPlaying: {
    title: document.getElementById("now-playing-title"),
    artist: document.getElementById("now-playing-artist"),
  },
  seek: {
    slider: document.getElementById("seek-slider"),
    current: document.getElementById("time-current"),
    total: document.getElementById("time-total"),
  },
  controls: {
    pause: document.getElementById("btn-pause"),
    ban: document.getElementById("btn-ban"),
    volume: document.getElementById("volume-slider"),
  },
  containers: {
    queue: document.getElementById("queue-container"),
    history: document.getElementById("history-container"),
    library: document.getElementById("library-container"),
    playlists: document.getElementById("playlists-container"),
    banned: document.getElementById("banned-container"),
  },
  views: {
    home: document.getElementById("home-view"),
    library: document.getElementById("library-view"),
    playlists: document.getElementById("playlists-view"),
    banned: document.getElementById("banned-list-view"),
  },
  nav: {
    home: document.getElementById("nav-home"),
    library: document.getElementById("nav-library"),
    playlists: document.getElementById("nav-playlists"),
    banned: document.getElementById("nav-banned"),
  }
};

let isSeeking = false;
let volumeTimeout;

// Smart Render (Prevents Scroll Jumping)
function renderList(container, items, renderFn, emptyMsg = "List is empty.") {
  if (!items || items.length === 0) {
    container.innerHTML = `<div style="padding: 20px; color: #666; text-align: center;">${emptyMsg}</div>`;
    return;
  }

  // Generate HTML
  const html = items.map(renderFn).join("");

  // If HTML hasn't changed, don't touch DOM
  if (container.innerHTML === html) return;

  container.innerHTML = html;
}

// API & WebSocket
async function apiRequest(method, path, body = null) {
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

function connectWS() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${window.location.host}/ws`);

  ws.onopen = async () => {
    DOM.status.classList.add("connected");
    DOM.status.classList.remove("error");
    const state = await apiRequest("GET", "/api/initial-state");
    updateState(state);
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "state_update") updateState(msg.payload);
    if (msg.type === "time_update") updateTime(msg.payload);
  };

  ws.onclose = () => {
    DOM.status.classList.remove("connected");
    DOM.status.classList.add("error");
    setTimeout(connectWS, 5000);
  };
}

// UI Updates
function updateState(state) {
  // Now Playing & Tab Title
  if (state.current_video) {
    DOM.nowPlaying.title.textContent = state.current_video.title;
    DOM.nowPlaying.artist.textContent = state.current_video.artist;
    document.title = `${state.current_video.artist} - ${state.current_video.title}`;
    
    DOM.controls.ban.disabled = false;
    DOM.seek.slider.disabled = false;
  } else {
    DOM.nowPlaying.title.textContent = "Not Playing";
    DOM.nowPlaying.artist.textContent = "—";
    document.title = "Chroma"; // Default fallback name

    DOM.controls.ban.disabled = true;
    DOM.seek.slider.disabled = true;
    DOM.seek.slider.value = 0;
  }

  // Play/Pause Button State
  DOM.controls.pause.textContent = state.is_paused ? "▶" : "⏸";

  // Queue
  renderList(DOM.containers.queue, state.queue, vid => `
    <div class="list-item">
      <div class="list-info">
        <div class="li-title">${vid.title}</div>
        <div class="li-sub">${vid.artist}</div>
      </div>
    </div>
  `, "Queue is empty.");

  // History
  renderList(DOM.containers.history, state.history, vid => `
    <div class="list-item">
      <div class="list-info">
        <div class="li-title">${vid.title}</div>
        <div class="li-sub">${vid.artist}</div>
      </div>
      <button class="btn-small" data-action="queue" data-id="${vid.id}">Queue</button>
    </div>
  `, "No recent history.");

  // Volume (only update if not dragging)
  if (document.activeElement !== DOM.controls.volume) {
    DOM.controls.volume.value = state.volume;
  }
}

function updateTime(payload) {
  if (isSeeking) return;
  DOM.seek.slider.max = payload.total;
  DOM.seek.slider.value = payload.current;
  DOM.seek.current.textContent = fmtTime(payload.current);
  DOM.seek.total.textContent = fmtTime(payload.total);
}

function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sc = Math.floor(s % 60);
  return `${m}:${sc < 10 ? '0' : ''}${sc}`;
}

// Keyboard Helpers

function adjustVolume(delta) {
  let val = parseInt(DOM.controls.volume.value) + delta;
  val = Math.max(0, Math.min(100, val));
  DOM.controls.volume.value = val;
  
  toast(`Volume: ${val}%`);

  clearTimeout(volumeTimeout);
  volumeTimeout = setTimeout(() => {
    apiRequest("POST", "/api/volume", { volume: val });
  }, 100);
}

function seekRelative(delta) {
  // Use slider value as proxy for current time
  const current = parseFloat(DOM.seek.slider.value);
  const max = parseFloat(DOM.seek.slider.max) || 0;
  let target = current + delta;
  
  if (target < 0) target = 0;
  if (target > max) target = max;

  apiRequest("POST", "/api/seek", { time: target });
  const sign = delta > 0 ? "+" : "";
  toast(`Seek ${sign}${delta}s`);
}

// Interactions
function toast(msg, err = false) {
  DOM.message.textContent = msg;
  DOM.message.style.color = err ? "#ff8a80" : "#fff";
  DOM.message.style.display = "block";
  setTimeout(() => DOM.message.style.display = "none", 3000);
}

function switchView(id) {
  Object.values(DOM.views).forEach(el => el.classList.add("hidden"));
  Object.values(DOM.nav).forEach(el => el.classList.remove("active"));

  DOM.views[id].classList.remove("hidden");
  if(DOM.nav[id]) DOM.nav[id].classList.add("active");
}

async function handleAction(action, id) {
  try {
    if (action === "queue") {
      await apiRequest("POST", `/api/queue/add/${id}`);
      toast("Added to queue");
    } else if (action === "unban") {
      await apiRequest("POST", `/api/unban/${id}`);
      toast("Unbanned");
      document.getElementById("nav-banned").click(); // Refresh list
    } else if (action === "play_playlist") {
       await apiRequest("POST", `/api/playlists/${id}/load`);
       toast("Playlist queued");
    } else if (action === "delete_playlist") {
       if(confirm("Delete playlist?")) {
         await apiRequest("DELETE", `/api/playlists/${id}`);
         document.getElementById("nav-playlists").click();
       }
    }
  } catch (e) {
    toast(e.message, true);
  }
}

// Init
document.addEventListener("DOMContentLoaded", () => {
  connectWS();

  // Controls
  document.getElementById("btn-next").onclick = () => apiRequest("POST", "/api/next");
  document.getElementById("btn-pause").onclick = () => apiRequest("POST", "/api/pause");
  document.getElementById("btn-stop").onclick = () => apiRequest("POST", "/api/stop");
  document.getElementById("btn-ban").onclick = () => apiRequest("POST", "/api/ban");
  document.getElementById("btn-stats").onclick = () => apiRequest("POST", "/api/stats");

  document.getElementById("btn-save-queue").onclick = async () => {
    const name = prompt("Playlist Name:");
    if(name) {
      try { await apiRequest("POST", "/api/playlists/create", {name}); toast("Saved!"); }
      catch(e) { toast(e.message, true); }
    }
  };

  // Navigation
  DOM.nav.home.onclick = (e) => { e.preventDefault(); switchView("home"); };

  DOM.nav.library.onclick = async (e) => {
    e.preventDefault();
    switchView("library");
    DOM.containers.library.innerHTML = "Loading...";
    const data = await apiRequest("GET", "/api/videos");
    renderList(DOM.containers.library, data.videos, v => `
       <div class="list-item">
         <div class="list-info"><div class="li-title">${v.title}</div><div class="li-sub">${v.artist}</div></div>
         <button class="btn-small" data-action="queue" data-id="${v.id}">Queue</button>
       </div>
    `);
  };

  DOM.nav.playlists.onclick = async (e) => {
    e.preventDefault();
    switchView("playlists");
    const data = await apiRequest("GET", "/api/playlists");
    renderList(DOM.containers.playlists, data.playlists, p => `
      <div class="list-item">
        <div class="list-info"><div class="li-title">${p.name}</div></div>
        <div style="display:flex; gap:5px;">
          <button class="btn-small" data-action="play_playlist" data-id="${p.id}">Load</button>
          <button class="btn-small" style="border-color:#b71c1c; color:#ff8a80;" data-action="delete_playlist" data-id="${p.id}">Del</button>
        </div>
      </div>
    `, "No playlists.");
  };

  DOM.nav.banned.onclick = async (e) => {
    e.preventDefault();
    switchView("banned");
    const data = await apiRequest("GET", "/api/banned");
    renderList(DOM.containers.banned, data.banned, v => `
      <div class="list-item">
        <div class="list-info"><div class="li-title">${v.title}</div><div class="li-sub">${v.artist}</div></div>
        <button class="btn-small" data-action="unban" data-id="${v.id}">Unban</button>
      </div>
    `, "No banned videos.");
  };

  // Search
  const doSearch = async () => {
    const q = document.getElementById("search-input").value;
    if(q.length < 2) return;
    DOM.containers.library.innerHTML = "Searching...";
    const data = await apiRequest("GET", `/api/search?q=${encodeURIComponent(q)}`);
    renderList(DOM.containers.library, data.videos, v => `
       <div class="list-item">
         <div class="list-info"><div class="li-title">${v.title}</div><div class="li-sub">${v.artist}</div></div>
         <button class="btn-small" data-action="queue" data-id="${v.id}">Queue</button>
       </div>
    `, "No results.");
  };
  document.getElementById("search-btn").onclick = doSearch;
  document.getElementById("search-input").onkeyup = (e) => e.key === "Enter" && doSearch();

  // Seek & Volume
  DOM.seek.slider.onmousedown = () => isSeeking = true;
  DOM.seek.slider.onchange = (e) => {
    isSeeking = false;
    apiRequest("POST", "/api/seek", { time: parseFloat(e.target.value) });
  };
  DOM.controls.volume.oninput = (e) => {
    clearTimeout(volumeTimeout);
    volumeTimeout = setTimeout(() => {
      apiRequest("POST", "/api/volume", { volume: parseInt(e.target.value) });
    }, 100);
  };

  // Delegated Actions
  document.body.onclick = (e) => {
    const btn = e.target.closest("[data-action]");
    if(btn) handleAction(btn.dataset.action, btn.dataset.id);
  };

  // Keyboard Shortcuts
  document.addEventListener("keydown", (e) => {
    // Ignore input if typing in a text field
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    switch (e.code) {
      case "Space":
        e.preventDefault(); // Prevent scrolling
        apiRequest("POST", "/api/next");
        toast("Skipping...");
        break;

      case "ArrowUp":
        e.preventDefault();
        adjustVolume(5);
        break;

      case "ArrowDown":
        e.preventDefault();
        adjustVolume(-5);
        break;

      case "ArrowRight":
        e.preventDefault();
        seekRelative(10);
        break;

      case "ArrowLeft":
        e.preventDefault();
        seekRelative(-10);
        break;

      case "KeyS":
        apiRequest("POST", "/api/stats");
        break;
    }
  });

});
