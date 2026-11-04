"""Step 02 - DEM -> Mapbox terrain-rgb PMTiles for MapLibre setTerrain + hillshade.

Same approach as the Lake Victoria app: max zoom 11, terrain-rgb PNG (0.1 m interval),
bilinear warp, average overviews, padding beyond the DEM filled with smoothly extrapolated
elevations so a bounded camera never sees black missing-terrain tiles.

DEM source: inputs/dem_ucayali_basin_extent.tif - provenance recorded in the registry as
"to confirm" until the Earth Engine export script is filed in prep/ (see DATA_REPORT §2).

Usage:  python scripts/02_terrain.py [--area pilot|full] [--force]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import numpy as np
import rasterio
import scipy.ndimage as nd
from rasterio.enums import Resampling

from tiler import clip_source, cut_tiles, terrain_encoder, warp_to_mercator


def fill_padding(path, step=16, sigma=4.0, strip=1024):
    """Replace NaN padding with nearest-edge elevations, smoothed, at 1/step resolution.
    Strip-wise read/write: the full-resolution band never sits in memory at once (this machine
    runs the pipeline next to OneDrive and a browser; memwatch stopped the whole-array version)."""
    from rasterio.windows import Window
    with rasterio.open(path, "r+") as ds:
        H, W = ds.height, ds.width
        # the decimated copy is small (1/step^2): fill it globally
        small = ds.read(1, out_shape=(H // step, W // step)).astype("f4")
        sbad = ~np.isfinite(small)
        if not sbad.any():
            return
        idx = nd.distance_transform_edt(sbad, return_distances=False, return_indices=True)
        filled = small[tuple(idx)]
        smooth = nd.gaussian_filter(filled, sigma)
        filled[sbad] = smooth[sbad]
        sh, sw = filled.shape
        for r0 in range(0, H, strip):
            h = min(strip, H - r0)
            win = Window(0, r0, W, h)
            a = ds.read(1, window=win)
            bad = ~np.isfinite(a)
            if bad.any():
                # bilinear up-sample of the small fill for just this strip (map rows/cols to small grid)
                rows = np.minimum((np.arange(r0, r0 + h) / step), sh - 1)
                cols = np.minimum((np.arange(W) / step), sw - 1)
                r0i = np.floor(rows).astype(int); r1i = np.minimum(r0i + 1, sh - 1); rf = (rows - r0i)[:, None]
                c0i = np.floor(cols).astype(int); c1i = np.minimum(c0i + 1, sw - 1); cf = (cols - c0i)[None, :]
                up = (filled[np.ix_(r0i, c0i)] * (1 - rf) * (1 - cf) + filled[np.ix_(r0i, c1i)] * (1 - rf) * cf
                      + filled[np.ix_(r1i, c0i)] * rf * (1 - cf) + filled[np.ix_(r1i, c1i)] * rf * cf)
                a[bad] = up.astype("f4")[bad]
                ds.write(a, 1, window=win)


def main():
    args = common.setup("02_terrain")
    cfg = common.CFG
    src = common.INPUTS / cfg["inputs"]["dem"]
    out = common.DATA / "tiles" / "terrain.pmtiles"
    maxzoom = cfg["tiles"]["terrain_maxzoom"]
    minzoom = cfg["tiles"]["minzoom"]
    if common.fresh(out, src) and not args.force:
        log.info("terrain.pmtiles is fresh; --force to rebuild")
        return
    if common.AREA == "pilot":
        src = clip_source(src, "dem_pilot", common.bbox())
        pad = 30_000
    else:
        pad = 300_000      # bounded camera: every visible tile must exist (padding is synthetic)
    merc = warp_to_mercator(src, f"dem_{common.AREA}", maxzoom, Resampling.bilinear,
                            dtype="float32", pad_m=pad, pad_fill=float("nan"))
    fill_padding(merc)
    cut_tiles(merc, out, "terrain-rgb", "png", minzoom, maxzoom,
              terrain_encoder, Resampling.bilinear, {"encoding": "mapbox"})
    common.record("02_terrain", out)
    common.update_registry("terrain", {
        "title": "Terrain", "group": "Base", "type": "raster-dem",
        "urls": {"pmtiles": "tiles/terrain.pmtiles"}, "encoding": "mapbox",
        "minzoom": minzoom, "maxzoom": maxzoom,
        "exaggeration": {"default": 1.6, "min": 1.0, "max": 4.0},
        "source": "30 m DEM, department extent (inputs/dem_ucayali_basin_extent.tif; "
                  "provenance to confirm - see the data report)",
        "units": "m above sea level",
        "licence": "per DEM source (to confirm)",
        "caveats": "Terrain beyond the department extent is synthetic padding for display; "
                   "elevations are neither shown nor queryable there."})


if __name__ == "__main__":
    main()
