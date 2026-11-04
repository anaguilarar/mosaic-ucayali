"""Step 12 - filter GEDI L2A shots to Parquet, granule by granule (memory stays bounded).

The Parquet holds the PAPER set - exactly the filters of Cooley et al. (2024) sect. 2.4
pp. 11-12 (their modification of Potapov et al. 2021), nothing more:
  1. full-power beams only (config [gedi].beams)
  2. beam sensitivity >= 0.9
  3. ground-elevation agreement: of the six algorithms' elev_lowestmode_a1..a6, drop the one
     farthest from the median, then require max-min of the remaining five <= 2 m
  4. inside the area bbox (Harmony subsets carry a margin)
The paper does NOT filter on quality_flag or degrade_flag; both are stored as COLUMNS, so the
app's own map products can use the STRICT set (quality_flag == 1 and degrade_flag == 0) by
filtering the same Parquet - 13_gedi_stats reports both sets, DATA_REPORT labels them.

Each input .h5 becomes one Parquet file in <work>/gedi/parquet/<YYYY-MM>/ with positions,
elevation, sensitivity, solar elevation, the flags, the full RH profile (101 values) and named
rh50/75/95/98 columns. Per-stage shot counts go to <work>/gedi/filter_counts.json.

Usage:  python scripts/12_gedi_filter.py [--area pilot|full] [--force]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import h5py
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

STAGES = ["in_file", "power_beam", "sensitivity", "elev_agreement", "in_bbox_paper", "strict"]


def filter_file(path: Path, beams, sens_min, elev_max, bbox):
    counts = dict.fromkeys(STAGES, 0)
    rows = {k: [] for k in ["shot_number", "beam", "lon", "lat", "elev", "sensitivity",
                            "solar_elevation", "quality_flag", "degrade_flag", "rh"]}
    with h5py.File(path, "r") as f:
        groups = [k for k in f.keys() if k.startswith("BEAM")]
        for b in groups:
            gr = f[b]
            if "shot_number" not in gr:
                continue
            n = gr["shot_number"].shape[0]
            counts["in_file"] += n
            if b not in beams:
                continue
            counts["power_beam"] += n
            sens = gr["sensitivity"][:]
            # beam sensitivity is a fraction in [0, 1]; values above 1 are fill/invalid (seen up to
            # 98 in cloud-struck shots) and are not a "sensitivity >= 0.9" in the paper's sense
            q = (sens >= sens_min) & (sens <= 1.0)
            counts["sensitivity"] += int(q.sum())
            try:
                elevs = np.stack([gr[f"geolocation/elev_lowestmode_a{i}"][:] for i in range(1, 7)])
            except KeyError:
                log.warning("%s %s: per-algorithm elevations missing; elev-agreement filter skipped", path.name, b)
                elevs = None
            if elevs is not None:
                med = np.median(elevs, axis=0)
                dev = np.abs(elevs - med)
                drop = np.argmax(dev, axis=0)
                keep5 = np.ma.masked_array(elevs, mask=np.arange(6)[:, None] == drop)
                rng = keep5.max(axis=0) - keep5.min(axis=0)
                q &= np.asarray(rng <= elev_max)
            counts["elev_agreement"] += int(q.sum())
            lon = gr["lon_lowestmode"][:]
            lat = gr["lat_lowestmode"][:]
            w, s, e, nn = bbox
            q &= (lon >= w) & (lon <= e) & (lat >= s) & (lat <= nn)
            k = int(q.sum())
            counts["in_bbox_paper"] += k
            if not k:
                continue
            qf = gr["quality_flag"][:][q].astype("u1")
            df = (gr["degrade_flag"][:][q] if "degrade_flag" in gr else np.zeros(k)).astype("u1")
            counts["strict"] += int(((qf == 1) & (df == 0)).sum())
            rows["shot_number"].append(gr["shot_number"][:][q])
            rows["beam"].append(np.full(k, b))
            rows["lon"].append(lon[q]); rows["lat"].append(lat[q])
            rows["elev"].append(gr["elev_lowestmode"][:][q])
            rows["sensitivity"].append(sens[q])
            rows["solar_elevation"].append(gr["solar_elevation"][:][q]
                                           if "solar_elevation" in gr else np.full(k, np.nan))
            rows["quality_flag"].append(qf)
            rows["degrade_flag"].append(df)
            rows["rh"].append(gr["rh"][:][q].astype("f4"))
    if not rows["shot_number"]:
        return counts, None
    cat = {k: np.concatenate(v) for k, v in rows.items()}
    rh = cat.pop("rh")
    # acquisition date from the granule name (GEDI02_A_YYYYDDDHHMMSS_...): the replication set is a
    # date filter (2019-04-18..2021-12-31) over the one mission-window download
    import datetime as _dt
    m = __import__("re").search(r"GEDI02_A_(\d{4})(\d{3})", path.name)
    date = (_dt.date(int(m.group(1)), 1, 1) + _dt.timedelta(days=int(m.group(2)) - 1)) if m else None
    n_rows = len(cat["shot_number"])
    table = pa.table({**{k: v for k, v in cat.items()},
                      "date": pa.array([date] * n_rows, pa.date32()),
                      "rh": pa.FixedSizeListArray.from_arrays(pa.array(rh.ravel(), pa.float32()), 101),
                      "rh50": rh[:, 50], "rh75": rh[:, 75], "rh95": rh[:, 95], "rh98": rh[:, 98]})
    return counts, table


def main():
    args = common.setup("12_gedi_filter")
    g = common.CFG["gedi"]
    subsets = common.WORK / "gedi" / "subsets"
    if not subsets.exists():
        sys.exit("no subsets found: run 11_gedi_subset.py first")
    outroot = common.WORK / "gedi" / "parquet"
    total = dict.fromkeys(STAGES, 0)
    files = sorted(subsets.rglob("*.h5")) + sorted(subsets.rglob("*.nc")) + sorted(subsets.rglob("*.h5.nc"))
    if not files:
        sys.exit(f"no .h5/.nc files under {subsets}")
    done = 0
    for f in files:
        month = f.parent.name
        out = outroot / month / (f.stem + ".parquet")
        if out.exists() and not args.force:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        counts, table = filter_file(f, set(g["beams"]), g["sensitivity_min"],
                                    g["elev_range_max_m"], common.bbox())
        for k in STAGES:
            total[k] += counts[k]
        if table is not None:
            pq.write_table(table, out, compression="zstd")
            common.record("12_gedi_filter", out, "paper-set shots + quality/degrade columns")
        log.info("%s: %s -> paper %s / strict %s", f.name,
                 " / ".join(str(counts[k]) for k in STAGES[:4]),
                 counts["in_bbox_paper"], counts["strict"])
        done += 1
    cj = common.WORK / "gedi" / "filter_counts.json"
    old = {} if args.force else (json.loads(cj.read_text()).get("stages", {}) if cj.exists() else {})
    merged = {k: old.get(k, 0) + total[k] for k in STAGES}
    cj.write_text(json.dumps({"stages": merged,
                              "note": "cumulative over processed files; 'in_bbox_paper' = the paper's "
                                      "three filters (Cooley et al. 2024 sect. 2.4); 'strict' adds "
                                      "quality_flag=1 & degrade_flag=0 (app map products only)"},
                             indent=1), encoding="utf-8")
    log.info("processed %d new file(s); cumulative counts: %s", done, merged)


if __name__ == "__main__":
    main()
