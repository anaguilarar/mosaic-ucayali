/* Uses & studies drawer: two tabs.
   "Story" (default) - scroll-driven chapters from data/meta/story_chapters.json. A chapter entering the middle
   of the drawer applies its map state (layer, climate time step, camera). Charts render inline from
   the app's served series; static figures (prep/90_story_figures.py) enlarge over the map on click.
   Rules carried in the registry: study numbers as printed (page recorded), app numbers labelled
   "this app's analysis", pending chapters show a placeholder.
   "Studies" - the question cards (data/meta/studies.json): published findings verified against the PDFs in
   bibliography/, or explore questions. "Show me on the map" applies the card's state and closes the
   drawer; the Story tab keeps the drawer open and repositions the legend and time bar instead. */

import * as compare from "./compare.js";

import { dataUrl } from "./config.js";
const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };

const state = { stories: [], chapters: [], storyTitle: "", hooks: null, expanded: null,
                tab: "story", series: new Map(), io: null, chapter: null };

/* app.js hands over: { setOverlay, map, overlayAvailable(id), overlayTitle(id), activeOverlay() } */
export async function init(hooks) {
  state.hooks = hooks;
  $("#storiesBtn").addEventListener("click", toggle);
  $("#storiesClose").addEventListener("click", () => setOpen(false));
  const grab = async (f) => { try { const r = await fetch(dataUrl("meta/" + f)); return r.ok ? r.json() : null; } catch { return null; } };
  const [cards, story] = await Promise.all([grab("studies.json"), grab("story_chapters.json")]);
  state.stories = cards?.stories || [];
  state.chapters = story?.chapters || [];
  state.storyTitle = story?.title || "Story";
}

export function isOpen() { return !$("#storiesPanel").hidden; }
export function toggle() { setOpen($("#storiesPanel").hidden); }

function setOpen(open) {
  const panel = $("#storiesPanel");
  if (open) { window.closeFloatingPanels?.("storiesPanel"); render(); }
  panel.hidden = !open;
  $("#storiesBtn").setAttribute("aria-expanded", String(open));
  syncBodyClass();
}

function syncBodyClass() {
  const on = isOpen() && state.tab === "story";
  const was = document.body.classList.contains("story-open");
  document.body.classList.toggle("story-open", on);
  if (on !== was) setStoryMode(on);
  if (!on && compare.isOpen()) compare.close(true);
}

/* story mode: camera padding keeps the subject left of the drawer; leaving story mode eases it back.
   (Story map labels/highlights arrive with the story in Phase 4: add their layers here when they do.) */
function setStoryMode(on) {
  const map = state.hooks?.map;
  if (!map) return;
  const apply = () => {
    if (!on) {
      setOutlines(false);
      map.easeTo({ padding: { top: 0, bottom: 0, left: 0, right: 0 }, duration: 400, freezeElevation: true });
    }
  };
  if (map.isStyleLoaded()) apply(); else map.once("load", apply);
}

/* vegetation-class outlines over whatever overlay a chapter shows; focus: one PLOTID drawn heavier */
function setOutlines(on, focus = null) {
  const map = state.hooks?.map;
  if (!map) return;
  for (const id of ["story-veg-halo", "story-veg-line"]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
  }
  for (const id of ["story-veg-focus-halo", "story-veg-focus"]) {
    if (!map.getLayer(id)) continue;
    map.setFilter(id, ["==", ["get", "PLOTID"], focus || ""]);
    map.setLayoutProperty(id, "visibility", on && focus ? "visible" : "none");
  }
}

/* camera padding so the chapter's subject sits centred in the visible map, not under the drawer/sheet */
function storyPadding() {
  const map = state.hooks.map;
  return window.matchMedia("(max-width: 900px)").matches
    ? { top: 0, left: 0, right: 0, bottom: Math.round(map.getContainer().clientHeight * 0.5) }
    : { top: 0, left: 0, bottom: 0, right: 424 };
}

function setHeader(i) {
  const story = state.tab === "story";
  $("#storiesH2").textContent = story ? state.storyTitle : "Uses & studies";
  $("#storiesMeta").textContent = story
    ? `Chapter ${i} / ${state.chapters.length} · the map follows the scroll`
    : "Questions this app helps answer, with published findings where they exist";
}

