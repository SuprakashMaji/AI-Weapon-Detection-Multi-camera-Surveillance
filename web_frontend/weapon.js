// weapon.js — logic for weapon.html only. Requires common.js loaded first.

wireSourceTypeToggle("wType", "wSourceField", "wSource", "wFileField");

function sanitizeNamePart(s) {
  return String(s)
    .replace(/\.[^/.]+$/, "")       // strip extension
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "cam";
}

function uniqueName(base, taken) {
  let candidate = base;
  let n = 2;
  while (taken.has(candidate)) {
    candidate = `${base}-${n}`;
    n++;
  }
  taken.add(candidate);
  return candidate;
}

document.getElementById("weaponForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const namePrefix = document.getElementById("wName").value.trim();
  const type = document.getElementById("wType").value;
  const submitBtn = e.target.querySelector("button[type=submit]");
  submitBtn.disabled = true;

  const errors = [];

  try {
    // Find names already running so auto-generated names don't collide.
    let taken = new Set();
    try {
      const existing = await getJSON("/api/weapon-cameras");
      taken = new Set(existing.map((c) => c.name));
    } catch {
      /* if this fails, we just risk a per-camera "already running" error below */
    }

    if (type === "file") {
      const files = Array.from(document.getElementById("wFile").files || []);
      if (!files.length) throw new Error("Choose at least one video file");

      const multiple = files.length > 1;

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        submitBtn.textContent = `Starting ${i + 1}/${files.length}…`;

        // Single file: use the typed name as-is (unchanged behavior).
        // Multiple files: treat the typed name as a prefix and derive one
        // camera name per file from its filename, auto-de-duplicated.
        const base = multiple
          ? `${namePrefix ? namePrefix + "-" : ""}${sanitizeNamePart(file.name)}`
          : namePrefix;
        const name = uniqueName(base, taken);

        try {
          const source = await uploadVideo(file);
          await postForm("/api/weapon-cameras/start", { name, source });
        } catch (err) {
          errors.push(`${file.name}: ${err.message}`);
        }
      }
    } else {
      // Webcam / RTSP — single source, unchanged behavior.
      const source = document.getElementById("wSource").value.trim() || "0";
      const name = uniqueName(namePrefix, taken);
      try {
        await postForm("/api/weapon-cameras/start", { name, source });
      } catch (err) {
        errors.push(err.message);
      }
    }

    e.target.reset();
    document.getElementById("wSourceField").style.display = "block";
    document.getElementById("wFileField").style.display = "none";
    refreshWeaponSources();

    if (errors.length) {
      alert(`Some cameras failed to start:\n\n${errors.join("\n")}`);
    }
  } catch (err) {
    alert(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Start camera(s)";
  }
});

async function stopWeaponCamera(name) {
  try {
    await postForm("/api/weapon-cameras/stop", { name });
  } catch (err) {
    alert(err.message);
  }
  refreshWeaponSources();
}

let knownWeaponCams = new Set();

