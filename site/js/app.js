/* MOSAIC Ucayali Explorer — map-first app screen, scaffolded from the Lake Victoria Basin Explorer.
   Static: PMTiles + GeoJSON + JSON read from the data root (site/js/config.js dataUrl). No backend. */

import * as climate from "./climate.js";
import * as stories from "./stories.js";
import * as thematic from "./thematic.js";

import { dataUrl, isWithheld } from "./config.js";
import { split as splitLazy, setVisibility } from "./layers.js";
const TILE_V = "1";   // bump to defeat stale HTTP caches after tile rebuilds
const fmtCoord = (lat, lng) =>
  `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lng).toFixed(2)}° ${lng >= 0 ? "E" : "W"}`;
const closeFloating = (except) => {
  for (const id of ["popover", "cellPanel", "aboutPanel", "storiesPanel"]) {
    if (id !== except) { const n = document.getElementById(id); if (n) n.hidden = true; }
  }
  if (except !== "storiesPanel") document.getElementById("storiesBtn")?.setAttribute("aria-expanded", "false");
};
const pmUrl = (f) => "pmtiles://" + new URL(dataUrl(f) + "?v=" + TILE_V, location.href).href;

/* Thematic overlays: one active at a time (radio). type "thematic" layers live in thematic.js
   (per-year tiles, legends, click panels); vector overlays are handled here. */
const OVERLAYS = [
  { id: "veg_classes", group: "Vegetation", title: "Vegetation classes", type: "vector",
    file: "vectors/veg_classes.geojson", regKey: "veg_classes", swatch: "#55a05f" },
  { id: "canopy", group: "Vegetation", title: "Canopy height", type: "thematic",
    regKey: "canopy", swatch: "#1f704a" },
  { id: "gedi", group: "Vegetation", title: "GEDI lidar canopy height", type: "thematic",
    regKey: "gedi", swatch: "#579a66" },
  { id: "landcover", group: "Land", title: "Land cover", type: "thematic",
    regKey: "landcover", swatch: "#e49635" },
  { id: "forest_loss", group: "Land", title: "Forest loss", type: "thematic",
    regKey: "forest_loss", swatch: "#b2182b" },
  { id: "fire", group: "Fire", title: "Active fires", type: "thematic",
    regKey: "fire", swatch: "#e55064" },
  { id: "burned_area", group: "Fire", title: "Burned area", type: "thematic",
    regKey: "burned_area", swatch: "#782012" },
  { id: "protected_areas", group: "Conservation", title: "Protected areas (ANP & ACR)", type: "vector",
    file: "vectors/protected_areas.geojson", regKey: "protected_areas", swatch: "#2e86ab" },
  { id: "precip", group: "Climate", title: "Precipitation", type: "climate",
    file: "climate/app/app_meta.json", swatch: "#434e6b" },
  { id: "temperature", group: "Climate", title: "Temperature", type: "climate",
    file: "climate/app/app_meta.json", swatch: "#e14c66" },
  { id: "spi3", group: "Climate", title: "Drought (SPI-3)", type: "climate",
    file: "climate/app/spi3.tif", swatch: "#35978f" },
];

const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const exists = async (url) => { try { const r = await fetch(url, { method: "HEAD" }); return r.ok; } catch { return false; } };
const getJSON = async (url) => { const r = await fetch(url); if (!r.ok) throw new Error(url); return r.json(); };

const state = { registry: {}, overlay: null };

/* ---------------- boot ---------------- */
window.addEventListener("error", (e) => notice("Script error: " + e.message));
window.addEventListener("unhandledrejection", (e) => notice("Error: " + (e.reason?.message || e.reason)));

