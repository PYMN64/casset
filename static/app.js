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
  // Allow admin-friendly "60" (percent) or legacy "0.6" (ratio)
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

window.__queue = [];          // current playback queue order
window.__queueBase = [];      // original (unshuffled) order for toggling shuffle
window.__qIndex = -1;

window.__shuffle = false;     // shuffle enabled?
window.__repeat = "off";      // "off" | "all" | "one"

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
    repBtn.textContent = window.__repeat === "one" ? "🔂" : "🔁";
  }

  // Queue panel render (اگر بازه)
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

  if (pbTitle) pbTitle.textContent = title || "—";
  if (pbBy) pbBy.textContent = by || "—";
  if (pbCover) pbCover.innerHTML = coverHtml || "";

  window.__nowTrackId = trackId || null;

  audio.src = src;
  bar.style.display = "block";
  audio.play().catch(() => {});

  // Media Session
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
      showToast("پایان صف ✅", true);
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

  // current رو ببر اول صف برای اینکه ترک در حال پخش عوض نشه
  if (current && current.trackId) {
    shuffled = [current, ...shuffled.filter(x => x.trackId !== current.trackId)];
    window.__qIndex = 0;
  }
  window.__queue = shuffled;
}

function toggleShuffle() {
  window.__shuffle = !window.__shuffle;

  // اگر روشن شد: shuffle کن ولی ترک فعلی حفظ
  if (window.__shuffle) {
    applyShuffleKeepingCurrent();
    showToast("Shuffle روشن شد 🔀", true);
  } else {
    // خاموش: برگرد به base و index رو روی track فعلی تنظیم کن
    const cur = window.__queue[window.__qIndex];
    window.__queue = (window.__queueBase || []).slice();
    if (cur && cur.trackId) {
      const idx = window.__queue.findIndex(x => x.trackId === cur.trackId);
      window.__qIndex = idx >= 0 ? idx : 0;
    }
    showToast("Shuffle خاموش شد", true);
  }

  updateQueueUI();
  saveQueueState();
}

function cycleRepeat() {
  window.__repeat = window.__repeat === "off" ? "all" : (window.__repeat === "all" ? "one" : "off");
  showToast(window.__repeat === "off" ? "Repeat خاموش" : (window.__repeat === "all" ? "Repeat: All 🔁" : "Repeat: One 🔂"), true);
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
    title: b.dataset.title || "—",
    by: b.dataset.by || "—",
    coverHtml: b.dataset.cover || "",
    trackId: b.dataset.track || null,
  }));
  const idx = finalButtons.indexOf(clickedBtn);
  return { items, index: idx >= 0 ? idx : 0 };
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
  showToast(data.liked ? "لایک شد ♥" : "آنلایک شد", true);
}

async function handleFavorite(btn) {
  const trackId = btn.dataset.track;
  if (!trackId) return;

  const data = await postForm("/api/v1/favorite/", { track_id: trackId });
  if (!data || !data.ok) return;

  const countEl = document.getElementById("favoriteCount");
  if (countEl) countEl.textContent = data.favorite_count;

  btn.classList.toggle("primary", !!data.favorited);
  btn.setAttribute("aria-pressed", data.favorited ? "true" : "false");
  showToast(data.favorited ? "به علاقه‌مندی‌ها اضافه شد ★" : "از علاقه‌مندی‌ها حذف شد", true);
}

async function handleShare(btn) {
  const url = btn.dataset.url || window.location.href;
  const title = btn.dataset.title || "Casset";

  if (navigator.share) {
    try {
      await navigator.share({ title, url });
      return;
    } catch (_) {
      return; // user cancelled the native share sheet — not an error
    }
  }

  try {
    await navigator.clipboard.writeText(url);
    showToast("لینک کپی شد 🔗", true);
  } catch (_) {
    showToast("کپی لینک ممکن نشد", false);
  }
}

// ---------- Comments ----------
function renderCommentRow(c) {
  const wrap = document.createElement("div");
  wrap.className = "row";
  wrap.style.cssText = "align-items:flex-start;gap:10px";
  wrap.setAttribute("data-comment-row", c.id);
  wrap.innerHTML = `
    <div style="min-width:0;flex:1">
      <div style="font-weight:900">@${c.author_username}</div>
      <div class="muted small"></div>
      <div class="row" style="justify-content:flex-start;gap:8px;margin-top:4px">
        <a href="#" class="btn btn--ghost" data-comment-like="1" data-comment="${c.id}">♥ <span class="commentLikeCount">0</span></a>
        <a href="#" class="btn btn--ghost" data-comment-delete="1" data-comment="${c.id}">حذف</a>
      </div>
    </div>
  `;
  wrap.querySelector(".muted.small").textContent = c.body; // textContent: never trust comment body as HTML
  return wrap;
}

