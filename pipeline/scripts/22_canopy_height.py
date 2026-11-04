"""Step 22 - canopy height: ETH Global Canopy Height 2020, 10 m (Lang et al. 2023, CC BY 4.0).

Downloads the six 3°x3° COG tiles covering the department from the dataset's own file share
(libdrive.ethz.ch, the host the ETH Research Collection record 20.500.11850/609802 points to),
mosaics them clipped to the area bbox strip-by-strip (never whole rasters in memory; tiles are
36000x36000 uint8, nodata 255), and produces:
  - data/query/canopy_height_10m.tif  - the click-query raster (full 10 m; Hugging Face)
  - data/tiles/canopy.pmtiles         - display tiles, max zoom 12, green height ramp 0-40 m

Usage:  python scripts/22_canopy_height.py [--area pilot|full] [--force]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window, from_bounds

from tiler import TILE, cut_tiles, encode_png, warp_to_mercator

BASE = "https://libdrive.ethz.ch/index.php/s/cO8or7iOe5dT2Rt/download?path=%2F3deg_cogs&files="
TILES_3DEG = ["S09W078", "S09W075", "S09W072", "S12W078", "S12W075", "S12W072"]
NODATA = 255
RAMP_MAX = 40            # m; heights above are shown at the top colour


def mosaic_clip(tile_files, bbox, out, strip=2048):
    """Strip-wise mosaic of aligned 10 m EPSG:4326 tiles clipped to bbox."""
    w, s, e, n = bbox
    with rasterio.open(tile_files[0]) as ref:
        res = ref.transform.a
    import math
    left = math.floor(w / res) * res
    top = math.ceil(n / res) * res
    width = math.ceil((e - left) / res)
    height = math.ceil((top - s) / res)
    from rasterio.transform import from_origin
    prof = dict(driver="GTiff", crs="EPSG:4326", transform=from_origin(left, top, res, res),
                width=width, height=height, count=1, dtype="uint8", nodata=NODATA,
                tiled=True, blockxsize=512, blockysize=512, compress="DEFLATE", BIGTIFF="IF_SAFER")
    srcs = [rasterio.open(f) for f in tile_files]
    try:
        with rasterio.open(out, "w", **prof) as dst:
            for r0 in range(0, height, strip):
                h = min(strip, height - r0)
                a = np.full((h, width), NODATA, "uint8")
                win_bounds = rasterio.windows.bounds(Window(0, r0, width, h), prof["transform"])
                for src in srcs:
                    bw, bs, be, bn = src.bounds
                    iw, is_, ie, in_ = (max(win_bounds[0], bw), max(win_bounds[1], bs),
                                        min(win_bounds[2], be), min(win_bounds[3], bn))
                    if iw >= ie or is_ >= in_:
                        continue
                    sw = from_bounds(iw, is_, ie, in_, src.transform).round_offsets().round_lengths()
                    dwin = from_bounds(iw, is_, ie, in_, prof["transform"]).round_offsets().round_lengths()
                    data = src.read(1, window=sw, out_shape=(int(dwin.height), int(dwin.width)))
                    r, c = int(dwin.row_off) - r0, int(dwin.col_off)
                    sub = a[r:r + data.shape[0], c:c + data.shape[1]]
                    np.copyto(sub, data[:sub.shape[0], :sub.shape[1]],
                              where=data[:sub.shape[0], :sub.shape[1]] != NODATA)
                dst.write(a, 1, window=Window(0, r0, width, h))
        with rasterio.open(out, "r+") as ds:                       # overviews for remote range reads
            ds.build_overviews([2, 4, 8, 16, 32, 64], Resampling.average)
    finally:
        for s_ in srcs:
            s_.close()


def make_ramp_encoder():
    """0..RAMP_MAX m -> dark ground to bright green canopy; nodata transparent."""
    stops = [(0, (240, 238, 225)), (5, (205, 213, 171)), (10, (155, 188, 134)),
             (20, (87, 154, 102)), (30, (31, 112, 74)), (40, (6, 66, 43))]
    lut = np.zeros((256, 4), "u1")
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        for v in range(v0, v1 + 1):
            t = (v - v0) / (v1 - v0)
            lut[v] = [round(c0[i] + t * (c1[i] - c0[i])) for i in range(3)] + [255]
    lut[RAMP_MAX + 1:NODATA] = lut[RAMP_MAX]
    lut[NODATA] = (0, 0, 0, 0)

    def enc(data):
        rgba = lut[data[0]]
        if not rgba[..., 3].any():
            return None
        import io as _io
        from PIL import Image as _Image
        buf = _io.BytesIO()
        _Image.fromarray(rgba).save(buf, "WEBP", quality=80)   # smooth ramp: webp is ~4x smaller than png
        return buf.getvalue()
    return enc


def main():
    args = common.setup("22_canopy_height")
    q = common.DATA / "query"
    q.mkdir(parents=True, exist_ok=True)
    clip = q / "canopy_height_10m.tif"
    tiles_out = common.DATA / "tiles" / "canopy.pmtiles"

    files = []
    for t in TILES_3DEG:
        name = f"ETH_GlobalCanopyHeight_10m_2020_{t}_Map.tif"
        files.append(common.download(BASE + name, common.WORK_ROOT / "downloads" / "eth_canopy" / name,
                                     timeout=7200))
    if args.force or not clip.exists():
        log.info("mosaicking %d tiles clipped to %s", len(files), common.bbox())
        mosaic_clip(files, common.bbox(), clip)
        common.record("22_canopy_height", clip)
        log.info("canopy_height_10m.tif: %.0f MB", clip.stat().st_size / 1e6)

    if args.force or not tiles_out.exists():
        merc = warp_to_mercator(clip, f"canopy_{common.AREA}", 12, Resampling.average,
                                dtype="uint8", nodata=NODATA, src_nodata=NODATA)
        cut_tiles(merc, tiles_out, "ETH canopy height 2020", "webp", common.CFG["tiles"]["minzoom"], 12,
                  make_ramp_encoder(), Resampling.average)
        common.record("22_canopy_height", tiles_out)

    common.update_registry("canopy", {
        "title": "Canopy height (ETH 2020)", "group": "Vegetation", "type": "thematic",
        "urls": {"tiles": "tiles/canopy.pmtiles", "query": "query/canopy_height_10m.tif"},
        "minzoom": common.CFG["tiles"]["minzoom"], "maxzoom": 12,
        "ramp": {"max_m": RAMP_MAX},
        "source": "ETH Global Canopy Height 2020, 10 m (GEDI + Sentinel-2 deep-learning fusion), "
                  "six 3-degree tiles mosaicked and clipped to the department",
        "period": "2020", "units": "canopy top height, m (RH98-calibrated)",
        "licence": "CC BY 4.0 (ETH Research Collection record)",
        "citation": "Lang, N., Jetz, W., Schindler, K. & Wegner, J.D. (2023). A high-resolution "
                    "canopy height model of the Earth. Nature Ecology & Evolution 7:1778-1789. "
                    "doi:10.1038/s41559-023-02206-6. Data: doi:10.3929/ethz-b-000609802",
        "caveats": "Model estimate, not a measurement: tall-canopy heights saturate and the map "
                   "carries the model's uncertainty (a per-pixel SD layer exists upstream). "
                   "Display tiles are averaged to ~38 m at z12; clicks read the 10 m raster."})


if __name__ == "__main__":
    main()
