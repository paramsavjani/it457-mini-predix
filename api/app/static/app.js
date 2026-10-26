const REFRESH_MS = 3000;
let selected = null;

async function getJSON(url) {
  const start = performance.now();
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  const data = await res.json();
  return { data, ms: performance.now() - start };
}

function fmt(n, digits = 1) {
  return n === null || n === undefined ? "-" : Number(n).toFixed(digits);
}

async function refreshStats() {
  const { data, ms } = await getJSON("/api/system");
  document.getElementById("deployment").textContent = data.deployment;
  document.getElementById("s-readings").textContent = data.readings.toLocaleString();
  document.getElementById("s-alerts").textContent = data.alerts.toLocaleString();
  document.getElementById("s-load").textContent = fmt(data.load_average["1m"], 2);
  document.getElementById("s-mem").textContent = data.memory ? `${data.memory.used_percent}%` : "-";
  document.getElementById("s-latency").textContent = `${ms.toFixed(0)} ms`;
}

async function refreshFleet() {
  const { data } = await getJSON("/api/twin");
  const latest = Object.fromEntries((await getJSON("/api/readings/latest")).data.map(r => [r.asset_id, r]));
  if (!selected && data.length) selected = data[0].id;

  document.getElementById("fleet").innerHTML = data.map(a => {
    const r = latest[a.id] || {};
    const predict = a.minutes_to_critical !== null
      ? `Predicted critical in ~${fmt(a.minutes_to_critical, 0)} min`
      : "";
    return `
      <div class="card ${a.id === selected ? "selected" : ""}" data-id="${a.id}">
        <div class="top">
          <span class="name">${a.name}</span>
          <span class="pill ${a.status}">${a.status}</span>
        </div>
        <div class="score ${a.status}">${a.health ?? "-"}</div>
        <div class="meta">${fmt(r.temperature)} &deg;C &middot; ${fmt(r.vibration, 2)} mm/s &middot; ${fmt(r.rpm, 0)} rpm</div>
        <div class="meta">Trend ${a.temp_trend >= 0 ? "+" : ""}${fmt(a.temp_trend, 2)} &deg;C/min</div>
        <div class="predict">${predict}</div>
      </div>`;
  }).join("");

  document.querySelectorAll(".card").forEach(card =>
    card.addEventListener("click", () => { selected = card.dataset.id; refresh(); })
  );
}

async function refresh() {
  try {
    await Promise.all([refreshStats(), refreshFleet()]);
  } catch (err) {
    console.error(err);
  }
}

refresh();
setInterval(refresh, REFRESH_MS);
