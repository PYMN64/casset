// ===== Casset: Advanced Queue (Shuffle/Repeat) + Player + MVP features =====

// ---------- Helpers ----------
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}
function csrfHeader() {
  const token = getCookie("csrftoken");
  return token ? { "X-CSRFToken": token } : {};
}
function showToast(msg, ok = true) {
  const wrap = document.getElementById("toast");
  const inner = document.getElementById("toastInner");
  if (!wrap || !inner) return;
  inner.textContent = msg;
  inner.classList.toggle("primary", !!ok);
  wrap.style.display = "block";
  setTimeout(() => (wrap.style.display = "none"), 2200);
}
async function postForm(url, dataObj) {
  const body = new URLSearchParams();
  Object.entries(dataObj).forEach(([k, v]) => body.append(k, v));
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", ...csrfHeader() },
    body: body.toString(),
  });
  if (res.status === 401) {
    window.location.href = "/login/?next=" + encodeURIComponent(window.location.pathname);
    return null;
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("Request failed:", url, res.status, text);
    return null;
  }
  return await res.json();
}
async function getJSON(url) {
  const res = await fetch(url, { method: "GET", headers: { ...csrfHeader() } });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("GET failed:", url, res.status, text);
    return null;
  }
  return await res.json();
}

// ---------- Play counting (59s) ----------
function postPlay(trackId) {
  if (!trackId) return;
  window.__playedOnce = window.__playedOnce || {};
  if (window.__playedOnce[trackId]) return;
  window.__playedOnce[trackId] = true;

  const body = new URLSearchParams();
  body.append("track_id", trackId);

  fetch("/api/v1/play/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/x-www-form-urlencoded", ...csrfHeader() },
    body: body.toString(),
  }).then((res) => {
    if (res && res.status === 401) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = "/login/?next=" + next;
    }
  }).catch(() => {});
}

function postPlayProgress(trackId, progress) {
  if (!trackId) return;
  window.__progressOnce = window.__progressOnce || {};
  if (window.__progressOnce[trackId]) return;
  window.__progressOnce[trackId] = true;

  const body = new URLSearchParams();
  body.append("track_id", trackId);
  body.append("progress", String(progress));

  fetch("/api/v1/play/progress/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/x-www-form-urlencoded", ...csrfHeader() },
    body: body.toString(),
  }).then((res) => {
    if (res && res.status === 401) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = "/login/?next=" + next;
    }
  }).catch(() => {});
}

function getPlayThresholdPercent() {
  const el = document.querySelector('meta[name="play-threshold-percent"]');
  const v = el ? parseFloat(el.getAttribute("content") || "0.6") : 0.6;
  if (!Number.isFinite(v)) return 0.6;
  return v > 1 ? (v / 100) : v;
}

function getPlayThresholdSeconds() {
  const el = document.querySelector('meta[name="play-threshold-seconds"]');
  const v = el ? parseInt(el.getAttribute("content") || "59", 10) : 59;
  return Number.isFinite(v) ? v : 59;
}
function attachProgressThreshold(audioEl, getTrackId, percent) {
  let fired = false;
  const onTime = () => {
    if (fired) return;
    const dur = audioEl.duration;
    if (!dur || !isFinite(dur) || dur <= 0) return;
    const p = audioEl.currentTime / dur;
    if (p >= percent) {
      fired = true;
      postPlayProgress(getTrackId(), p);
    }
  };
  audioEl.addEventListener('timeupdate', onTime);
}

function attachCountAfterSeconds(audioEl, getTrackId, seconds) {
  let timer = null;
  function clearTimer() { if (timer) { clearTimeout(timer); timer = null; } }
  audioEl.addEventListener("play", () => {
    clearTimer();
    const trackId = getTrackId();
    if (!trackId) return;
    window.__playedOnce = window.__playedOnce || {};
    if (window.__playedOnce[trackId]) return;
    timer = setTimeout(() => { postPlay(trackId); clearTimer(); }, (seconds || 59) * 1000);
  });
  audioEl.addEventListener("pause", clearTimer);
  audioEl.addEventListener("ended", clearTimer);
}

// ---------- Global player + Queue state ----------
function getAudioEl() { return document.getElementById("globalAudio"); }

window.__nowTrackId = null;

const QKEY = "casset.queue.v1";
const SKEY = "casset.queueState.v1";

window.__queue = [];
window.__queueBase = [];
window.__qIndex = -1;

window.__shuffle = false;
window.__repeat = "off"; // "off" | "all" | "one"

