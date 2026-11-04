"""Step 26 - SPI-3 (3-month Standardized Precipitation Index) from the step-25 monthly stack.
Direct port of the Lake Victoria app's method (prep/09): 3-month rolling totals; per cell and
calendar month a gamma distribution is fitted to the 1991-2020 calibration totals with the
Thom (1958) approximation, the zero-rain probability handled as a mixed distribution
(q0 + (1-q0)*GammaCDF); SPI = standard normal quantile, clamped to [-3, 3], stored x0.01.
The index: McKee, Doesken & Kleist (1993); class names in the app: WMO (2012), WMO-No. 1090.

Writes climate/app/spi3.tif (+ _cells.bin, _qc.tif), series/spi3_dept.json, updates app_meta.

Usage:  python scripts/26_spi.py [--area pilot|full] [--force]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import check_encoding, log

import numpy as np
import rasterio
from scipy.stats import gamma as sgamma
from scipy.stats import norm

NODATA = -32768
WINDOW = 3


def main():
    args = common.setup("26_spi")
    NORMAL = tuple(common.CFG.get("climate", {}).get("normal", [1991, 2020]))
    CLIMATE = common.DATA / "climate"
    APPD = CLIMATE / "app"
    SERIES = common.DATA / "series"
    out_tif = APPD / "spi3.tif"
    src = CLIMATE / "precip_monthly.tif"
    if out_tif.exists() and not args.force and common.fresh(out_tif, src):
        log.info("spi3.tif is fresh; --force to recompute")
        return

    with rasterio.open(src) as r:
        a = r.read().astype("f8")
        labels = list(r.descriptions)
        t = r.transform
    a[a == NODATA] = np.nan
    a /= 10.0

    tot = np.full_like(a, np.nan)
    for i in range(WINDOW - 1, a.shape[0]):
        tot[i] = a[i - WINDOW + 1: i + 1].sum(0)
    months = np.array([int(lb[5:7]) for lb in labels])
    years = np.array([int(lb[:4]) for lb in labels])
    calib = (years >= NORMAL[0]) & (years <= NORMAL[1])

    spi = np.full_like(tot, np.nan, dtype="f8")
    qc_normal = np.full((12,) + tot.shape[1:], np.nan)
    qc_q0 = np.full((12,) + tot.shape[1:], np.nan)
    eps = 1e-9
    for m in range(1, 13):
        sel = (months == m)
        cal = sel & calib
        x = tot[cal]
        pos = np.where(x > eps, x, np.nan)
        n_all = np.isfinite(x).sum(0).astype("f8")
        n_pos = np.isfinite(pos).sum(0).astype("f8")
        with np.errstate(all="ignore"):
            q0 = (n_all - n_pos) / np.maximum(n_all, 1)
            mean = np.nanmean(pos, axis=0)
            lnmean = np.log(np.maximum(mean, eps))
            meanln = np.nanmean(np.log(np.maximum(pos, eps)), axis=0)
            A = np.maximum(lnmean - meanln, 1e-6)                 # Thom approximation
            shape = (1 + np.sqrt(1 + 4 * A / 3)) / (4 * A)
            scale = mean / shape
            xt = tot[sel]
            cdf = sgamma.cdf(np.maximum(xt, eps), shape[None], scale=scale[None])
            p = q0[None] + (1 - q0[None]) * cdf
            p = np.where(xt <= eps, q0[None] / 2 + 1e-4, p)
            p = np.clip(p, 1e-4, 1 - 1e-4)
            spi[sel] = norm.ppf(p)
            qc_normal[m - 1] = np.nanmean(x, axis=0)
            qc_q0[m - 1] = q0
        log.info("month %02d fitted (valid cells: %d)", m, int(np.isfinite(shape).sum()))
    spi = np.clip(spi, -3, 3)
    spi[~np.isfinite(tot)] = np.nan
    spi = spi[WINDOW - 1:]
    out_labels = labels[WINDOW - 1:]

    enc = np.where(np.isfinite(spi), np.round(spi * 100), NODATA).astype("i2")
    check_encoding("spi3.tif", spi, enc, 100)
    prof = dict(driver="GTiff", height=enc.shape[1], width=enc.shape[2], count=enc.shape[0],
                dtype="int16", crs="EPSG:4326", transform=t, nodata=NODATA, tiled=True,
                blockxsize=256, blockysize=256, compress="DEFLATE", predictor=2)
    with rasterio.open(out_tif, "w", **prof) as dst:
        dst.write(enc)
        for i, lb in enumerate(out_labels, 1):
            dst.set_band_description(i, lb)
        dst.update_tags(units="SPI (unitless)", scale_factor="0.01",
                        calibration=f"{NORMAL[0]}-{NORMAL[1]}", window="3 months, label = end month")
    log.info("spi3.tif: %d bands, %.1f MB", len(out_labels), out_tif.stat().st_size / 1e6)
    common.record("26_spi", out_tif)

    flat = np.ascontiguousarray(np.moveaxis(enc, 0, -1).astype("<i2"))
    (APPD / "spi3_cells.bin").write_bytes(flat.tobytes())

    meta = json.loads((APPD / "app_meta.json").read_text(encoding="utf-8"))
    meta["months_spi3"] = {"start": out_labels[0], "end": out_labels[-1], "n": len(out_labels)}
    (APPD / "app_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    with rasterio.open(APPD / "landmask.tif") as lm:
        land = lm.read(1) == 10
    series = {lb: round(float(np.nanmean(np.where(land, s, np.nan))), 2) for lb, s in zip(out_labels, spi)}
    (SERIES / "spi3_dept.json").write_text(json.dumps(
        {"units": "SPI-3", "calibration": f"{NORMAL[0]}-{NORMAL[1]}",
         "mask": "department land cells", "monthly": series}), encoding="utf-8")

    qc = np.concatenate([qc_normal, qc_q0 * 100])
    qlabels = [f"normal_mm_{m:02d}" for m in range(1, 13)] + [f"q0_pct_{m:02d}" for m in range(1, 13)]
    qenc = np.where(np.isfinite(qc), np.round(qc * 10), NODATA).astype("i2")
    check_encoding("spi3_qc.tif", qc, qenc, 10, nonneg=True)
    with rasterio.open(APPD / "spi3_qc.tif", "w", **{**prof, "count": 24}) as dst:
        dst.write(qenc)
        for i, lb in enumerate(qlabels, 1):
            dst.set_band_description(i, lb)
        dst.update_tags(scale_factor="0.1",
                        caution="SPI is unreliable where the calibration window normal is small or "
                                "zero-inflated (low-normal flag: normal < 30 mm or q0 > 20%)")

    common.update_registry("spi3", {
        "title": "Drought index (SPI-3)", "group": "Climate", "type": "climate-monthly",
        "urls": {"stack": "climate/app/spi3.tif", "cells": "climate/app/spi3_cells.bin",
                 "qc": "climate/app/spi3_qc.tif", "series": "series/spi3_dept.json"},
        "palette": {"value": "BrBG diverging, centred 0, fixed -3..3 (values clipped to +-3)"},
        "source": "SPI-3 computed from CHIRPS v3.0 monthly totals (gamma fit, Thom 1958; "
                  f"zero-rain mixed distribution), calibration {NORMAL[0]}-{NORMAL[1]}",
        "period": f"{out_labels[0]} to {out_labels[-1]}", "units": "SPI (unitless)",
        "licence": "Derived from CHIRPS v3.0 (CC-BY-4.0)",
        "caveats": "The latest 2-3 CHIRPS months are provisional; class names follow WMO (2012).",
        "citation": "McKee, Doesken & Kleist (1993), 8th Conf. Applied Climatology; classes: "
                    "WMO (2012), SPI User Guide, WMO-No. 1090; Funk et al. (2015), Sci. Data 2:150066"})


if __name__ == "__main__":
    main()