function bumpCommentCount(delta) {
  const el = document.getElementById("commentCount");
  if (!el) return;
  const n = Math.max(0, (parseInt(el.textContent, 10) || 0) + delta);
  el.textContent = n;
}

async function handleCommentSubmit(form) {
  const trackId = form.dataset.track;
  const textarea = form.querySelector("textarea[name=body]");
  const body = (textarea.value || "").trim();
  if (!trackId || !body) return;

  const data = await postForm("/api/v1/comment/add/", { track_id: trackId, body });
  if (!data || !data.ok) {
    showToast("ارسال نظر انجام نشد ❌", false);
    return;
  }

  const list = document.getElementById("commentList");
  const emptyHint = document.getElementById("commentEmptyHint");
  if (emptyHint) emptyHint.remove();
  if (list) list.prepend(renderCommentRow(data.comment));
  bumpCommentCount(1);

  textarea.value = "";
  showToast("نظر ثبت شد ✅", true);
}

async function handleCommentLike(btn) {
  const commentId = btn.dataset.comment;
  if (!commentId) return;
  const data = await postForm(`/api/v1/comment/${commentId}/like/`, {});
  if (!data || !data.ok) return;
  const countEl = btn.querySelector(".commentLikeCount");
  if (countEl) countEl.textContent = data.like_count;
  btn.classList.toggle("primary", !!data.liked);
}

async function handleCommentDelete(btn) {
  const commentId = btn.dataset.comment;
  if (!commentId) return;
  const data = await postForm(`/api/v1/comment/${commentId}/delete/`, {});
  if (!data || !data.ok) { showToast("حذف انجام نشد ❌", false); return; }
  const row = document.querySelector(`[data-comment-row="${commentId}"]`);
  if (row) row.remove();
  bumpCommentCount(-1);
  showToast("نظر حذف شد", true);
}

async function handleCommentReport(btn) {
  const commentId = btn.dataset.comment;
  if (!commentId) return;
  const data = await postForm(`/report/comment/${commentId}/`, {});
  if (!data || !data.ok) { showToast("گزارش ثبت نشد ❌", false); return; }
  showToast("گزارش ثبت شد. ممنون از توجهت 🙏", true);
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
  showToast(data.following ? "فالو شد ✅" : "آنفالو شد", true);
}

// ---------- Playlist modal ----------
window.__plTrackId = null;

function plModalOpen(trackId, trackTitle) {
  const modal = document.getElementById("plModal");
  const list = document.getElementById("plModalList");
  const t = document.getElementById("plModalTrack");
  if (!modal || !list) return;

  window.__plTrackId = trackId;
  if (t) t.textContent = `ترک: ${trackTitle || trackId}`;

  list.innerHTML = `<div class="item"><span class="muted">در حال بارگذاری...</span></div>`;
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
    list.innerHTML = `<div class="item"><span class="muted">خطا در دریافت پلی‌لیست‌ها</span></div>`;
    return;
  }
  const pls = data.playlists || [];
  if (!pls.length) {
    list.innerHTML = `<div class="item"><span class="muted">پلی‌لیستی نداری. از Library بساز.</span></div>`;
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
  if (!data || !data.ok) { showToast("انجام نشد ❌", false); return; }
  showToast(data.added ? "به پلی‌لیست اضافه شد ✅" : "از پلی‌لیست حذف شد ✅", true);
}

