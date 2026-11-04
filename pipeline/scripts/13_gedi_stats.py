"""Step 13 - pilot/QA statistics: filtered shots against the Cooley vegetation polygons.

Counts shots per class (a) inside the polygons, and (b) inside the polygons eroded by 32.5 m
(so the shot's ~65 m-diameter homogeneous area - footprint + 2-sigma geolocation error, Cooley
et al. 2024 Fig. 6 p.15 - fits entirely in one polygon). Also projects the full-run volume
from the processed months. Writes <work>/gedi/stats.json and prints a summary.

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
    frames = [pq.read_table(f, columns=["lon", "lat", "rh95", "rh50", "beam"]).to_pandas() for f in files]
    shots = pd.concat(frames, ignore_index=True)
    log.info("filtered shots loaded: %d from %d file(s)", len(shots), len(files))

    pts = gpd.GeoDataFrame(shots, geometry=gpd.points_from_xy(shots.lon, shots.lat), crs="EPSG:4326")
    src = common.COOLEY / common.CFG["inputs"]["cooley_geojson"]
    polys = gpd.read_file(src).to_crs("EPSG:4326")
    polys["COBERTURA"] = polys["COBERTURA"].replace(
        {"Bosque_secudario_o_degradado": "Bosque_secundario_o_degradado"})

    def count_in(p):
        j = gpd.sjoin(pts, p[["COBERTURA", "geometry"]], predicate="within")
        return j.groupby("COBERTURA").size().to_dict(), len(j)

    inside, n_in = count_in(polys)
    eroded = polys.to_crs(UTM)
    eroded["geometry"] = eroded.geometry.buffer(-ERODE_M)
    eroded = eroded[~eroded.geometry.is_empty].to_crs("EPSG:4326")
    inside65, n_65 = count_in(eroded)

    months = sorted({f.parent.name for f in files})
    sub = common.WORK / "gedi" / "subsets"
    mb = sum(json.loads(j.read_text())["mb"] for j in sub.rglob("job.json")) if sub.exists() else 0
    secs = sum(json.loads(j.read_text())["seconds"] for j in sub.rglob("job.json")) if sub.exists() else 0
    # mission months with data in the replication window ~ 2019-04..2021-12 = 33 months
    proj = {"months_processed": months, "subset_mb": mb, "subset_seconds": secs,
            "per_month_mb": round(mb / max(len(months), 1), 1),
            "projected_full_33mo_gb": round(mb / max(len(months), 1) * 33 / 1e3, 1),
            "projected_full_33mo_hours": round(secs / max(len(months), 1) * 33 / 3600, 1)}

    stats = {"shots_filtered": int(len(shots)),
             "in_polygons": {"total": int(n_in), "by_class": inside},
             "in_polygons_65m_homogeneous": {"total": int(n_65), "by_class": inside65},
             "rh95_mean_by_class_m": {}, "projection": proj}
    j = gpd.sjoin(pts, polys[["COBERTURA", "geometry"]], predicate="within")
    if len(j):
        stats["rh95_mean_by_class_m"] = {k: round(v, 2) for k, v in
                                         j.groupby("COBERTURA")["rh95"].mean().to_dict().items()}
    out = common.WORK / "gedi" / "stats.json"
    out.write_text(json.dumps(stats, indent=1), encoding="utf-8")
    log.info("stats:\n%s", json.dumps(stats, indent=1))
    log.info("wrote %s", out)


if __name__ == "__main__":
    main()
