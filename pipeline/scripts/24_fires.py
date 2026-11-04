"""Step 24 - fire: VIIRS active fires (NASA FIRMS country archives, S-NPP, 2012-2025) and
MapBiomas Peru burned area (Collection 1, 2013-2024, CC BY 4.0).

VIIRS: downloads the yearly Peru CSVs from FIRMS, keeps nominal/high-confidence detections in
the area bbox, writes per-year density tiles (fires per km2 on a ~1 km grid; fired_YYYY.pmtiles),
per-year point GeoJSONs (data/fire/points_YYYY.geojson, drawn from zoom 10) and a detections
series. MapBiomas burned: the published storage.googleapis.com links answer 403 server-side
(2026-11-04); the step uses files already in <work>/downloads/mapbiomas_fire/ (direct download
retried first) and otherwise skips the burned part with instructions, so VIIRS still ships.

Usage:  python scripts/24_fires.py [--area pilot|full] [--force]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from tiler import clip_source, cut_tiles, encode_png, max_levels, warp_to_mercator

VIIRS_YEARS = list(range(2012, 2026))
VIIRS_URL = "https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/{y}/viirs-snpp_{y}_Peru.csv"
BURNED_YEARS = list(range(2013, 2025))
BURNED_URL = ("https://storage.googleapis.com/shared-development-storage/COLLECTIONS/PERU/FIRE/"
              "COLLECTION1/mbfire_col1_peru_annual_burned/mbfire_col1_peru_annual_burned-burned_area_{y}.tif")
GRID_DEG = 0.01                      # ~1.1 km density cells
DENSITY_BREAKS = [1, 3, 10, 30, 100]
DENSITY_COLORS = ["#f8c471", "#eb984e", "#e55064", "#b03a2e", "#78281f"]


def density_encoder():
    lut = np.zeros((256, 4), "u1")
    hex2rgb = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    for i, c in enumerate(DENSITY_COLORS, start=1):
        lut[i] = hex2rgb(c) + (230,)
    def enc(data):
        rgba = lut[np.clip(data[0], 0, len(DENSITY_COLORS))]
        if not rgba[..., 3].any():
            return None
        return encode_png(rgba)
    return enc


def viirs(args, dept_geom):
    w, s, e, n = common.bbox()
    fire_dir = common.DATA / "fire"
    fire_dir.mkdir(parents=True, exist_ok=True)
    detections = {}
    km_per_deg = 111.3195
    cell_km2 = (GRID_DEG * km_per_deg) ** 2 * np.cos(np.radians((s + n) / 2))
    W, H = int(np.ceil((e - w) / GRID_DEG)), int(np.ceil((n - s) / GRID_DEG))
    for y in VIIRS_YEARS:
        csv = common.download(VIIRS_URL.format(y=y),
                              common.WORK_ROOT / "downloads" / "viirs" / f"viirs-snpp_{y}_Peru.csv")
        df = pd.read_csv(csv, usecols=["latitude", "longitude", "confidence", "acq_date"])
        df = df[(df.longitude >= w) & (df.longitude <= e) & (df.latitude >= s) & (df.latitude <= n)
                & df.confidence.isin(["n", "h"])]
        pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
        inside = pts[pts.within(dept_geom)]
        detections[str(y)] = int(len(inside))
        log.info("VIIRS %d: %d detections in bbox, %d in the department", y, len(df), len(inside))

        gj = fire_dir / f"points_{y}.geojson"
        if args.force or not gj.exists():
            keep = inside[["acq_date", "confidence", "geometry"]]
            gj.write_text(keep.to_json(drop_id=True), encoding="utf-8")

        out = common.DATA / "tiles" / f"fire_density_{y}.pmtiles"
        if out.exists() and not args.force:
            continue
        cols = ((inside.longitude - w) / GRID_DEG).astype(int).clip(0, W - 1)
        rows = ((n - inside.latitude) / GRID_DEG).astype(int).clip(0, H - 1)
        counts = np.zeros((H, W), "f4")
        np.add.at(counts, (rows.values, cols.values), 1)
        dens = counts / cell_km2
        cls = np.digitize(dens, DENSITY_BREAKS, right=True).astype("u1")   # 0..5; 0 = none
        cls[dens <= 0] = 0
        grid = common.WORK / f"fire_density_{y}.tif"
        prof = dict(driver="GTiff", crs="EPSG:4326", transform=from_origin(w, n, GRID_DEG, GRID_DEG),
                    width=W, height=H, count=1, dtype="uint8", nodata=0, compress="DEFLATE")
        with rasterio.open(grid, "w", **prof) as dst:
            dst.write(cls, 1)
        merc = warp_to_mercator(grid, f"fired_{y}_{common.AREA}", 10, Resampling.nearest,
                                dtype="uint8", nodata=0)
        levels = max_levels(merc, common.CFG["tiles"]["minzoom"], 10)
        cut_tiles(merc, out, f"VIIRS density {y}", "png", common.CFG["tiles"]["minzoom"], 10,
                  density_encoder(), Resampling.nearest, levels=levels)
        common.record("24_fires", out)
    return detections


def burned(args, dept_geom):
    burned_km2 = {}
    missing = []
    for y in BURNED_YEARS:
        dest = common.WORK_ROOT / "downloads" / "mapbiomas_fire" / f"burned_area_{y}.tif"
        try:
            nat = common.download(BURNED_URL.format(y=y), dest)
        except Exception:
            if dest.exists():
                nat = dest
            else:
                missing.append(y)
                continue
        clip = clip_source(nat, f"burned_{y}", common.bbox())
        burned_km2[str(y)] = round(sum(common.class_areas_km2(clip, {"d": dept_geom})["d"].values()), 1)
        out = common.DATA / "tiles" / f"burned_{y}.pmtiles"
        if out.exists() and not args.force:
            continue
        merc = warp_to_mercator(clip, f"burned_{y}_{common.AREA}", 12, Resampling.nearest,
                                dtype="uint8", nodata=0)
        levels = max_levels(merc, common.CFG["tiles"]["minzoom"], 12)
        colormap = np.zeros((256, 4), "u1"); colormap[1] = (120, 32, 18, 235)
        enc = lambda data: (None if not colormap[np.clip(data[0], 0, 1)][..., 3].any()
                            else encode_png(colormap[np.clip(data[0], 0, 1)]))
        cut_tiles(merc, out, f"MapBiomas burned {y}", "png", common.CFG["tiles"]["minzoom"], 12,
                  enc, Resampling.nearest, levels=levels)
        common.record("24_fires", out)
    if missing:
        log.warning("MapBiomas burned rasters missing for %s: the published GCS links answer 403 "
                    "(2026-11-04). Export them with prep/gee_mapbiomas_export.js (or the MapBiomas "
                    "platform) into %s as burned_area_<YEAR>.tif and re-run; VIIRS layers are built.",
                    missing, common.WORK_ROOT / "downloads" / "mapbiomas_fire")
    return burned_km2


def main():
    args = common.setup("24_fires")
    dept = gpd.read_file(common.INPUTS / common.CFG["inputs"]["department"]).to_crs("EPSG:4326")
    dept_geom = dept.union_all()

    detections = viirs(args, dept_geom)
    burned_km2 = burned(args, dept_geom)

    series = common.DATA / "series"
    series.mkdir(parents=True, exist_ok=True)
    (series / "fire.json").write_text(json.dumps({
        "snpp_detections_dept": detections, "burned_km2_dept": burned_km2,
        "caveats": "VIIRS S-NPP only (NOAA-20/21 excluded for a consistent series), confidence "
                   "nominal/high, inside the department boundary; this app's analysis"},
        indent=1), encoding="utf-8")
    common.record("24_fires", series / "fire.json")

    common.update_registry("fire", {
        "title": "Active fires (VIIRS)", "group": "Fire", "type": "thematic",
        "urls": {"density": {str(y): f"tiles/fire_density_{y}.pmtiles" for y in VIIRS_YEARS},
                 "points": "fire/points_{year}.geojson"},
        "years": VIIRS_YEARS, "points_from_zoom": 10,
        "legend_steps": {"breaks": DENSITY_BREAKS, "colors": DENSITY_COLORS},
        "source": "NASA FIRMS VIIRS 375 m active fires (S-NPP), yearly Peru archives, bbox clip",
        "period": "2012-2025", "units": "detections per km² per year (~1 km cells)",
        "licence": "NASA FIRMS data are freely available; cite NASA FIRMS",
        "citation": "NASA FIRMS: VIIRS 375 m active fire product (VNP14IMGT). "
                    "firms.modaps.eosdis.nasa.gov",
        "caveats": "Detections, not burned area: small/short fires can be missed under cloud; "
                   "confidence nominal/high only."})
    if burned_km2:
        common.update_registry("burned_area", {
            "title": "Burned area (MapBiomas)", "group": "Fire", "type": "thematic",
            "urls": {"tiles": {y: f"tiles/burned_{y}.pmtiles" for y in burned_km2}},
            "years": [int(y) for y in burned_km2],
            "source": "MapBiomas Perú Fuego Collection 1 annual burned area, 30 m, department clip",
            "period": "2013-2024", "units": "burned at least once in the year",
            "licence": "CC BY 4.0 (MapBiomas: public, open and free use, subject to citation)",
            "citation": "MapBiomas Perú - Colección 1 de fuego (peru.mapbiomas.org)",
            "caveats": "Landsat-based: misses small or low-severity burns; Collection 2 "
                       "(1990-2025) exists as GEE assets and can replace this later. Burned km² "
                       "per year is this app's analysis."})


if __name__ == "__main__":
    main()
