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
    refreshPlaylistSelect();
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