// ---------- Search ----------
let __searchTimer = null;
function renderSearchResults(data) {
  const box = document.getElementById("searchResults");
  if (!box) return;

  if (!data || !data.ok) { box.innerHTML = `<div class="item"><span class="muted">خطا در جستجو</span></div>`; return; }

  const tracks = data.tracks || [];
  const creators = data.creators || [];
  const genres = data.genres || [];

  if (!tracks.length && !creators.length && !genres.length) {
    box.innerHTML = `<div class="item"><span class="muted">نتیجه‌ای پیدا نشد.</span></div>`;
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
  if (hint) hint.textContent = "در حال جستجو...";
  const data = await getJSON("/api/v1/search/?q=" + encodeURIComponent(q));
  renderSearchResults(data);
  if (hint) hint.textContent = "تمام";
}
function hookSearchUI() {
  const input = document.getElementById("searchInput");
  if (!input) return;
  input.addEventListener("input", () => {
    const q = (input.value || "").trim();
    const hint = document.getElementById("searchHint");
    if (__searchTimer) clearTimeout(__searchTimer);
    if (q.length < 2) {
      if (hint) hint.textContent = "حداقل ۲ کاراکتر";
      const box = document.getElementById("searchResults");
      if (box) box.innerHTML = `<div class="item"><span class="muted">شروع کن به تایپ…</span></div>`;
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
    list.innerHTML = `<div class="item"><span class="muted">Queue خالیه.</span></div>`;
    return;
  }

  list.innerHTML = q.map((it, i) => {
    const active = i === window.__qIndex;
    return `
      <div class="item" data-q-row="1" data-q-index="${i}" style="${active ? "outline:1px solid rgba(255,255,255,.25)" : ""}">
        <div style="min-width:0">
          <div style="font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${it.title || "—"}</div>
          <div class="muted" style="font-size:12px">${it.by || ""}</div>
        </div>
        <a class="btn ${active ? "primary" : ""}" href="#" data-q-play="1" data-q-index="${i}">${active ? "Playing" : "Play"}</a>
      </div>
    `;
  }).join("");
}

// ---------- Player UX: speed / resume position / sleep timer ----------
const SPEED_STEPS = [1, 1.25, 1.5, 1.75, 2, 0.5, 0.75];
const SPEED_KEY = "casset.playbackRate.v1";
const RESUME_PREFIX = "casset.resume.";
const SLEEP_STEPS_MIN = [0, 15, 30, 45, 60];

let __sleepTimer = null;
let __sleepTimerEndsAt = null;

function getSavedSpeed() {
  let v = 1;
  try { v = parseFloat(localStorage.getItem(SPEED_KEY) || "1"); } catch (_) {}
  return SPEED_STEPS.includes(v) ? v : 1;
}
function applySpeed(rate) {
  const audio = getAudioEl();
  if (audio) audio.playbackRate = rate;
  try { localStorage.setItem(SPEED_KEY, String(rate)); } catch (_) {}
  const btn = document.getElementById("pbSpeed");
  if (btn) btn.textContent = `${rate}x`;
}
function cycleSpeed() {
  const cur = getSavedSpeed();
  const idx = SPEED_STEPS.indexOf(cur);
  const next = SPEED_STEPS[(idx + 1) % SPEED_STEPS.length];
  applySpeed(next);
  showToast(`سرعت پخش: ${next}x`, true);
}

function saveResumePosition(trackId, time) {
  if (!trackId) return;
  try { localStorage.setItem(RESUME_PREFIX + trackId, String(Math.floor(time))); } catch (_) {}
}
function loadResumePosition(trackId) {
  if (!trackId) return 0;
  let v = 0;
  try { v = parseFloat(localStorage.getItem(RESUME_PREFIX + trackId) || "0"); } catch (_) {}
  return Number.isFinite(v) ? v : 0;
}
function clearResumePosition(trackId) {
  if (!trackId) return;
  try { localStorage.removeItem(RESUME_PREFIX + trackId); } catch (_) {}
}

// Resume + speed are attached once per <audio> element (global bar and any
// page-embedded player); trackId is read lazily via getTrackId() because it
// can change (global bar swaps tracks without a new <audio> element).
function hookResumeAndSpeed(audioEl, getTrackId) {
  audioEl.addEventListener("loadedmetadata", () => {
    audioEl.playbackRate = getSavedSpeed();
    const trackId = getTrackId();
    const resumeAt = loadResumePosition(trackId);
    // Don't resume into the last 15s — that's "finished", not "paused".
    if (resumeAt > 5 && audioEl.duration && resumeAt < audioEl.duration - 15) {
      audioEl.currentTime = resumeAt;
      showToast("از جایی که رها کرده بودی ادامه دادیم ⏱", true);
    }
  });

  let lastSaved = 0;
  audioEl.addEventListener("timeupdate", () => {
    const trackId = getTrackId();
    if (!trackId) return;
    const now = audioEl.currentTime;
    if (now - lastSaved >= 5) {
      lastSaved = now;
      saveResumePosition(trackId, now);
    }
  });

  audioEl.addEventListener("ended", () => clearResumePosition(getTrackId()));
}

function updateSleepButtonUI() {
  const btn = document.getElementById("pbSleep");
  if (!btn) return;
  btn.classList.toggle("primary", !!__sleepTimer);
  if (__sleepTimer && __sleepTimerEndsAt) {
    const mins = Math.max(0, Math.ceil((__sleepTimerEndsAt - Date.now()) / 60000));
    btn.title = `تایمر خواب: ${mins} دقیقه مانده`;
  } else {
    btn.title = "تایمر خواب";
  }
}
function clearSleepTimer() {
  if (__sleepTimer) { clearTimeout(__sleepTimer); __sleepTimer = null; }
  __sleepTimerEndsAt = null;
  updateSleepButtonUI();
}
function cycleSleepTimer() {
  const curMin = __sleepTimerEndsAt
    ? Math.round((__sleepTimerEndsAt - Date.now()) / 60000)
    : 0;
  let idx = SLEEP_STEPS_MIN.findIndex((m) => m >= curMin);
  if (idx === -1) idx = 0;
  const nextMin = SLEEP_STEPS_MIN[(idx + 1) % SLEEP_STEPS_MIN.length];

  clearSleepTimer();
  if (nextMin === 0) {
    showToast("تایمر خواب خاموش شد", true);
    return;
  }
  __sleepTimerEndsAt = Date.now() + nextMin * 60000;
  __sleepTimer = setTimeout(() => {
    const audio = getAudioEl();
    if (audio) audio.pause();
    showToast("تایمر خواب: پخش متوقف شد 🌙", true);
    clearSleepTimer();
  }, nextMin * 60000);
  showToast(`تایمر خواب: ${nextMin} دقیقه`, true);
  updateSleepButtonUI();
}

// ---------- Click handler ----------
document.addEventListener("click", (e) => {
  // Player buttons (support clicks on inner SVG)
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
  const pbSpeedEl = e.target.closest("#pbSpeed");
  if (pbSpeedEl) { e.preventDefault(); cycleSpeed(); return; }
  const pbSleepEl = e.target.closest("#pbSleep");
  if (pbSleepEl) { e.preventDefault(); cycleSleepTimer(); return; }

  if (e.target && e.target.id === "qClose") { e.preventDefault(); qPanelClose(); return; }
  const qPlay = e.target.closest("[data-q-play]");
  if (qPlay) { e.preventDefault(); const i = parseInt(qPlay.dataset.qIndex || "-1", 10); if (Number.isFinite(i) && i >= 0) playAt(i); return; }

  const qPanel = document.getElementById("qPanel");
  if (qPanel && e.target === qPanel) { e.preventDefault(); qPanelClose(); return; }

  // Play: build queue from context
  const playBtn = e.target.closest("[data-play]");
  if (playBtn) {
    e.preventDefault();
    const built = buildQueueFromContext(playBtn);
    setQueue(built.items, built.index);
    playAt(window.__qIndex);
    return;
  }

  const likeBtn = e.target.closest("[data-like]");
  if (likeBtn) { e.preventDefault(); handleLike(likeBtn); return; }

  const followBtn = e.target.closest("[data-follow]");
  if (followBtn) { e.preventDefault(); handleFollow(followBtn); return; }

  const favoriteBtn = e.target.closest("[data-favorite]");
  if (favoriteBtn) { e.preventDefault(); handleFavorite(favoriteBtn); return; }

  const shareBtn = e.target.closest("[data-share]");
  if (shareBtn) { e.preventDefault(); handleShare(shareBtn); return; }

  const commentLikeBtn = e.target.closest("[data-comment-like]");
  if (commentLikeBtn) { e.preventDefault(); handleCommentLike(commentLikeBtn); return; }

  const commentDeleteBtn = e.target.closest("[data-comment-delete]");
  if (commentDeleteBtn) { e.preventDefault(); handleCommentDelete(commentDeleteBtn); return; }

  const commentReportBtn = e.target.closest("[data-comment-report]");
  if (commentReportBtn) { e.preventDefault(); handleCommentReport(commentReportBtn); return; }

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

document.addEventListener("submit", (e) => {
  const commentForm = e.target.closest("[data-comment-form]");
  if (commentForm) { e.preventDefault(); handleCommentSubmit(commentForm); return; }
});

// ---------- Boot ----------
document.addEventListener("DOMContentLoaded", () => {
  loadQueueState();
  updateQueueUI();

  const seconds = getPlayThresholdSeconds();
  const globalAudio = getAudioEl();
  if (globalAudio) {
    attachCountAfterSeconds(globalAudio, () => window.__nowTrackId, seconds);
    hookResumeAndSpeed(globalAudio, () => window.__nowTrackId);
  }

  const pageAudio = document.querySelector("audio[data-track]");
  if (pageAudio) {
    attachCountAfterSeconds(pageAudio, () => pageAudio.getAttribute("data-track"), seconds);
    hookResumeAndSpeed(pageAudio, () => pageAudio.getAttribute("data-track"));
  }

  applySpeed(getSavedSpeed());
  updateSleepButtonUI();
  setInterval(updateSleepButtonUI, 30000);

  hookSearchUI();
  hookAutoNext();
});