(async function boot() {
  try {
    const reg = await getJSON(dataUrl("meta/layers.json"));
    for (const l of reg.layers) state.registry[l.id] = l;
  } catch { /* registry optional at this stage */ }

  const have = {};
  const probeList = ["tiles/terrain.pmtiles", "tiles/s2_rgb.pmtiles", "tiles/osm_basemap.pmtiles",
                     "vectors/department.geojson", "vectors/department_mask.geojson",
                     "vectors/provinces.geojson", "vectors/districts.geojson",
                     "vectors/admin_labels.geojson", "climate/app/app_meta.json",
                     ...OVERLAYS.filter((o) => o.file).map((o) => o.file)];
  await Promise.all([...new Set(probeList)].map(async (f) => { have[f] = !isWithheld(f) && await exists(dataUrl(f)); }));
  state.have = have;

  const miss = [];
  if (!have["tiles/terrain.pmtiles"]) miss.push("terrain (pipeline 02)");
  if (!have["tiles/s2_rgb.pmtiles"]) miss.push("imagery (pipeline 03)");
  if (miss.length) notice(`Base tiles not built yet: ${miss.join(", ")}. The map shows data layers only.`);

  buildRail();
  buildAbout();
  initMap();
  wireUI();
  await stories.init({
    setOverlay,
    get map() { return map; },
    activeOverlay: () => state.overlay,
    overlayTitle: (id) => OVERLAYS.find((o) => o.id === id)?.title,
    overlayAvailable: (id) => {
      const item = document.querySelector(`.rail .item[data-overlay="${id}"]`);
      return Boolean(item && !item.classList.contains("unavailable"));
    },
    presetClimate: (p) => climate.presetFromHash(p),
    presetTime: (layer, t) => (layer === "spi3" ? climate.showMonth(String(t)) : thematic.setYear(layer, +t)),
  });
})();

function notice(msg) {
  const n = $("#notice");
  n.hidden = false;
  n.append(el("div", null, msg));
}

/* ---------------- layer rail ---------------- */
function buildRail() {
  const rail = $("#rail");
  const groups = new Map([["Base", []], ["Vegetation", []], ["Land", []], ["Climate", []], ["Fire", []], ["Conservation", []]]);
  const toggle = (title, swatch, ids, on, extra) => {
    const b = railItem(title, swatch, "");
    b.setAttribute("aria-pressed", String(on));
    b.addEventListener("click", () => {
      const now = b.getAttribute("aria-pressed") !== "true";
      b.setAttribute("aria-pressed", String(now));
      for (const id of ids) setVisibility(map, id, now ? "visible" : "none");
      extra?.(now);
      updateAttrib();
    });
    groups.get("Base").push(b);
    return b;
  };
  if (state.have["tiles/osm_basemap.pmtiles"]) {
    state.placeNames = true;
    toggle("Place names", "#ffffff", PLACE_IDS, true, (v) => (state.placeNames = v)).id = "placeNamesItem";
  }
  if (state.have["vectors/provinces.geojson"]) {
    state.admin = false;
    toggle("Provinces & districts", "#c9ced2", ADMIN_IDS, false, (v) => (state.admin = v)).id = "adminItem";
  }

  for (const o of OVERLAYS) {
    const ok = o.type === "thematic" ? Boolean(state.registry[o.regKey]?.urls) : state.have[o.file];
    const item = railItem(o.title, o.swatch, ok ? "" : o.type === "climate" ? "preparing data" : "not built");
    if (!ok) item.classList.add("unavailable");
    else item.addEventListener("click", () => setOverlay(state.overlay === o.id ? null : o.id));
    item.dataset.overlay = o.id;
    groups.get(o.group).push(item);
  }

  for (const [name, items] of groups) {
    if (!items.length) continue;
    const g = el("div", "group");
    g.append(el("div", "group-label", name));
    items.forEach((i) => g.append(i));
    rail.append(g);
  }
}

function railItem(title, swatchColor, meta) {
  const b = el("button", "item");
  b.setAttribute("aria-pressed", "false");
  const sw = el("span", "swatch");
  sw.style.background = swatchColor;
  b.append(sw, el("span", "label", title));
  if (meta) {
    const tag = el("span", "pill", meta);
    tag.style.marginLeft = "auto";
    b.append(tag);
  } else {
    b.append(el("span", "meta", ""));
  }
  return b;
}

async function setOverlay(id) {
  state.overlay = id;
  document.querySelectorAll(".rail .item[data-overlay]").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.overlay === id));
  });
  for (const o of OVERLAYS.filter((x) => x.type === "vector")) {
    for (const lid of overlayLayerIds(o.id)) setVisibility(map, lid, o.id === id ? "visible" : "none");
  }
  thematic.deactivate();
  climate.deactivate();
  const def = OVERLAYS.find((x) => x.id === id);
  if (def?.type === "thematic") {
    $("#legend").hidden = true;
    await thematic.activate(id);          // thematic.js owns the legend while active
  } else if (def?.type === "climate") {
    $("#legend").hidden = true;
    await climate.activate(id);           // climate.js owns the legend and the time bar
  } else {
    renderLegend(id);
  }
  updateAttrib();
  $("#popover").hidden = true;
}

