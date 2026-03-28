// /opt/jukebox/static/js/player.js

let isSeeking = false;

function updateState(state) {
  if (state.current_video) {
    DOM.nowPlaying.title.textContent = state.current_video.title;
    DOM.nowPlaying.artist.textContent = state.current_video.artist;
    document.title = `${state.current_video.artist} - ${state.current_video.title}`;
    DOM.controls.ban.disabled = false;
    DOM.seek.slider.disabled = false;
  } else {
    DOM.nowPlaying.title.textContent = "Not Playing";
    DOM.nowPlaying.artist.textContent = "—";
    document.title = "Chroma";
    DOM.controls.ban.disabled = true;
    DOM.seek.slider.disabled = true;
    DOM.seek.slider.value = 0;
  }

  DOM.controls.pause.textContent = state.is_paused ? "▶" : "⏸";

  renderList(DOM.containers.queue, state.queue, vid => `
    <div class="list-item">
      <div class="list-info">
        <div class="li-title">${vid.title}</div>
        <div class="li-sub">${vid.artist}</div>
      </div>
      <div style="display:flex; gap:5px; align-items:center;">
        <button class="btn-small" data-action="edit-gain" data-id="${vid.id}" data-current="${vid.audio_gain || 0}" title="Edit Gain">${fmtGain(vid.audio_gain)}</button>
        <button class="btn-small" data-action="play-next" data-id="${vid.id}">Play Next</button>
        <button class="btn-small" data-action="add-to-playlist" data-id="${vid.id}" title="Add to selected playlist">+</button>
        <span style="display:inline-block; min-width: 24px; text-align: right; font-size: 0.75rem; color: var(--text-sub); opacity: 0.5; font-family: monospace; margin-left: 4px;" title="Play Count">${vid.play_count || 0}</span>
      </div>
    </div>
  `, "Queue is empty.");

  renderList(DOM.containers.history, state.history, vid => {
    let timeStr = "";
    if (vid.played_at) {
        const d = new Date(vid.played_at + "Z");
        if (d.toString() !== "Invalid Date") {
            timeStr = `<span style="font-size: 0.75rem; color: var(--text-sub); margin-left: 8px;">(${d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})})</span>`;
        }
    }

    return `
    <div class="list-item">
      <div class="list-info">
        <div class="li-title">${vid.title}</div>
        <div class="li-sub">${vid.artist} ${timeStr}</div>
      </div>
      <div style="display:flex; gap:5px; align-items:center;">
        <button class="btn-small" data-action="edit-gain" data-id="${vid.id}" data-current="${vid.audio_gain || 0}" title="Edit Gain">${fmtGain(vid.audio_gain)}</button>
        <button class="btn-small" data-action="queue" data-id="${vid.id}">Queue</button>
        <button class="btn-small" data-action="play-next" data-id="${vid.id}">Play Next</button>
        <button class="btn-small" data-action="add-to-playlist" data-id="${vid.id}" title="Add to selected playlist">+</button>
        <button class="btn-small danger" data-action="ban-history" data-id="${vid.id}">Ban</button>
        <span style="display:inline-block; min-width: 24px; text-align: right; font-size: 0.75rem; color: var(--text-sub); opacity: 0.5; font-family: monospace; margin-left: 4px;" title="Play Count">${vid.play_count || 0}</span>
      </div>
    </div>
  `}, "No recent history.");

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