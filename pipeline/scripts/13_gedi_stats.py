"""Step 13 - pilot/QA statistics: filtered shots against the Cooley vegetation polygons. One
mission-window download serves everything; the sets are column/date filters over the same Parquet:
  filter sets:  paper  - exactly Cooley et al. (2024) sect. 2.4 (everything in the Parquet);
                strict - paper + quality_flag = 1 and degrade_flag = 0 (app map products).
  date windows: replication - 2019-04-18..2021-12-31 (config replication_window), the only window
                compared with the paper's tables; mission - every shot downloaded.
The polygon comparison is reported for both filter sets in BOTH windows (mission counts over the
2020/21-vintage polygons are QA only, flagged as such).

For each set: shots per class (a) inside the polygons and (b) inside the polygons eroded by
32.5 m (the shot's ~65 m homogeneous area - footprint + 2-sigma geolocation error, Fig. 6 p.15 -
fits in one polygon), plus mean RH95 per class. Also projects the full-run volume from the
processed months. Writes <work>/gedi/stats.json and prints a summary.

Usage:  python scripts/13_gedi_stats.py [--area pilot|full]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq

UTM = "EPSG:32718"       # UTM 18S: covers the Cooley polygons (-75.9..-72.9)
ERODE_M = 32.5


def main():
    common.setup("13_gedi_stats")
    pdir = common.WORK / "gedi" / "parquet"
    files = sorted(pdir.rglob("*.parquet"))
    if not files:
        sys.exit("no parquet yet: run 12_gedi_filter.py first")
    cols = ["lon", "lat", "rh95", "rh50", "beam", "quality_flag", "degrade_flag", "date"]
    shots = pd.concat([pq.read_table(f, columns=cols).to_pandas() for f in files], ignore_index=True)
    log.info("paper-set shots loaded (mission download): %d from %d file(s)", len(shots), len(files))

    src = common.COOLEY / common.CFG["inputs"]["cooley_geojson"]
    polys = gpd.read_file(src).to_crs("EPSG:4326")
    polys["COBERTURA"] = polys["COBERTURA"].replace(
        {"Bosque_secudario_o_degradado": "Bosque_secundario_o_degradado"})
    eroded = polys.to_crs(UTM)
    eroded["geometry"] = eroded.geometry.buffer(-ERODE_M)
    eroded = eroded[~eroded.geometry.is_empty].to_crs("EPSG:4326")

    def analyse(df):
        pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")
        j = gpd.sjoin(pts, polys[["COBERTURA", "geometry"]], predicate="within")
        j65 = gpd.sjoin(pts, eroded[["COBERTURA", "geometry"]], predicate="within")
        return {"shots": int(len(df)),
                "in_polygons": {"total": int(len(j)), "by_class": j.groupby("COBERTURA").size().to_dict()},
                "in_polygons_65m": {"total": int(len(j65)), "by_class": j65.groupby("COBERTURA").size().to_dict()},
                "rh95_mean_by_class_m": {k: round(v, 2) for k, v in
                                         j.groupby("COBERTURA")["rh95"].mean().to_dict().items()},
                "rh95_n_by_class": j.groupby("COBERTURA").size().to_dict()}

    import datetime as dt
    r0, r1 = (dt.date.fromisoformat(d) for d in common.CFG["gedi"]["replication_window"])
    in_rep = shots.date.map(lambda d: d is not None and r0 <= d <= r1)
    strict_m = (shots.quality_flag == 1) & (shots.degrade_flag == 0)
    stats = {"replication": {"paper": analyse(shots[in_rep]),
                             "strict": analyse(shots[in_rep & strict_m])},
             "mission": {"paper": analyse(shots), "strict": analyse(shots[strict_m]),
                         "note": "QA only: the polygons are 2020/21 vintage; paper comparisons "
                                 "use the replication window"}}

    months = sorted({f.parent.name for f in files})
    sub = common.WORK / "gedi" / "subsets"
    mb = sum(json.loads(j.read_text())["mb"] for j in sub.rglob("job.json")) if sub.exists() else 0
    secs = sum(json.loads(j.read_text())["seconds"] for j in sub.rglob("job.json")) if sub.exists() else 0
    per_mo = mb / max(len(months), 1)
    g = common.CFG["gedi"]
    stats["projection"] = {
        "months_processed": months, "subset_mb": mb, "per_month_mb": round(per_mo, 1),
        "replication_window": g.get("replication_window"),
        "mission_window": g.get("mission_window"),
        "note": "fill months-with-data per window from 10_gedi_search --pick-month; "
                "size ~ months x per_month_mb, wall ~ months x 6-10 min of Harmony queue"}
    out = common.WORK / "gedi" / "stats.json"
    out.write_text(json.dumps(stats, indent=1), encoding="utf-8")
    log.info("stats:\n%s", json.dumps(stats, indent=1))
    log.info("wrote %s", out)


if __name__ == "__main__":
    main()
