"""Climate encoding test (2026-11-04 bug: annual precipitation x10 overflowed int16 above
3,276.7 mm and wrapped to negative values).

Checks every stored climate file in data/climate against its dtype and scale:
  1. no negative precipitation anywhere (monthly, annual, seasonal, normals, cells.bin)
  2. no value at the int16 ceiling/floor other than nodata
  3. decoded annual maximum == maximum of the float annual sums recomputed from the monthly stack
  4. the pipeline guard (common.check_encoding) rejects the old x10 encoding of a 4,000 mm total
Exits 1 on any failure.

Usage:  python tests/climate_encoding_check.py   (any env with numpy + rasterio)
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "data" / "climate"
APP = C / "app"
ND = -32768
fails = []


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)


meta = json.loads((APP / "app_meta.json").read_text(encoding="utf-8"))
scales = meta.get("scales", {})

# 1-2: every int16 file
for p in sorted(list(C.glob("*.tif")) + list(APP.glob("*.tif"))):
    with rasterio.open(p) as r:
        a = r.read()
        nd = r.nodata
    if a.dtype.kind == "f":
        v = a[np.isfinite(a)]
        if p.name == "normals.tif":
            with rasterio.open(p) as r:
                labels = list(r.descriptions)
            for i, lb in enumerate(labels):
                b = a[i][np.isfinite(a[i])]
                if lb.startswith("precip"):
                    check((b >= 0).all(), f"{p.name} band {lb}: no negative precipitation (min {b.min():.0f})")
        continue
    v = a[a != nd] if nd is not None else a.ravel()
    info = np.iinfo(a.dtype)
    check(not ((v >= info.max) | (v <= info.min)).any(), f"{p.name}: no values at the {a.dtype} ceiling/floor")
    if p.name.startswith("precip"):
        check((v >= 0).all(), f"{p.name}: no negative precipitation ({int((v < 0).sum())} negative)")

for f in ("precip_cells.bin", "tmean_cells.bin"):
    a = np.fromfile(APP / f, "<i2")
    v = a[a != ND]
    check(not (v >= 32767).any(), f"{f}: no values at the int16 ceiling")
    if f.startswith("precip"):
        check((v >= 0).all(), f"{f}: no negative precipitation")

# 3: decoded annual max == float max recomputed from the monthly stack
with rasterio.open(C / "precip_monthly.tif") as r:
    mon = r.read().astype("f8")
    labels = list(r.descriptions)
mon[mon == ND] = np.nan
mon /= 10.0
years = np.array([int(lb[:4]) for lb in labels])
full = [y for y in sorted(set(years)) if (years == y).sum() == 12]
float_max = max(np.nanmax(mon[years == y].sum(0)) for y in full)
with rasterio.open(APP / "precip_annual.tif") as r:
    ann = r.read().astype("f8")
ann[ann == ND] = np.nan
dec_max = np.nanmax(ann) / scales.get("precip", 10)
check(abs(dec_max - float_max) <= 0.5 / scales.get("precip", 10) + 1e-6,
      f"precip_annual decoded max {dec_max:.1f} mm == float max {float_max:.1f} mm")

# 4: the pipeline guard rejects the old encoding
sys.path.insert(0, str(ROOT / "pipeline" / "scripts"))
try:
    import common  # needs pipeline/config.toml; skip gracefully on a machine without it
    bad = np.array([[[4000.0]]])
    enc = np.round(bad * 10).astype("i2")          # wraps to a negative number
    try:
        common.check_encoding("synthetic", bad, enc, 10, nonneg=True)
        check(False, "guard rejects a 4,000 mm total stored x10 in int16")
    except SystemExit:
        check(True, "guard rejects a 4,000 mm total stored x10 in int16")
except SystemExit:
    print("SKIP  guard test (no pipeline/config.toml on this machine)")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
