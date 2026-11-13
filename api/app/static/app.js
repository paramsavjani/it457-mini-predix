const REFRESH_MS = 3000;
let selected = null;

async function getJSON(url) {
  const start = performance.now();
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  const data = await res.json();
  return { data, ms: performance.now() - start };
}

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
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
      <div class="card ${a.id === selected ? "selected" : ""}" data-id="${esc(a.id)}">
        <div class="top">
          <span class="name">${esc(a.name)}</span>
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

const charts = {};

function lineChart(id, label, color, limits) {
  const limitSets = limits.map(([value, name, c]) => ({
    label: name, data: [], borderColor: c, borderDash: [6, 4], borderWidth: 1, pointRadius: 0, _limit: value,
  }));
  return new Chart(document.getElementById(id), {
    type: "line",
    data: { labels: [], datasets: [{ label, data: [], borderColor: color, borderWidth: 2, pointRadius: 0, tension: 0.3 }, ...limitSets] },
    options: {
      animation: false,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#8b98a5", boxWidth: 12 } } },
      scales: {
        x: { ticks: { color: "#8b98a5", maxTicksLimit: 6 }, grid: { color: "#26313d" } },
        y: { ticks: { color: "#8b98a5" }, grid: { color: "#26313d" } },
      },
    },
  });
}

function updateChart(chart, labels, values) {
  chart.data.labels = labels;
  chart.data.datasets[0].data = values;
  chart.data.datasets.slice(1).forEach(ds => { ds.data = labels.map(() => ds._limit); });
  chart.update();
}

async function refreshCharts() {
  if (!selected || typeof Chart === "undefined") return;
  if (!charts.temp) {
    charts.temp = lineChart("chart-temp", "Temperature (°C)", "#58a6ff", [[90, "Warning", "#d29922"], [105, "Critical", "#f85149"]]);
    charts.vib = lineChart("chart-vib", "Vibration (mm/s)", "#a371f7", [[7, "Warning", "#d29922"], [10, "Critical", "#f85149"]]);
  }
  const { data } = await getJSON(`/api/readings?asset_id=${encodeURIComponent(selected)}&limit=90`);
  const labels = data.map(r => new Date(r.ts).toLocaleTimeString());
  updateChart(charts.temp, labels, data.map(r => r.temperature));
  updateChart(charts.vib, labels, data.map(r => r.vibration));
  document.getElementById("chart-title").textContent = `Sensor history: ${selected}`;
}

async function refreshAlerts() {
  const { data } = await getJSON("/api/alerts?limit=12");
  if (!data.length) return;
  document.getElementById("alerts").innerHTML = data.map(a => `
    <tr>
      <td>${new Date(a.ts).toLocaleTimeString()}</td>
      <td>${esc(a.asset_id)}</td>
      <td class="${a.severity === "critical" ? "critical" : "degraded"}">${esc(a.severity)}</td>
      <td>${esc(a.message)}</td>
    </tr>`).join("");
}

function setConnection(online) {
  const el = document.getElementById("conn");
  el.textContent = online ? "online" : "offline";
  el.className = `conn ${online ? "online" : "offline"}`;
}

async function refresh() {
  try {
    await Promise.all([refreshStats(), refreshFleet(), refreshCharts(), refreshAlerts()]);
    setConnection(true);
  } catch (err) {
    console.error(err);
    setConnection(false);
  }
}

refresh();
setInterval(refresh, REFRESH_MS);