const overlayLayerIds = (id) => (id === "veg_classes" ? ["veg-fill", "veg-line"]
  : id === "protected_areas" ? ["pa-fill", "pa-line"] : ["ov-" + id]);

/* ---------------- legend + attribution ---------------- */
function renderLegend(id) {
  const box = $("#legend");
  box.hidden = true;
  if (id === "protected_areas") {
    const reg = state.registry.protected_areas || {};
    box.innerHTML = "";
    box.append(el("h3", null, "Protected areas"));
    for (const [c, lab] of [["#2e86ab", "ANP — national protected area"], ["#7fb069", "ACR — regional conservation area"]]) {
      const row = el("div", "cat-row");
      const sw = el("span", "swatch"); sw.style.background = c;
      row.append(sw, document.createTextNode(lab));
      box.append(row);
    }
    box.append(el("p", "src", "Click an area for its name, category and creation year · source: SERNANP"));
    box.hidden = false;
    updateAttrib();
    return;
  }
  if (id !== "veg_classes") { updateAttrib(); return; }
  const reg = state.registry.veg_classes;
  if (!reg?.classes) return;
  box.innerHTML = "";
  box.append(el("h3", null, "Vegetation classes (co-produced with local experts)"));
  const list = el("div", "cat-list");
  for (const c of reg.classes) {
    const row = el("div", "cat-row");
    const sw = el("span", "swatch"); sw.style.background = c.color;
    row.append(sw, el("span", null,
      `${c.class_en} · <em>${c.COBERTURA.replaceAll("_", " ")}</em> <span class="num">(${c.count})</span>`));
    list.append(row);
  }
  box.append(list);
  box.append(el("p", "src", "Polygon counts are this app's analysis of the CC0 dataset. "
    + "Class definitions: Cooley et al. (2024), Table 1."));
  box.append(el("p", "src", (reg.source || "") + " · " + (reg.period || "")));
  box.hidden = false;
}

function updateAttrib() {
  const names = { veg_classes: " · Cooley et al. (2024) vegetation typologies (CC0)",
                  canopy: " · ETH canopy height 2020 (CC BY 4.0)",
                  gedi: " · NASA GEDI L2A v002",
                  landcover: " · MapBiomas Perú C4 (CC BY 4.0)",
                  forest_loss: " · GEOBOSQUES (MINAM/SERFOR)",
                  fire: " · NASA FIRMS VIIRS", burned_area: " · MapBiomas fuego (CC BY 4.0)",
                  protected_areas: " · SERNANP",
                  precip: " · CHIRPS v3 (UCSB CHC, CC BY 4.0)", temperature: " · CHIRTS-ERA5 (UCSB CHC)",
                  spi3: " · SPI-3 from CHIRPS v3" };
  const extra = state.overlay ? (names[state.overlay] || "") : "";
  const ref = (state.placeNames ? " · © OpenStreetMap contributors" : "")
            + (state.admin ? " · IGN (ODC-By)" : "");
  $("#attrib").textContent = "Sentinel-2 · DEM" + extra + ref;
}

/* ---------------- reference labels: OSM place names + admin boundaries ----------------
   Label-only layers from the Protomaps basemap extract (schema v4): no roads, buildings or fills. */
const LABEL_TEXT = { "text-color": "#ffffff", "text-halo-color": "rgba(17,26,34,0.88)", "text-halo-width": 1.5 };
const PLACE_IDS = ["osm-natural", "osm-water-river", "osm-water", "osm-village", "osm-town", "osm-city", "osm-country"];
const ADMIN_IDS = ["districts-line", "provinces-line", "districts-hit", "provinces-hit", "districts-label", "provinces-label"];

