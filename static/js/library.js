// /opt/jukebox/static/library.js

let currentVideoData = [];

function applySortAndRender() {
    const sortSelect = document.getElementById("sort-select");
    const sortVal = sortSelect ? sortSelect.value : "artist-asc";

    currentVideoData.sort((a, b) => {
        if (sortVal === "artist-asc") return a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title);
        if (sortVal === "title-asc") return a.title.localeCompare(b.title) || a.artist.localeCompare(b.artist);
        if (sortVal === "plays-desc") return (b.play_count || 0) - (a.play_count || 0) || a.artist.localeCompare(b.artist);
        if (sortVal === "plays-asc") return (a.play_count || 0) - (b.play_count || 0) || a.artist.localeCompare(b.artist);
        return 0;
    });

    DOM.counts.library.textContent = `(${currentVideoData.length})`;

    renderList(DOM.containers.library, currentVideoData, v => `
        <div class="list-item">
          <div class="list-info">
            <div class="li-title">${v.title}</div>
            <div class="li-sub">${v.artist}</div>
          </div>
          <div style="display:flex; gap:5px; align-items:center;">
            <button class="btn-small" data-action="edit-gain" data-id="${v.id}" data-current="${v.audio_gain || 0}" title="Edit Gain">${fmtGain(v.audio_gain)}</button>
            <button class="btn-small" data-action="queue" data-id="${v.id}">Queue</button>
            <button class="btn-small" data-action="play-next" data-id="${v.id}">Play Next</button>
            <button class="btn-small" data-action="add-to-playlist" data-id="${v.id}" title="Add to selected playlist">+</button>
            <span style="display:inline-block; min-width: 24px; text-align: right; font-size: 0.75rem; color: var(--text-sub); opacity: 0.5; font-family: monospace; margin-left: 4px;" title="Play Count">${v.play_count || 0}</span>
          </div>
        </div>
    `, "No results.");
}

async function doSearch() {
    const q = document.getElementById("search-input").value.trim();
    if(q.length < 2) return;

    DOM.containers.library.innerHTML = "Searching...";
    const data = await apiRequest("GET", `/api/search?q=${encodeURIComponent(q)}`);

    currentVideoData = data.videos || [];
    applySortAndRender();
}