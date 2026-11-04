"""Step 21 - land cover: MapBiomas Perú Collection 4 (CC BY 4.0), 30 m, years 2000/2005/2010/
2015/2020/2024 (the catalogue's selection; the collection itself spans 1985-2025).

Downloads the national annual GeoTIFFs from MapBiomas' public bucket, clips to the area bbox,
and produces per year: a PMTiles layer in the official class palette; plus one click-query
stack (data/query/lulc_stack_30m.tif, one band per year) and series/lulc_areas.json (class
areas km² for the department). Class codes/names/colours come from the official legend CSV
(cached); oil palm is its own class (35, 'Palma aceitera') - cacao has no class of its own and
falls inside 'Mosaico agropecuario' (21): recorded in the registry caveats for the paper link.

Usage:  python scripts/21_landcover.py [--area pilot|full] [--force]
"""
import csv
import io
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

from tiler import clip_source, cut_tiles, make_colormap_encoder, warp_to_mercator

YEARS = [2000, 2005, 2010, 2015, 2020, 2024]
URL = ("https://storage.googleapis.com/mapbiomas-public/initiatives/peru/collection4/lulc/"
       "coverage/peru_coverage/peru_coverage-col4_{y}.tif")
LEGEND_CSV = "https://peru.mapbiomas.org/wp-content/uploads/sites/6/2026/08/MapBiomasPeru_legend.csv"

# fallback palette (official hex from peru.mapbiomas.org Collection-4 legend table, fetched
# 2026-11-04) in case the legend CSV moves; the CSV, when readable, takes precedence for names
FALLBACK = {
    3: ("Bosque", "Forest", "#1f8d49"), 4: ("Bosque seco", "Dry forest", "#7dc975"),
    5: ("Manglar", "Mangrove", "#04381d"), 6: ("Bosque inundable", "Flooded forest", "#007785"),
    51: ("Herbazal inundable de tierras bajas", "Lowland flooded grassland", "#5faf92"),
    82: ("Herbazal inundable altoandino", "High-Andean flooded grassland", "#26abab"),
    12: ("Formación herbácea", "Grassland", "#d6bc74"),
    66: ("Matorral y otros arbustales", "Shrubland", "#a89358"),
    70: ("Loma costera (beta)", "Coastal loma (beta)", "#be9e00"),
    21: ("Mosaico agropecuario", "Agricultural mosaic", "#ffefc3"),
    9: ("Plantación forestal", "Forest plantation", "#7a6c00"),
    35: ("Palma aceitera", "Oil palm", "#9065d0"), 40: ("Arroz (beta)", "Rice (beta)", "#c71585"),
    15: ("Pasto (beta)", "Pasture (beta)", "#edde8e"),
    24: ("Infraestructura urbana", "Urban infrastructure", "#d4271e"),
    30: ("Minería", "Mining", "#9c0027"), 23: ("Playa", "Beach/dune", "#ffa07a"),
    92: ("Superficie rocosa", "Rocky surface", "#857848"),
    68: ("Otra área natural sin vegetación", "Other natural non-vegetated", "#e3e3c8"),
    25: ("Otra área antrópica sin vegetación", "Other anthropic non-vegetated", "#db4d4f"),
    33: ("Río, lago u océano", "River, lake or ocean", "#2532e4"),
    31: ("Acuicultura", "Aquaculture", "#091077"), 34: ("Glaciar", "Glacier", "#93dfe6"),
}


def legend() -> dict:
    """code -> (name_es, name_en, hex). CSV first, fallback table otherwise."""
    cls = dict(FALLBACK)
    try:
        f = common.download(LEGEND_CSV, common.WORK_ROOT / "downloads" / "mapbiomas" / "legend.csv")
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        rows = list(csv.DictReader(io.StringIO(text), delimiter=";" if ";" in text.splitlines()[0] else ","))
        cols = {c.lower().strip(): c for c in rows[0].keys()}
        def pick(row, *names):
            for n in names:
                if n in cols and row[cols[n]].strip():
                    return row[cols[n]].strip()
            return None
        n = 0
        for row in rows:
            code = pick(row, "class_id", "id", "code", "codigo", "pixel value", "class")
            if code is None or not code.isdigit():
                continue
            es = pick(row, "leyenda", "descripcion", "name_es", "clase", "nombre") or FALLBACK.get(int(code), ("?",))[0]
            en = pick(row, "legend_en", "name_en", "english") or FALLBACK.get(int(code), ("?", "?"))[1] if int(code) in FALLBACK else es
            hx = pick(row, "color", "hex", "paleta") or FALLBACK.get(int(code), ("?", "?", "#999999"))[2]
            if not str(hx).startswith("#"):
                hx = "#" + str(hx).lstrip("#")
            cls[int(code)] = (es, en, hx)
            n += 1
        log.info("legend CSV parsed: %d classes (fallback table covers %d)", n, len(FALLBACK))
    except Exception as err:
        log.warning("legend CSV not usable (%s); using the embedded official palette", err)
    return cls