/* ---------------- shell: tabs ---------------- */
function render() {
  const body = $("#storiesBody");
  body.innerHTML = "";
  state.io?.disconnect(); state.io = null;
  const tabs = el("div", "seg story-tabs");
  for (const [id, label] of [["story", "Story"], ["studies", "Studies"]]) {
    const b = el("button", null, label);
    b.setAttribute("aria-pressed", String(state.tab === id));
    b.addEventListener("click", () => { state.tab = id; render(); syncBodyClass(); });
    tabs.append(b);
  }
  body.append(tabs);
  if (state.tab === "story") renderStory(body); else renderStudies(body);
  syncBodyClass();
}

/* ---------------- story tab ---------------- */
function renderStory(body) {
  if (!state.chapters.length) {
    body.append(el("div", "empty", "No story registered yet (data/meta/story_chapters.json)."));
    return;
  }
  setHeader(1);
  for (const ch of state.chapters) body.append(chapterEl(ch));
  body.append(el("p", "stories-note",
    "Study numbers are as printed in the cited papers (pages in story_chapters.json); " +
    "“this app's analysis” numbers come from the app's own data (methods in the data report)."));
  body.append(el("div", "story-spacer"));   // lets the last chapter reach the trigger band

  state.io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (en.isIntersecting && en.target.dataset.id !== state.chapter) {
        state.chapter = en.target.dataset.id;
        body.querySelectorAll(".chapter").forEach((c) => c.classList.toggle("active", c === en.target));
        setHeader(state.chapters.findIndex((c) => c.id === state.chapter) + 1);
        /* IO callbacks run inside the browser's rendering steps, i.e. inside maplibre's own animation
           frame: a flyTo here re-enters the camera's running task queue. Defer to a macrotask. */
        const id = state.chapter;
        setTimeout(() => { if (state.chapter === id) applyChapter(state.chapters.find((c) => c.id === id)); }, 0);
      }
    }
  }, { root: body, rootMargin: "-30% 0px -62% 0px", threshold: 0 });   // a thin band near the top third
  body.querySelectorAll(".chapter").forEach((c) => state.io.observe(c));
  /* the first chapter is the opening state, before any scroll */
  state.chapter = state.chapters[0].id;
  body.querySelector(".chapter")?.classList.add("active");
  setTimeout(() => { if (state.chapter === state.chapters[0].id) applyChapter(state.chapters[0]); }, 0);
}

function chapterEl(ch) {
  const c = el("section", "chapter");
  c.dataset.id = ch.id;
  const h = el("h3", "chapter-title", ch.title);
  if (ch.status === "pending") h.append(" ", el("span", "pill review", "pending"));
  if (ch.status === "provisional") h.append(" ", el("span", "pill review", "provisional"));
  c.append(h);
  c.append(el("p", "chapter-text", ch.text));
  if (ch.status === "pending" && ch.placeholder) c.append(el("div", "story-placeholder", ch.placeholder));
  if (ch.visual?.figure && ch.status !== "pending") {
    const img = el("img", "chapter-figure");
    img.src = dataUrl(ch.visual.figure); img.alt = ch.visual.alt || ch.title; img.loading = "lazy";
    img.title = "Click to enlarge";
    img.addEventListener("click", () => enlarge(img.src, img.alt));
    c.append(img);
  }
  if (ch.visual?.chart && ch.status !== "pending") {
    const mount = el("div", "chapter-chart");
    c.append(mount);
    buildChart(ch.visual.chart, mount).catch(() => mount.append(el("div", "empty", "Chart data not available.")));
  }
  if (ch.visual?.steps?.length && ch.status !== "pending") {
    const row = el("div", "story-actions");
    for (const st of ch.visual.steps) {
      const chip = el("button", "story-chip", st.label);
      chip.addEventListener("click", async () => {
        if (st.layer && state.hooks.overlayAvailable(st.layer)) {
          await state.hooks.setOverlay(st.layer);
          if (st.time != null) await state.hooks.presetTime?.(st.layer, st.time);
        }
        if (st.focus || ch.visual.outlines) setOutlines(true, st.focus || null);
        if (st.camera) fly(st.camera);
      });
      row.append(chip);
    }
    c.append(row);
  }
  if (ch.visual?.note) c.append(el("p", "stories-note", ch.visual.note));
  if (ch.visual?.pending_note) c.append(el("p", "stories-note", ch.visual.pending_note));
  for (const n of ch.numbers || []) c.append(numberEl(n));
  if (ch.sources?.length) {
    const d = el("details", "sources");
    d.append(el("summary", null, "Sources"));
    for (const s of ch.sources) d.append(el("p", null, s));
    c.append(d);
  }
  if (ch.visual?.action === "explore") {
    const btn = el("button", "story-show", "Open the explorer at this view");
    btn.addEventListener("click", async () => { await applyChapter(ch); setOpen(false); });
    c.append(el("div", "story-actions"), btn);
  }
  return c;
}

