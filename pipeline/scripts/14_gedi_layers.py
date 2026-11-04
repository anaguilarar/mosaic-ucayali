"""Step 14 - GEDI map products from the STRICT shot set (the paper's three filters plus
quality_flag = 1 and degrade_flag = 0), full mission window (decision D4), shots inside the
department only:
  data/tiles/gedi_footprints.pmtiles  vector tiles, layer 'footprints': rh95 and rh50 in decimetres,
                                      date as yyyymmdd. Every shot at z11 (overzoomed beyond); a fixed
                                      random 1-in-4 sample at z10 and 1-in-16 at z9.
  data/query/gedi_rh95_1km.tif        0.01-degree grid (~1.1 km), int16: band 1 mean RH95 (dm),
                                      band 2 number of shots; cells kept when their centre is inside
                                      the department. Read by the click panel. Cells without a valid
                                      shot are nodata and transparent in the display tiles.
  data/tiles/gedi_grid.pmtiles        display tiles of the grid mean (z5-9, nearest), canopy ramp 0-40 m.
RH95 here is GEDI's own rh[95] (no ground-return transformation), as in steps 12-13.

Usage:  python scripts/14_gedi_layers.py [--area pilot|full] [--force]
"""
import gzip
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log
from tiler import cut_tiles, make_colormap_encoder, warp_to_mercator

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import rasterio
import shapely
from rasterio import features
from rasterio.enums import Resampling
from rasterio.transform import from_origin

FP_ZOOMS = {9: 1 / 16, 10: 1 / 4, 11: 1.0}     # zoom -> share of shots kept
EXTENT = 4096
GRID_RES = 0.01
NODATA = -32768
RAMP_MAX = 40
STOPS = [(0, (240, 238, 225)), (5, (205, 213, 171)), (10, (155, 188, 134)),   # = 22_canopy_height
         (20, (87, 154, 102)), (30, (31, 112, 74)), (40, (6, 66, 43))]


# ---------------------------------------------------------------- minimal MVT (points only)
def _varint(n, out):
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return


def _key(out, field, wire):
    _varint((field << 3) | wire, out)


def _sub(out, field, payload):
    _key(out, field, 2)
    _varint(len(payload), out)
    out += payload


def _zz(n):
    return (n << 1) ^ (n >> 31)


def encode_points(name, px, py, cols):
    """One MVT layer of points. px, py: tile pixel coords (0..EXTENT-1); cols: {key: int array >= 0}."""
    keys = list(cols)
    stacked = np.stack([cols[k] for k in keys], axis=1)
    uniq, inv = np.unique(stacked.ravel(), return_inverse=True)
    inv = inv.reshape(stacked.shape)
    layer = bytearray()
    _key(layer, 15, 0); _varint(2, layer)
    _sub(layer, 1, name.encode())
    for i in range(len(px)):
        f = bytearray()
        tags = bytearray()
        for k in range(len(keys)):
            _varint(k, tags); _varint(int(inv[i, k]), tags)
        _sub(f, 2, tags)
        _key(f, 3, 0); _varint(1, f)                       # POINT
        g = bytearray()
        _varint(9, g); _varint(_zz(int(px[i])), g); _varint(_zz(int(py[i])), g)   # MoveTo(1)
        _sub(f, 4, g)
        _sub(layer, 2, f)
    for k in keys:
        _sub(layer, 3, k.encode())
    for v in uniq:
        val = bytearray(); _key(val, 5, 0); _varint(int(v), val)   # uint_value
        _sub(layer, 4, val)
    _key(layer, 5, 0); _varint(EXTENT, layer)
    tile = bytearray()
    _sub(tile, 3, layer)
    return bytes(tile)