function referenceLayers(sources) {
  const L = [{ id: "labels-start", type: "background", paint: { "background-opacity": 0 } }];
  if (state.have["vectors/provinces.geojson"]) {
    sources.provinces = { type: "geojson", data: dataUrl("vectors/provinces.geojson") };
    sources.districts = { type: "geojson", data: dataUrl("vectors/districts.geojson") };
    sources.admLabels = { type: "geojson", data: dataUrl("vectors/admin_labels.geojson") };
    const hidden = { visibility: "none" };
    L.push(
      { id: "districts-hit", type: "fill", source: "districts", minzoom: 8, layout: hidden, paint: { "fill-opacity": 0 } },
      { id: "provinces-hit", type: "fill", source: "provinces", layout: hidden, paint: { "fill-opacity": 0 } },
      { id: "districts-line", type: "line", source: "districts", minzoom: 8, layout: hidden,
        paint: { "line-color": "#c9ced2", "line-width": 0.6, "line-dasharray": [3, 2], "line-opacity": 0.8 } },
      { id: "provinces-line", type: "line", source: "provinces", layout: hidden,
        paint: { "line-color": "#dfe3e6", "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.7, 11, 1.4],
                 "line-opacity": 0.9 } },
      { id: "provinces-label", type: "symbol", source: "admLabels", minzoom: 6.5, maxzoom: 11,
        filter: ["==", ["get", "level"], "province"],
        layout: { ...hidden, "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"],
                  "text-size": 11, "text-letter-spacing": 0.06, "text-transform": "uppercase", "text-padding": 4 },
        paint: { ...LABEL_TEXT, "text-color": "#e4e8eb", "text-halo-width": 1.3 } },
      { id: "districts-label", type: "symbol", source: "admLabels", minzoom: 9,
        filter: ["==", ["get", "level"], "district"],
        layout: { ...hidden, "text-field": ["get", "name"], "text-font": ["Noto Sans Italic"], "text-size": 11,
                  "text-padding": 4 },
        paint: { ...LABEL_TEXT, "text-color": "#e4e8eb", "text-halo-width": 1.3 } });
  }
  if (state.have["tiles/osm_basemap.pmtiles"]) {
    sources.osm = { type: "vector", url: pmUrl("tiles/osm_basemap.pmtiles"),
                    attribution: "© OpenStreetMap contributors" };
    const sym = (font, size) => ({ "text-field": ["get", "name"], "text-font": [font], "text-size": size,
                                   "text-padding": 3, "text-max-width": 8 });
    const rank = ["-", 0, ["coalesce", ["get", "population_rank"], 0]];
    L.push(
      { id: "osm-natural", type: "symbol", source: "osm", "source-layer": "pois", minzoom: 8,
        filter: ["all", ["has", "name"], ["in", ["get", "kind"], ["literal", ["national_park", "nature_reserve", "protected_area", "forest"]]]],
        layout: sym("Noto Sans Italic", 11), paint: { ...LABEL_TEXT, "text-color": "#e6f0dc" } },
      { id: "osm-water-river", type: "symbol", source: "osm", "source-layer": "water", minzoom: 8,
        filter: ["all", ["has", "name"], ["in", ["get", "kind"], ["literal", ["river", "canal", "stream"]]]],
        layout: { ...sym("Noto Sans Italic", 11), "symbol-placement": "line", "symbol-spacing": 400 },
        paint: { ...LABEL_TEXT, "text-color": "#d6eef2" } },
      { id: "osm-water", type: "symbol", source: "osm", "source-layer": "water",
        filter: ["all", ["has", "name"], ["==", ["geometry-type"], "Point"],
                 ["in", ["get", "kind"], ["literal", ["lake", "water", "bay", "reservoir"]]]],
        layout: sym("Noto Sans Italic", ["interpolate", ["linear"], ["zoom"], 6, 12, 10, 14]),
        paint: { ...LABEL_TEXT, "text-color": "#d6eef2" } },
      { id: "osm-village", type: "symbol", source: "osm", "source-layer": "places", minzoom: 11,
        filter: ["all", ["has", "name"], ["==", ["get", "kind"], "locality"],
                 ["in", ["get", "kind_detail"], ["literal", ["village", "hamlet"]]]],
        layout: { ...sym("Noto Sans Regular", 11), "symbol-sort-key": rank }, paint: LABEL_TEXT },
      { id: "osm-town", type: "symbol", source: "osm", "source-layer": "places", minzoom: 7,
        filter: ["all", ["has", "name"], ["==", ["get", "kind"], "locality"], ["==", ["get", "kind_detail"], "town"]],
        layout: { ...sym("Noto Sans Medium", ["interpolate", ["linear"], ["zoom"], 7, 11, 12, 13]), "symbol-sort-key": rank },
        paint: LABEL_TEXT },
      { id: "osm-city", type: "symbol", source: "osm", "source-layer": "places",
        filter: ["all", ["has", "name"], ["==", ["get", "kind"], "locality"], ["==", ["get", "kind_detail"], "city"]],
        layout: { ...sym("Noto Sans Medium", ["interpolate", ["linear"], ["zoom"], 6, 12, 12, 15]), "symbol-sort-key": rank },
        paint: LABEL_TEXT },
      { id: "osm-country", type: "symbol", source: "osm", "source-layer": "places", maxzoom: 7,
        filter: ["all", ["has", "name"], ["==", ["get", "kind"], "country"]],
        layout: { ...sym("Noto Sans Medium", 13), "text-transform": "uppercase", "text-letter-spacing": 0.12 },
        paint: { ...LABEL_TEXT, "text-color": "#f3f5f6" } });
  }
  return L;
}