function saveQueueState() {
  try {
    sessionStorage.setItem(QKEY, JSON.stringify({
      queue: window.__queue,
      base: window.__queueBase,
      index: window.__qIndex
    }));
    sessionStorage.setItem(SKEY, JSON.stringify({
      shuffle: window.__shuffle,
      repeat: window.__repeat
    }));
  } catch (_) {}
}
function loadQueueState() {
  try {
    const q = JSON.parse(sessionStorage.getItem(QKEY) || "null");
    const s = JSON.parse(sessionStorage.getItem(SKEY) || "null");
    if (q && Array.isArray(q.queue)) {
      window.__queue = q.queue || [];
      window.__queueBase = q.base || q.queue || [];
      window.__qIndex = Number.isFinite(q.index) ? q.index : -1;
    }
    if (s) {
      window.__shuffle = !!s.shuffle;
      window.__repeat = (s.repeat === "all" || s.repeat === "one") ? s.repeat : "off";
    }
  } catch (_) {}
}

function updateQueueUI() {
  const pos = document.getElementById("pbPos");
  const n = window.__queue.length;
  if (pos) {
    pos.textContent = (n > 0 && window.__qIndex >= 0) ? `${window.__qIndex + 1} / ${n}` : "";
  }

  const shBtn = document.getElementById("pbShuffle");
  if (shBtn) shBtn.classList.toggle("primary", window.__shuffle);

  const repBtn = document.getElementById("pbRepeat");
  if (repBtn) {
    repBtn.classList.toggle("primary", window.__repeat !== "off");
    repBtn.textContent = window.__repeat === "one" ? "1" : "ALL";
  }

  const panel = document.getElementById("qPanel");
  if (panel && panel.style.display === "block") renderQueuePanel();
}

function setQueue(items, index) {
  window.__queueBase = items || [];
  window.__queue = items || [];
  window.__qIndex = Number.isFinite(index) ? index : 0;

  if (window.__shuffle) {
    applyShuffleKeepingCurrent();
  }
  updateQueueUI();
  saveQueueState();
}

function openPlayerBar({ src, title, by, coverHtml, trackId }) {
  const bar = document.getElementById("playerbar");
  const audio = getAudioEl();
  if (!audio || !bar) return;

  const pbTitle = document.getElementById("pbTitle");
  const pbBy = document.getElementById("pbBy");
  const pbCover = document.getElementById("pbCover");

  if (pbTitle) pbTitle.textContent = title || "--";
  if (pbBy) pbBy.textContent = by || "--";
  let coverMarkup = coverHtml || "";
  if (coverMarkup && !coverMarkup.includes("<")) {
    coverMarkup = `<img src="${coverMarkup}" alt="" />`;
  }
  if (pbCover) pbCover.innerHTML = coverMarkup;

  window.__nowTrackId = trackId || null;

  audio.src = src;
  bar.style.display = "block";
  audio.play().catch(() => {});

  if ("mediaSession" in navigator) {
    const artwork = [];
    try {
      const tmp = document.createElement("div");
      tmp.innerHTML = coverHtml || "";
      const img = tmp.querySelector("img");
      const srcArt = img ? img.getAttribute("src") : null;
      if (srcArt) artwork.push({ src: srcArt, sizes: "512x512", type: "image/png" });
    } catch (_) {}

    navigator.mediaSession.metadata = new MediaMetadata({
      title: title || "Casset",
      artist: by || "",
      album: "Casset",
      artwork
    });

    navigator.mediaSession.setActionHandler("play", () => audio.play().catch(()=>{}));
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("nexttrack", () => queueNext());
    navigator.mediaSession.setActionHandler("previoustrack", () => queuePrev());
  }
}

function playAt(index) {
  const q = window.__queue || [];
  if (!q.length) return;
  if (index < 0 || index >= q.length) return;

  window.__qIndex = index;
  updateQueueUI();
  saveQueueState();

  const item = q[index];
  openPlayerBar(item);
}

function queueNext() {
  const q = window.__queue || [];
  if (!q.length) return;

  if (window.__repeat === "one") {
    playAt(window.__qIndex);
    return;
  }

  const next = window.__qIndex + 1;
  if (next >= q.length) {
    if (window.__repeat === "all") {
      playAt(0);
    } else {
      showToast("End of queue", true);
    }
    return;
  }
  playAt(next);
}

function queuePrev() {
  const q = window.__queue || [];
  if (!q.length) return;

  const prev = window.__qIndex - 1;
  if (prev < 0) return;
  playAt(prev);
}

