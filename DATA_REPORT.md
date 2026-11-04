# MOSAIC Ucayali Explorer — data report

Status: Phase 1 (scaffold, base layers, GEDI pilot). Started 2026-11-04. Owner: Andres Aguilar
(CGIAR). This report records, for every layer the app serves: the source as found, the licence as
stated by that source, processing steps, and the method notes behind any number the app prints.
Rules: published numbers appear only as printed in the cited paper, with the page recorded;
numbers computed by this pipeline are labelled **"this app's analysis"**; no causal claims beyond
the papers.

## 1. Layers

| Layer (registry id) | Source (as found) | Licence (as stated by the source) | Resolution / period | Pipeline step |
|---|---|---|---|---|
| terrain | `inputs/dem_ucayali_basin_extent.tif`, 30 m, EPSG:4326 — **provenance to confirm** (Earth Engine export; script pending in `prep/`) | per DEM source — **to confirm** | 30 m; epoch tbc | 02 |
| s2_rgb | `inputs/Sentinel2_uyacali_Mosaic_2025.tif`, Sentinel-2 L2A RGB (B4/B3/B2) mosaic, Earth Engine export (script pending in `prep/`) | Copernicus Sentinel data: free use, incl. reproduction and distribution, with ESA attribution | 30 m; 2025 | 03 |
| department | `inputs/ucayali.shp` (FUENTE=INEI) | the same referential boundaries on datosabiertos.gob.pe (publisher: **IGN**) carry the **Open Data Commons Attribution License (ODC-By)** — note the local file attributes INEI while the portal names IGN; recorded as "INEI/IGN via datosabiertos.gob.pe" until confirmed | 1:100,000; portal release 2022-03-10, modified 2023-08-01 | 01 |
| admin_boundaries | `DISTRITOS_LIMITES.zip`, resource of the IGN dataset "Limites Departamentales", datosabiertos.gob.pe (dataset id 6c5c52fd-047d-4ba7-9ac7-3865860118c2); provinces dissolved from districts | **ODC-By** (stated twice on the dataset page: "Licencia" block and DCAT table) | 1:100,000; same release | 01 (portal refuses non-browser downloads — fetch the zip in a browser into `<work>/downloads/`, step 01 then uses it) |
| osm_labels | Protomaps daily OSM basemap extract (build date in config), labels only | **ODbL 1.0** — © OpenStreetMap contributors; fonts Noto Sans (SIL OFL) | vector, z0–12; OSM as of build date | 04 (needs the go-pmtiles CLI; pending) |
| veg_classes | Cooley et al., "Vegetation typology classification and data set in Ucayali, Peru", v4.0, CaltechDATA, doi:10.22002/D1.2318 (files `_VegTypol_Ucayali_v4__Feb2022.geojson` + README PDF) | **CC0** ("cc-zero" on the record page) | 324 polygons digitised on 2020/2021 imagery (MAXAR 2020; Google Earth/Bing ~2015–2019, Planet-verified) | 05 |
| (phase 2) gedi_* | GEDI02_A v002, NASA LP DAAC (collection C2142771958-LPCLOUD), via Harmony subsets | NASA Earth science data: free and open; cite the product DOI | 25 m footprints; 2019-04-18 → 2021-12-31 (replication window) | 10–13 |

## 2. Notes

- **Shared grid.** The DEM and the S2 mosaic sit on one grid: EPSG:4326, 20237 × 15535,
  0.00026949° (~30 m), bounds −75.9482, −11.4484 → −70.4944, −7.2618. Neither declares nodata;
  the S2 encoder treats all-zero pixels as transparent, and DEM padding is synthetic (see below).
- **Terrain padding.** As in the Lake Victoria app, the mercator DEM is padded (~300 km) and the
  padding filled with smoothed nearest-edge elevations so a bounded camera never sees missing
  tiles; elevations there are synthetic, for display only (registry caveat says so).
- **DEM provenance — OPEN ITEM (reconstruction filed).** The original export scripts were not
  found; `prep/gee_dem_export.js` and `prep/gee_s2_mosaic_2025.js` are **RECONSTRUCTIONS**
  (headers say so) built from the files' own properties — grid EPSG:4326 at 0.000269494585236°
  (= GEE scale:30), bounds −75.9482, −11.4484 → −70.4944, −7.2618, S2 bands B4/B3/B2 uint16
  harmonized, DEM float32 with band name **'DEM'** (the GEE band name of Copernicus GLO-30).
  The DEM is assumed **Copernicus GLO-30** per Andres (2026-11-04), supported by the band name;
  the registry/About keep "to confirm" until the real script or an explicit confirmation lands.
  The reconstructions have not been run.
