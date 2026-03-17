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
  counts: {
    library: document.getElementById("library-count"),
  },
  views: {
    queue: document.getElementById("queue-view"),
    history: document.getElementById("history-view"),
    library: document.getElementById("library-view"),
    playlists: document.getElementById("playlists-view"),
    banned: document.getElementById("banned-list-view"),
  },
  nav: {
    queue: document.getElementById("nav-queue"),
    history: document.getElementById("nav-history"),
    library: document.getElementById("nav-library"),
    playlists: document.getElementById("nav-playlists"),
    banned: document.getElementById("nav-banned"),
  },
  playlistSelect: document.getElementById("playlist-select")
};

function renderList(container, items, renderFn, emptyMsg = "List is empty.") {
  if (!items || items.length === 0) {
    container.innerHTML = `<div style="padding: 20px; color: #666; text-align: center;">${emptyMsg}</div>`;
    return;
  }
  const html = items.map(renderFn).join("");
  if (container.innerHTML === html) return;
  container.innerHTML = html;
}

function fmtGain(gain) {
  const g = parseFloat(gain) || 0;
  return `${g > 0 ? '+' : ''}${g.toFixed(1)}dB`;
}

function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sc = Math.floor(s % 60);
  return `${m}:${sc < 10 ? '0' : ''}${sc}`;
}

function toast(msg, err = false) {
  DOM.message.textContent = msg;
  DOM.message.style.color = err ? "#ff8a80" : "#fff";
  DOM.message.style.display = "block";
  setTimeout(() => DOM.message.style.display = "none", 3000);
}

function switchView(id) {
  Object.values(DOM.views).forEach(el => el && el.classList.add("hidden"));
  Object.values(DOM.nav).forEach(el => el && el.classList.remove("active"));
  if (DOM.views[id]) DOM.views[id].classList.remove("hidden");
  if (DOM.nav[id]) DOM.nav[id].classList.add("active");
}