// ---------- Shuffle / Repeat ----------
function fisherYates(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function applyShuffleKeepingCurrent() {
  const base = window.__queueBase || [];
  if (!base.length) return;

  const current = base[window.__qIndex] || window.__queue[window.__qIndex] || null;
  let shuffled = fisherYates(base);

  if (current && current.trackId) {
    shuffled = [current, ...shuffled.filter(x => x.trackId !== current.trackId)];
    window.__qIndex = 0;
  }
  window.__queue = shuffled;
}

function toggleShuffle() {
  window.__shuffle = !window.__shuffle;

  if (window.__shuffle) {
    applyShuffleKeepingCurrent();
    showToast("Shuffle enabled", true);
  } else {
    const cur = window.__queue[window.__qIndex];
    window.__queue = (window.__queueBase || []).slice();
    if (cur && cur.trackId) {
      const idx = window.__queue.findIndex(x => x.trackId === cur.trackId);
      window.__qIndex = idx >= 0 ? idx : 0;
    }
    showToast("Shuffle disabled", true);
  }

  updateQueueUI();
  saveQueueState();
}

function cycleRepeat() {
  window.__repeat = window.__repeat === "off" ? "all" : (window.__repeat === "all" ? "one" : "off");
  showToast(window.__repeat === "off" ? "Repeat off" : (window.__repeat === "all" ? "Repeat: all" : "Repeat: one"), true);
  updateQueueUI();
  saveQueueState();
}

// ---------- Queue builder (DOM context) ----------
function buildQueueFromContext(clickedBtn) {
  const container = clickedBtn.closest(".list") || clickedBtn.closest("section") || document;
  const buttons = Array.from(container.querySelectorAll("[data-play]")).filter(b => b.dataset && b.dataset.src);
  const finalButtons = buttons.length > 1 ? buttons : Array.from(document.querySelectorAll("[data-play]")).filter(b => b.dataset && b.dataset.src);

  const items = finalButtons.map(b => ({
    src: b.dataset.src,
    title: b.dataset.title || "--",
    by: b.dataset.by || "--",
    coverHtml: b.dataset.cover || "",
    trackId: b.dataset.track || null,
  }));
  const idx = finalButtons.indexOf(clickedBtn);
  return { items, index: idx >= 0 ? idx : 0 };
}

function addToQueueFromButton(btn) {
  const item = {
    src: btn.dataset.src,
    title: btn.dataset.title || "--",
    by: btn.dataset.by || "--",
    coverHtml: btn.dataset.cover || "",
    trackId: btn.dataset.track || null,
  };
  if (!item.src) return;
  window.__queueBase = window.__queueBase || [];
  window.__queue = window.__queue || [];
  window.__queueBase.push(item);
  window.__queue.push(item);
  if (window.__qIndex < 0) window.__qIndex = 0;
  updateQueueUI();
  saveQueueState();
  showToast("Added to queue", true);
}

// ---------- Auto next on ended ----------
function hookAutoNext() {
  const audio = getAudioEl();
  if (!audio) return;
  audio.addEventListener("ended", () => queueNext());
}

// ---------- Like / Follow ----------
async function handleLike(btn) {
  const trackId = btn.dataset.track;
  if (!trackId) return;

  const data = await postForm("/api/v1/like/", { track_id: trackId });
  if (!data || !data.ok) return;

  const countEl = document.getElementById("likeCount");
  if (countEl) countEl.textContent = data.like_count;

  btn.classList.toggle("primary", !!data.liked);
  btn.setAttribute("aria-pressed", data.liked ? "true" : "false");
  showToast(data.liked ? "Liked" : "Unliked", true);
}

async function handleFollow(btn) {
  const creator = btn.dataset.creator;
  if (!creator) return;

  const data = await postForm("/api/v1/follow/", { creator_username: creator });
  if (!data || !data.ok) return;

  const countEl = document.getElementById("followCount");
  if (countEl) countEl.textContent = data.follower_count;

  btn.classList.toggle("primary", !!data.following);
  btn.setAttribute("aria-pressed", data.following ? "true" : "false");
  showToast(data.following ? "Followed" : "Unfollowed", true);
}

// ---------- Playlist modal ----------
window.__plTrackId = null;

function plModalOpen(trackId, trackTitle) {
  const modal = document.getElementById("plModal");
  const list = document.getElementById("plModalList");
  const t = document.getElementById("plModalTrack");
  if (!modal || !list) return;

  window.__plTrackId = trackId;
  if (t) t.textContent = `Track: ${trackTitle || trackId}`;

  list.innerHTML = `<div class="item"><span class="muted">Loading...</span></div>`;
  modal.style.display = "block";
  loadMyPlaylistsIntoModal();
}
function plModalClose() {
  const modal = document.getElementById("plModal");
  if (modal) modal.style.display = "none";
  window.__plTrackId = null;
}
async function loadMyPlaylistsIntoModal() {
  const list = document.getElementById("plModalList");
  if (!list) return;
  const data = await getJSON("/api/v1/playlist/mine/");
  if (!data || !data.ok) {
    list.innerHTML = `<div class="item"><span class="muted">Failed to load playlists</span></div>`;
    return;
  }
  const pls = data.playlists || [];
  if (!pls.length) {
    list.innerHTML = `<div class="item"><span class="muted">No playlists yet. Create one in Library.</span></div>`;
    return;
  }
  list.innerHTML = pls.map(p => `
    <div class="item">
      <div style="min-width:0">
        <div style="font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${p.name}</div>
        <div class="muted" style="font-size:12px">${p.item_count} tracks</div>
      </div>
      <a class="btn" href="#" data-pl-toggle="1" data-playlist="${p.id}">Add/Remove</a>
    </div>
  `).join("");
}
async function toggleTrackInPlaylist(playlistId, trackId) {
  const data = await postForm("/api/v1/playlist/toggle-track/", { playlist_id: playlistId, track_id: trackId });
  if (!data || !data.ok) { showToast("Failed", false); return; }
  showToast(data.added ? "Added to playlist" : "Removed from playlist", true);
}

// ---------- Search ----------
let __searchTimer = null;
function renderSearchResults(data) {
  const box = document.getElementById("searchResults");
  if (!box) return;

  if (!data || !data.ok) { box.innerHTML = `<div class="item"><span class="muted">Search failed</span></div>`; return; }

  const tracks = data.tracks || [];
  const creators = data.creators || [];
  const genres = data.genres || [];

  if (!tracks.length && !creators.length && !genres.length) {
    box.innerHTML = `<div class="item"><span class="muted">No results.</span></div>`;
    return;
  }

  let html = "";
  if (tracks.length) {
    html += `<div class="item"><b>Tracks</b></div>`;
    tracks.forEach(t => html += `<div class="item"><a href="/t/${t.slug}/" style="font-weight:900">${t.title}</a><span class="muted" style="font-size:12px">@${t["creator__username"]} • ${t.play_count} plays</span></div>`);
  }
  if (creators.length) {
    html += `<div class="item"><b>Creators</b></div>`;
    creators.forEach(u => {
      const fc = u["profile__follower_count"] ?? 0;
      html += `<div class="item"><a href="/artist/${u.username}/" style="font-weight:900">@${u.username}</a><span class="muted" style="font-size:12px">${fc} followers</span></div>`;
    });
  }
  if (genres.length) {
    html += `<div class="item"><b>Genres</b></div>`;
    genres.forEach(g => html += `<div class="item"><a href="/tracks/?genre=${g.slug}" style="font-weight:900">${g.name}</a><span class="muted" style="font-size:12px">open</span></div>`);
  }
  box.innerHTML = html;
}
async function doSearch(q) {
  const hint = document.getElementById("searchHint");
  if (hint) hint.textContent = "Searching...";
  const data = await getJSON("/api/v1/search/?q=" + encodeURIComponent(q));
  renderSearchResults(data);
  if (hint) hint.textContent = "Done";
}
function hookSearchUI() {
  const input = document.getElementById("searchInput");
  if (!input) return;
  input.addEventListener("input", () => {
    const q = (input.value || "").trim();
    const hint = document.getElementById("searchHint");
    if (__searchTimer) clearTimeout(__searchTimer);
    if (q.length < 2) {
      if (hint) hint.textContent = "Type at least 2 characters";
      const box = document.getElementById("searchResults");
      if (box) box.innerHTML = `<div class="item"><span class="muted">Start typing...</span></div>`;
      return;
    }
    __searchTimer = setTimeout(() => doSearch(q), 250);
  });
}

// ---------- Queue panel ----------
function qPanelOpen() {
  const p = document.getElementById("qPanel");
  if (!p) return;
  p.style.display = "block";
  renderQueuePanel();
}
function qPanelClose() {
  const p = document.getElementById("qPanel");
  if (!p) return;
  p.style.display = "none";
}
function renderQueuePanel() {
  const list = document.getElementById("qList");
  const meta = document.getElementById("qMeta");
  if (!list) return;

  const q = window.__queue || [];
  if (meta) meta.textContent = `Shuffle: ${window.__shuffle ? "ON" : "OFF"} • Repeat: ${window.__repeat.toUpperCase()} • ${q.length} tracks`;

  if (!q.length) {
    list.innerHTML = `<div class="item"><span class="muted">Queue is empty.</span></div>`;
    return;
  }

  list.innerHTML = q.map((it, i) => {
    const active = i === window.__qIndex;
    return `
      <div class="item" data-q-row="1" data-q-index="${i}" style="${active ? "outline:1px solid rgba(255,255,255,.25)" : ""}">
        <div style="min-width:0">
          <div style="font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${it.title || "--"}</div>
          <div class="muted" style="font-size:12px">${it.by || ""}</div>
        </div>
        <a class="btn ${active ? "primary" : ""}" href="#" data-q-play="1" data-q-index="${i}">${active ? "Playing" : "Play"}</a>
      </div>
    `;
  }).join("");
}

// ---------- Click handler ----------
document.addEventListener("click", (e) => {
  const pbNextEl = e.target.closest("#pbNext");
  if (pbNextEl) { e.preventDefault(); queueNext(); return; }
  const pbPrevEl = e.target.closest("#pbPrev");
  if (pbPrevEl) { e.preventDefault(); queuePrev(); return; }
  const pbShuffleEl = e.target.closest("#pbShuffle");
  if (pbShuffleEl) { e.preventDefault(); toggleShuffle(); return; }
  const pbRepeatEl = e.target.closest("#pbRepeat");
  if (pbRepeatEl) { e.preventDefault(); cycleRepeat(); return; }
  const pbQueueEl = e.target.closest("#pbQueue");
  if (pbQueueEl) { e.preventDefault(); qPanelOpen(); return; }

  if (e.target && e.target.id === "qClose") { e.preventDefault(); qPanelClose(); return; }
  const qPlay = e.target.closest("[data-q-play]");
  if (qPlay) { e.preventDefault(); const i = parseInt(qPlay.dataset.qIndex || "-1", 10); if (Number.isFinite(i) && i >= 0) playAt(i); return; }

  const qPanel = document.getElementById("qPanel");
  if (qPanel && e.target === qPanel) { e.preventDefault(); qPanelClose(); return; }

  const playBtn = e.target.closest("[data-play]");
  if (playBtn) {
    e.preventDefault();
    const built = buildQueueFromContext(playBtn);
    setQueue(built.items, built.index);
    playAt(window.__qIndex);
    return;
  }

  const queueBtn = e.target.closest("[data-queue]");
  if (queueBtn) {
    e.preventDefault();
    addToQueueFromButton(queueBtn);
    return;
  }

  const likeBtn = e.target.closest("[data-like]");
  if (likeBtn) { e.preventDefault(); handleLike(likeBtn); return; }

  const followBtn = e.target.closest("[data-follow]");
  if (followBtn) { e.preventDefault(); handleFollow(followBtn); return; }

  const plOpenBtn = e.target.closest("[data-pl-open]");
  if (plOpenBtn) {
    e.preventDefault();
    const trackId = plOpenBtn.dataset.track;
    const trackTitle = plOpenBtn.dataset.title || "";
    if (!trackId) return;
    plModalOpen(trackId, trackTitle);
    return;
  }

  const plToggleBtn = e.target.closest("[data-pl-toggle]");
  if (plToggleBtn) {
    e.preventDefault();
    const pid = plToggleBtn.dataset.playlist;
    const tid = window.__plTrackId;
    if (!pid || !tid) return;
    toggleTrackInPlaylist(pid, tid);
    return;
  }

  if (e.target && e.target.id === "plClose") { e.preventDefault(); plModalClose(); return; }
  const plModal = document.getElementById("plModal");
  if (plModal && e.target === plModal) { e.preventDefault(); plModalClose(); return; }
});

// ---------- Boot ----------
document.addEventListener("DOMContentLoaded", () => {
  loadQueueState();
  updateQueueUI();

  const seconds = getPlayThresholdSeconds();
  const percent = getPlayThresholdPercent();
  const globalAudio = getAudioEl();
  if (globalAudio) {
    attachCountAfterSeconds(globalAudio, () => window.__nowTrackId, seconds);
    attachProgressThreshold(globalAudio, () => window.__nowTrackId, percent);
  }

  const pageAudio = document.querySelector("audio[data-track]");
  if (pageAudio) {
    attachCountAfterSeconds(pageAudio, () => pageAudio.getAttribute("data-track"), seconds);
    attachProgressThreshold(pageAudio, () => pageAudio.getAttribute("data-track"), percent);
  }

  hookSearchUI();
  hookAutoNext();
});
