"""Step 01 - boundaries: Ucayali department outline + outside mask, provinces and districts.

Outputs (EPSG:4326, <data>/vectors/): department.geojson, department_mask.geojson,
provinces.geojson, districts.geojson, admin_labels.geojson. Registry entries 'department'
and 'admin_boundaries'.

The department outline comes from inputs (INEI, FUENTE field). Districts come from the IGN
dataset on Peru's open-data portal (ODC-By; DISTRITOS_LIMITES.zip inside the 'limites-
departamentales' dataset) - downloaded once into the work dir; provinces are dissolved from
districts. With --area pilot, only units intersecting the pilot box are kept.

Usage:  python scripts/01_boundary.py [--area pilot|full] [--force]
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Polygon

# IGN "Limites Departamentales" dataset resource (ODC-By), datosabiertos.gob.pe dataset
# 6c5c52fd-047d-4ba7-9ac7-3865860118c2; the district zip lives inside the same dataset.
DISTRITOS_URL = "https://www.datosabiertos.gob.pe/sites/default/files/DISTRITOS_LIMITES.zip"
SIMPLIFY_DEG = 0.0008          # ~90 m, invisible at the app's zooms


def get_districts() -> gpd.GeoDataFrame:
    z = common.WORK_ROOT / "downloads" / "DISTRITOS_LIMITES.zip"
    z.parent.mkdir(parents=True, exist_ok=True)
    if not z.exists():
        log.info("downloading %s", DISTRITOS_URL)
        # identify the pipeline honestly; the portal rejects the bare python-requests default
        r = requests.get(DISTRITOS_URL, timeout=600,
                         headers={"User-Agent": "MOSAIC-ucayali-pipeline/0.1 (CGIAR research; "
                                                "github.com/anaguilarar/mosaic-ucayali)"})
        if r.status_code != 200:
            raise SystemExit(
                f"download refused ({r.status_code}). Download it manually in a browser:\n"
                f"  dataset page: https://www.datosabiertos.gob.pe/dataset/limites-departamentales\n"
                f"  resource:     DISTRITOS_LIMITES.zip\n"
                f"and save it as {z} , then re-run this step.")
        z.write_bytes(r.content)
        common.record("01_boundary", z, "IGN districts zip (ODC-By)")
    d = z.parent / "distritos"
    if not d.exists():
        with zipfile.ZipFile(z) as f:
            f.extractall(d)
    shp = next(d.rglob("*.shp"))
    return gpd.read_file(shp)


def main():
    args = common.setup("01_boundary")
    vec = common.DATA / "vectors"
    cfg = common.CFG

    dep = gpd.read_file(common.INPUTS / cfg["inputs"]["department"])[["geometry"]].to_crs("EPSG:4326")
    simp = dep.simplify(SIMPLIFY_DEG)
    out = vec / "department.geojson"
    if args.force or not common.fresh(out, common.INPUTS / cfg["inputs"]["department"]):
        simp.to_frame("geometry").to_file(out, driver="GeoJSON")
        log.info("department.geojson: %.0f kB", out.stat().st_size / 1e3)

        w, s, e, n = cfg["area"]["full_bbox"]
        pad = 2.5                                              # beyond the terrain padding
        world = Polygon([(w - pad, s - pad), (e + pad, s - pad), (e + pad, n + pad), (w - pad, n + pad)])
        mask = gpd.GeoDataFrame(geometry=[world.difference(simp.union_all())], crs="EPSG:4326")
        mask.to_file(vec / "department_mask.geojson", driver="GeoJSON")

    dist = get_districts().to_crs("EPSG:4326")
    # IGN DISTRITOS.shp schema: CODDEP/DEPARTAMEN, CODPROV/PROVINCIA, CODDIST/DISTRITO, FUENTE=INEI
    cod = next(c for c in dist.columns if c.upper().startswith("CODDEP") or c.upper() == "CCDD")
    name_col = next(c for c in dist.columns if c.upper() in ("DISTRITO", "NOMBDIST", "DISTRICT"))
    prov_col = next(c for c in dist.columns if c.upper() in ("PROVINCIA", "NOMBPROV", "PROVINCE"))
    du = dist[dist[cod].astype(str).str.zfill(2) == "25"].copy()
    log.info("districts in Ucayali: %d (columns %s)", len(du), [cod, prov_col, name_col])

    du = du.rename(columns={name_col: "district", prov_col: "province"})[["district", "province", "geometry"]]
    du["geometry"] = du.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)
    if common.AREA == "pilot":
        from shapely.geometry import box
        du = du[du.intersects(box(*common.bbox()))]
    du.to_file(vec / "districts.geojson", driver="GeoJSON")

    prov = du.dissolve(by="province", as_index=False)[["province", "geometry"]]
    prov.to_file(vec / "provinces.geojson", driver="GeoJSON")

    labels = []
    p1 = prov.copy(); p1["name"] = p1["province"]; p1["level"] = "province"
    p2 = du.copy(); p2["name"] = p2["district"]; p2["level"] = "district"
    for g in (p1, p2):
        g["geometry"] = g.geometry.representative_point()
        labels.append(g[["name", "level", "geometry"]])
    lab = gpd.GeoDataFrame(pd.concat(labels, ignore_index=True), crs="EPSG:4326")
    (vec / "admin_labels.geojson").write_text(lab.to_json(drop_id=True), encoding="utf-8")
    log.info("provinces: %d, districts: %d, labels: %d", len(prov), len(du), len(lab))

    for f in ("department.geojson", "department_mask.geojson", "provinces.geojson",
              "districts.geojson", "admin_labels.geojson"):
        common.record("01_boundary", vec / f)

    common.update_registry("department", {
        "title": "Ucayali department", "group": "Base", "type": "vector",
        "urls": {"boundary": "vectors/department.geojson", "mask": "vectors/department_mask.geojson"},
        "source": "INEI department boundary (inputs/ucayali.shp, FUENTE=INEI)",
        "licence": "Peruvian government boundary data; the same boundaries on datosabiertos.gob.pe "
                   "(publisher IGN) carry the Open Data Commons Attribution License (ODC-By)",
        "citation": "INEI / IGN via the Plataforma Nacional de Datos Abiertos (datosabiertos.gob.pe)",
        "caveats": "Boundaries are referential (1:100,000), not an official delimitation."})
    common.update_registry("admin_boundaries", {
        "title": "Provinces & districts", "group": "Base", "type": "vector",
        "urls": {"provinces": "vectors/provinces.geojson", "districts": "vectors/districts.geojson",
                 "labels": "vectors/admin_labels.geojson"},
        "source": "IGN 'Limites Departamentales' dataset (DISTRITOS_LIMITES.zip), datosabiertos.gob.pe; "
                  "provinces dissolved from districts",
        "period": "portal release 2022-03-10, modified 2023-08-01",
        "licence": "Open Data Commons Attribution License (ODC-By), as stated on the dataset page",
        "citation": "Instituto Geográfico Nacional (IGN), Plataforma Nacional de Datos Abiertos",
        "caveats": "Referential boundaries at 1:100,000; simplified ~90 m for display."})


if __name__ == "__main__":
    main()
