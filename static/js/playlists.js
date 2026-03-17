let currentPlaylistData = [];

async function refreshPlaylistSelect() {
    if(!DOM.playlistSelect) return;
    try {
        const data = await apiRequest("GET", "/api/playlists");
        const current = DOM.playlistSelect.value;

        const placeholder = `<option value="" disabled selected>Select Playlist...</option>`;
        const createNewOpt = `<option value="create_new">Create New (From Queue)</option>`;
        const opts = data.playlists.map(p => `<option value="${p.id}">${p.name}</option>`).join("");

        DOM.playlistSelect.innerHTML = placeholder + createNewOpt + opts;
        DOM.playlistSelect.style.display = "inline-block";

        if(current && current !== "create_new" && data.playlists.find(p => p.id == current)) {
            DOM.playlistSelect.value = current;
            document.getElementById("sidebar-playlist-actions").style.display = "flex";
        } else {
            DOM.playlistSelect.value = "";
            document.getElementById("sidebar-playlist-actions").style.display = "none";
        }
    } catch(e) {}
}

function renderPlaylists() {
    const sortVal = document.getElementById("playlist-sort-select")?.value || "default";

    const playlistsToRender = currentPlaylistData.map(p => {
        const sortedItems = [...p.items].sort((a, b) => {
            if (sortVal === "artist-asc") return a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title);
            if (sortVal === "title-asc") return a.title.localeCompare(b.title) || a.artist.localeCompare(b.artist);
            if (sortVal === "plays-desc") return (b.play_count || 0) - (a.play_count || 0) || a.artist.localeCompare(b.artist);
            if (sortVal === "plays-asc") return (a.play_count || 0) - (b.play_count || 0) || a.artist.localeCompare(b.artist);
            return 0;
        });
        return { ...p, items: sortedItems };
    });

    renderList(DOM.containers.playlists, playlistsToRender, p => {
        const itemsHtml = p.items.map(v => `
            <div class="list-item" style="padding-left: 20px; font-size: 0.9em; border-bottom: none;">
               <div class="list-info"><div class="li-title">${v.title}</div>
               <div class="li-sub">${v.artist}</div></div>
               <div style="display:flex; gap:5px; align-items:center;">
                 <button class="btn-small" style="padding: 2px 8px;" data-action="edit-gain" data-id="${v.id}" data-current="${v.audio_gain || 0}" title="Edit Gain">${fmtGain(v.audio_gain)}</button>
                 <button class="btn-small" style="padding: 2px 8px;" data-action="add-to-playlist" data-id="${v.id}" title="Add to selected playlist">+</button>
                 <button class="btn-small danger" style="padding: 2px 8px;" data-action="remove_playlist_item" data-id="${p.id}-${v.id}">x</button>
                 <span style="display:inline-block; min-width: 24px; text-align: right; font-size: 0.75rem; color: var(--text-sub); opacity: 0.5; font-family: monospace; margin-left: 4px;" title="Play Count">${v.play_count || 0}</span>
               </div>
            </div>
        `).join("");

        return `
      <div style="border-bottom: 1px solid var(--border-subtle); margin-bottom: 5px;">
          <div class="list-item">
            <div class="list-info" style="cursor:pointer;" data-action="toggle_playlist_details" data-id="${p.id}">
                <div class="li-title">${p.name} <span style="font-size:0.8rem; color:var(--text-sub);">(${p.items.length})</span></div>
            </div>
            <div style="display:flex; gap:5px;">
              <button class="btn-small" data-action="play_playlist" data-id="${p.id}">Load</button>
              <button class="btn-small" data-action="shuffle_playlist" data-id="${p.id}">Shuffle</button>
              <button class="btn-small" data-action="play_least_played" data-id="${p.id}">Least Played</button>
              <button class="btn-small danger" data-action="delete_playlist" data-id="${p.id}">Del</button>
            </div>
          </div>
          <div id="pl-details-${p.id}" class="hidden" style="margin-bottom: 10px;">
              ${itemsHtml}
          </div>
      </div>
    `}, "No playlists.");
}