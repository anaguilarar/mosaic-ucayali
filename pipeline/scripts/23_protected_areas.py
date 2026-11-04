"""Step 23 - protected areas: SERNANP ANP (national, definitive) and ACR (regional conservation
areas) intersecting Ucayali, from SERNANP's public ArcGIS REST service (geoservicios.sernanp.gob.pe,
service servicios_ogc/peru_sernanp_0102; layer 0 = ANP definitivas, layer 2 = ACR).

Writes <data>/vectors/protected_areas.geojson: kind, name, category, code, legal area (ha), legal
document and year; geometries clipped to the department outline and simplified ~90 m. SERNANP's
viewer terms: information is "de dominio público", derived maps are authorised with SERNANP cited
as source, no commercialisation, redistribution of the ORIGINAL information not authorised - this
file is a clipped/simplified derivative with citation; the verbatim terms are in DATA_REPORT §2.

Usage:  python scripts/23_protected_areas.py [--area pilot|full] [--force]
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import geopandas as gpd
import pandas as pd
import requests

SVC = "https://geoservicios.sernanp.gob.pe/arcgis/rest/services/servicios_ogc/peru_sernanp_0102/MapServer"
LAYERS = {0: "ANP (national)", 2: "ACR (regional)"}
SIMPLIFY_DEG = 0.0008


def fetch_layer(layer_id: int, bbox) -> gpd.GeoDataFrame:
    w, s, e, n = bbox
    frames, offset = [], 0
    while True:
        params = {"where": "1=1", "outFields": "*", "f": "geojson",
                  "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope",
                  "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                  "resultOffset": offset, "resultRecordCount": 50}
        r = requests.get(f"{SVC}/{layer_id}/query", params=params, timeout=300,
                         headers={"User-Agent": "MOSAIC-ucayali-pipeline/0.1 (CGIAR research)"})
        r.raise_for_status()
        gj = r.json()
        feats = gj.get("features", [])
        if feats:
            frames.append(gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326"))
        if not gj.get("properties", {}).get("exceededTransferLimit") and len(feats) < 50:
            break
        offset += len(feats)
        if not feats:
            break
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def main():
    args = common.setup("23_protected_areas")
    out = common.DATA / "vectors" / "protected_areas.geojson"
    if out.exists() and not args.force:
        log.info("protected_areas.geojson exists; --force to rebuild")
        return
    dept = gpd.read_file(common.INPUTS / common.CFG["inputs"]["department"]).to_crs("EPSG:4326")
    dept_geom = dept.union_all()
    rows = []
    for lid, kind in LAYERS.items():
        g = fetch_layer(lid, common.bbox())
        log.info("%s: %d features intersect the bbox", kind, len(g))
        if g.empty:
            continue
        p = "anp_" if lid == 0 else "acr_"
        g = g.rename(columns={p + "nomb": "name", p + "codi": "code", p + "suleg": "area_legal_ha",
                              p + "balec": "legal_doc", p + "felec": "created_ms"})
        g["category"] = g["anp_cate"] if lid == 0 else "Área de Conservación Regional"
        g["kind"] = kind
        g["year"] = g["created_ms"].map(
            lambda v: datetime.datetime.utcfromtimestamp(v / 1000).year if pd.notna(v) else None)
        g = g[g.intersects(dept_geom)]
        g["geometry"] = g.geometry.intersection(dept_geom).simplify(SIMPLIFY_DEG, preserve_topology=True)
        g = g[~g.geometry.is_empty]
        rows.append(g[["kind", "name", "category", "code", "area_legal_ha", "legal_doc", "year", "geometry"]])
    gdf = gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), crs="EPSG:4326")
    if common.AREA == "pilot":
        from shapely.geometry import box
        gdf = gdf[gdf.intersects(box(*common.bbox()))]
    out.write_text(gdf.to_json(drop_id=True), encoding="utf-8")
    log.info("protected_areas.geojson: %d features (%s), %.0f kB", len(gdf),
             gdf.groupby("kind").size().to_dict(), out.stat().st_size / 1e3)
    common.record("23_protected_areas", out)
    common.update_registry("protected_areas", {
        "title": "Protected areas (ANP & ACR)", "group": "Conservation", "type": "vector",
        "urls": {"polygons": "vectors/protected_areas.geojson"},
        "source": "SERNANP public map service (geoservicios.sernanp.gob.pe, peru_sernanp_0102: "
                  "ANP definitivas + ACR), clipped to Ucayali and simplified ~90 m",
        "period": "fetched 2026-11-04 (creation year per area in the popup)",
        "licence": "SERNANP viewer terms: information 'de dominio público'; derived maps authorised "
                   "with SERNANP cited as source; no commercialisation; redistribution of the "
                   "original information not authorised (this file is a clipped, simplified "
                   "derivative; verbatim terms in the data report)",
        "citation": "SERNANP - Servicio Nacional de Áreas Naturales Protegidas por el Estado "
                    "(geo.sernanp.gob.pe)",
        "caveats": "Boundaries simplified for display; legal areas (ha) are the service's "
                   "anp_suleg/acr_suleg values, not recomputed."})


if __name__ == "__main__":
    main()