async function refreshWeaponSources() {
  let cams;
  try {
    cams = await getJSON("/api/weapon-cameras");
    setApiStatus(true);
  } catch {
    setApiStatus(false);
    return;
  }

  document.getElementById("camCount").textContent = cams.length;

  const listEl = document.getElementById("weaponSourceList");
  listEl.innerHTML = cams.length
    ? cams
        .map(
          (c) => `
        <div class="source-row">
          <div class="info">
            <span class="name mono"><span class="live-dot"></span> ${c.name}</span>
            <span class="src" title="${c.source}">${basename(c.source)}</span>
          </div>
          <button class="btn small danger" onclick="stopWeaponCamera('${c.name}')">Stop</button>
        </div>`
        )
        .join("")
    : `<div class="empty-state">No cameras running yet.</div>`;

  const grid = document.getElementById("weaponFeedGrid");
  if (!cams.length) {
    grid.innerHTML = `<div class="panel"><div class="empty-state">Add a camera on the left to see its live, annotated feed here.</div></div>`;
    knownWeaponCams = new Set();
    return;
  }

  const currentNames = new Set(cams.map((c) => c.name));
  if (
    currentNames.size !== knownWeaponCams.size ||
    [...currentNames].some((n) => !knownWeaponCams.has(n))
  ) {
    grid.innerHTML = cams
      .map(
        (c) => `
      <div class="panel feed-card">
        <div class="feed-head">
          <span class="mono"><span class="live-dot"></span> ${c.name}</span>
          <span class="mono" style="color:var(--muted-2);font-size:10px;">weapon + re-id</span>
        </div>
        <div class="feed-stats" id="wcounts-${c.name}">
          <span class="stat-sit">SIT: 0</span><span class="stat-std">STD: 0</span><span class="stat-walk">WALK: 0</span><span class="stat-run">RUN: 0</span>
        </div>
        <div class="feed-img-wrap">
          <img id="feed-w-${c.name}" alt="${c.name} live feed">
        </div>
      </div>`
      )
      .join("");
    knownWeaponCams = currentNames;
  }

  cams.forEach(async (c) => {
    const img = document.getElementById(`feed-w-${c.name}`);
    if (img) img.src = `/api/frame/${encodeURIComponent(c.name)}?t=${Date.now()}`;

    try {
      const counts = await getJSON(`/api/weapon-activity-counts/${encodeURIComponent(c.name)}`);
      const el = document.getElementById(`wcounts-${c.name}`);
      if (!el) return;

      const cnt = counts.counts || {};
      el.innerHTML = `
        <span class="stat-sit">SIT: ${cnt.Sitting || 0}</span>
        <span class="stat-std">STD: ${cnt.Standing || 0}</span>
        <span class="stat-walk">WALK: ${cnt.Walking || 0}</span>
        <span class="stat-run">RUN: ${cnt.Running || 0}</span>`;
    } catch {
      // Non-fatal — leave the last known counts on screen.
    }
  });
}

async function refreshStats() {
  try {
    const stats = await getJSON("/api/stats");
    document.getElementById("kpiSuspects").textContent = stats.total_suspects;
    document.getElementById("kpiReid").textContent = stats.reid_matches;
    document.getElementById("kpiLogs").textContent = stats.evidence_logs;
    document.getElementById("kpiPistol").textContent = stats.pistol_cases;
    document.getElementById("kpiKnife").textContent = stats.knife_cases;
    document.getElementById("kpiConf").textContent = `${stats.avg_confidence}%`;
    setApiStatus(true);
  } catch {
    setApiStatus(false);
  }
}

async function refreshSuspects() {
  let suspects;
  try {
    suspects = await getJSON("/api/suspects");
  } catch {
    return;
  }

  const ids = Object.keys(suspects);
  const grid = document.getElementById("snapGrid");
  if (!ids.length) {
    grid.innerHTML = `<div class="empty-state">No suspects logged yet.</div>`;
    return;
  }

  grid.innerHTML = ids
    .map((id) => {
      const s = suspects[id];
      const cls = (s.weapon || "").toLowerCase();
      return `
      <div class="panel snap-card">
        <img src="/api/suspect-snapshot/${encodeURIComponent(id)}" alt="suspect ${id}" loading="lazy">
        <div class="cap">
          <span class="badge ${cls}">${s.weapon || "unknown"}</span><br>${id}
        </div>
      </div>`;
    })
    .join("");
}

// =====================================================
// Sound alerts (client-side, no server/audio-file needed)
// =====================================================
// Plays a beep in the browser the moment a NEW evidence-log entry shows
// up — an urgent triple-beep for a weapon detection, a single softer
// beep for a Re-ID match. Pure Web Audio API oscillator tones, so
// there's no audio file to ship or host.

let soundEnabled = localStorage.getItem("sentinelSoundAlerts") !== "off";
let audioCtx = null;
let knownLogKeys = null; // null = first load; don't beep for pre-existing history

function updateSoundButton() {
  const btn = document.getElementById("soundToggleBtn");
  if (!btn) return;
  btn.textContent = soundEnabled ? "🔊 Sound: ON" : "🔇 Sound: OFF";
  btn.classList.toggle("danger", !soundEnabled);
}

