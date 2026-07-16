// activity.js — logic for activity.html only. Requires common.js loaded first.

wireSourceTypeToggle("aType", "aSourceField", "aSource", "aFileField");

document.getElementById("activityForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("aName").value.trim();
  const type = document.getElementById("aType").value;
  const submitBtn = e.target.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "Starting…";
  try {
    let source;
    if (type === "file") {
      const file = document.getElementById("aFile").files[0];
      if (!file) throw new Error("Choose a video file first");
      source = await uploadVideo(file);
    } else {
      source = document.getElementById("aSource").value.trim() || "0";
    }
    await postForm("/api/activity/start", { name, source });
    e.target.reset();
    document.getElementById("aSourceField").style.display = "block";
    document.getElementById("aFileField").style.display = "none";
    refreshActivitySources();
  } catch (err) {
    alert(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Start source";
  }
});

async function stopActivitySource(name) {
  try {
    await postForm("/api/activity/stop", { name });
  } catch (err) {
    alert(err.message);
  }
  refreshActivitySources();
}

let knownActivitySources = new Set();

async function refreshActivitySources() {
  let sources;
  try {
    sources = await getJSON("/api/activity");
    setApiStatus(true);
  } catch {
    setApiStatus(false);
    return;
  }

  document.getElementById("actCount").textContent = sources.length;

  const listEl = document.getElementById("activitySourceList");
  listEl.innerHTML = sources.length
    ? sources
        .map(
          (s) => `
        <div class="source-row">
          <div class="info">
            <span class="name mono"><span class="live-dot amber"></span> ${s.name}</span>
            <span class="src" title="${s.source}">${basename(s.source)}</span>
          </div>
          <button class="btn small danger" onclick="stopActivitySource('${s.name}')">Stop</button>
        </div>`
        )
        .join("")
    : `<div class="empty-state">No sources running yet.</div>`;

  const grid = document.getElementById("activityFeedGrid");
  if (!sources.length) {
    grid.innerHTML = `<div class="panel"><div class="empty-state">Add a source on the left to see live activity detection and the movement heatmap here.</div></div>`;
    knownActivitySources = new Set();
    return;
  }

  const currentNames = new Set(sources.map((s) => s.name));
  if (
    currentNames.size !== knownActivitySources.size ||
    [...currentNames].some((n) => !knownActivitySources.has(n))
  ) {
    grid.innerHTML = sources
      .map(
        (s) => `
      <div class="panel feed-card">
        <div class="feed-head">
          <span class="mono"><span class="live-dot amber"></span> ${s.name} · activity</span>
        </div>
        <div class="feed-stats" id="counts-${s.name}">
          <span class="stat-sit">SIT: 0</span><span class="stat-std">STD: 0</span><span class="stat-walk">WALK: 0</span><span class="stat-run">RUN: 0</span>
        </div>
        <div class="feed-img-wrap"><img id="feed-a-${s.name}" alt="${s.name} activity feed"></div>
      </div>
      <div class="panel feed-card">
        <div class="feed-head">
          <span class="mono"><span class="live-dot amber"></span> ${s.name} · heatmap</span>
        </div>
        <div class="feed-stats">
          <span class="mono" style="color:var(--muted-2);">live movement density</span>
        </div>
        <div class="feed-img-wrap"><img id="feed-h-${s.name}" alt="${s.name} heatmap feed"></div>
      </div>`
      )
      .join("");
    knownActivitySources = currentNames;
  }

  sources.forEach(async (s) => {
    const imgA = document.getElementById(`feed-a-${s.name}`);
    const imgH = document.getElementById(`feed-h-${s.name}`);
    if (imgA) imgA.src = `/api/activity-frame/${encodeURIComponent(s.name)}?t=${Date.now()}`;
    if (imgH) imgH.src = `/api/heatmap-frame/${encodeURIComponent(s.name)}?t=${Date.now()}`;

    try {
      const counts = await getJSON(`/api/activity-counts/${encodeURIComponent(s.name)}`);
      const el = document.getElementById(`counts-${s.name}`);
      if (!el) return;

      if (counts.counts) {
        const c = counts.counts;
        el.innerHTML = `
          <span class="stat-sit">SIT: ${c.Sitting || 0}</span>
          <span class="stat-std">STD: ${c.Standing || 0}</span>
          <span class="stat-walk">WALK: ${c.Walking || 0}</span>
          <span class="stat-run">RUN: ${c.Running || 0}</span>`;
      } else if (counts.error) {
        el.innerHTML = `<span style="color:var(--red);">Error: ${counts.error}</span>`;
      } else {
        el.innerHTML = `<span style="color:var(--muted-2);">Starting…</span>`;
      }
    } catch {
      /* ignore network errors; next poll will retry */
    }
  });
}

wireGridSizeControl("activityGridSize", "activityFeedGrid", 2);
refreshActivitySources();
setInterval(refreshActivitySources, 900);