// /opt/jukebox/static/js/app-touch.js

document.addEventListener("DOMContentLoaded", () => {
    // --- DOM Elements ---
    const elArtist = document.getElementById("touch-artist");
    const elTitle = document.getElementById("touch-title");
    const elStatus = document.getElementById("touch-status");
    const btnPause = document.getElementById("btn-touch-pause");
    const btnNext = document.getElementById("btn-touch-next");
    const btnBan = document.getElementById("btn-touch-ban");
    const plSelect = document.getElementById("touch-playlist-select");
    
    // Drawers
    const btnSearch = document.getElementById("btn-toggle-search");
    const searchDrawer = document.getElementById("search-drawer");
    const searchInput = document.getElementById("touch-search-input");
    const searchResults = document.getElementById("touch-search-results");
    
    const btnQueue = document.getElementById("btn-toggle-queue");
    const queueDrawer = document.getElementById("queue-drawer");
    const queueResults = document.getElementById("touch-queue-results");

    let searchTimeout;

    // --- Core Listeners ---
    chroma.addEventListener('ws-connected', () => {
        elStatus.classList.add("connected");
        elStatus.classList.remove("error");
        loadPlaylists(); 
    });

    chroma.addEventListener('ws-disconnected', () => {
        elStatus.classList.remove("connected");
        elStatus.classList.add("error");
    });

    chroma.addEventListener('state-changed', (e) => {
        const state = e.detail;
        
        // Update Now Playing Text
        if (state.current_video) {
            elArtist.textContent = state.current_video.artist;
            elTitle.textContent = state.current_video.title;
        } else {
            elArtist.textContent = "—";
            elTitle.textContent = "Not Playing";
        }

        // Update Play/Pause Button
        btnPause.textContent = state.is_paused ? "▶" : "⏸";

        // Always re-render the queue in the background
        renderQueue(state.queue);
    });

    // --- Basic Actions ---
    btnNext.onclick = () => chroma.playNext();
    
    btnPause.onclick = () => chroma.togglePause();
    
    btnBan.onclick = () => {
        if (confirm("Permanently ban this song?")) {
            chroma.banCurrent();
        }
    };

    // --- Playlist Loading ---
    plSelect.addEventListener("change", async (e) => {
        const playlistId = e.target.value;
        if (!playlistId) return;
        
        if (confirm(`Load this playlist?`)) {
            try {
                await chroma.apiRequest("POST", `/api/playlists/${playlistId}/load`);
                plSelect.selectedIndex = 0;
                // If nothing is playing, kickstart it
                if (!chroma.state.current_video) {
                    chroma.playNext();
                }
            } catch (err) {
                console.error("Failed to load playlist", err);
            }
        } else {
            plSelect.selectedIndex = 0;
        }
    });

    // --- Drawer Toggles ---
    btnSearch.onclick = () => {
        searchDrawer.classList.toggle("hidden");
        queueDrawer.classList.add("hidden"); // Auto-close queue if searching
        if (!searchDrawer.classList.contains("hidden")) {
            searchInput.focus();
        } else {
            searchInput.value = "";
            searchResults.innerHTML = "";
        }
    };

    btnQueue.onclick = () => {
        queueDrawer.classList.toggle("hidden");
        searchDrawer.classList.add("hidden"); // Auto-close search if viewing queue
    };

    // --- Search Logic ---
    searchInput.addEventListener("input", (e) => {
        clearTimeout(searchTimeout);
        const q = e.target.value.trim();
        
        if (q.length < 2) {
            searchResults.innerHTML = "";
            return;
        }

        searchResults.innerHTML = `<div style="text-align:center; padding: 20px; color: #888;">Searching...</div>`;

        searchTimeout = setTimeout(async () => {
            try {
                const data = await chroma.search(q);
                renderSearchResults(data.videos || []);
            } catch (err) {
                searchResults.innerHTML = `<div style="color: #ff5252; text-align:center; padding: 20px;">Search failed.</div>`;
            }
        }, 300);
    });

    // --- Render Helpers ---
    function renderSearchResults(videos) {
        if (videos.length === 0) {
            searchResults.innerHTML = `<div style="text-align:center; padding: 20px; color: #888;">No matches found.</div>`;
            return;
        }

        searchResults.innerHTML = videos.map(v => `
            <div class="result-item">
                <div class="result-info">
                    <div class="result-title">${v.title}</div>
                    <div class="result-artist">${v.artist}</div>
                </div>
                <div class="result-actions">
                    <button class="btn-action" 
                            onclick="chroma.queueAdd(${v.id}); this.style.background='#1db954'; this.textContent='✓';" 
                            title="Queue Last">➕</button>
                    <button class="btn-action" 
                            onclick="chroma.queuePlayNext(${v.id}); this.style.background='#1db954'; this.textContent='✓';" 
                            title="Play Next">⏭</button>
                </div>
            </div>
        `).join("");
    }

    function renderQueue(queue) {
        if (!queue || queue.length === 0) {
            queueResults.innerHTML = `<div style="text-align:center; padding: 20px; color: #888;">Queue is empty.</div>`;
            return;
        }

        queueResults.innerHTML = queue.map((v, i) => `
            <div class="result-item">
                <div class="result-info">
                    <div class="result-title">
                        <span style="color:#666; margin-right:8px; font-family: monospace;">${i + 1}.</span>
                        ${v.title}
                    </div>
                    <div class="result-artist">${v.artist}</div>
                </div>
            </div>
        `).join("");
    }

    async function loadPlaylists() {
        try {
            const data = await chroma.apiRequest("GET", "/api/playlists");
            if (data.playlists) {
                const options = data.playlists.map(p => 
                    `<option value="${p.id}">${p.name}</option>`
                ).join("");
                
                plSelect.innerHTML = `<option value="" disabled selected>Load a Playlist...</option>` + options;
            }
        } catch (err) {
            console.error("Failed to load playlists", err);
        }
    }

    // --- Boot ---
    chroma.init();
});