function numberEl(n) {
  const d = el("div", "story-num");
  d.append(el("span", "story-num-val num", n.value));
  const right = el("div", "story-num-body", n.label);
  const src = n.source || {};
  if (src.kind === "study") {
    right.append(el("div", "meta", `${src.citation}${src.page ? " · " + src.page : ""}`));
  } else if (src.kind === "app") {
    const m = el("div", "meta", `this app's analysis — ${src.method} · `);
    const a = el("a", null, "data report"); a.href = "../DATA_REPORT.md"; a.target = "_blank"; a.rel = "noopener";
    m.append(a);
    right.append(m);
  }
  d.append(right);
  return d;
}

/* chapter applications are serialised: each takes a ticket, and one overtaken by a later scroll stops at
   its next await - otherwise a stale apply can close the comparison while the current one reopens it */
let applySeq = 0;
async function applyChapter(ch) {
  if (!ch) return;
  const ticket = ++applySeq;
  const stale = () => ticket !== applySeq;
  const h = state.hooks, v = ch.visual || {};
  if (v.time) {
    const p = new URLSearchParams();
    for (const [k, val] of Object.entries(v.time)) p.set(k, String(val));
    h.presetClimate?.(p);
  }
  const swipe = v.type === "swipe" && ch.status !== "pending" && h.overlayAvailable(v.right);
  if (!swipe && compare.isOpen()) compare.close(false);   // the next chapter's flyTo sets the pitch
  const layer = swipe ? null : (v.layers || []).find((id) => h.overlayAvailable(id));
  await h.setOverlay(layer || null);
  if (stale()) return;
  setOutlines(Boolean(v.outlines), v.focus || null);
  /* swipe: open first - its synchronous part levels the map (terrain off, max pitch 0) before the
     flight starts. Opening during a flight would stop the camera mid-way, still tilted. */
  const opening = swipe && !compare.isOpen() ? compare.open(h.map, {
      overlayLayerId: "ov-" + v.right, left: v.left_label, right: v.right_label, padding: storyPadding(),
      restorePitch: v.camera?.pitch ?? 0,          // Close keeps the chapter's own view, terrain back on
      /* Close keeps the chapter's subject on screen: the overlay goes back on the main map */
      onClose: () => { if (state.chapter === ch.id) h.setOverlay(v.right); },
    }) : null;
  if (v.camera) fly(v.camera);
  await opening;
}

/* freezeElevation: without it, maplibre 5.6's terrain elevation update can crash mid-flight
   ('reading wrap') and jam the camera's task queue for good */