/* admin unit under a map point, for the popover titles */
function adminAt(lngLat) {
  if (!map || !map.getLayer("provinces-hit") || map.getLayoutProperty("provinces-hit", "visibility") !== "visible") return null;
  const pt = map.project([lngLat.lng, lngLat.lat]);
  const hits = map.queryRenderedFeatures(pt, { layers: ["districts-hit", "provinces-hit"] });
  const pr = hits.find((f) => f.layer.id === "provinces-hit"), di = hits.find((f) => f.layer.id === "districts-hit");
  if (!pr && !di) return null;
  return { province: pr?.properties.province, district: di?.properties.district };
}

/* ---------------- map ---------------- */
let map;
function initMap() {
  const protocol = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);

  const EMPTY = { type: "FeatureCollection", features: [] };
  const optional = (f) => (state.have[f] ? dataUrl(f) : EMPTY);
  const sources = {
    department: { type: "geojson", data: optional("vectors/department.geojson") },
    mask: { type: "geojson", data: optional("vectors/department_mask.geojson") },
  };
  const layers = [
    { id: "bg", type: "background", paint: { "background-color": "#dfe5ea" } },
  ];

  if (state.have["tiles/s2_rgb.pmtiles"]) {
    sources.s2 = { type: "raster", url: pmUrl("tiles/s2_rgb.pmtiles"), tileSize: 256 };
    layers.push({ id: "s2", type: "raster", source: "s2", paint: { "raster-resampling": "linear" } });
  }
  if (state.have["tiles/terrain.pmtiles"]) {
    // separate raster-dem sources for 3D terrain and hillshade (MapLibre warns when they share one)
    sources.dem = { type: "raster-dem", url: pmUrl("tiles/terrain.pmtiles"),
                    tileSize: 256, encoding: "mapbox" };
    sources.demHillshade = { type: "raster-dem", url: pmUrl("tiles/terrain.pmtiles"),
                             tileSize: 256, encoding: "mapbox" };
    layers.push({ id: "hillshade", type: "hillshade", source: "demHillshade",
                  paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "#3c4148",
                           "hillshade-highlight-color": "#ffffff", "hillshade-accent-color": "#5b6672" } });
  }

  const th = thematic.layersFor(state.registry, pmUrl);   // per-year + static thematic tile layers
  Object.assign(sources, th.sources);
  layers.push(...th.layers);

  if (state.have["vectors/veg_classes.geojson"]) {
    sources.veg = { type: "geojson", data: dataUrl("vectors/veg_classes.geojson") };
    layers.push({ id: "veg-fill", type: "fill", source: "veg", layout: { visibility: "none" },
                  paint: { "fill-color": ["get", "color"], "fill-opacity": 0.72 } });
    layers.push({ id: "veg-line", type: "line", source: "veg", layout: { visibility: "none" },
                  paint: { "line-color": ["get", "color"], "line-width": 1.2 } });
    // story only (stories.js setOutlines): class outlines over any overlay, and the polygon a step is about
    const none = { visibility: "none" }, noPlot = ["==", ["get", "PLOTID"], ""];
    layers.push({ id: "story-veg-halo", type: "line", source: "veg", layout: none,
                  paint: { "line-color": "#ffffff", "line-width": 3, "line-opacity": 0.75 } });
    layers.push({ id: "story-veg-line", type: "line", source: "veg", layout: none,
                  paint: { "line-color": ["get", "color"], "line-width": 1.4 } });
    layers.push({ id: "story-veg-focus-halo", type: "line", source: "veg", layout: none, filter: noPlot,
                  paint: { "line-color": "#ffffff", "line-width": 6 } });
    layers.push({ id: "story-veg-focus", type: "line", source: "veg", layout: none, filter: noPlot,
                  paint: { "line-color": "#1c2b3a", "line-width": 2.6 } });
  }
  if (state.have["vectors/protected_areas.geojson"]) {
    sources.pa = { type: "geojson", data: dataUrl("vectors/protected_areas.geojson") };
    const paColor = ["case", ["==", ["get", "kind"], "ACR (regional)"], "#7fb069", "#2e86ab"];
    layers.push({ id: "pa-fill", type: "fill", source: "pa", layout: { visibility: "none" },
                  paint: { "fill-color": paColor, "fill-opacity": 0.35 } });
    layers.push({ id: "pa-line", type: "line", source: "pa", layout: { visibility: "none" },
                  paint: { "line-color": paColor, "line-width": 1.8 } });
  }
  /* the outside mask sits ABOVE every data layer (imagery, hillshade, thematic tiles, climate grid,
     fire points, vectors) and below the outline and labels. It stays OPAQUE: at 82 % (tested
     2026-11-04) the hillshade showed streaks and grooves from the synthetic terrain padding beyond
     the DEM (department zoom and 60° tilt). climate.js and the fire points insert before "dim". */
  layers.push({ id: "dim", type: "fill", source: "mask",
                paint: { "fill-color": "#dfe5ea", "fill-opacity": 1 } });
  /* the outline: a light halo under a dark line, so it reads on imagery, on every thematic palette
     and on the mask alike */
  layers.push({ id: "department-halo", type: "line", source: "department",
                layout: { "line-join": "round" },
                paint: { "line-color": "#ffffff", "line-opacity": 0.85,
                         "line-width": ["interpolate", ["linear"], ["zoom"], 5, 3, 8, 4.5, 12, 6] } });
  layers.push({ id: "department-line", type: "line", source: "department",
                layout: { "line-join": "round" },
                paint: { "line-color": "#1c2b3a",
                         "line-width": ["interpolate", ["linear"], ["zoom"], 5, 1.4, 8, 2, 12, 2.6] } });
  layers.push(...referenceLayers(sources));

  map = new maplibregl.Map({
    container: "map",
    style: { version: 8, ...splitLazy(sources, layers),
             sky: { "sky-color": "#c8d4de", "horizon-color": "#e7ebef", "fog-color": "#e7ebef",
                    "sky-horizon-blend": 0.6, "horizon-fog-blend": 0.7 },
             glyphs: new URL(dataUrl("fonts/"), location.href).href + "{fontstack}/{range}.pbf" },
    center: [-73.6, -9.5], zoom: 6.1, pitch: 32, bearing: 0,
    maxPitch: 62, minZoom: 5.5, maxZoom: 16, attributionControl: false,   // 16: GEDI footprints at true size
    maxBounds: [[-79.0, -14.3], [-67.4, -4.4]],   // terrain tiles are padded ~300 km beyond the DEM
  });
  window.__map = map;
  window.fmtCoord = (lat, lng) => {
    const a = adminAt({ lat, lng });
    return fmtCoord(lat, lng) + (a ? ` · ${a.district || a.province}` : "");
  };
  window.closeFloatingPanels = closeFloating;
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");

  map.on("load", async () => {
    try { thematic.init(map); } catch (e) { notice("Thematic layers failed to start: " + e.message); }
    if (state.have["climate/app/app_meta.json"]) {
      try { await climate.init(map); } catch (e) { notice("Climate layers failed to start: " + e.message); }
    }
    applyHash();
    if (map.setSky) {
      map.setSky({ "sky-color": "#c8d4de", "horizon-color": "#e7ebef", "fog-color": "#e7ebef",
                   "sky-horizon-blend": 0.6, "horizon-fog-blend": 0.7 });
    }
    if (state.have["tiles/terrain.pmtiles"]) {
      map.setTerrain({ source: "dem", exaggeration: 1.6 });
    } else {
      $("#exag").disabled = true;
    }
  });

  map.on("click", (e) => {
    if (climate.isActive()) { climate.showCell(e.lngLat); return; }
    if (thematic.isActive()) { thematic.onClick(e.lngLat); return; }
    showPopover(e);
  });
  for (const lid of ["veg-fill", "pa-fill"]) {
    map.on("mouseenter", lid, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", lid, () => (map.getCanvas().style.cursor = ""));
  }
}

