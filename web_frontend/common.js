// common.js — shared helpers for both Sentinel dashboard pages.
// Loaded before weapon.js / activity.js on each page.

const API = ""; // same-origin

async function postForm(path, fields) {
  const body = new FormData();
  Object.entries(fields).forEach(([k, v]) => body.append(k, v));
  const res = await fetch(API + path, { method: "POST", body });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${path} failed (${res.status})`);
  }
  return res.json();
}

async function getJSON(path) {
  const res = await fetch(API + path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return res.json();
}

async function uploadVideo(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(API + "/api/upload-video", { method: "POST", body });
  if (!res.ok) throw new Error("Upload failed");
  const data = await res.json();
  return data.path;
}

function fmtTime(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

function basename(path) {
  if (!path) return path;
  const parts = String(path).split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

// Resizable feed grid (1 / 2 / 3 / 4 columns per row), remembered per page tab.
function wireGridSizeControl(controlId, gridId, defaultCols = 2) {
  const control = document.getElementById(controlId);
  const grid = document.getElementById(gridId);
  if (!control || !grid) return;

  function applyCols(n) {
    grid.className = grid.className.replace(/\bcols-\d\b/g, "").trim();
    grid.classList.add("feed-grid", `cols-${n}`);
    control.querySelectorAll(".gs-btn").forEach((b) => {
      b.classList.toggle("active", Number(b.dataset.cols) === n);
    });
  }

  control.querySelectorAll(".gs-btn").forEach((btn) => {
    btn.addEventListener("click", () => applyCols(Number(btn.dataset.cols)));
  });

  applyCols(defaultCols);
}

function setApiStatus(ok) {
  const dot = document.getElementById("apiDot");
  const label = document.getElementById("apiStatus");
  if (!dot || !label) return;
  dot.className = ok ? "live-dot" : "live-dot red";
  label.textContent = ok ? "api connected" : "api unreachable";
}

function tickClock() {
  const el = document.getElementById("clock");
  if (el) el.textContent = new Date().toLocaleTimeString();
}
setInterval(tickClock, 1000);
tickClock();

// Tabs (used on the weapon page; harmless no-op if a page has no tabs)
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => (p.style.display = "none"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).style.display = "block";
  });
});

// Source-type field toggling (webcam / RTSP / uploaded file)
function wireSourceTypeToggle(typeSelectId, sourceFieldId, sourceInputId, fileFieldId) {
  const typeSelect = document.getElementById(typeSelectId);
  const sourceField = document.getElementById(sourceFieldId);
  const sourceInput = document.getElementById(sourceInputId);
  const fileField = document.getElementById(fileFieldId);
  if (!typeSelect) return;
  const label = sourceField.querySelector("label");

  typeSelect.addEventListener("change", () => {
    const v = typeSelect.value;
    if (v === "file") {
      sourceField.style.display = "none";
      fileField.style.display = "block";
    } else {
      sourceField.style.display = "block";
      fileField.style.display = "none";
      if (v === "webcam") {
        label.textContent = "Device index";
        sourceInput.placeholder = "0";
      } else {
        label.textContent = "RTSP / HTTP stream URL";
        sourceInput.placeholder = "rtsp://192.168.1.10:554/stream1";
      }
    }
  });
}