function fly(cam) {
  let center = [cam.lng, cam.lat], zoom = cam.zoom ?? 8;
  if (cam.bounds) {                      // [w, s, e, n]: frame it in the part of the map the drawer leaves free
    const b = cam.bounds;
    center = [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
    zoom = Math.min(cam.maxZoom ?? state.hooks.map.getMaxZoom(), boundsZoom(b, cam.fill ?? 0.6));
  }
  state.hooks.map.flyTo({ center, zoom, pitch: cam.pitch ?? 0, bearing: 0,
                          duration: 1600, freezeElevation: true, padding: storyPadding() });
}

/* the zoom at which bounds fill `fill` of the visible map (container minus the story padding) */
function boundsZoom(b, fill) {
  const map = state.hooks.map, p = storyPadding(), box = map.getContainer();
  const w = (box.clientWidth - p.left - p.right) * fill, h = (box.clientHeight - p.top - p.bottom) * fill;
  const my = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
  const sx = ((b[2] - b[0]) / 360) * 512, sy = (Math.abs(my(b[3]) - my(b[1])) / (2 * Math.PI)) * 512;
  return Math.log2(Math.min(w / sx, h / sy));
}

/* figure overlay over the map */
function enlarge(src, alt) {
  let ov = $("#figOverlay");
  if (!ov) {
    ov = el("div", "fig-overlay"); ov.id = "figOverlay";
    ov.addEventListener("click", () => (ov.hidden = true));
    document.body.append(ov);
  }
  ov.innerHTML = "";
  const img = el("img"); img.src = src; img.alt = alt || "";
  ov.append(img, el("p", "meta", "Click anywhere to close"));
  ov.hidden = false;
}

/* ---------------- inline charts (data: the app's own series files) ---------------- */
async function series(file) {
  if (!state.series.has(file)) state.series.set(file, (await fetch(dataUrl("series/" + file))).json());
  return state.series.get(file);
}
const yearLabels = (keys, step = 5) => keys.map((k) => (+String(k).slice(0, 4) % step === 0 && (String(k).length === 4 || String(k).endsWith("-01")) ? String(k).slice(0, 4) : ""));

async function buildChart(kind, mount) {
  /* Charts.line / Charts.bars own their element: they clear it and redraw (again once fonts load), so the
     heading and every chart get their own child - never draw into a container that holds anything else.
     Chart kinds arrive with the Ucayali story in Phase 4 (RH distributions per class, annual forest
     loss, shots per filter stage) and read the app's own series/ files, as in the Lake Victoria app. */
  const host = (title, parent = mount) => {
    if (title) parent.append(el("h4", "chapter-chart-title", title));
    const d = el("div"); parent.append(d); return d;
  };
  /* categorical charts are horizontal bars (Charts.hbars): every class keeps its full name; label
     thinning is only for time axes. Classes are ordered by value, largest first. */
  const CLASS_GROUPS = { forest: { label: "Forest regeneration classes", colour: "#2f7d4f" },
                         agri: { label: "Agricultural classes", colour: "#c48a2c" } };
  const byValue = (rows) => [...rows].sort((a, b) => b.value - a.value);
  if (kind === "rh95_by_class") {
    const t = await series("cooley_tables.json");
    Charts.hbars(host("Canopy height by class — mean RH95 (Table 2a)"), byValue(t.classes.map((c) => ({
      label: c.label, value: c.rh95_mean, group: c.group,
      tip: `${c.label}: ${c.rh95_mean.toFixed(2)} m (sd ${c.rh95_sd.toFixed(2)} m; n = ${c.n.toLocaleString("en-US")} footprints, Table 2a)` }))),
      { format: (v) => v.toFixed(2) + " m", groups: CLASS_GROUPS });
    mount.append(el("p", "stories-note", "The paper's published means (ground returns removed), Table 2a p.16, "
      + "ordered by value; hover a bar for its standard deviation and footprint count."));
  } else if (kind === "rh_ratio_by_class") {
    const t = await series("cooley_tables.json");
    Charts.hbars(host("Canopy shape — mean RH50/RH95 (Table 4a)"), byValue(t.classes.map((c) => ({
      label: c.label, value: c.ratio_mean, group: c.group,
      tip: `${c.label}: ${c.ratio_mean.toFixed(2)} (Table 4a; n = ${c.n.toLocaleString("en-US")} footprints, Table 2a)` }))),
      { format: (v) => v.toFixed(2), groups: CLASS_GROUPS, max: 1 });
    mount.append(el("p", "stories-note", "Scale 0–1: closer to 1 = energy returned high in the canopy. "
      + "The paper's values, Table 4a p.17 (abstract p.1: 0.58 / 0.54 / 0.53), ordered by value."));
  } else if (kind === "forest_loss_classes") {
    const f = await series("forest_classes.json");
    const d = f.regions["Ucayali"] || {};
    const colours = { 1: "#2e5573", 2: "#1f6b45", 3: "#d64530", 4: "#d8c26a" };
    Charts.hbars(host("Department land by GEOBOSQUES class, km²"), byValue(Object.entries(d).map(([c, km]) => ({
      label: f.classes[c] || c, value: km, group: c,
      tip: `${f.classes[c] || c}: ${Math.round(km).toLocaleString("en-US")} km² (this app's analysis)` }))),
      { format: (v) => Math.round(v).toLocaleString("en-US") + " km²",
        groups: Object.fromEntries(Object.keys(d).map((c) => [c, { label: "", colour: colours[c] || "#888" }])) });
    mount.append(el("p", "stories-note", "This app's analysis of the GEOBOSQUES combined raster; ordered by area."));
  } else if (kind === "fire_detections") {
    const f = await series("fire.json");
    const d = f.snpp_detections_dept;
    const years = Object.keys(d);
    Charts.bars(host("VIIRS active-fire detections per year (department)"), {
      labels: years.map((x) => (+x % 4 === 0 ? x : "")), values: Object.values(d), height: 150,
      format: (v) => Math.round(v).toLocaleString(), highlight: years.indexOf("2024") });
    mount.append(el("p", "stories-note", "S-NPP only, confidence nominal/high; this app's analysis."));
  } else {
    throw new Error("unknown chart kind: " + kind);
  }
}

/* ---------------- studies tab (unchanged behaviour) ---------------- */
function renderStudies(body) {
  setHeader(0);
  if (!state.stories.length) {
    body.append(el("div", "empty", "No studies registered yet (data/meta/studies.json)."));
    return;
  }
  const active = state.hooks.activeOverlay();
  if (active) {
    const t = state.hooks.overlayTitle(active);
    if (t && state.stories.some((s) => (s.layers || []).includes(active))) {
      body.append(el("p", "stories-note", `Cards about <strong>${t}</strong> first.`));
    }
  }
  const hit = (s) => active && (s.layers || []).includes(active);
  for (const s of [...state.stories.filter(hit), ...state.stories.filter((s) => !hit(s))]) body.append(card(s));
  body.append(el("p", "stories-note",
    "Published findings quote the cited paper (page and figure recorded in studies.json); " +
    "explore cards are open questions, not claims."));
}

function card(s) {
  const c = el("article", "story-card");
  c.dataset.kind = s.kind;
  const head = el("button", "story-head");
  head.setAttribute("aria-expanded", String(state.expanded === s.id));
  head.append(el("span", "story-q", s.question),
              el("span", "pill " + (s.kind === "published" ? "validated" : ""),
                 s.kind === "published" ? "study" : "explore"));
  head.addEventListener("click", () => { state.expanded = state.expanded === s.id ? null : s.id; render(); });
  c.append(head);

  if (state.expanded !== s.id) return c;
  const bd = el("div", "story-body");
  if (s.finding) bd.append(el("p", "story-finding", s.finding));
  if (s.caveat) bd.append(el("p", "story-caveat", "Caveat: " + s.caveat));
  if (s.citation) {
    const p = el("p", "meta", s.citation + (s.doi ? " · " : ""));
    if (s.doi) {
      const a = el("a", null, "doi:" + s.doi);
      a.href = "https://doi.org/" + s.doi; a.target = "_blank"; a.rel = "noopener";
      p.append(a);
    }
    bd.append(p);
  }
  const layers = (s.layers || []).filter((id) => state.hooks.overlayAvailable(id));
  const missing = (s.layers || []).filter((id) => !state.hooks.overlayAvailable(id));
  const actions = el("div", "story-actions");
  if (layers.length || s.camera || s.open_panel) {
    const btn = el("button", "story-show", "Show me on the map");
    btn.addEventListener("click", () => applyCard(s, layers[0]));
    actions.append(btn);
    for (const id of layers.slice(1)) {
      const chip = el("button", "story-chip", state.hooks.overlayTitle(id) || id);
      chip.title = "Switch the map to this layer";
      chip.addEventListener("click", () => applyCard(s, id));
      actions.append(chip);
    }
  } else {
    actions.append(el("span", "meta", "Not in the app yet — no layer to show."));
  }
  bd.append(actions);
  if (missing.length) bd.append(el("p", "meta", "Layer not built in this copy: " + missing.join(", ")));
  c.append(bd);
  return c;
}

async function applyCard(s, layerId) {
  const h = state.hooks;
  if (s.time) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(s.time)) p.set(k, String(v));
    h.presetClimate?.(p);
  }
  if (layerId) await h.setOverlay(layerId);
  if (s.camera) {
    h.map.flyTo({ center: [s.camera.lng, s.camera.lat], zoom: s.camera.zoom ?? 8,
                  pitch: s.camera.pitch ?? 0, bearing: 0, duration: 1400, freezeElevation: true });
  }
  /* Studies only: close so the map state (and its legend) is in full view */
  setOpen(false);
}
