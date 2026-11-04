"""Step 20 - forest loss: GEOBOSQUES (MINAM/SERFOR) original 30 m rasters - forest/non-forest
2000 baseline and annual forest loss 2001-2024 (2025 update if published).

geobosques.minam.gob.pe answers HTTP 403 to every non-browser client (checked 2026-11-04), so the
rasters are downloaded ONCE by hand from the GEOBOSQUES "Descargas" page into
<work>/downloads/geobosques/ - any filename containing 'bosque_no_bosque' or 'bnb' (baseline) and
'perdida' (loss). ALSO copy the licence/terms text from the download page into
<work>/downloads/geobosques/LICENCIA.txt - DATA_REPORT must quote it exactly as stated.

Outputs: data/tiles/forest_loss.pmtiles (loss year, sequential palette, any-loss visible zoomed
out), data/tiles/forest2000.pmtiles (baseline forest mask), series/forest_loss.json (annual loss
km² for the department and per province). Hansen GFC stays a fallback only on Andres' word.

Usage:  python scripts/20_forest_loss.py [--area pilot|full] [--force]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling

from tiler import clip_source, cut_tiles, encode_png, make_colormap_encoder, max_levels, warp_to_mercator

DL = None  # set in main: <work_root>/downloads/geobosques


def find(keywords):
    for f in sorted(DL.glob("*.tif")):
        if any(k in f.name.lower() for k in keywords):
            return f
    return None


def year_values(path):
    """Loss rasters code years either as 1..n (2000+v) or as 2001..2025; detect from the data."""
    with rasterio.open(path) as src:
        a = src.read(1, out_shape=(min(2048, src.height), min(2048, src.width)))
    vals = np.unique(a)
    vals = vals[(vals > 0) & (vals < 60000)]
    if len(vals) and vals.max() > 1900:
        return {int(v): int(v) for v in vals}
    return {int(v): 2000 + int(v) for v in vals}


def viridis_years(years):
    import colorsys
    out = {}
    lo, hi = min(years), max(years)
    for v, y in years.items():
        t = (y - lo) / max(hi - lo, 1)
        # dark violet -> teal -> yellow, hand-rolled viridis-like ramp
        r, g, b = colorsys.hsv_to_rgb(0.75 - 0.6 * t, 0.85 - 0.35 * t, 0.45 + 0.5 * t)
        out[v] = (int(r * 255), int(g * 255), int(b * 255), 235)
    return out


def main():
    global DL
    args = common.setup("20_forest_loss")
    DL = common.WORK_ROOT / "downloads" / "geobosques"
    DL.mkdir(parents=True, exist_ok=True)
    bnb = find(["bosque_no_bosque", "bnb", "no_bosque"])
    loss = find(["perdida", "pérdida", "loss"])
    if not loss:
        log.warning(
            "GEOBOSQUES rasters not found - STEP SKIPPED (the forest-loss layer shows 'not built').\n"
            "The site blocks scripted downloads (HTTP 403, checked 2026-11-04). In a browser, open\n"
            "https://geobosques.minam.gob.pe/geobosque/view/descargas.php and download the national\n"
            "(or Ucayali) 30 m rasters:\n"
            "  - Bosque / No bosque 2000  -> save under " + str(DL) + "\\ (name containing 'bosque_no_bosque')\n"
            "  - Pérdida de bosque 2001-2024 (or -2025) -> name containing 'perdida'\n"
            "and paste the page's licence/terms text into LICENCIA.txt in the same folder. Re-run.")
        return
    lic = DL / "LICENCIA.txt"
    log.info("loss raster: %s | baseline: %s | licence note: %s",
             loss.name, bnb.name if bnb else "missing", "present" if lic.exists() else "MISSING")

    dept = gpd.read_file(common.INPUTS / common.CFG["inputs"]["department"]).to_crs("EPSG:4326")
    provs = gpd.read_file(common.DATA / "vectors" / "provinces.geojson") \
        if (common.DATA / "vectors" / "provinces.geojson").exists() else None
    zones = {"Ucayali": dept.union_all()}
    if provs is not None:
        zones.update({r.province: r.geometry for r in provs.itertuples()})

    clip = clip_source(loss, "geobosques_loss", common.bbox())
    years = year_values(clip)
    log.info("loss raster values -> years: %s..%s (%d values)",
             min(years.values()), max(years.values()), len(years))

    areas = common.class_areas_km2(clip, zones)
    series = {z: {str(years[v]): km for v, km in sorted(d.items())} for z, d in areas.items()}
    s = common.DATA / "series"
    s.mkdir(parents=True, exist_ok=True)
    (s / "forest_loss.json").write_text(json.dumps({
        "unit": "km2", "regions": series,
        "method": "GEOBOSQUES loss raster clipped to the department; pixel areas with cos(lat) "
                  "correction; this app's analysis"}, indent=1), encoding="utf-8")
    common.record("20_forest_loss", s / "forest_loss.json")

    out = common.DATA / "tiles" / "forest_loss.pmtiles"
    if args.force or not out.exists():
        merc = warp_to_mercator(clip, f"gbloss_{common.AREA}", 12, Resampling.nearest,
                                dtype="uint16" if max(years) > 255 else "uint8", nodata=0)
        levels = max_levels(merc, common.CFG["tiles"]["minzoom"], 12)
        cmap = viridis_years(years)
        if max(years) > 255:                       # year-coded uint16 values: direct match encoder
            def enc(data):
                a = data[0]
                rgba = np.zeros(a.shape + (4,), "u1")
                for v, c in cmap.items():
                    rgba[a == v] = c
                if not rgba[..., 3].any():
                    return None
                return encode_png(rgba)
        else:
            enc = make_colormap_encoder(cmap, 0)
        cut_tiles(merc, out, "GEOBOSQUES forest loss", "png", common.CFG["tiles"]["minzoom"], 12,
                  enc, Resampling.nearest, levels=levels)
        common.record("20_forest_loss", out)

    if bnb:
        clip_b = clip_source(bnb, "geobosques_bnb", common.bbox())
        out_b = common.DATA / "tiles" / "forest2000.pmtiles"
        if args.force or not out_b.exists():
            merc_b = warp_to_mercator(clip_b, f"gbbnb_{common.AREA}", 11, Resampling.nearest,
                                      dtype="uint8", nodata=0)
            with rasterio.open(merc_b) as srcb:
                vals = np.unique(srcb.read(1, out_shape=(1024, 1024)))
            log.info("baseline values: %s (forest class assumed the largest nonzero)", vals.tolist())
            cmap_b = {int(v): (49, 104, 68, 200) for v in vals if v > 0}
            cut_tiles(merc_b, out_b, "GEOBOSQUES forest 2000", "png",
                      common.CFG["tiles"]["minzoom"], 11, make_colormap_encoder(cmap_b, 0),
                      Resampling.nearest)
            common.record("20_forest_loss", out_b)

    lic_txt = lic.read_text(encoding="utf-8", errors="replace").strip() if lic.exists() else \
        "LICENCIA.txt not provided yet - copy the licence text from the GEOBOSQUES download page"
    common.update_registry("forest_loss", {
        "title": "Forest loss (GEOBOSQUES)", "group": "Land", "type": "thematic",
        "urls": {"tiles": "tiles/forest_loss.pmtiles",
                 **({"forest2000": "tiles/forest2000.pmtiles"} if bnb else {})},
        "years": sorted(set(years.values())),
        "source": "MINAM/SERFOR GEOBOSQUES forest monitoring (Bosque/No bosque 2000 + annual "
                  "loss), 30 m, department clip; downloaded manually from "
                  "geobosques.minam.gob.pe (the site blocks scripted access)",
        "period": f"{min(years.values())}-{max(years.values())}",
        "licence": lic_txt[:400],
        "citation": "GEOBOSQUES - Plataforma de monitoreo de los cambios sobre la cobertura de "
                    "los bosques (MINAM/SERFOR), geobosques.minam.gob.pe",
        "caveats": "Loss year colours: early years dark, recent years bright. Annual km² per "
                   "province is this app's analysis."})


if __name__ == "__main__":
    main()
