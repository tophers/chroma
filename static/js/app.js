// /opt/jukebox/static/app.js

const apiRequest = chroma.apiRequest.bind(chroma);
let volumeTimeout;
let searchTimeout;

async function handleAction(action, id, el) {
  try {
    if (action === "queue") {
      await apiRequest("POST", `/api/queue/add/${id}`);
      toast("Added to queue");

    } else if (action === "play-next") {
      await apiRequest("POST", `/api/queue/play_next/${id}`);
      toast("Playing Next!");

    } else if (action === "edit-gain") {
        const currentGain = parseFloat(el.dataset.current) || 0;
        const input = prompt(`Enter new gain offset in dB (e.g., -2.5, 3.0):\n(Current: ${currentGain}dB)`);

        if (input !== null && input.trim() !== "") {
            const newGain = parseFloat(input);
            if (!isNaN(newGain)) {
                if (newGain < -30 || newGain > 20) {
                    toast("Keep gain between -30dB and +20dB", true);
                    return;
                }
                await apiRequest("POST", `/api/videos/${id}/gain`, { gain: newGain });
                toast(`Gain updated to ${newGain}dB`);
                el.dataset.current = newGain;
                el.textContent = fmtGain(newGain);
            } else {
                toast("Invalid number format", true);
            }
        }

    } else if (action === "add-to-playlist") {
        if(!DOM.playlistSelect || !DOM.playlistSelect.value) {
            toast("No playlist selected", true);
            return;
        }
        const pid = DOM.playlistSelect.value;
        const pname = DOM.playlistSelect.options[DOM.playlistSelect.selectedIndex].text;

        const res = await apiRequest("POST", `/api/playlists/${pid}/add`, {video_id: parseInt(id)});

        if (res.added) {
            toast(`Added to ${pname}`);
        } else {
            toast(`Already in ${pname}`, true);
        }

    } else if (action === "unban") {
      await apiRequest("POST", `/api/unban/${id}`);
      toast("Unbanned");
      document.getElementById("nav-banned").click();

    } else if (action === "ban-history") {
       if (confirm("Only ban retail unsafe songs. Skip tracks you don't want to hear.\n\nPermanently ban this song?")) {
           await apiRequest("POST", `/api/ban/${id}`);
           toast("Banned");
       }

    } else if (action === "play_playlist") {
       await apiRequest("POST", `/api/playlists/${id}/load`);
       toast("Playlist queued");

    } else if (action === "shuffle_playlist") {
        await apiRequest("POST", `/api/playlists/${id}/load?shuffle=true`);
        toast("Playlist queued (Shuffled)");

    } else if (action === "play_least_played") {
        await apiRequest("POST", `/api/playlists/${id}/load?least_played=true`);
        toast("Playlist queued (Least Played First)");

    } else if (action === "delete_playlist") {
       if(confirm("Delete entire playlist?")) {
         await apiRequest("DELETE", `/api/playlists/${id}`);
         document.getElementById("nav-playlists").click();
       }

    } else if (action === "toggle_playlist_details") {
        const details = document.getElementById(`pl-details-${id}`);
        if(details.classList.contains("hidden")) {
            details.classList.remove("hidden");
        } else {
            details.classList.add("hidden");
        }

    } else if (action === "remove_playlist_item") {
        const [pid, vid] = id.split("-");
        await apiRequest("POST", `/api/playlists/${pid}/remove`, {video_id: parseInt(vid)});
        el.closest(".list-item").remove();
        toast("Removed from playlist");
    }

  } catch (e) {
    toast(e.message, true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  
  // --- CHROMA CORE BINDINGS ---
  chroma.addEventListener('ws-connected', () => {
      DOM.status.classList.add("connected");
      DOM.status.classList.remove("error");
      refreshPlaylistSelect();
  });

  chroma.addEventListener('ws-disconnected', () => {
      DOM.status.classList.remove("connected");
      DOM.status.classList.add("error");
  });

  // Wire core state updates directly to your existing player.js functions
  chroma.addEventListener('state-changed', (e) => updateState(e.detail));
  chroma.addEventListener('time-changed', (e) => updateTime(e.detail));

  // Boot up the core
  chroma.init();
  
  const sortDropdown = document.getElementById("sort-select");
  if (sortDropdown) {
      sortDropdown.addEventListener("change", applySortAndRender);
  }

  const playlistSortDropdown = document.getElementById("playlist-sort-select");
  if (playlistSortDropdown) {
      playlistSortDropdown.addEventListener("change", renderPlaylists);
  }

  DOM.playlistSelect = document.getElementById("playlist-select");
  if (DOM.playlistSelect) {
      DOM.playlistSelect.addEventListener("change", async (e) => {
          if (e.target.value === "create_new") {
              const name = prompt("Save current queue as new playlist:\nEnter Name:");
              if (name) {
                  try {
                      await apiRequest("POST", "/api/playlists/create", {name});
                      toast("Playlist Saved!");
                      await refreshPlaylistSelect(); 
                      
                      const data = await apiRequest("GET", "/api/playlists");
                      const newPl = data.playlists.find(p => p.name === name);
                      if (newPl) {
                          DOM.playlistSelect.value = newPl.id;
                          document.getElementById("sidebar-playlist-actions").style.display = "flex";
                      }
                  } catch(err) { 
                      toast(err.message, true); 
                      DOM.playlistSelect.value = ""; 
                      document.getElementById("sidebar-playlist-actions").style.display = "none";
                  }
              } else {
                  DOM.playlistSelect.value = ""; 
                  document.getElementById("sidebar-playlist-actions").style.display = "none";
              }
              return;
          }

          if(e.target.value) {
              document.getElementById("sidebar-playlist-actions").style.display = "flex";
          }
      });
  }

  document.getElementById("btn-sidebar-play").onclick = async () => {
      const pid = DOM.playlistSelect.value;
      if(!pid) return;
      await apiRequest("POST", `/api/playlists/${pid}/load`);
      toast("Playlist queued");
  };

  document.getElementById("btn-sidebar-shuffle").onclick = async () => {
      const pid = DOM.playlistSelect.value;
      if(!pid) return;
      await apiRequest("POST", `/api/playlists/${pid}/load?shuffle=true`);
      toast("Playlist queued (Shuffled)");
  };

  const btnLeastPlayed = document.getElementById("btn-sidebar-least-played");
  if (btnLeastPlayed) {
      btnLeastPlayed.onclick = async () => {
          const pid = DOM.playlistSelect.value;
          if(!pid) return;
          await apiRequest("POST", `/api/playlists/${pid}/load?least_played=true`);
          toast("Playlist queued (Least Played First)");
      };
  }

  const themeToggleBtn = document.getElementById("theme-toggle");
  if (themeToggleBtn) {
      const currentTheme = localStorage.getItem("chroma-theme") || "dark";
      document.documentElement.setAttribute("data-theme", currentTheme);

      themeToggleBtn.onclick = (e) => {
        e.preventDefault();
        let theme = document.documentElement.getAttribute("data-theme");
        theme = theme === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("chroma-theme", theme);
      };
  }

  document.getElementById("btn-clear-queue").onclick = async () => {
    if (confirm("Clear all items from the current queue?")) {
      try {
        await apiRequest("POST", "/api/queue/clear");
        toast("Queue cleared");
      } catch (e) {
        toast(e.message, true);
      }
    }
  };

  document.getElementById("btn-next").onclick = () => apiRequest("POST", "/api/next");
  document.getElementById("btn-pause").onclick = () => apiRequest("POST", "/api/pause");
  document.getElementById("btn-stop").onclick = () => apiRequest("POST", "/api/stop");
  document.getElementById("btn-ban").onclick = () => {
      if (confirm("Only ban retail unsafe songs. Skip tracks you don't want to hear.\n\nPermanently ban this song?")) {
          apiRequest("POST", "/api/ban");
      }
  };
  document.getElementById("btn-stats").onclick = () => apiRequest("POST", "/api/stats");

  const btnRescan = document.getElementById("btn-rescan");
  if(btnRescan) {
      btnRescan.onclick = async () => {
        const ogText = btnRescan.textContent;
        btnRescan.disabled = true;
        btnRescan.textContent = "Scanning...";
        try {
          await apiRequest("POST", "/api/library/scan");
          toast("Scan Complete");
          if (!DOM.views.library.classList.contains("hidden")) {
            DOM.nav.library.click();
          }
        } catch(e) {
          toast("Scan Failed", true);
        } finally {
          btnRescan.disabled = false;
          btnRescan.textContent = ogText;
        }
      };
  }

  document.getElementById("btn-save-queue").onclick = async () => {
    const name = prompt("Playlist Name:");
    if(name) {
      try {
          await apiRequest("POST", "/api/playlists/create", {name});
          toast("Saved!");
          refreshPlaylistSelect();
      }
      catch(e) { toast(e.message, true); }
    }
  };

  DOM.nav.queue.onclick = (e) => { e.preventDefault(); switchView("queue"); };
  DOM.nav.history.onclick = (e) => { e.preventDefault(); switchView("history"); };

  DOM.nav.library.onclick = async (e) => {
    e.preventDefault();
    switchView("library");
    DOM.containers.library.innerHTML = "Loading...";
    refreshPlaylistSelect();
    const data = await apiRequest("GET", "/api/videos");

    currentVideoData = data.videos || [];
    applySortAndRender();
  };

  DOM.nav.playlists.onclick = async (e) => {
    e.preventDefault();
    switchView("playlists");
    const data = await apiRequest("GET", "/api/playlists");
    currentPlaylistData = data.playlists || [];
    renderPlaylists();
  };

  DOM.nav.banned.onclick = async (e) => {
    e.preventDefault();
    switchView("banned");
    const data = await apiRequest("GET", "/api/banned");
    renderList(DOM.containers.banned, data.banned, v => {
      let banDate = "Unknown Date";
      if (v.banned_at) {
          const d = new Date(v.banned_at + "Z");
          banDate = d.toLocaleString(undefined, {
              month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
          });
      }
      return `
      <div class="list-item">
        <div class="list-info">
            <div class="li-title">${v.title}</div>
            <div class="li-sub">${v.artist} <span style="color:var(--danger); margin-left: 8px;">(Banned: ${banDate})</span></div>
        </div>
        <button class="btn-small" data-action="unban" data-id="${v.id}">Unban</button>
      </div>
    `}, "No banned videos.");
  };

  document.getElementById("search-btn").onclick = doSearch;

  document.getElementById("search-input").addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      const q = e.target.value.trim();

      if (q.length === 0) {
          DOM.nav.library.click();
          return;
      }

      if (q.length < 2) return;

      searchTimeout = setTimeout(() => {
          doSearch();
      }, 300);
  });

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

  document.body.onclick = (e) => {
    const btn = e.target.closest("[data-action]");
    if(btn) handleAction(btn.dataset.action, btn.dataset.id, btn);
  };

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    switch (e.code) {
      case "Space": e.preventDefault(); apiRequest("POST", "/api/next"); toast("Skipping..."); break;
      case "ArrowUp": e.preventDefault(); DOM.controls.volume.value = Math.min(100, parseInt(DOM.controls.volume.value) + 5); DOM.controls.volume.dispatchEvent(new Event('input')); break;
      case "ArrowDown": e.preventDefault(); DOM.controls.volume.value = Math.max(0, parseInt(DOM.controls.volume.value) - 5); DOM.controls.volume.dispatchEvent(new Event('input')); break;
      case "ArrowRight": e.preventDefault(); apiRequest("POST", "/api/seek", { time: parseFloat(DOM.seek.slider.value) + 10 }); toast("Seek +10s"); break;
      case "ArrowLeft": e.preventDefault(); apiRequest("POST", "/api/seek", { time: parseFloat(DOM.seek.slider.value) - 10 }); toast("Seek -10s"); break;
      case "KeyS": apiRequest("POST", "/api/stats"); break;
    }
  });
});