- **S2 reflectance scale.** Checked on 3 × 1024² sample windows at tiling time (03_s2 logs the
  1/5/50/95/99 percentiles); the fixed stretch is 0–3000 with gamma 2.2. If the darkest sampled
  reflectance is ≥ 900 the post-2022 +1000 L2A offset is suspected and the log warns — fix the
  Earth Engine export, not the stretch.
- **S2 tile-size check (2026-11-04).** `s2_rgb.pmtiles` is 5.0 MB (1,828 WebP tiles ≈ 2.7 KB
  each) vs 38 MB for the Lake Victoria app. Verified, not a defect: max zoom 12 (native 30 m),
  WebP quality 82 (same as LVB); the input is **masked to the department** — 62.1 % of the
  raster is empty (all outside the boundary), **0.000 % empty inside the department** (no cloud
  gaps; full-year median). So only ~38 % of candidate tiles carry data, and what they carry is
  near-uniform dense forest, which WebP compresses far harder than the LVB's heterogeneous
  water/agriculture/urban scene. Visual check at z8 (department) and z12 (Pucallpa street grid)
  is clean and continuous.
- **Boundaries.** The IGN portal page states the boundaries are *referential* at 1:100,000 — not
  an official delimitation (registry caveats carry this). Geometry simplified ~90 m for display.
  The portal's download endpoint answers HTTP 418 to non-browser clients; the zip is fetched once
  manually and cached in the work dir (path printed by step 01).
- **Cooley polygons.** The file's class value `Bosque_secudario_o_degradado` (83 features) is the
  same class as `Bosque_secundario_o_degradado` (133) — a spelling variant in the source. The app
  normalises to the correct spelling and keeps the original in `COBERTURA_RAW`. Class mapping to
  the paper (README Table 1 pp. 6–10; paper Table 1 pp. 7–10):

  The app's English labels are **exactly the README Table 1 names** (checked 2026-11-04 against
  README pp. 2, 6–10 and the paper's Table 1 pp. 7–10):

  | GeoJSON class (normalised) | n | README Table 1 English name (= app label) | Paper's six analysis classes? |
  |---|---|---|---|
  | Bosque_de_colina_baja | 12 | Mature lowland forest ("Lowland forest: old-growth"; paper: "Bosque maduro de colina baja / Mature lowland forest") | yes — see the sampling note below |
  | Bosque_secundario_o_degradado | 216 | Secondary or degraded lowland forest (paper: "Secondary lowland forest") | yes |
  | Purma | 77 | Young vegetation regrowth (purma) | yes |
  | Pastizales_o_herbazales_degradados | 10 | Degraded shrubland or pasture (README regrowth class 4) | no (not in Table 2) |
  | Bosque_de_colina_alta | 4 | **Cloud forest** — the README's own translation of "bosque de colina alta" (old-growth forest of mountainous regions, ~20–25 m, README p.2 & Table 1B p.7) | no |
  | Aguajales | 3 | Palm groves (inundated) — "Aguajales / palmerales (inundable)" | no |
  | Bosque_inundado | 2 | Wetland forest — the README spells the class "Bosque inundable"; the GeoJSON's "Bosque_inundado" is the same class (spelling variant, recorded here) | no |
  | (absent) | 0 | Mature oil palm; monocrop cacao; agroforestry cacao | in the paper only — **no polygons published**, so those results cannot be reproduced from this dataset; any comparison this app draws covers the forest classes only |

  **Mature-forest sampling note:** the paper's Table 2a reports 2,063 mature-forest footprints
  from only 12 digitised `Bosque_de_colina_baja` polygons — these 12 are large (95,147 ha total,
  this app's analysis), so the footprint count is plausible, but per-polygon leverage is high;
  treat per-class comparisons accordingly.
- **Quoting the paper's canopy numbers.** Table 2a (p.16, ground returns removed): mature
  29.55 ± 6.78 m, secondary 21.25 ± 8.85 m. Table 2b (p.16, untransformed — the abstract's
  numbers): mature 29.40 ± 6.89 m, secondary 20.82 ± 9.15 m. **Always name the table** a number
  comes from.
- **Method notes — inconsistencies in Cooley et al. (2024), recorded for every use:**
  1. Discussion text (sect. 4.1, p.13) states RH50/RH95 "highest **secondary** (0.53) closely
     followed by **mature** (0.54)" — the reverse of Table 4a (p.17) and the abstract (p.1:
     mature 0.58, secondary 0.54, oil palm 0.53). The app quotes **Table 4a / abstract** and
     notes the discrepancy in the card caveat.
  2. Table 4b (p.17) appears to have the mature and oil-palm rows swapped (mature RH95 11.28 m,
     oil palm 29.4 m). Table 4b is not quoted.