function getAudioCtx() {
  if (!audioCtx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    audioCtx = new Ctx();
  }
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

function beep(frequency, startTime, duration, volume = 0.25) {
  const ctx = getAudioCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "square";
  osc.frequency.value = frequency;
  gain.gain.setValueAtTime(volume, startTime);
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
  osc.connect(gain).connect(ctx.destination);
  osc.start(startTime);
  osc.stop(startTime + duration);
}

function playWeaponAlertSound() {
  if (!soundEnabled) return;
  const ctx = getAudioCtx();
  const now = ctx.currentTime;
  // Urgent alarm: high-low-high
  beep(1046, now, 0.16, 0.3);
  beep(784, now + 0.18, 0.16, 0.3);
  beep(1046, now + 0.36, 0.2, 0.3);
}

function playReidAlertSound() {
  if (!soundEnabled) return;
  const ctx = getAudioCtx();
  beep(660, ctx.currentTime, 0.18, 0.2);
}

document.getElementById("soundToggleBtn").addEventListener("click", () => {
  soundEnabled = !soundEnabled;
  localStorage.setItem("sentinelSoundAlerts", soundEnabled ? "on" : "off");
  updateSoundButton();
  if (soundEnabled) {
    getAudioCtx();
    beep(880, getAudioCtx().currentTime, 0.12, 0.25);
  }
});

updateSoundButton();

function checkForNewAlertSounds(logs) {
  const currentKeys = new Set(
    logs.map((log) => `${log.event}_${log.suspect_id}_${log.camera}_${log.timestamp}`)
  );

  if (knownLogKeys === null) {
    knownLogKeys = currentKeys;
    return;
  }

  let newWeapon = false;
  let newReid = false;

  for (const log of logs) {
    const key = `${log.event}_${log.suspect_id}_${log.camera}_${log.timestamp}`;
    if (!knownLogKeys.has(key)) {
      if (log.event === "WEAPON_DETECTED") newWeapon = true;
      else if (log.event === "REIDENTIFIED") newReid = true;
    }
  }

  knownLogKeys = currentKeys;

  if (newWeapon) playWeaponAlertSound();
  else if (newReid) playReidAlertSound();
}
async function refreshLogs() {
  let logs;
  try {
    logs = await getJSON("/api/logs");
  } catch {
    return;
  }

  const tbody = document.getElementById("logsTableBody");
  const alertList = document.getElementById("alertList");

  if (!Array.isArray(logs) || !logs.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No entries yet.</td></tr>`;
    alertList.innerHTML = `<div class="empty-state">No alerts yet.</div>`;
    return;
  }
  checkForNewAlertSounds(logs);
  const sorted = [...logs].reverse();

  tbody.innerHTML = sorted
    .slice(0, 200)
    .map((log) => {
      const weapon = (log.weapon || "—").toLowerCase();
      const sim = log.similarity != null ? `${(log.similarity * 100).toFixed(1)}%` : "—";
      return `<tr>
        <td class="mono">${fmtTime(log.timestamp)}</td>
        <td>${log.event || "—"}</td>
        <td>${log.weapon ? `<span class="badge ${weapon}">${log.weapon}</span>` : "—"}</td>
        <td>${log.camera || "—"}</td>
        <td class="mono">${sim}</td>
      </tr>`;
    })
    .join("");

  alertList.innerHTML = sorted
    .slice(0, 25)
    .map((log) => {
      const isWeapon = log.event === "WEAPON_DETECTED";
      const cls = isWeapon ? "weapon" : "reid";
      const msg = isWeapon
        ? `${log.weapon || "Weapon"} detected on ${log.camera || "camera"}`
        : `Suspect re‑identified on ${log.camera || "camera"}`;
      return `<div class="alert-item ${cls}">${msg}<span class="t">${fmtTime(log.timestamp)}</span></div>`;
    })
    .join("");
}

document.getElementById("clearEvidenceBtn").addEventListener("click", async () => {
  const sure = confirm(
    "This permanently deletes ALL suspects, evidence log entries, and " +
    "suspect snapshot images. This cannot be undone. Continue?"
  );
  if (!sure) return;

  try {
    await postForm("/api/reset-evidence", {});
    refreshSuspects();
    refreshLogs();
    refreshStats();
  } catch (err) {
    alert(err.message);
  }
});

wireGridSizeControl("weaponGridSize", "weaponFeedGrid", 2);
refreshWeaponSources();
refreshStats();
refreshSuspects();
refreshLogs();

setInterval(refreshWeaponSources, 900);
setInterval(refreshStats, 3000);
setInterval(refreshSuspects, 4000);
setInterval(refreshLogs, 3000);