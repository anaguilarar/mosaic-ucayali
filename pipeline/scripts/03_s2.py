"""Step 03 - Sentinel-2 RGB mosaic -> WebP PMTiles (base texture draped on the terrain).

Fixed stretch for all bands (reflectance 0..stretch_max, gamma from config), as in the Lake
Victoria app. Before tiling, the reflectance scale is checked on sample windows: harmonized
L2A reflectance x10000 is expected; if the darkest river/forest pixels sit ~1000 too high,
the post-2022 +1000 offset is still present and the log says so (the stretch is then wrong
and the Earth Engine export should be fixed instead of papering over it here).

Usage:  python scripts/03_s2.py [--area pilot|full] [--force]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import numpy as np
import rasterio
from rasterio.enums import Resampling

from tiler import clip_source, cut_tiles, make_s2_encoder, warp_to_mercator


def check_scale(src_path):
    """Sample central windows; report percentiles so the offset question is answered from data."""
    with rasterio.open(src_path) as src:
        h, w = src.height, src.width
        vals = []
        for fy, fx in [(0.3, 0.3), (0.5, 0.5), (0.7, 0.6)]:
            win = rasterio.windows.Window(int(w * fx), int(h * fy), 1024, 1024)
            a = src.read(window=win).astype("f4")
            a = a[a > 0]
            if a.size:
                vals.append(a)
        a = np.concatenate(vals)
        pct = np.percentile(a, [1, 5, 50, 95, 99])
        log.info("S2 reflectance sample percentiles (1/5/50/95/99): %s", np.round(pct, 0).tolist())
        if pct[0] >= 900:
            log.warning("darkest sampled reflectance >= 900: the +1000 L2A offset may still be "
                        "present - check the Earth Engine export (harmonized collection expected)")
        return pct


def main():
    args = common.setup("03_s2")
    cfg = common.CFG
    src = common.INPUTS / cfg["inputs"]["s2_mosaic"]
    out = common.DATA / "tiles" / "s2_rgb.pmtiles"
    maxzoom, minzoom = cfg["tiles"]["s2_maxzoom"], cfg["tiles"]["minzoom"]
    year = cfg["s2"]["year"]
    if common.fresh(out, src) and not args.force:
        log.info("s2_rgb.pmtiles is fresh; --force to rebuild")
        return
    check_scale(src)
    if common.AREA == "pilot":
        src = clip_source(src, "s2_pilot", common.bbox())
    merc = warp_to_mercator(src, f"s2_{common.AREA}", maxzoom, Resampling.bilinear, dtype="uint16")
    cut_tiles(merc, out, "Sentinel-2 RGB mosaic", "webp", minzoom, maxzoom,
              make_s2_encoder(cfg["s2"]["stretch_max"], cfg["s2"]["gamma"]), Resampling.bilinear)
    common.record("03_s2", out)
    common.update_registry("s2_rgb", {
        "title": "Satellite imagery (Sentinel-2)", "group": "Base", "type": "raster",
        "urls": {"pmtiles": "tiles/s2_rgb.pmtiles"},
        "minzoom": minzoom, "maxzoom": maxzoom,
        "source": f"Sentinel-2 L2A mosaic {year}, 30 m (Earth Engine export; script in prep/)",
        "period": str(year),
        "units": f"true colour (fixed stretch 0-{cfg['s2']['stretch_max']:.0f}, gamma {cfg['s2']['gamma']})",
        "licence": "Copernicus Sentinel data: free use with attribution",
        "citation": f"Contains modified Copernicus Sentinel-2 data [{year}]"})


if __name__ == "__main__":
    main()