## 3. GEDI method (draft — Phase 2 will finalise with the pilot/full-run numbers)

- **Product.** GEDI L2A Geolocated Elevation and Height Metrics, **v002**, NASA LP DAAC
  (C2142771958-LPCLOUD). The paper's Data Availability links v001 (p.20); v002 is the current
  archive — noted as a deviation.
- **Access.** CMR search via earthaccess; spatial (department bbox −75.95, −11.45 → −70.49, −7.26)
  + variable subsets via NASA **Harmony**, one job per calendar month. Credentials from
  `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD` or `~/.netrc`; never stored in the repo.
- **Two windows** (config `[gedi]`): **replication** 2019-04-18 → 2021-12-31, compared with the
  paper's tables; **mission** 2019-04-18 → latest granule, for the app's own canopy products.
  Inventory 2026-11-04: replication **650 granules / 33 months with data** (826 GB whole →
  ~3.1 GB subset, ~3.3 h of Harmony wall time at the pilot rate); mission **1,195 granules /
  63 months with data, last 2025-07** (1.49 TB whole → ~5.6 GB subset, ~6.5 h). Pilot month
  2020-07 (28 granules).
- **Variables requested** (per full-power beam): rh, sensitivity, quality_flag, degrade_flag,
  elev_lowestmode, lat/lon_lowestmode, shot_number, solar_elevation,
  geolocation/elev_lowestmode_a1..a6.
