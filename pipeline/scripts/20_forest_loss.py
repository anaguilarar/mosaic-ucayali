"""Step 20 - forest loss: GEOBOSQUES (MINAM/SERFOR) 30 m rasters, downloaded manually in a
browser (the site answers HTTP 403 to every script) into <work>/downloads/geobosques/ (zips
extracted; subfolders are searched).

GEOBOSQUES publishes TWO raster products (metadata docx in the download):
  A. combined "Bosque - No Bosque y Perdida": one national uint8 raster, EPSG:32718, classes
     1 Hidrografia, 2 Bosque <year>, 3 Perdida 2001-<year> (all years lumped), 4 No Bosque 2000,
     5 No Monitoreado, 0 nodata  -> the app's forest/loss/non-forest layer + class areas
  B. annual "Perdida de bosque" with the year field ("campo 'Ano'")  -> the loss-year layer
     (sequential palette) and the annual km2 series, built when that file lands here too
The product's own metadata states LICENCIA: "-" (none stated) and requires the citation
"MINAM (PNCBMCC) y MIDAGRI (SERFOR) ... Acceso a traves de GEOBOSQUES".

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
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds as win_from_bounds

from tiler import cut_tiles, encode_png, make_colormap_encoder, max_levels, warp_to_mercator

# source codes: 1 Hidrografía, 2 Bosque, 3 Pérdida, 4 No Bosque 2000, 5 No Monitoreado, 0 nodata.
# The zoom-out pyramid keeps each 2x2 block's MAX code, so codes are REMAPPED by display priority
# (loss on top, then non-forest, forest, water) before tiling: 3<->4 swapped.
PRIORITY_LUT = [0, 1, 2, 4, 3, 0]           # index = source code -> display code (5 -> transparent)
COMBINED_CLASSES = {1: ("Hidrografía", "Water", (46, 85, 115, 200)),
                    2: ("Bosque", "Humid Amazon forest (remaining)", (31, 107, 69, 170)),
                    3: ("No Bosque 2000", "Non-forest at the 2000 baseline", (216, 194, 106, 140)),
                    4: ("Pérdida 2001–2024", "Forest loss 2001–2024", (214, 69, 48, 235))}


def find(keywords, exclude=()):
    for f in sorted(DL.rglob("*.tif")):
        n = f.name.lower()
        if any(k in n for k in keywords) and not any(x in n for x in exclude):
            return f
    return None


def clip_any_crs(src_path: Path, out_name: str, bbox4326) -> Path:
    """Windowed copy cut to the lon/lat bbox, whatever the source CRS (GEOBOSQUES is UTM 18S)."""
    out = common.WORK / f"{out_name}_clip.tif"
    with rasterio.open(src_path) as src:
        if out.exists() and out.stat().st_mtime >= Path(src_path).stat().st_mtime:
            return out
        b = transform_bounds("EPSG:4326", src.crs, *bbox4326, densify_pts=21)
        win = win_from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        prof = src.profile | dict(width=int(win.width), height=int(win.height),
                                  transform=src.window_transform(win), tiled=True,
                                  blockxsize=512, blockysize=512, compress="DEFLATE")
        with rasterio.open(out, "w", **prof) as dst:
            for r0 in range(0, int(win.height), 2048):
                h = min(2048, int(win.height) - r0)
                w2 = rasterio.windows.Window(win.col_off, win.row_off + r0, win.width, h)
                dst.write(src.read(1, window=w2), 1,
                          window=rasterio.windows.Window(0, r0, win.width, h))
    log.info("clipped %s -> %s (%dx%d, %s)", src_path.name, out.name, win.width, win.height, src.crs)
    return out


def year_values(path):
    with rasterio.open(path) as src:
        a = src.read(1, out_shape=(min(2048, src.height), min(2048, src.width)))
    vals = np.unique(a)
    vals = vals[(vals > 0) & (vals < 60000)]
    if len(vals) and vals.max() > 1900:
        return {int(v): int(v) for v in vals}
    return {int(v): 2000 + int(v) for v in vals}


def viridis_years(years):
    import colorsys
    lo, hi = min(years.values()), max(years.values())
    out = {}
    for v, y in years.items():
        t = (y - lo) / max(hi - lo, 1)
        r, g, b = colorsys.hsv_to_rgb(0.75 - 0.6 * t, 0.85 - 0.35 * t, 0.45 + 0.5 * t)
        out[v] = (int(r * 255), int(g * 255), int(b * 255), 235)
    return out


def main():
    global DL
    args = common.setup("20_forest_loss")
    DL = common.WORK_ROOT / "downloads" / "geobosques"
    DL.mkdir(parents=True, exist_ok=True)
    combined = find(["bosque_no_bosque", "bosque_nobosque", "bnb"])
    annual = find(["perdida", "pérdida", "ano", "año"], exclude=["bosque_no_bosque", "bosque_nobosque"])
    if not combined and not annual:
        log.warning("no GEOBOSQUES rasters under %s - step skipped. Download them in a browser from "
                    "https://geobosques.minam.gob.pe/geobosque/view/descargas.php (both the combined "
                    "Bosque/No bosque zip and the annual Perdida product) and re-run.", DL)
        return

    dept = gpd.read_file(common.INPUTS / common.CFG["inputs"]["department"]).to_crs("EPSG:4326")
    provs_f = common.DATA_FULL / "vectors" / "provinces.geojson"
    zones4326 = {"Ucayali": dept.union_all()}
    if provs_f.exists():
        provs = gpd.read_file(provs_f)
        zones4326.update({r.province: r.geometry for r in provs.itertuples()})

    reg = {"title": "Forest & loss (GEOBOSQUES)", "group": "Land", "type": "thematic", "urls": {},
           "source": "GEOBOSQUES (MINAM PNCBMCC + SERFOR/MIDAGRI) Bosque Húmedo Amazónico monitoring, "
                     "30 m, national rasters clipped to the department; downloaded manually "
                     "(the site blocks scripted access)",
           "licence": "the product metadata's LICENCIA field is '-' (no licence stated); citation "
                      "required as given by GEOBOSQUES",
           "citation": "MINAM (PNCBMCC) y MIDAGRI (SERFOR). 'Mapa del Bosque Húmedo Amazónico "
                       "Peruano, 2000-2024'. Acceso a través de GEOBOSQUES, geobosques.minam.gob.pe",
           "caveats": "Covers the Bosque Húmedo Amazónico monitoring area only ('No Monitoreado' "
                      "elsewhere). Loss includes natural losses, not only deforestation; river-channel "
                      "migration losses are excluded (metadata PRECAUCIONES). 2001-2016 follow the UMD "
                      "methodology, 2017+ the PNCBMCC methodology. Areas are this app's analysis."}

    if combined:
        raw = clip_any_crs(combined, "geobosques_bnb", common.bbox())
        clip = raw.with_name("geobosques_bnb_pri.tif")        # priority-remapped copy (see LUT above)
        if args.force or not common.fresh(clip, raw):
            lut = np.array(PRIORITY_LUT + [0] * 250, "u1")
            with rasterio.open(raw) as src:
                with rasterio.open(clip, "w", **src.profile) as dst:
                    for r0 in range(0, src.height, 2048):
                        h = min(2048, src.height - r0)
                        w2 = rasterio.windows.Window(0, r0, src.width, h)
                        dst.write(lut[src.read(1, window=w2)], 1, window=w2)
        with rasterio.open(clip) as src:
            crs = src.crs
        zones = {k: gpd.GeoSeries([g], crs="EPSG:4326").to_crs(crs).iloc[0] for k, g in zones4326.items()}
        areas = common.class_areas_km2(clip, zones)
        s = common.DATA / "series"
        s.mkdir(parents=True, exist_ok=True)
        names = {str(k): COMBINED_CLASSES[k][1] for k in COMBINED_CLASSES}
        (s / "forest_classes.json").write_text(json.dumps({
            "unit": "km2", "classes": names,
            "regions": {z: {str(c): km for c, km in sorted(d.items()) if c in COMBINED_CLASSES}
                        for z, d in areas.items()},
            "method": "GEOBOSQUES combined raster (EPSG:32718) clipped to the department; 30 m "
                      "pixel counting; this app's analysis"}, indent=1), encoding="utf-8")
        common.record("20_forest_loss", s / "forest_classes.json")
        out = common.DATA / "tiles" / "forest_loss.pmtiles"
        if args.force or not out.exists():
            merc = warp_to_mercator(clip, f"gbbnb_{common.AREA}", 12, Resampling.nearest,
                                    dtype="uint8", nodata=0)
            levels = max_levels(merc, common.CFG["tiles"]["minzoom"], 12)
            cmap = {k: v[2] for k, v in COMBINED_CLASSES.items()}
            cut_tiles(merc, out, "GEOBOSQUES forest & loss", "png", common.CFG["tiles"]["minzoom"],
                      12, make_colormap_encoder(cmap, 0), Resampling.nearest, levels=levels)
            common.record("20_forest_loss", out)
        reg["urls"]["tiles"] = "tiles/forest_loss.pmtiles"
        reg["classes"] = {str(k): {"name_es": v[0], "name_en": v[1],
                                   "color": "#%02x%02x%02x" % v[2][:3]} for k, v in COMBINED_CLASSES.items()}
        reg["period"] = "baseline 2000, loss 2001-2024, forest state 2024"

    if annual:
        clip_a = clip_any_crs(annual, "geobosques_loss_annual", common.bbox())
        years = year_values(clip_a)
        log.info("annual loss raster: values -> years %s..%s", min(years.values()), max(years.values()))
        with rasterio.open(clip_a) as src:
            crs = src.crs
        zones = {k: gpd.GeoSeries([g], crs="EPSG:4326").to_crs(crs).iloc[0] for k, g in zones4326.items()}
        areas = common.class_areas_km2(clip_a, zones)
        series = {z: {str(years[v]): km for v, km in sorted(d.items()) if v in years}
                  for z, d in areas.items()}
        s = common.DATA / "series"
        (s / "forest_loss.json").write_text(json.dumps({
            "unit": "km2", "regions": series,
            "method": "GEOBOSQUES annual loss raster clipped to the department; 30 m pixel "
                      "counting; this app's analysis"}, indent=1), encoding="utf-8")
        common.record("20_forest_loss", s / "forest_loss.json")
        out_a = common.DATA / "tiles" / "forest_loss_year.pmtiles"
        if args.force or not out_a.exists():
            big = max(years) > 255
            merc = warp_to_mercator(clip_a, f"gbloss_{common.AREA}", 12, Resampling.nearest,
                                    dtype="uint16" if big else "uint8", nodata=0)
            levels = max_levels(merc, common.CFG["tiles"]["minzoom"], 12)
            cmap = viridis_years(years)
            if big:
                def enc(data):
                    a = data[0]
                    rgba = np.zeros(a.shape + (4,), "u1")
                    for v, c in cmap.items():
                        rgba[a == v] = c
                    return None if not rgba[..., 3].any() else encode_png(rgba)
            else:
                enc = make_colormap_encoder(cmap, 0)
            cut_tiles(merc, out_a, "GEOBOSQUES loss year", "png", common.CFG["tiles"]["minzoom"],
                      12, enc, Resampling.nearest, levels=levels)
            common.record("20_forest_loss", out_a)
        reg["urls"]["loss_year"] = "tiles/forest_loss_year.pmtiles"
        reg["years"] = sorted(set(years.values()))
    else:
        log.warning("annual loss raster (with the year field) not found under %s - the loss-year "
                    "layer and the annual km² series wait for it; the combined forest/loss layer "
                    "%s built.", DL, "was" if combined else "was NOT")

    common.update_registry("forest_loss", reg)


if __name__ == "__main__":
    main()