/* shareable state: #layer=veg_classes&c=lng,lat,zoom,pitch */
async function applyHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const c = h.get("c");
  if (c) {
    const [lng, lat, zoom, pitch] = c.split(",").map(Number);
    map.jumpTo({ center: [lng, lat], zoom: zoom || 10, pitch: pitch ?? 0, bearing: 0 });
  }
  if (!h.get("layer")) return;
  const id = h.get("layer");
  const item = document.querySelector(`.rail .item[data-overlay="${id}"]`);
  if (item && !item.classList.contains("unavailable")) await setOverlay(id);
}

async function showPopover(e) {
  const p = $("#popover");
  const rows = [
    `<div class="row"><span>Place</span><span>${fmtCoord(e.lngLat.lat, e.lngLat.lng)}</span></div>`,
  ];
  const adm = adminAt(e.lngLat);
  if (adm) {
    if (adm.district) rows.push(`<div class="row"><span>District</span><span>${adm.district}</span></div>`);
    if (adm.province) rows.push(`<div class="row"><span>Province</span><span>${adm.province}</span></div>`);
  }
  closeFloating("popover");
  let title = "Ucayali";
  if (state.overlay === "protected_areas" && map.getLayer("pa-fill")) {
    const hits = map.queryRenderedFeatures(e.point, { layers: ["pa-fill"] });
    if (hits.length) {
      const f = hits[0].properties;
      title = f.name;
      rows.push(`<div class="row"><span>Category</span><span>${f.category}</span></div>`,
                `<div class="row"><span>Kind</span><span>${f.kind}</span></div>`,
                `<div class="row"><span>Created</span><span>${f.year ?? "—"}${f.legal_doc ? " · " + f.legal_doc : ""}</span></div>`,
                `<div class="row"><span>Legal area</span><span>${f.area_legal_ha ? Number(f.area_legal_ha).toLocaleString() + " ha" : "—"}</span></div>`);
      rows.push(`<p class="meta">Source: SERNANP (boundaries simplified for display; not an official delimitation).</p>`);
    } else {
      rows.push(`<p class="meta">No protected area here.</p>`);
    }
  } else if (state.overlay === "veg_classes" && map.getLayer("veg-fill")) {
    const hits = map.queryRenderedFeatures(e.point, { layers: ["veg-fill"] });
    if (hits.length) {
      const f = hits[0].properties;
      title = f.class_en;
      rows.push(`<div class="row"><span>Class (local name)</span><span>${String(f.COBERTURA).replaceAll("_", " ")}</span></div>`,
                `<div class="row"><span>Polygon</span><span>${f.PLOTID} · ${Number(f.area_ha).toLocaleString()} ha</span></div>`,
                `<div class="row"><span>Digitised on</span><span>${f.MAPA_BASE} imagery, ${f.ANO_IMAGEN}</span></div>`);
      rows.push(`<p class="meta">Class co-produced with local experts; polygon from the CC0 dataset `
              + `(doi:10.22002/D1.2318). Area is this app's analysis.</p>`);
    } else {
      rows.push(`<p class="meta">No digitised polygon here. The 324 polygons cover sampled patches, `
              + `not the whole department.</p>`);
    }
  }
  p.innerHTML = `<h3>${title}</h3>${rows.join("")}
    <p class="meta">${state.overlay === "veg_classes" ? "Cooley et al. (2024) · classes of the forest–agriculture interface" : "Sentinel-2 mosaic · 30 m"}</p>`;
  const r = $("#map").getBoundingClientRect();
  p.style.left = Math.min(e.point.x + 12, r.width - 300) + "px";
  p.style.top = Math.min(e.point.y + 12, r.height - 140) + "px";
  p.hidden = false;
}

