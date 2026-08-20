/* =====================================================================
   Casset — chrome & form behaviour
   Everything here is progressive enhancement: with JavaScript disabled the
   pages still render, forms still submit, and destructive actions still
   work (they fall back to a plain submit). app.js owns the player, the
   queue and the API calls; this file owns the shell around them.
   ===================================================================== */
(function () {
  "use strict";

  var d = document;
  var THEME_KEY = "casset.theme";

  function $(sel, root) { return (root || d).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || d).querySelectorAll(sel)); }

  /* ------------------------------------------------------------------
     Theme toggle. The initial value is applied by an inline script in
     <head> so the page never paints the wrong theme first.
     ------------------------------------------------------------------ */
  function applyTheme(theme) {
    d.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
    var icon = $("#themeIcon");
    if (icon) {
      icon.innerHTML = "";
      var use = d.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", theme === "dark" ? "#i-moon" : "#i-sun");
      icon.appendChild(use);
    }
  }

  function initTheme() {
    var current = d.documentElement.getAttribute("data-theme") || "dark";
    applyTheme(current);
    var btn = $("#themeToggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var now = d.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(now);
    });
  }

  /* ------------------------------------------------------------------
     Dropdown menus — the account chip and any [data-menu-toggle].
     ------------------------------------------------------------------ */
  function closeAllMenus(except) {
    $$(".menu__panel.open").forEach(function (panel) {
      if (panel === except) return;
      panel.classList.remove("open");
      var owner = panel.closest(".menu");
      var btn = owner && owner.querySelector("[aria-haspopup]");
      if (btn) btn.setAttribute("aria-expanded", "false");
    });
  }

  function initMenus() {
    d.addEventListener("click", function (e) {
      var toggle = e.target.closest("#accountMenuBtn, [data-menu-toggle]");
      if (toggle) {
        e.preventDefault();
        var wrap = toggle.closest(".menu");
        var panel = wrap && wrap.querySelector(".menu__panel");
        if (!panel) return;
        var willOpen = !panel.classList.contains("open");
        closeAllMenus(panel);
        panel.classList.toggle("open", willOpen);
        toggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
        return;
      }
      if (!e.target.closest(".menu__panel")) closeAllMenus();
    });

    d.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeAllMenus();
    });
  }

  /* ------------------------------------------------------------------
     Second confirmation for destructive actions.

     Any element carrying data-confirm="message" routes through the modal
     instead of firing on one click. Works for links, buttons and submit
     buttons inside a form. Without JS the element behaves normally — the
     server-side guards (POST-only, ownership checks) are the real
     protection; this is protection against a mis-click.
     ------------------------------------------------------------------ */
  var pendingConfirm = null;

  function openConfirm(message, title) {
    var modal = $("#confirmModal");
    if (!modal) return false;
    $("#confirmText").textContent = message;
    $("#confirmTitle").textContent = title || "تایید عملیات";
    modal.classList.remove("hidden");
    var ok = $("#confirmOk");
    if (ok) ok.focus();
    return true;
  }

  function closeConfirm() {
    var modal = $("#confirmModal");
    if (modal) modal.classList.add("hidden");
    pendingConfirm = null;
  }

  function initConfirm() {
    d.addEventListener("click", function (e) {
      var el = e.target.closest("[data-confirm]");
      if (!el || el.__confirmed) return;
      var msg = el.getAttribute("data-confirm");
      if (!msg) return;
      if (!openConfirm(msg, el.getAttribute("data-confirm-title"))) return; // no modal: let it through
      e.preventDefault();
      e.stopPropagation();
      pendingConfirm = el;
    }, true);

    var cancel = $("#confirmCancel");
    if (cancel) cancel.addEventListener("click", closeConfirm);

    var modal = $("#confirmModal");
    if (modal) {
      modal.addEventListener("click", function (e) {
        if (e.target === modal) closeConfirm();
      });
    }

    var ok = $("#confirmOk");
    if (ok) {
      ok.addEventListener("click", function () {
        var el = pendingConfirm;
        closeConfirm();
        if (!el) return;
        // Re-dispatch the original action with the guard lifted for one tick.
        el.__confirmed = true;
        if (el.tagName === "A") {
          window.location.href = el.getAttribute("href");
        } else if (el.form) {
          if (el.name) {
            var hidden = d.createElement("input");
            hidden.type = "hidden";
            hidden.name = el.name;
            hidden.value = el.value || "1";
            el.form.appendChild(hidden);
          }
          el.form.submit();
        } else {
          el.click();
        }
        el.__confirmed = false;
      });
    }

    d.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeConfirm();
    });
  }

  /* ------------------------------------------------------------------
     Password: show/hide and a live strength meter.

     The meter is advisory only — Django's AUTH_PASSWORD_VALIDATORS are
     what actually accept or reject the password on submit. Showing the
     rating live just stops the user finding out after a round trip.
     ------------------------------------------------------------------ */
  function scorePassword(pw) {
    if (!pw) return 0;
    var score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    var classes = 0;
    if (/[a-z]/.test(pw)) classes++;
    if (/[A-Z]/.test(pw)) classes++;
    if (/[0-9]/.test(pw)) classes++;
    if (/[^A-Za-z0-9]/.test(pw)) classes++;
    if (classes >= 3) score++;
    // An all-digit password passes length checks but Django rejects it —
    // reflect that here instead of promising "strong".
    if (/^\d+$/.test(pw)) score = Math.min(score, 1);
    return Math.max(1, Math.min(3, score));
  }

  var STRENGTH_LABELS = ["", "ضعیف — حداقل ۸ کاراکتر و ترکیبی از حرف و عدد", "متوسط — با یک نماد قوی‌تر می‌شود", "قوی"];

  function initPasswordUI() {
    $$("[data-toggle-password]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var input = d.getElementById(btn.getAttribute("data-toggle-password"));
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.setAttribute("aria-label", show ? "پنهان کردن رمز" : "نمایش رمز");
        var use = btn.querySelector("use");
        if (use) use.setAttribute("href", show ? "#i-eye-off" : "#i-eye");
      });
    });

    $$("[data-strength-for]").forEach(function (meter) {
      var input = d.getElementById(meter.getAttribute("data-strength-for"));
      if (!input) return;
      var label = meter.parentNode.querySelector(".strength__label");
      input.addEventListener("input", function () {
        var level = scorePassword(input.value);
        meter.setAttribute("data-level", String(level));
        if (label) label.textContent = STRENGTH_LABELS[level] || "";
      });
    });
  }

  /* ------------------------------------------------------------------
     OTP resend countdown.

     The server enforces the cooldown (accounts/services.py); this only
     makes the wait visible, which reads as "protected" rather than
     "broken" when the resend link does nothing.
     ------------------------------------------------------------------ */
  function initResendCountdown() {
    var box = $("[data-resend-seconds]");
    if (!box) return;
    var remaining = parseInt(box.getAttribute("data-resend-seconds"), 10) || 0;
    var btn = box.querySelector("button, a");
    var counter = box.querySelector("[data-resend-counter]");
    if (!btn) return;

    function tick() {
      if (remaining <= 0) {
        btn.disabled = false;
        btn.classList.remove("hidden");
        if (counter) counter.classList.add("hidden");
        return;
      }
      btn.disabled = true;
      btn.classList.add("hidden");
      if (counter) {
        counter.classList.remove("hidden");
        counter.textContent = "ارسال مجدد تا " + remaining + " ثانیه دیگر";
      }
      remaining -= 1;
      setTimeout(tick, 1000);
    }
    tick();
  }

  /* OTP box: paste a 6-digit code and it just works; only digits accepted. */
  function initOtpInput() {
    $$(".otp-input").forEach(function (input) {
      input.addEventListener("input", function () {
        var digits = input.value.replace(/[^\d۰-۹٠-٩]/g, "");
        // Persian/Arabic-Indic digits to ASCII, matching the server's
        // normalisation in accounts/services.py.
        digits = digits.replace(/[۰-۹]/g, function (c) { return String(c.charCodeAt(0) - 1776); })
                       .replace(/[٠-٩]/g, function (c) { return String(c.charCodeAt(0) - 1632); });
        input.value = digits.slice(0, 6);
        if (input.value.length === 6 && input.form) {
          var submit = input.form.querySelector("[type=submit]");
          if (submit) submit.focus();
        }
      });
    });
  }

  /* ------------------------------------------------------------------
     Tabs — [data-tab-group] + [data-tab] + [data-tab-panel]
     ------------------------------------------------------------------ */
  function initTabs() {
    $$("[data-tab-group]").forEach(function (group) {
      var tabs = $$("[data-tab]", group);
      tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
          var key = tab.getAttribute("data-tab");
          tabs.forEach(function (t) {
            var on = t === tab;
            t.classList.toggle("tabs__tab--active", on);
            t.setAttribute("aria-selected", on ? "true" : "false");
          });
          $$("[data-tab-panel]", group.parentNode).forEach(function (panel) {
            panel.classList.toggle("hidden", panel.getAttribute("data-tab-panel") !== key);
          });
        });
      });
    });
  }

  /* ------------------------------------------------------------------
     Notification badge — unread count, polled.
     ------------------------------------------------------------------ */
  function initNotificationBadge() {
    var badge = $("#notifBadge");
    if (!badge || !window.__cassetAuthed) return;

    function refresh() {
      fetch("/api/v1/notifications/", { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data) return;
          var n = data.unread_count || 0;
          badge.textContent = n > 99 ? "99+" : String(n);
          badge.classList.toggle("hidden", n === 0);
        })
        .catch(function () { /* offline: leave the last known value */ });
    }
    refresh();
    setInterval(refresh, 60000);
  }

  /* ------------------------------------------------------------------
     Recent searches — client-side only, no server round trip and no
     search history stored on our side.
     ------------------------------------------------------------------ */
  var RECENT_KEY = "casset.recentSearches.v1";

  function readRecent() {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch (e) { return []; }
  }

  function rememberSearch(q) {
    q = (q || "").trim();
    if (q.length < 2) return;
    var list = readRecent().filter(function (item) { return item !== q; });
    list.unshift(q);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 8))); } catch (e) {}
  }

  function initRecentSearches() {
    var host = $("#recentSearches");
    var params = new URLSearchParams(window.location.search);
    if (params.get("q")) rememberSearch(params.get("q"));
    if (!host) return;

    var list = readRecent();
    if (!list.length) { host.classList.add("hidden"); return; }
    host.classList.remove("hidden");
    var row = host.querySelector("[data-recent-list]");
    if (!row) return;
    row.innerHTML = "";
    list.forEach(function (q) {
      var a = d.createElement("a");
      a.className = "pill";
      a.href = "/search/?q=" + encodeURIComponent(q);
      a.textContent = q;
      row.appendChild(a);
    });
    var clear = host.querySelector("[data-recent-clear]");
    if (clear) {
      clear.addEventListener("click", function () {
        try { localStorage.removeItem(RECENT_KEY); } catch (e) {}
        host.classList.add("hidden");
      });
    }
  }

  /* ------------------------------------------------------------------
     Drag-to-reorder for playlist items.

     Native HTML5 drag and drop — no library. The ▲▼ buttons stay in the
     markup and keep working, which is what makes this usable on touch
     devices and with a keyboard; dragging is the desktop shortcut, not
     the only way in.
     ------------------------------------------------------------------ */
  function initDragReorder() {
    var lists = $$("[data-reorder-list]");
    lists.forEach(function (list) {
      var dragged = null;

      list.addEventListener("dragstart", function (e) {
        var row = e.target.closest("[data-reorder-item]");
        if (!row) return;
        dragged = row;
        row.classList.add("is-dragging");
        e.dataTransfer.effectAllowed = "move";
        // Firefox refuses to start a drag without data set.
        e.dataTransfer.setData("text/plain", row.getAttribute("data-reorder-item"));
      });

      list.addEventListener("dragend", function () {
        if (dragged) dragged.classList.remove("is-dragging");
        $$(".drop-target", list).forEach(function (el) { el.classList.remove("drop-target"); });
        dragged = null;
      });

      list.addEventListener("dragover", function (e) {
        if (!dragged) return;
        e.preventDefault();
        var over = e.target.closest("[data-reorder-item]");
        if (!over || over === dragged) return;
        $$(".drop-target", list).forEach(function (el) { el.classList.remove("drop-target"); });
        over.classList.add("drop-target");
      });

      list.addEventListener("drop", function (e) {
        if (!dragged) return;
        e.preventDefault();
        var over = e.target.closest("[data-reorder-item]");
        if (!over || over === dragged) return;
        var rows = $$("[data-reorder-item]", list);
        var from = rows.indexOf(dragged);
        var to = rows.indexOf(over);
        if (from < 0 || to < 0) return;
        if (from < to) over.after(dragged); else over.before(dragged);
        over.classList.remove("drop-target");
        persistOrder(list);
      });
    });
  }

  function persistOrder(list) {
    var url = list.getAttribute("data-reorder-url");
    if (!url) return;
    var ids = $$("[data-reorder-item]", list).map(function (row) {
      return row.getAttribute("data-reorder-item");
    });
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest"
      },
      body: JSON.stringify({ order: ids })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (window.showToast) window.showToast(data.ok ? "ترتیب ذخیره شد" : "ذخیره نشد", !!data.ok);
      })
      .catch(function () {
        if (window.showToast) window.showToast("ذخیره ترتیب ناموفق بود", false);
      });
  }

  function getCookie(name) {
    var match = d.cookie.match(new RegExp("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  /* ------------------------------------------------------------------
     Live avatar/cover preview in settings and upload.
     ------------------------------------------------------------------ */
  function initImagePreview() {
    $$("[data-preview-for]").forEach(function (target) {
      var input = d.getElementById(target.getAttribute("data-preview-for"));
      if (!input) return;
      input.addEventListener("change", function () {
        var file = input.files && input.files[0];
        if (!file) return;
        var url = URL.createObjectURL(file);
        target.style.backgroundImage = "url('" + url + "')";
        target.classList.add("cover-preview--visible");
      });
    });
  }

  /* ------------------------------------------------------------------
     Share button — the Web Share sheet where it exists, clipboard where
     it does not. Never leaves the user with a dead button.
     ------------------------------------------------------------------ */
  function initShare() {
    d.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-share]");
      if (!btn) return;
      e.preventDefault();
      var url = btn.getAttribute("data-share") || window.location.href;
      if (url.indexOf("http") !== 0) url = window.location.origin + url;
      var title = btn.getAttribute("data-share-title") || d.title;

      if (navigator.share) {
        navigator.share({ title: title, url: url }).catch(function () {});
        return;
      }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () {
          if (window.showToast) window.showToast("لینک کپی شد");
        }).catch(function () {
          if (window.showToast) window.showToast("کپی نشد", false);
        });
      }
    });
  }

  /* ------------------------------------------------------------------
     Service worker.
     ------------------------------------------------------------------ */
  function initServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    });
  }

  /* ------------------------------------------------------------------
     Install prompt — shown only after the visitor has used the site a
     little, and never again once dismissed. An install banner on the
     first page view is the single most-complained-about PWA pattern.
     ------------------------------------------------------------------ */
  var VISIT_KEY = "casset.visits.v1";
  var INSTALL_DISMISSED = "casset.installDismissed.v1";

  function initInstallPrompt() {
    var visits = 0;
    try {
      visits = (parseInt(localStorage.getItem(VISIT_KEY), 10) || 0) + 1;
      localStorage.setItem(VISIT_KEY, String(visits));
    } catch (e) { return; }

    var deferred = null;
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferred = e;

      var dismissed = false;
      try { dismissed = localStorage.getItem(INSTALL_DISMISSED) === "1"; } catch (err) {}
      if (dismissed || visits < 3) return;

      var banner = $("#installBanner");
      if (!banner) return;
      banner.classList.remove("hidden");

      var accept = banner.querySelector("[data-install-accept]");
      var close = banner.querySelector("[data-install-dismiss]");
      if (accept) {
        accept.addEventListener("click", function () {
          banner.classList.add("hidden");
          if (deferred) { deferred.prompt(); deferred = null; }
        });
      }
      if (close) {
        close.addEventListener("click", function () {
          banner.classList.add("hidden");
          try { localStorage.setItem(INSTALL_DISMISSED, "1"); } catch (err) {}
        });
      }
    });
  }

  /* ------------------------------------------------------------------
     Auto-submitting filter selects (staff consoles, sort dropdowns).
     ------------------------------------------------------------------ */
  function initAutoSubmit() {
    $$("[data-autosubmit]").forEach(function (el) {
      el.addEventListener("change", function () {
        if (el.form) el.form.submit();
      });
    });
  }

  d.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initMenus();
    initConfirm();
    initPasswordUI();
    initResendCountdown();
    initOtpInput();
    initTabs();
    initNotificationBadge();
    initRecentSearches();
    initDragReorder();
    initImagePreview();
    initShare();
    initAutoSubmit();
    initInstallPrompt();
    initServiceWorker();
  });
})();