def main():
    args = common.setup("21_landcover")
    cls = legend()
    hex2rgba = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    colormap = {code: hex2rgba(v[2]) for code, v in cls.items()}

    dept = gpd.read_file(common.INPUTS / common.CFG["inputs"]["department"]).to_crs("EPSG:4326")
    zones = {"Ucayali": dept.union_all()}
    areas, clipped, present = {}, {}, set()
    for y in YEARS:
        dest = common.WORK_ROOT / "downloads" / "mapbiomas" / f"peru_coverage-col4_{y}.tif"
        try:
            nat = common.download(URL.format(y=y), dest)
        except Exception as err:
            if dest.exists():
                nat = dest
            else:
                log.warning(
                    f"MapBiomas download failed ({err}) - STEP SKIPPED (the land-cover layer shows "
                    f"'not built').\n"
                    f"As of 2026-11-04 the published storage.googleapis.com links answer 403 to everyone\n"
                    f"(server-side permissions). Alternatives:\n"
                    f"  1. run prep/gee_mapbiomas_export.js in Earth Engine (exports the needed years\n"
                    f"     clipped to the department) and save each year as {dest.parent}\\peru_coverage-col4_<YEAR>.tif\n"
                    f"  2. or download via https://plataforma.peru.mapbiomas.org/ (Downloads > Crear análisis)\n"
                    f"  3. or retry later in case MapBiomas fixes the bucket ACL.\n"
                    f"Then re-run this step.")
                return
        clip = common.mask_to_department(clip_source(nat, f"lulc_{y}", common.bbox()),
                                         common.WORK / f"lulc_{y}_dept.tif", nodata=0)
        clipped[y] = clip
        a = common.class_areas_km2(clip, zones)["Ucayali"]
        areas[str(y)] = a
        present.update(a.keys())
        log.info("%d: %d classes in the department, %.0f km² classified", y, len(a), sum(a.values()))

        out = common.DATA / "tiles" / f"lulc_{y}.pmtiles"
        if not out.exists() or args.force:
            merc = warp_to_mercator(clip, f"lulc_{y}", 12, Resampling.nearest, dtype="uint8",
                                    nodata=0, ovr=Resampling.mode)
            cut_tiles(merc, out, f"MapBiomas Peru C4 {y}", "png", common.CFG["tiles"]["minzoom"], 12,
                      make_colormap_encoder(colormap, 0), Resampling.nearest)
            common.record("21_landcover", out)

    # click-query stack: one uint8 band per year on the clipped grid, strip-wise
    q = common.DATA / "query"
    q.mkdir(parents=True, exist_ok=True)
    stack = q / "lulc_stack_30m.tif"
    if not stack.exists() or args.force:
        with rasterio.open(clipped[YEARS[0]]) as ref:
            prof = ref.profile | dict(count=len(YEARS), dtype="uint8", nodata=0, tiled=True,
                                      blockxsize=256, blockysize=256, compress="DEFLATE")
            H = ref.height
        with rasterio.open(stack, "w", **prof) as dst:
            for bi, y in enumerate(YEARS, start=1):
                with rasterio.open(clipped[y]) as src:
                    assert (src.height, src.width) == (prof["height"], prof["width"]), f"grid mismatch {y}"
                    for r0 in range(0, H, 1024):
                        h = min(1024, H - r0)
                        win = rasterio.windows.Window(0, r0, prof["width"], h)
                        dst.write(src.read(1, window=win), bi, window=win)
            dst.descriptions = tuple(str(y) for y in YEARS)
        common.record("21_landcover", stack)

    series = common.DATA / "series"
    series.mkdir(parents=True, exist_ok=True)
    (series / "lulc_areas.json").write_text(json.dumps({
        "unit": "km2", "region": "Ucayali department",
        "areas": {y: {str(c): v for c, v in a.items()} for y, a in areas.items()},
        "method": "MapBiomas Peru C4 rasters clipped to the department; pixel areas with cos(lat) "
                  "correction; this app's analysis"}, indent=1), encoding="utf-8")
    common.record("21_landcover", series / "lulc_areas.json")

    reg_classes = {str(c): {"name_es": cls[c][0], "name_en": cls[c][1], "color": cls[c][2]}
                   for c in sorted(present) if c in cls}
    common.update_registry("landcover", {
        "title": "Land cover (MapBiomas)", "group": "Land", "type": "thematic",
        "urls": {"tiles": {str(y): f"tiles/lulc_{y}.pmtiles" for y in YEARS},
                 "query": "query/lulc_stack_30m.tif"},
        "years": YEARS, "classes": reg_classes,
        "minzoom": common.CFG["tiles"]["minzoom"], "maxzoom": 12,
        "source": "MapBiomas Perú Collection 4 (Landsat, 30 m), national rasters clipped to Ucayali",
        "period": "collection spans 1985-2025; the app serves 2000/2005/2010/2015/2020/2024",
        "licence": "CC BY 4.0 - 'Los datos de MapBiomas son de uso público, abierto y gratuito, "
                   "sujetos a citación' (site footer)",
        "citation": "MapBiomas Perú Collection 4 (peru.mapbiomas.org). Official class palette.",
        "caveats": "Oil palm is its own class (35, Palma aceitera); cacao and other specific crops "
                   "have no class and fall inside 'Mosaico agropecuario' (21) - relevant when "
                   "relating classes to Cooley et al. (2024). Class areas are this app's analysis."})


if __name__ == "__main__":
    main()