/* ---------------- about panel ---------------- */
function buildAbout() {
  const body = $("#aboutBody");
  const brand = el("div", "about-brand", `
    <img src="assets/brand/cgiar-mfl-lockup.png" alt="CGIAR Multifunctional Landscapes" width="180" height="60">
    <p>Part of <a href="https://mosaic-mfl.github.io/website/">MOSAIC</a> — the CGIAR Multifunctional
       Landscapes Science Programme. See the <a href="https://mosaic-mfl.github.io/website/catalogue">data
       catalogue</a> and the <a href="../DATA_REPORT.md">full data report</a> for this app.</p>
    <p class="meta">Content licensed under CC BY 4.0 unless otherwise stated. Each layer below carries its
       own source, period and citation.</p>`);
  body.append(brand);
  const layers = Object.values(state.registry);
  if (!layers.length) {
    body.append(el("div", "empty", "Layer registry not found (data/meta/layers.json)."));
    return;
  }
  for (const l of layers) {
    const sec = el("div", "chart-block");
    sec.append(el("h3", null, l.title));
    sec.append(el("p", "meta",
      [l.source, l.period, l.units, l.licence].filter(Boolean).join(" · ")));
    if (l.citation) sec.append(el("p", "meta", l.citation));
    if (l.caveats) sec.append(el("p", "meta", l.caveats));
    body.append(sec);
  }
  /* layers deliberately not hosted here */
  const raisg = el("div", "chart-block");
  raisg.append(el("h3", null, "Indigenous territories (not hosted here)"));
  raisg.append(el("p", "meta",
    'RAISG\'s Indigenous-territories data is not redistributed in this app: RAISG\'s use licence '
    + 'requires unaltered data and non-profit use, and the layer includes territories of peoples in '
    + 'isolation. View it on <a href="https://www.raisg.org/es/mapas/" target="_blank" '
    + 'rel="noopener">RAISG\'s own map</a>.'));
  body.append(raisg);
}