def merc_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    s = np.sin(np.radians(lat))
    y = (0.5 - np.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def write_footprints(df, out):
    w, s, e, n = common.bbox()
    mb = common.WORK / "gedi_footprints.mbtiles"
    meta = {"json": json.dumps({"vector_layers": [{"id": "footprints", "fields": {
        "rh95": "Number", "rh50": "Number", "date": "Number"}, "minzoom": min(FP_ZOOMS), "maxzoom": max(FP_ZOOMS)}]})}
    db = common.open_mbtiles(mb, "GEDI footprints (strict set)", "pbf", min(FP_ZOOMS), max(FP_ZOOMS),
                             (w, s, e, n), meta)
    empty = gzip.compress(b"", mtime=0)
    u = np.random.default_rng(14).random(len(df))
    lon, lat = df.lon.to_numpy(), df.lat.to_numpy()
    cols = {"rh95": df.rh95_dm.to_numpy(), "rh50": df.rh50_dm.to_numpy(), "date": df.date_i.to_numpy()}
    for z, share in FP_ZOOMS.items():
        keep = u < share
        x, y = merc_xy(lon[keep], lat[keep], z)
        tx, ty = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
        px = np.clip(((x - tx) * EXTENT).astype(np.int64), 0, EXTENT - 1)
        py = np.clip(((y - ty) * EXTENT).astype(np.int64), 0, EXTENT - 1)
        tid = tx * (1 << 24) + ty
        order = np.argsort(tid, kind="stable")
        tid_s = tid[order]
        starts = np.flatnonzero(np.r_[True, tid_s[1:] != tid_s[:-1]])
        ends = np.r_[starts[1:], len(tid_s)]
        sub = {k: v[keep][order] for k, v in cols.items()}
        pxo, pyo = px[order], py[order]
        done = set()
        for a, b in zip(starts, ends):
            t = int(tid_s[a]); X, Y = t >> 24, t & ((1 << 24) - 1)
            data = encode_points("footprints", pxo[a:b], pyo[a:b], {k: v[a:b] for k, v in sub.items()})
            common.put_tile(db, z, X, Y, gzip.compress(data, mtime=0))
            done.add((X, Y))
        # every candidate tile in the bbox exists (an empty tile, not a hole)
        x0, y1 = merc_xy(np.array([w]), np.array([s]), z)
        x1, y0 = merc_xy(np.array([e]), np.array([n]), z)
        for X in range(int(x0[0]), int(x1[0]) + 1):
            for Y in range(int(y0[0]), int(y1[0]) + 1):
                if (X, Y) not in done:
                    common.put_tile(db, z, X, Y, empty)
        log.info("footprints z%d: %d shots in %d tiles (max %d per tile)", z, int(keep.sum()), len(done),
                 int((ends - starts).max()))
    db.commit(); db.close()
    common.mbtiles_to_pmtiles(mb, out, max(FP_ZOOMS))


def write_grid(df, dept, query_out, display_out):
    w, s, e, n = common.bbox()
    width, height = math.ceil((e - w) / GRID_RES), math.ceil((n - s) / GRID_RES)
    tr = from_origin(w, n, GRID_RES, GRID_RES)
    col = np.floor((df.lon.to_numpy() - w) / GRID_RES).astype(np.int64)
    row = np.floor((n - df.lat.to_numpy()) / GRID_RES).astype(np.int64)
    ok = (col >= 0) & (col < width) & (row >= 0) & (row < height)
    idx = row[ok] * width + col[ok]
    cnt = np.bincount(idx, minlength=width * height).reshape(height, width).astype("f8")
    tot = np.bincount(idx, weights=df.rh95.to_numpy()[ok], minlength=width * height).reshape(height, width)
    inside = features.geometry_mask([dept], (height, width), tr, invert=True)
    has = (cnt > 0) & inside
    mean = np.where(has, tot / np.where(cnt > 0, cnt, 1), np.nan)
    cnt_f = np.where(has, cnt, np.nan)
    enc_mean = np.where(has, np.round(mean * 10), NODATA).astype("i2")
    enc_cnt = np.where(has, np.minimum(cnt, 32767), NODATA).astype("i2")
    common.check_encoding("gedi rh95 mean (dm)", mean, enc_mean, 10)
    common.check_encoding("gedi shot count", cnt_f, enc_cnt, 1, nonneg=True)
    prof = dict(driver="GTiff", width=width, height=height, count=2, dtype="int16", crs="EPSG:4326",
                transform=tr, nodata=NODATA, tiled=True, blockxsize=256, blockysize=256, compress="deflate")
    query_out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(query_out, "w", **prof) as ds:
        ds.write(enc_mean, 1); ds.write(enc_cnt, 2)
        ds.set_band_description(1, "mean RH95, decimetres"); ds.set_band_description(2, "shots")
        ds.update_tags(source="GEDI02_A v002 strict set (14_gedi_layers.py)", scale_band1="0.1")
    common.record("14_gedi_layers", query_out)
    log.info("grid: %d cells with shots; median %d shots per cell; %d of %d department cells empty (%.1f %%)",
             int(has.sum()), int(np.median(cnt[has])), int((inside & ~has).sum()), int(inside.sum()),
             100 * (inside & ~has).sum() / inside.sum())

    disp = common.WORK / "gedi_grid_display.tif"
    m8 = np.where(has, np.clip(np.round(mean), 0, 254), 255).astype("u1")
    with rasterio.open(disp, "w", **{**prof, "count": 1, "dtype": "uint8", "nodata": 255}) as ds:
        ds.write(m8, 1)
    lut = {}
    for (v0, c0), (v1, c1) in zip(STOPS, STOPS[1:]):
        for v in range(v0, v1 + 1):
            t = (v - v0) / (v1 - v0)
            lut[v] = tuple(round(c0[i] + t * (c1[i] - c0[i])) for i in range(3)) + (255,)
    for v in range(RAMP_MAX + 1, 255):
        lut[v] = lut[RAMP_MAX]
    merc = warp_to_mercator(disp, "gedi_grid", 9, Resampling.nearest, dtype="uint8", nodata=255, src_nodata=255)
    cut_tiles(merc, display_out, "GEDI RH95 1 km grid", "png", common.CFG["tiles"]["minzoom"], 9,
              make_colormap_encoder(lut, 255), Resampling.nearest)
    common.record("14_gedi_layers", display_out)
    return int(has.sum()), int((inside & ~has).sum())


def main():
    args = common.setup("14_gedi_layers")
    files = sorted((common.WORK / "gedi" / "parquet").rglob("*.parquet"))
    if not files:
        sys.exit("no parquet yet: run 12_gedi_filter.py first")
    fp_out = common.DATA / "tiles" / "gedi_footprints.pmtiles"
    grid_tiles = common.DATA / "tiles" / "gedi_grid.pmtiles"
    query_out = common.DATA / "query" / "gedi_rh95_1km.tif"
    if not args.force and fp_out.exists() and grid_tiles.exists() and query_out.exists():
        log.info("outputs exist (use --force to rebuild)")
        return

    cols = ["lon", "lat", "rh95", "rh50", "quality_flag", "degrade_flag", "date"]
    df = pd.concat([pq.read_table(f, columns=cols).to_pandas() for f in files], ignore_index=True)
    n_paper = len(df)
    df = df[(df.quality_flag == 1) & (df.degrade_flag == 0)]
    n_strict = len(df)
    dept = common.department_geometry()
    df = df[shapely.contains_xy(dept, df.lon.to_numpy(), df.lat.to_numpy())].reset_index(drop=True)
    log.info("shots: paper set %d, strict %d, strict inside the department %d", n_paper, n_strict, len(df))
    d = pd.to_datetime(df.date)
    df["date_i"] = (d.dt.year * 10000 + d.dt.month * 100 + d.dt.day).astype(np.int64)
    df["rh95_dm"] = np.clip(np.round(df.rh95 * 10), 0, None).astype(np.int64)   # negatives (bare ground) -> 0
    df["rh50_dm"] = np.clip(np.round(df.rh50 * 10), 0, None).astype(np.int64)
    first, last = d.min().date().isoformat(), d.max().date().isoformat()

    write_footprints(df, fp_out)
    common.record("14_gedi_layers", fp_out)
    cells, empty_cells = write_grid(df, dept, query_out, grid_tiles)

    common.update_registry("gedi", {
        "title": "GEDI canopy height (RH95)", "group": "Vegetation", "type": "thematic",
        "urls": {"footprints": "tiles/gedi_footprints.pmtiles", "grid_tiles": "tiles/gedi_grid.pmtiles",
                 "query": "query/gedi_rh95_1km.tif"},
        "minzoom": common.CFG["tiles"]["minzoom"], "footprints_from_zoom": min(FP_ZOOMS),
        "ramp": {"max_m": RAMP_MAX},
        "counts": {"shots_in_department": int(len(df)), "rh95_over_60m": int((df.rh95 > 60).sum()),
                   "grid_cells": cells, "grid_cells_empty": empty_cells, "first": first, "last": last},
        "source": "NASA GEDI L2A (GEDI02_A v002), full-power beams; the paper's filters (Cooley et al. 2024, "
                  "sect. 2.4) plus quality_flag = 1 and degrade_flag = 0 (this app's strict set)",
        "period": f"{first} to {last} (no shots April 2023 - April 2024: GEDI hibernation)",
        "units": "RH95: height above the ground at which 95 % of the returned energy is reached, m",
        "licence": "NASA Earth science data: free and open; cite the product DOI",
        "citation": "Dubayah, R., Hofton, M., Blair, J., Armston, J., Tang, H. & Luthcke, S. (2021). GEDI L2A "
                    "Elevation and Height Metrics Data Global Footprint Level V002. NASA EOSDIS Land Processes "
                    "DAAC. doi:10.5067/GEDI/GEDI02_A.002",
        "caveats": "This app's analysis. Each dot is one 25 m footprint, located to about ±10 m. Zoomed out, "
                   "a 1 km grid shows the mean RH95 of the shots in each cell; at zooms 9-10 the dots are a "
                   "random sample. RH95 is GEDI's own value (no ground-return transformation, unlike the "
                   "paper's Table 2a)."})


if __name__ == "__main__":
    main()
