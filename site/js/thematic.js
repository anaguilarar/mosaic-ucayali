/* Thematic layers: land cover (MapBiomas C4), canopy height (ETH 2020), forest loss (GEOBOSQUES),
   active-fire density (VIIRS) and burned area (MapBiomas fuego). Per-year tile sets share the
   year slider (#timebar); static sets (canopy, forest loss) hide it. Legends and the click panel
   are fed from the registry, the series JSONs and the two query COGs (geotiff.js). */

import { dataUrl } from "./config.js";
import { setVisibility } from "./layers.js";
const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };

const state = { reg: {}, active: null, year: {}, pointsYear: null, series: {}, tiffs: {}, lastClick: null };
let map, timebar;

const DEFS = {
  landcover: { prefix: "lulc-", urlKey: ["landcover", "urls", "tiles"], yearsKey: ["landcover", "years"] },
  fire: { prefix: "fired-", urlKey: ["fire", "urls", "density"], yearsKey: ["fire", "years"] },
  burned_area: { prefix: "burned-", urlKey: ["burned_area", "urls", "tiles"], yearsKey: ["burned_area", "years"] },
  canopy: { static: true, layerId: "canopy-tiles", urlKey: ["canopy", "urls", "tiles"] },
  forest_loss: { static: true, layerId: "loss-tiles", urlKey: ["forest_loss", "urls", "tiles"] },
};
const get = (o, path) => path.reduce((a, k) => (a ? a[k] : undefined), o);

export function layersFor(registry, pmUrl) {
  state.reg = registry;
  const sources = {}, layers = [];
  const add = (lid, f, opacity) => {
    sources[lid] = { type: "raster", url: pmUrl(f), tileSize: 256 };
    layers.push({ id: lid, type: "raster", source: lid, layout: { visibility: "none" },
                  paint: { "raster-resampling": "nearest", "raster-opacity": opacity } });
  };
  for (const d of Object.values(DEFS)) {
    const u = get(registry, d.urlKey);
    if (!u) continue;
    if (d.static) add(d.layerId, u, 0.85);
    else for (const [y, f] of Object.entries(u)) add(d.prefix + y, f, d.prefix === "lulc-" ? 0.8 : 0.85);
  }
  return { sources, layers };
}

let readyDone;
const ready = new Promise((r) => (readyDone = r));

export function init(mapRef) {
  map = mapRef;
  timebar = $("#timebar");
  readyDone();
  $("#yearSlider").addEventListener("input", (e) => {
    const d = DEFS[state.active];
    if (!d || d.static) return;
    const years = get(state.reg, d.yearsKey) || [];
    state.year[state.active] = years[+e.target.value];
    applyYear();
    label();
    if (state.lastClick) showPanel(state.lastClick, false);
  });
}

export function isActive() { return state.active != null; }

export async function activate(id) {
  state.active = id;
  await ready;
  if (state.active !== id) return;
  const d = DEFS[id];
  if (d.static) {
    timebar.hidden = true;
    setVisibility(map, d.layerId, "visible");
    renderLegend();
    return;
  }
  const years = get(state.reg, d.yearsKey) || [];
  if (!years.includes(state.year[id])) state.year[id] = years[years.length - 1];
  for (const x of ["segVar", "segSeason", "segMode"]) $("#" + x).hidden = true;   // climate's controls
  const sl = $("#yearSlider");
  sl.min = 0; sl.max = years.length - 1; sl.step = 1; sl.value = years.indexOf(state.year[id]);
  timebar.hidden = false;
  label();
  applyYear();
  renderLegend();
  if (id === "fire") await loadPoints();
}

export function deactivate() {
  if (!state.active) return;
  if (!map) { state.active = null; return; }
  for (const d of Object.values(DEFS)) {
    if (d.static) setVisibility(map, d.layerId, "none");
    else for (const y of Object.keys(get(state.reg, d.urlKey) || {})) setVisibility(map, d.prefix + y, "none");
  }
  if (map.getLayer("fire-points")) map.setLayoutProperty("fire-points", "visibility", "none");
  timebar.hidden = true;
  state.active = null;
  state.lastClick = null;
}

function applyYear() {
  const d = DEFS[state.active];
  const cur = String(state.year[state.active]);
  for (const y of Object.keys(get(state.reg, d.urlKey) || {})) {
    setVisibility(map, d.prefix + y, y === cur ? "visible" : "none");
  }
  if (state.active === "fire") loadPoints();
}

function label() {
  const names = { landcover: "land cover (MapBiomas C4)", fire: "active-fire density (VIIRS S-NPP)",
                  burned_area: "burned area (MapBiomas)" };
  $("#timeLabel").innerHTML = `<strong>${state.year[state.active]}</strong> · ${names[state.active] || state.active}`;
}