- **Two shot sets from one Parquet** (quality_flag and degrade_flag are stored as columns,
  never used to build the Parquet):
  - **paper set** (replication; compared with Tables 2a/3a/4a): exactly the filters of
    sect. 2.4 pp. 11–12 — (1) full-power beams only: BEAM0101, BEAM0110, BEAM1000, BEAM1011
    (the paper says "power beam mode only" without listing IDs); (2) beam sensitivity ≥ 0.9 —
    implemented as 0.9 ≤ sensitivity ≤ 1.0, because sensitivity is defined as a fraction and
    the v002 files carry fill values up to ~98 on cloud-struck shots, which a bare "≥ 0.9"
    would wrongly pass (observed: 70 such shots inside the mature-forest polygons with
    RH95 = 0 m and "ground" at cloud height); (3) ground-elevation agreement ≤ 2 m across
    the five algorithms left after dropping the one farthest from the six-algorithm median
    ("after removing the algorithm that yielded the largest outlier elevation", p.12);
    plus the department bbox. The paper does not filter on quality_flag or degrade_flag.
  - **strict set** (the app's own map products only, labelled as such): paper set plus
    quality_flag = 1 and degrade_flag = 0.
- **Homogeneous-area criterion.** Shots compared with the vegetation polygons are counted twice:
  within the polygon, and within the polygon eroded by 32.5 m, so the ~65 m diameter
  (25 m footprint ± 2σ ≈ 20 m geolocation error, Fig. 6 p.15) lies in one class.
- **Storage.** Filtered shots to Parquet (zstd), one file per granule, partitioned by month, in
  the work dir; full RH profile (101 values) kept per shot plus named rh50/75/95/98 columns.
  Per-stage counts recorded in `filter_counts.json` → this section when the pilot lands.
- **Pilot run (2020-07, executed 2026-11-04; filters re-run after the review).** Harmony job
  1e9cb8ec-94ab-43bd-9e69-a6fc8a2dfa49: 26 granules subset with the variable list above,
  **132 MB** downloaded in ~6 min wall (vs ~33 GB for the same granules whole). Filter stages
  (shots, cumulative): in subsets **514,148** (the four power beams only — Harmony returns only
  the requested beams); 0.9 ≤ sensitivity ≤ 1.0 **394,409**; ground-elevation agreement ≤ 2 m
  (5 of 6 algorithms) **110,832** = the **paper set** (bbox cut nothing — Harmony already
  clipped); quality_flag = 1 & degrade_flag = 0 on top → **81,128** = the **strict set**.
  Parquet: 21 files, ~15 MB.
- **Pilot shots in the Cooley polygons** (one month only — small numbers, QA not science).
  paper set: **95** inside, **89** with the 65 m homogeneity criterion (polygon eroded 32.5 m);
  strict set: 93 / 87. By class (paper, inside/65 m): Bosque_de_colina_alta 79/76,
  Bosque_secundario_o_degradado 7/5, Pastizales_o_herbazales_degradados 5/4, Purma 4/4,
  **Bosque_de_colina_baja 0/0 in both sets** — 142 raw July-2020 shots fall inside the
  mature-forest polygons but all carry fill sensitivity (> 1) and cloud-height "ground"
  elevations, i.e. genuinely invalid returns, not a filter choice; expected to fill in over
  the full window. Mean RH95 (this app's analysis, one month, tiny n), paper set:
  colina_alta 29.8 m, secundario 30.5 m (n = 7), pastizales 7.9 m, purma 4.0 m — strict set
  nearly identical (30.3 / 30.5 / 7.9 / 4.0).
- **Full-run projection** from the pilot (4.7 MB per subset granule, ~6 min of Harmony wall per
  month): replication window 650 granules / 33 months ≈ **3.1 GB subsets, ~3.3 h**, Parquet
  ≈ 0.4 GB; mission window 1,195 granules / 63 months ≈ **5.6 GB subsets, ~6.5 h**, Parquet
  ≈ 0.8 GB. Comfortably within the work-disk budget.

## 4. References

- Cooley, S.S., Pinto, N., Becerra, M., Vela Alvarado, J.W., Fahlen, J.C., Rivera, O., Fricker,
  G.A., De Los Ríos Dantas, A.R., Aguilar-Amuchastegui, N., Reygadas, Y., Gan, J., DeFries, R. &
  Menge, D.N.L. (2024). Combining spaceborne lidar from the Global Ecosystem Dynamics
  Investigation with local knowledge for monitoring fragmented tropical landscapes: A case study
  in the forest–agriculture interface of Ucayali, Peru. *Ecology and Evolution* 14:e70116.
  doi:10.1002/ece3.70116 (CC BY).
- Cooley, S., Pinto, N., Aguilar-Amuchastegui, N., Vela Alvarado, J. & Fahlen, J. (2021).
  Vegetation typology classification and data set in Ucayali, Peru (Version 4.0) [Dataset].
  CaltechDATA. doi:10.22002/D1.2318 (CC0).
- Dubayah, R., et al. (2020). The Global Ecosystem Dynamics Investigation: High-resolution laser
  ranging of the Earth's forests and topography. *Science of Remote Sensing* 1:100002.
  doi:10.1016/j.srs.2020.100002.
- GEDI L2A Elevation and Height Metrics Data Global Footprint Level V002 (GEDI02_A.002), NASA
  LP DAAC. doi:10.5067/GEDI/GEDI02_A.002.
- Potapov, P., et al. (2021). Mapping global forest canopy height through integration of GEDI and
  Landsat data. *Remote Sensing of Environment* 253:112165. doi:10.1016/j.rse.2020.112165
  (filter methodology followed by Cooley et al.).
- Lang, N., Jetz, W., Schindler, K. & Wegner, J.D. (2023). A high-resolution canopy height model
  of the Earth. *Nature Ecology & Evolution* 7:1778–1789. doi:10.1038/s41559-023-02206-6
  (CC BY 4.0 per the ETH Research Collection record; planned Phase-3 layer).
- Instituto Geográfico Nacional (IGN). Limites Departamentales / Distritales. Plataforma Nacional
  de Datos Abiertos, datosabiertos.gob.pe (ODC-By).
- OpenStreetMap contributors (ODbL 1.0), via Protomaps basemap builds (protomaps.com).
- Contains modified Copernicus Sentinel-2 data [2025].
