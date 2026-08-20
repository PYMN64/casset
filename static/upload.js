// Casset — upload.html progressive enhancement: drag & drop, client-side
// pre-validation, real XHR progress bar, auto-detected audio duration, and
// a cover-art preview. The plain <form method=post enctype=multipart> still
// works with JS disabled — this only intercepts submit when it's available.

(function () {
  const AUDIO_EXTS = ["mp3", "wav", "m4a", "ogg", "flac", "aac"];
  const VIDEO_EXTS = ["mp4", "webm", "mov", "mkv"];
  const COVER_EXTS = ["jpg", "jpeg", "png", "webp"];
  const AUDIO_MAX_BYTES = 150 * 1024 * 1024;
  const COVER_MAX_BYTES = 5 * 1024 * 1024;

  function ext(file) {
    const parts = (file.name || "").toLowerCase().split(".");
    return parts.length > 1 ? parts.pop() : "";
  }
  function fmtSize(bytes) {
    if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return Math.round(bytes / 1024) + " KB";
  }

  function setFieldError(input, message) {
    let el = input.parentElement.querySelector(".field-error");
    if (!el) {
      el = document.createElement("div");
      el.className = "field-error err";
      input.parentElement.appendChild(el);
    }
    el.textContent = message || "";
    el.style.display = message ? "block" : "none";
  }

  function validateFile(input, { exts, maxBytes, label }) {
    const file = input.files && input.files[0];
    let ok = true;
    if (!file) {
      setFieldError(input, "");
    } else {
      const e = ext(file);
      if (exts && !exts.includes(e)) {
        setFieldError(input, `فرمت «.${e}» برای ${label} پشتیبانی نمی‌شود. فرمت‌های مجاز: ${exts.join(", ")}`);
        ok = false;
      } else if (maxBytes && file.size > maxBytes) {
        setFieldError(input, `حجم فایل (${fmtSize(file.size)}) از سقف مجاز (${fmtSize(maxBytes)}) بیشتر است.`);
        ok = false;
      } else {
        setFieldError(input, "");
      }
    }
    input.dataset.validated = ok ? "1" : "0";
    return ok;
  }

  // ---- Drag & drop wrapper: makes a container drop files onto a real
  // <input type=file> so the existing Django-rendered field stays the
  // single source of truth (no parallel upload path to keep in sync). ----
  function wireDropzone(input, opts) {
    if (!input) return;
    const zone = document.createElement("div");
    zone.className = "dropzone";
    zone.innerHTML = `
      <div class="dropzone__hint">فایل را اینجا رها کن یا کلیک کن</div>
      <div class="dropzone__file muted small"></div>
    `;
    input.parentElement.insertBefore(zone, input);
    input.classList.add("dropzone__input");
    zone.appendChild(input);

    const fileLabel = zone.querySelector(".dropzone__file");
    function refreshLabel() {
      const file = input.files && input.files[0];
      fileLabel.textContent = file ? `${file.name} (${fmtSize(file.size)})` : "";
    }

    ["dragenter", "dragover"].forEach((evt) => {
      zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.add("dropzone--over"); });
    });
    ["dragleave", "drop"].forEach((evt) => {
      zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.remove("dropzone--over"); });
    });
    zone.addEventListener("drop", (e) => {
      const files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length) {
        input.files = files;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    input.addEventListener("change", () => {
      refreshLabel();
      if (opts) validateFile(input, opts);
      if (opts && opts.onFile) opts.onFile(input.files && input.files[0]);
    });
  }

  // ---- Auto-detect audio duration client-side (UX only — server still
  // trusts nothing from the client and validates independently). ----
  function wireDurationAutoDetect(audioInput, durationInput) {
    if (!audioInput || !durationInput) return;
    const hint = document.createElement("div");
    hint.className = "muted small";
    hint.textContent = "";
    durationInput.parentElement.appendChild(hint);

    audioInput.addEventListener("change", () => {
      const file = audioInput.files && audioInput.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      const probe = new Audio();
      probe.preload = "metadata";
      probe.addEventListener("loadedmetadata", () => {
        URL.revokeObjectURL(url);
        if (Number.isFinite(probe.duration) && probe.duration > 0) {
          durationInput.value = Math.ceil(probe.duration / 60);
          hint.textContent = `مدت شناسایی‌شده: ~${Math.ceil(probe.duration / 60)} دقیقه (در صورت نیاز ویرایش کن)`;
        }
      });
      probe.addEventListener("error", () => URL.revokeObjectURL(url));
      probe.src = url;
    });
  }

  // ---- Cover preview ----
  function wireCoverPreview(coverInput) {
    if (!coverInput) return;
    const preview = document.createElement("div");
    preview.className = "cover-preview";
    coverInput.parentElement.appendChild(preview);

    coverInput.addEventListener("change", () => {
      const file = coverInput.files && coverInput.files[0];
      if (!file || !validateFile(coverInput, { exts: COVER_EXTS, maxBytes: COVER_MAX_BYTES, label: "کاور" })) {
        preview.style.backgroundImage = "";
        preview.classList.remove("cover-preview--visible");
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        preview.style.backgroundImage = `url('${reader.result}')`;
        preview.classList.add("cover-preview--visible");
      };
      reader.readAsDataURL(file);
    });
  }

  // ---- Real upload progress via XHR (fetch has no progress event) ----
  function wireProgressSubmit(form, submitBtn, progressWrap, progressBar, progressLabel) {
    if (!form) return;
    form.addEventListener("submit", function (e) {
      if (form.dataset.submitting) { e.preventDefault(); return; }

      // Run all field validators one last time before sending.
      let ok = true;
      form.querySelectorAll("input[type=file]").forEach((input) => {
        if (input.dataset.validated === "0") ok = false;
      });
      if (!ok) { e.preventDefault(); return; }

      e.preventDefault();
      form.dataset.submitting = "1";
      submitBtn.disabled = true;
      submitBtn.textContent = "در حال آپلود…";
      if (progressWrap) progressWrap.style.display = "block";

      const xhr = new XMLHttpRequest();
      xhr.open("POST", form.action || window.location.href, true);
      xhr.upload.addEventListener("progress", (evt) => {
        if (!evt.lengthComputable) return;
        const pct = Math.round((evt.loaded / evt.total) * 100);
        if (progressBar) progressBar.style.width = pct + "%";
        if (progressLabel) progressLabel.textContent = `در حال آپلود… ${pct}٪ (${fmtSize(evt.loaded)} / ${fmtSize(evt.total)})`;
      });
      xhr.addEventListener("load", () => {
        // Success path redirects to /my/tracks/ — XHR follows the redirect
        // transparently, so responseURL tells us where we ended up.
        if (xhr.responseURL && !xhr.responseURL.includes(window.location.pathname)) {
          window.location.href = xhr.responseURL;
          return;
        }
        // Validation failed server-side (e.g. a check JS couldn't catch) —
        // the server re-rendered this same page with error messages; swap
        // it in so the user sees exactly what the server said.
        document.open();
        document.write(xhr.responseText);
        document.close();
      });
      xhr.addEventListener("error", () => {
        submitBtn.disabled = false;
        submitBtn.textContent = "ذخیره پیش‌نویس";
        form.dataset.submitting = "";
        if (progressLabel) progressLabel.textContent = "خطا در آپلود — دوباره تلاش کن.";
      });
      xhr.send(new FormData(form));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const audioInput = document.getElementById("id_audio");
    const videoInput = document.getElementById("id_video");
    const coverInput = document.getElementById("id_cover");
    const durationInput = document.getElementById("id_duration_minutes");

    wireDropzone(audioInput, { exts: AUDIO_EXTS, maxBytes: AUDIO_MAX_BYTES, label: "فایل صوتی" });
    wireDropzone(videoInput, { exts: VIDEO_EXTS, label: "فایل ویدیو" });
    wireDurationAutoDetect(audioInput, durationInput);
    wireCoverPreview(coverInput);

    const form = document.getElementById("uploadForm");
    const btn = document.getElementById("uploadSubmitBtn");
    const progressWrap = document.getElementById("uploadProgress");
    const progressBar = document.getElementById("uploadProgressBar");
    const progressLabel = document.getElementById("uploadProgressLabel");
    wireProgressSubmit(form, btn, progressWrap, progressBar, progressLabel);
  });
})();