/* ---------------- fire points (zoom >= 10, selected year) ---------------- */
async function loadPoints() {
  const y = state.year.fire;
  if (state.pointsYear !== y) {
    try {
      const gj = await (await fetch(dataUrl(`fire/points_${y}.geojson`))).json();
      if (!map.getSource("fire-points")) {
        map.addSource("fire-points", { type: "geojson", data: gj });
        map.addLayer({ id: "fire-points", type: "circle", source: "fire-points",
          minzoom: (state.reg.fire?.points_from_zoom ?? 10),
          paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 2, 13, 4.5],
                   "circle-color": "#e55064", "circle-opacity": 0.75,
                   "circle-stroke-color": "#7f1d2e", "circle-stroke-width": 0.5 } },
          map.getLayer("labels-start") ? "labels-start" : undefined);
      } else {
        map.getSource("fire-points").setData(gj);
      }
      state.pointsYear = y;
    } catch { /* points file missing: density still works */ }
  }
  if (map.getLayer("fire-points")) {
    map.setLayoutProperty("fire-points", "visibility", state.active === "fire" ? "visible" : "none");
  }
}

/* ---------------- legends ---------------- */
function legendBox(title, rows, srcText, ramp) {
  const box = $("#legend");
  box.innerHTML = "";
  box.append(el("h3", null, title));
  if (ramp) {
    const steps = el("div", "steps");
    ramp.colors.forEach((c) => { const s = el("span"); s.style.background = c; steps.append(s); });
    box.append(steps, el("div", "axis", `<span>${ramp.left}</span><span>${ramp.right}</span>`));
  }
  for (const [color, lab] of rows || []) {
    const r = el("div", "cat-row");
    const sw = el("span", "swatch"); sw.style.background = color;
    r.append(sw, document.createTextNode(lab));
    box.append(r);
  }
  box.append(el("p", "src", srcText));
  box.hidden = false;
}

function renderLegend() {
  const y = state.year[state.active];
  const reg = state.reg[state.active] || {};
  if (state.active === "landcover") {
    const rows = Object.entries(reg.classes || {})
      .map(([, c]) => [c.color, `${c.name_en} · ${c.name_es}`]);
    legendBox(`Land cover ${y} (MapBiomas Perú C4)`, rows,
      "30 m · CC BY 4.0 · official palette · cacao has no class of its own (inside 'Mosaico agropecuario')");
  } else if (state.active === "canopy") {
    legendBox("Canopy height 2020 (ETH, 10 m)", [],
      "Lang et al. (2023) · CC BY 4.0 · model estimate; clicks read the 10 m raster",
      { colors: ["#f0eee1", "#cdd5ab", "#9bbc86", "#579a66", "#1f704a", "#06422b"],
        left: "0 m", right: `≥ ${reg.ramp?.max_m ?? 40} m` });
  } else if (state.active === "forest_loss") {
    const rows = Object.values(reg.classes || {}).map((c) => [c.color, `${c.name_en} · ${c.name_es}`]);
    legendBox("Forest & loss (GEOBOSQUES)", rows,
      "30 m · MINAM/SERFOR · any loss within a pixel shows when zoomed out · loss includes "
      + "natural losses, not only deforestation");
  } else if (state.active === "fire") {
    const lg = reg.legend_steps || {};
    legendBox(`Active fires ${y} — density (S-NPP)`,
      (lg.colors || []).map((c, i) => [c, `≤ ${lg.breaks[i]} fires/km²`]),
      "VIIRS 375 m, confidence nominal/high · points from zoom 10");
  } else if (state.active === "burned_area") {
    legendBox(`Burned at least once in ${y}`, [["rgb(120,32,18)", "burned (MapBiomas fuego, 30 m)"]],
      "CC BY 4.0 · Landsat-based; misses small or low-severity burns");
  }
}

/* ---------------- clicks ---------------- */
export async function onClick(lngLat) { return showPanel(lngLat, true); }

async function valueAt(lngLat, file, sample) {
  if (!state.tiffs[file]) {
    const tif = await GeoTIFF.fromUrl(dataUrl(file), { allowFullFile: false });
    state.tiffs[file] = await tif.getImage();
  }
  const img = state.tiffs[file];
  const [ox, oy] = img.getOrigin();
  const [rx, ry] = img.getResolution();
  const col = Math.floor((lngLat.lng - ox) / rx), row = Math.floor((lngLat.lat - oy) / ry);
  if (col < 0 || row < 0 || col >= img.getWidth() || row >= img.getHeight()) return null;
  const d = await img.readRasters({ window: [col, row, col + 1, row + 1], samples: [sample ?? 0] });
  return d[0][0];
}

async function series(file) {
  if (!state.series[file]) state.series[file] = await (await fetch(dataUrl("series/" + file))).json();
  return state.series[file];
}

