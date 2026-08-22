// TerraTime Pillar 1 — offline viewer. No build step, no CDN: MapLibre GL and
// Chart.js are vendored in vendor/, and all hex data is embedded (not
// fetched) via data/hexes.js, so this page works from a plain double-click.

(function () {
  "use strict";

  // ---------------------------------------------------------------------
  // Pure helpers (color scales, domains, curve math) — no DOM/map/chart
  // references, so these are easy to unit-test in isolation (see
  // tests/viewer/test_app_logic.js, which imports this file under Node).
  // ---------------------------------------------------------------------

  const LIFECYCLE_COLORS = {
    Undeveloped: "#4b5563",
    Emerging: "#38bdf8",
    Accelerating: "#f59e0b",
    Maturing: "#a855f7",
    Saturated: "#16a34a",
    insufficient_signal: "#6b7280",
  };
  const NEUTRAL_COLOR = "#30363d";

  function computeDomain(features, prop, loPct, hiPct) {
    loPct = loPct === undefined ? 0.02 : loPct;
    hiPct = hiPct === undefined ? 0.98 : hiPct;
    const values = [];
    for (const f of features) {
      const v = f.properties[prop];
      if (v !== null && v !== undefined && Number.isFinite(v)) values.push(v);
    }
    if (values.length === 0) return { min: 0, max: 1 };
    values.sort((a, b) => a - b);
    const lo = values[Math.max(0, Math.floor(values.length * loPct))];
    const hi = values[Math.min(values.length - 1, Math.ceil(values.length * hiPct) - 1)];
    if (lo === hi) return { min: lo - 1, max: hi + 1 };
    return { min: lo, max: hi };
  }

  function velocityColorExpression(domain) {
    return [
      "case", ["==", ["get", "velocity_2026"], null], NEUTRAL_COLOR,
      ["interpolate", ["linear"], ["get", "velocity_2026"],
        domain.min, "#123736",
        domain.min + (domain.max - domain.min) * 0.33, "#1f9e89",
        domain.min + (domain.max - domain.min) * 0.66, "#f4d35e",
        domain.max, "#c1272d",
      ],
    ];
  }

  function accelerationColorExpression(domain) {
    const bound = Math.max(Math.abs(domain.min), Math.abs(domain.max), 1e-9);
    return [
      "case", ["==", ["get", "acceleration_2026"], null], NEUTRAL_COLOR,
      ["interpolate", ["linear"], ["get", "acceleration_2026"],
        -bound, "#2563eb",
        0, "#30363d",
        bound, "#f85149",
      ],
    ];
  }

  function confidenceColorExpression() {
    return ["interpolate", ["linear"], ["get", "confidence"], 0, "#30363d", 1, "#3fb950"];
  }

  function t0ColorExpression(domain) {
    return [
      "case", ["==", ["get", "t0"], null], NEUTRAL_COLOR,
      ["interpolate", ["linear"], ["get", "t0"],
        domain.min, "#2563eb",
        domain.min + (domain.max - domain.min) * 0.5, "#a855f7",
        domain.max, "#f59e0b",
      ],
    ];
  }

  function lifecycleColorExpression() {
    const expr = ["match", ["get", "lifecycle"]];
    for (const [k, v] of Object.entries(LIFECYCLE_COLORS)) { expr.push(k, v); }
    expr.push(NEUTRAL_COLOR);
    return expr;
  }

  function buildColorExpression(layerKey, features) {
    if (layerKey === "lifecycle") return { expr: lifecycleColorExpression(), domain: null };
    if (layerKey === "confidence") return { expr: confidenceColorExpression(), domain: { min: 0, max: 1 } };
    if (layerKey === "acceleration_2026") {
      const d = computeDomain(features, "acceleration_2026");
      return { expr: accelerationColorExpression(d), domain: d };
    }
    if (layerKey === "t0") {
      const d = computeDomain(features, "t0");
      return { expr: t0ColorExpression(d), domain: d };
    }
    const d = computeDomain(features, "velocity_2026");
    return { expr: velocityColorExpression(d), domain: d };
  }

  // Analytic logistic model, mirroring src/terratime/fit/models.py exactly.
  function logistic(t, K, r, t0) { return K / (1 + Math.exp(-r * (t - t0))); }
  function velocityFromF(F, K, r) { return r * F * (1 - F / K); }

  function sampleFittedCurve(K, r, t0, tStart, tEnd, n) {
    n = n || 60;
    const years = [], F = [], v = [];
    for (let i = 0; i < n; i++) {
      const t = tStart + ((tEnd - tStart) * i) / (n - 1);
      const f = logistic(t, K, r, t0);
      years.push(t);
      F.push(f);
      v.push(velocityFromF(f, K, r));
    }
    return { years, F, v };
  }

  function topAccelerating(features, n) {
    n = n || 10;
    return features
      .filter((f) => f.properties.tier === "tier1" && Number.isFinite(f.properties.acceleration_2026))
      .slice()
      .sort((a, b) => b.properties.acceleration_2026 - a.properties.acceleration_2026)
      .slice(0, n);
  }

  // Exposed for the Node-based logic tests; harmless in the browser.
  const TerraTimeLogic = {
    computeDomain, velocityColorExpression, accelerationColorExpression,
    confidenceColorExpression, t0ColorExpression, lifecycleColorExpression,
    buildColorExpression, logistic, velocityFromF, sampleFittedCurve, topAccelerating,
    LIFECYCLE_COLORS,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = TerraTimeLogic;
  if (typeof window !== "undefined") window.TerraTimeLogic = TerraTimeLogic;

  // ---------------------------------------------------------------------
  // App wiring — only runs in the browser.
  // ---------------------------------------------------------------------
  if (typeof window === "undefined" || typeof document === "undefined") return;
  if (typeof maplibregl === "undefined") return; // guards Node --check imports

  const DATA = window.TERRATIME_DATA || { provenance: "SIMULATED DATA", geojson: { type: "FeatureCollection", features: [] }, observations: {} };
  const FEATURES = DATA.geojson.features;
  const ALL_TIERS = ["tier1", "tier2", "tier3", "saturated_static", "undeveloped"];

  let activeLayer = "velocity_2026";
  let visibleTiers = new Set(ALL_TIERS);

  function initProvenanceBadge() {
    const badge = document.getElementById("provenance-badge");
    const isLive = /^LIVE/i.test(DATA.provenance || "");
    badge.textContent = DATA.provenance || "SIMULATED DATA";
    badge.className = isLive ? "live" : "simulated";
  }

  function initTierFilters() {
    const container = document.getElementById("tier-filters");
    container.innerHTML = "";
    ALL_TIERS.forEach((tier) => {
      const label = document.createElement("label");
      label.className = "tier-option";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = true;
      input.dataset.tier = tier;
      input.addEventListener("change", onTierFilterChange);
      label.appendChild(input);
      label.appendChild(document.createTextNode(tier));
      container.appendChild(label);
    });
  }

  function onTierFilterChange() {
    visibleTiers = new Set(
      Array.from(document.querySelectorAll("#tier-filters input:checked")).map((el) => el.dataset.tier)
    );
    applyTierFilter();
  }

  function applyTierFilter() {
    map.setFilter("hex-fill", ["in", ["get", "tier"], ["literal", Array.from(visibleTiers)]]);
    map.setFilter("hex-outline", ["in", ["get", "tier"], ["literal", Array.from(visibleTiers)]]);
  }

  function renderLegend(layerKey, domain) {
    const el = document.getElementById("legend");
    if (layerKey === "lifecycle") {
      el.innerHTML = '<div id="legend-categorical"></div>';
      const cat = document.getElementById("legend-categorical");
      Object.entries(TerraTimeLogic.LIFECYCLE_COLORS).forEach(([name, color]) => {
        const row = document.createElement("div");
        row.className = "cat-row";
        row.innerHTML = `<span class="swatch" style="background:${color}"></span><span>${name}</span>`;
        cat.appendChild(row);
      });
      return;
    }
    const gradients = {
      velocity_2026: "linear-gradient(90deg, #123736, #1f9e89, #f4d35e, #c1272d)",
      acceleration_2026: "linear-gradient(90deg, #2563eb, #30363d, #f85149)",
      confidence: "linear-gradient(90deg, #30363d, #3fb950)",
      t0: "linear-gradient(90deg, #2563eb, #a855f7, #f59e0b)",
    };
    const fmt = (v) => (layerKey === "t0" ? Math.round(v) : v.toFixed(3));
    el.innerHTML = `
      <div id="legend-gradient" style="background:${gradients[layerKey]}"></div>
      <div id="legend-labels"><span>${fmt(domain.min)}</span><span>${fmt(domain.max)}</span></div>
    `;
  }

  function applyLayer(layerKey) {
    activeLayer = layerKey;
    const { expr, domain } = TerraTimeLogic.buildColorExpression(layerKey, FEATURES);
    map.setPaintProperty("hex-fill", "fill-color", expr);
    renderLegend(layerKey, domain || { min: 0, max: 1 });
  }

  function initLayerControls() {
    document.querySelectorAll('input[name="layer"]').forEach((input) => {
      input.addEventListener("change", (e) => applyLayer(e.target.value));
    });
  }

  function fmtNum(v, digits) {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    return v.toFixed(digits === undefined ? 3 : digits);
  }

  function metricRow(label, value) {
    return `<div class="k">${label}</div><div class="v">${value}</div>`;
  }

  function renderSidePanel(props) {
    const panel = document.getElementById("sidepanel");
    const content = document.getElementById("sidepanel-content");
    const tierClass = props.tier;

    let html = `
      <h2>${props.h3_index}</h2>
      <div class="hexid">lat ${fmtNum(props.centroid_lat, 4)}, lon ${fmtNum(props.centroid_lon, 4)} &middot; ${fmtNum(props.area_m2, 0)} m&sup2;</div>
      <span class="badge ${tierClass}">${props.tier}</span>
      <span class="badge ${props.lifecycle}">${props.lifecycle}</span>
      <div class="metric-grid">
        ${metricRow("K (carrying capacity)", fmtNum(props.K))}
        ${metricRow("r (growth rate)", fmtNum(props.r))}
        ${metricRow("t0 (inflection year)", props.t0 !== null ? fmtNum(props.t0, 1) : "—")}
        ${metricRow("Velocity (frac/yr)", fmtNum(props.velocity_2026, 4))}
        ${metricRow("Velocity (m&sup2;/yr)", fmtNum(props.velocity_m2_per_year, 0))}
        ${metricRow("Acceleration", fmtNum(props.acceleration_2026, 5))}
        ${metricRow("Peak velocity", fmtNum(props.peak_velocity, 4))}
        ${metricRow("Years to inflection", fmtNum(props.years_to_inflection, 1))}
        ${metricRow("Years to saturation", fmtNum(props.years_to_saturation, 1))}
        ${metricRow("R&sup2;", fmtNum(props.r_squared))}
        ${metricRow("Confidence", fmtNum(props.confidence))}
        ${metricRow("Sen slope (robust)", fmtNum(props.sen_slope, 4))}
        ${metricRow("Isotonic adj.", fmtNum(props.isotonic_adjustment, 4))}
      </div>
      <div class="chart-wrap">
        <div class="chart-label">Observed vs. fitted S-curve</div>
        <canvas id="chart-fit" height="140"></canvas>
      </div>
      <div class="chart-wrap">
        <div class="chart-label">Velocity (dF/dt)</div>
        <canvas id="chart-derivative" height="90"></canvas>
      </div>
    `;
    const nonTier1Note = {
      tier2: `Tier 2: logistic fit not reliable enough to report K/r/t0. Showing the observed series${Number.isFinite(props.sen_slope) ? " and its robust (Theil-Sen) slope" : ""} instead.`,
      tier3: "Tier 3: insufficient signal to fit a curve. Showing the observed series only.",
      saturated_static: "Fully built out for the entire observed period — no curve fit needed.",
      undeveloped: "Negligible built-up area observed — no curve fit needed.",
    }[props.tier];
    if (nonTier1Note) {
      html += `<div class="note">${nonTier1Note}</div>`;
    }
    content.innerHTML = html;
    panel.classList.add("open");

    renderCharts(props);
  }

  let fitChart = null, derivChart = null;

  function renderCharts(props) {
    const obs = (DATA.observations && DATA.observations[props.h3_index]) || [];
    const obsYears = obs.map((p) => p[0]);
    const obsValues = obs.map((p) => p[1]);

    const fitCtx = document.getElementById("chart-fit").getContext("2d");
    const derivCtx = document.getElementById("chart-derivative").getContext("2d");
    if (fitChart) fitChart.destroy();
    if (derivChart) derivChart.destroy();

    const datasets = [{
      label: "Observed",
      data: obs.map((p) => ({ x: p[0], y: p[1] })),
      type: "scatter",
      backgroundColor: "#e6edf3",
      pointRadius: 4,
    }];
    let derivDatasets = [];

    if (props.tier === "tier1" && Number.isFinite(props.K)) {
      const tStart = Math.min(props.first_year_obs, obsYears[0] || props.first_year_obs) - 1;
      const tEnd = Math.max(props.last_year_obs, props.t0 + 3) + 2;
      const curve = TerraTimeLogic.sampleFittedCurve(props.K, props.r, props.t0, tStart, tEnd);
      datasets.push({
        label: "Fitted S-curve",
        data: curve.years.map((y, i) => ({ x: y, y: curve.F[i] })),
        type: "line",
        borderColor: "#58a6ff",
        backgroundColor: "transparent",
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.15,
      });
      derivDatasets.push({
        label: "dF/dt",
        data: curve.years.map((y, i) => ({ x: y, y: curve.v[i] })),
        type: "line",
        borderColor: "#f59e0b",
        backgroundColor: "rgba(245,158,11,0.15)",
        pointRadius: 0,
        borderWidth: 2,
        fill: true,
      });
    } else if (Number.isFinite(props.sen_slope) && obsYears.length > 1) {
      const x0 = obsYears[0], x1 = obsYears[obsYears.length - 1];
      const y0 = obsValues[0];
      datasets.push({
        label: "Theil-Sen slope",
        data: [{ x: x0, y: y0 }, { x: x1, y: y0 + props.sen_slope * (x1 - x0) }],
        type: "line",
        borderColor: "#d29922",
        borderDash: [6, 4],
        pointRadius: 0,
        borderWidth: 2,
      });
    }

    fitChart = new Chart(fitCtx, {
      type: "line", // default controller; individual datasets override via their own `type`
      data: { datasets },
      options: chartOptions("Built-up fraction"),
    });

    derivChart = new Chart(derivCtx, {
      type: "line",
      data: { datasets: derivDatasets },
      options: chartOptions("dF/dt (frac/yr)"),
    });
  }

  function chartOptions(yLabel) {
    return {
      responsive: true,
      animation: false,
      scales: {
        x: { type: "linear", ticks: { color: "#8b949e" }, grid: { color: "rgba(255,255,255,0.06)" } },
        y: { title: { display: true, text: yLabel, color: "#8b949e" }, ticks: { color: "#8b949e" }, grid: { color: "rgba(255,255,255,0.06)" } },
      },
      plugins: { legend: { labels: { color: "#e6edf3", boxWidth: 12, font: { size: 10 } } } },
    };
  }

  function initTop10Panel() {
    const top = TerraTimeLogic.topAccelerating(FEATURES, 10);
    const tbody = document.getElementById("top10-rows");
    tbody.innerHTML = "";
    top.forEach((f) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${f.properties.h3_index.slice(-6)}</td><td>${fmtNum(f.properties.acceleration_2026, 5)}</td><td>${f.properties.lifecycle}</td>`;
      tr.addEventListener("click", () => {
        map.flyTo({ center: [f.properties.centroid_lon, f.properties.centroid_lat], zoom: 15 });
        renderSidePanel(f.properties);
      });
      tbody.appendChild(tr);
    });

    document.getElementById("top10-toggle").addEventListener("click", () => {
      const body = document.getElementById("top10-body");
      const caret = document.getElementById("top10-caret");
      body.classList.toggle("collapsed");
      caret.innerHTML = body.classList.contains("collapsed") ? "&#9656;" : "&#9662;";
    });
  }

  // --- Map init ---
  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        carto: {
          type: "raster",
          tiles: ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"],
          tileSize: 256,
          attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
        },
      },
      layers: [{ id: "carto", type: "raster", source: "carto" }],
    },
    center: [77.15, 28.64],
    zoom: 10,
  });
  // Tile-load failures (offline demo, no network) are expected and should
  // not break the page — but still log to the console so a real bug isn't
  // silently swallowed.
  map.on("error", (e) => console.error("MapLibre error:", e && e.error ? e.error.message : e));

  map.on("load", () => {
    map.addSource("hexes", { type: "geojson", data: DATA.geojson });
    map.addLayer({
      id: "hex-fill",
      type: "fill",
      source: "hexes",
      paint: { "fill-color": "#1f9e89", "fill-opacity": 0.75 },
    });
    map.addLayer({
      id: "hex-outline",
      type: "line",
      source: "hexes",
      paint: { "line-color": "rgba(255,255,255,0.15)", "line-width": 0.5 },
    });

    initProvenanceBadge();
    initTierFilters();
    initLayerControls();
    applyLayer(activeLayer);
    initTop10Panel();

    map.on("click", "hex-fill", (e) => {
      if (e.features && e.features.length) renderSidePanel(e.features[0].properties);
    });
    map.on("mouseenter", "hex-fill", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "hex-fill", () => { map.getCanvas().style.cursor = ""; });

    document.getElementById("sidepanel-close").addEventListener("click", () => {
      document.getElementById("sidepanel").classList.remove("open");
    });
  });
})();