/* ---------------- ui wiring ---------------- */
function wireUI() {
  $("#exag").addEventListener("input", (e) => {
    const v = +e.target.value;
    $("#exagVal").textContent = "×" + v.toFixed(1);
    if (map.getTerrain()) map.setTerrain({ source: "dem", exaggeration: v });
  });
  $("#aboutBtn").addEventListener("click", () => {
    const show = $("#aboutPanel").hidden;
    if (show) closeFloating("aboutPanel");
    $("#aboutPanel").hidden = !show;
  });
  $("#aboutClose").addEventListener("click", () => ($("#aboutPanel").hidden = true));
  /* narrow windows: the layer menu is a drawer. ☰ turns into ✕ while it is open; it also closes on Escape,
     on a tap on the map, and on a phone after a layer is chosen (so the layer can be seen) */
  const setMenu = (open) => {
    $("#sidebar").classList.toggle("open", open);
    $("#menuBtn").setAttribute("aria-expanded", String(open));
    $("#menuBtn").setAttribute("aria-label", open ? "Close menu" : "Menu");
    $("#menuBtn path").setAttribute("d", open ? "M3 3l10 10M13 3L3 13" : "M2 4h12M2 8h12M2 12h12");
  };
  $("#menuBtn").addEventListener("click", () => setMenu(!$("#sidebar").classList.contains("open")));
  map.on("click", () => setMenu(false));
  /* also close on a tap anywhere outside the drawer (legend, panels): the veg-class legend is tall
     enough at narrow widths that a "tap on the map" often lands on it */
  document.addEventListener("pointerdown", (e) => {
    if ($("#sidebar").classList.contains("open")
        && !e.target.closest("#sidebar") && !e.target.closest("#menuBtn")) setMenu(false);
  });
  $("#rail").addEventListener("click", (e) => {
    if (e.target.closest(".item") && matchMedia("(max-width: 480px)").matches) setMenu(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      setMenu(false);
      for (const id of ["popover", "aboutPanel", "storiesPanel"]) $("#" + id).hidden = true;
      $("#storiesBtn").setAttribute("aria-expanded", "false");
    }
  });
}