async function showPanel(lngLat, open) {
  state.lastClick = lngLat;
  const panel = $("#cellPanel"), body = $("#cellBody");
  window.closeFloatingPanels?.("cellPanel");
  const y = state.year[state.active];
  const reg = state.reg[state.active] || {};
  body.innerHTML = "";

  if (state.active === "landcover") {
    const years = reg.years || [];
    const v = await valueAt(lngLat, reg.urls.query, years.indexOf(y));
    const cls = reg.classes?.[String(v)];
    const s = await series("lulc_areas.json").catch(() => null);
    const km2 = s?.areas?.[String(y)]?.[String(v)];
    $("#cellTitle").textContent = `Land cover at ${window.fmtCoord(lngLat.lat, lngLat.lng)}`;
    $("#cellHint").textContent = reg.source;
    body.append(el("div", "kpis", `
      <div class="lead"><div class="label">Class · ${y}</div>
        <div class="value" style="font-size:19px">${cls ? `${cls.name_en} · ${cls.name_es}` : "no data"}</div></div>
      <div><div class="label">Department area of class</div>
        <div class="value num" style="font-size:17px">${km2 != null ? Math.round(km2).toLocaleString() + " km²" : "—"}</div></div>`));
    body.append(el("p", "meta", reg.caveats || ""));
  } else if (state.active === "canopy") {
    const v = await valueAt(lngLat, reg.urls.query, 0);
    const ok = v != null && v !== 255;
    $("#cellTitle").textContent = `Canopy height at ${window.fmtCoord(lngLat.lat, lngLat.lng)}`;
    $("#cellHint").textContent = reg.source;
    body.append(el("div", "kpis", `
      <div class="lead"><div class="label">Canopy top height · 2020</div>
        <div class="value num">${ok ? v : "no data"} <span class="unit">${ok ? "m" : ""}</span></div></div>
      <div><div class="label">Product</div><div class="value" style="font-size:15px">ETH 10 m (GEDI + Sentinel-2)</div></div>
      <div><div class="label">Licence</div><div class="value" style="font-size:15px">CC BY 4.0</div></div>`));
    body.append(el("p", "meta", reg.caveats || ""));
  } else if (state.active === "forest_loss") {
    $("#cellTitle").textContent = "Forest & loss · Ucayali";
    $("#cellHint").textContent = reg.source;
    const annual = await series("forest_loss.json").catch(() => null);   // the annual product (year field)
    if (annual?.regions?.Ucayali) {
      const data = annual.regions.Ucayali;
      const years = Object.keys(data);
      const total = Object.values(data).reduce((a, v) => a + v, 0);
      body.append(el("div", "kpis", `
        <div class="lead"><div class="label">Total loss ${years[0]}–${years[years.length - 1]}</div>
          <div class="value num">${Math.round(total).toLocaleString()} <span class="unit">km²</span></div></div>`));
      const block = el("div", "chart-block");
      block.append(el("h3", null, "Annual forest loss (km², department)"));
      const mount = el("div"); block.append(mount);
      Charts.bars(mount, { labels: years.map((x) => (+x % 5 === 0 ? x : "")), values: Object.values(data),
                           height: 150, format: (v) => Math.round(v).toLocaleString() + " km²" });
      block.append(el("p", "meta", "this app's analysis of the GEOBOSQUES rasters — see the data report"));
      body.append(block);
    } else {
      const cls = await series("forest_classes.json").catch(() => null); // the combined product
      const data = cls?.regions?.Ucayali || {};
      body.append(el("div", "kpis", Object.entries(data).map(([c, km]) => `
        <div><div class="label">${cls.classes[c] || c}</div>
          <div class="value num" style="font-size:17px">${Math.round(km).toLocaleString()} <span class="unit">km²</span></div></div>`).join("")));
      body.append(el("p", "meta", "Department totals, this app's analysis. The year-by-year loss "
        + "series arrives with GEOBOSQUES' annual loss raster."));
    }
  } else {
    const f = await series("fire.json");
    const isBurn = state.active === "burned_area";
    const data = isBurn ? f.burned_km2_dept : f.snpp_detections_dept;
    const years = Object.keys(data);
    $("#cellTitle").textContent = isBurn ? "Burned area · department" : "Active fires · department (S-NPP)";
    $("#cellHint").textContent = reg.source;
    const unit = isBurn ? "km²" : "detections";
    body.append(el("div", "kpis", `
      <div class="lead"><div class="label">${y} · department</div>
        <div class="value num">${Math.round(data[String(y)] ?? 0).toLocaleString()} <span class="unit">${unit}</span></div></div>
      <div><div class="label">Record year</div>
        <div class="value num" style="font-size:18px">${Math.round(Math.max(...Object.values(data))).toLocaleString()}</div></div>`));
    const block = el("div", "chart-block");
    block.append(el("h3", null, isBurn ? "Burned area per year (km²)" : "S-NPP detections per year"));
    const mount = el("div"); block.append(mount);
    Charts.bars(mount, { labels: years.map((x) => (+x % 5 === 0 ? x : "")), values: Object.values(data),
                         height: 150, format: (v) => Math.round(v).toLocaleString(),
                         highlight: years.indexOf(String(y)) });
    block.append(el("p", "meta", f.caveats || reg.caveats || ""));
    body.append(block);
  }
  if (open) panel.hidden = false;
}
