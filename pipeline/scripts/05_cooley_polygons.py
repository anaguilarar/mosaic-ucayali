"""Step 05 - Cooley et al. (2024) vegetation-type polygons (CC0, doi:10.22002/D1.2318) for the app.

Normalises the dataset's class-name typo ('Bosque_secudario_o_degradado' -> the correct
'Bosque_secundario_o_degradado'), keeping the file's original value in COBERTURA_RAW. Adds
English class names (per the dataset README and the paper's Table 1). Writes
<data>/vectors/veg_classes.geojson and a per-class summary into the registry (count and area,
this app's analysis of the CC0 file; the paper's own numbers are quoted in the story only).

Usage:  python scripts/05_cooley_polygons.py [--area pilot|full] [--force]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log

import geopandas as gpd

TYPO = {"Bosque_secudario_o_degradado": "Bosque_secundario_o_degradado"}

# Spanish class -> (English name, legend colour). English names are EXACTLY the dataset README's
# Table 1 names (pp. 2, 6-10); the first three also match the paper's Table 1 (pp. 7-10).
# Colours are the app's own. Note: the GeoJSON says 'Bosque_inundado' where the README writes
# 'Bosque inundable' (same class); 'Bosque_de_colina_alta' is the README's "Cloud forest".
CLASSES = {
    "Bosque_de_colina_baja":              ("Mature lowland forest", "#1b6b45"),
    "Bosque_secundario_o_degradado":      ("Secondary or degraded lowland forest", "#55a05f"),
    "Purma":                              ("Young vegetation regrowth (purma)", "#a9c977"),
    "Pastizales_o_herbazales_degradados": ("Degraded shrubland or pasture", "#d8c26a"),
    "Bosque_de_colina_alta":              ("Cloud forest", "#2e5d78"),
    "Aguajales":                          ("Palm groves (inundated)", "#5e9ea0"),
    "Bosque_inundado":                    ("Wetland forest", "#3f7f93"),
}


def main():
    args = common.setup("05_cooley_polygons")
    src = common.COOLEY / common.CFG["inputs"]["cooley_geojson"]
    out = common.DATA / "vectors" / "veg_classes.geojson"
    if common.fresh(out, src) and not args.force:
        log.info("veg_classes.geojson is fresh; --force to rebuild")
        return

    g = gpd.read_file(src).to_crs("EPSG:4326")
    assert len(g) == 324, f"expected 324 polygons (dataset v4), got {len(g)}"
    g["COBERTURA_RAW"] = g["COBERTURA"]
    g["COBERTURA"] = g["COBERTURA"].replace(TYPO)
    unknown = set(g["COBERTURA"]) - set(CLASSES)
    assert not unknown, f"unmapped classes: {unknown}"
    g["class_en"] = g["COBERTURA"].map(lambda c: CLASSES[c][0])
    g["color"] = g["COBERTURA"].map(lambda c: CLASSES[c][1])

    if common.AREA == "pilot":
        from shapely.geometry import box
        g = g[g.intersects(box(*common.bbox()))]
        log.info("pilot area: %d of 324 polygons", len(g))

    area_ha = g.to_crs("ESRI:102033").area / 1e4          # South America Albers
    g["area_ha"] = area_ha.round(1)
    cols = ["PLOTID", "COBERTURA", "COBERTURA_RAW", "class_en", "color", "area_ha",
            "ANO_IMAGEN", "MAPA_BASE", "FUENTE", "geometry"]
    g[cols].to_file(out, driver="GeoJSON")
    log.info("veg_classes.geojson: %d polygons, %.0f kB", len(g), out.stat().st_size / 1e3)
    common.record("05_cooley_polygons", out)

    summary = (g.groupby(["COBERTURA", "class_en", "color"])
                .agg(count=("PLOTID", "size"), area_ha=("area_ha", "sum"))
                .round(0).reset_index().to_dict("records"))
    common.update_registry("veg_classes", {
        "title": "Vegetation classes (co-produced)", "group": "Vegetation", "type": "vector",
        "urls": {"polygons": "vectors/veg_classes.geojson"},
        "classes": summary,
        "source": "Cooley et al. (2021) vegetation typology dataset v4 (Feb 2022), CaltechDATA; "
                  "classes co-produced with local experts in Ucayali",
        "period": "digitised on 2020/2021 imagery",
        "licence": "CC0 (as stated on the CaltechDATA record)",
        "citation": "Cooley, S., Pinto, N., Aguilar-Amuchastegui, N., Vela Alvarado, J. & Fahlen, J. "
                    "(2021). Vegetation typology classification and data set in Ucayali, Peru (v4.0). "
                    "CaltechDATA. doi:10.22002/D1.2318. Described in Cooley et al. (2024), Ecology and "
                    "Evolution 14:e70116, doi:10.1002/ece3.70116",
        "caveats": "Counts and areas are this app's analysis of the CC0 polygon file. The published "
                   "dataset has no oil-palm or cacao polygons; the paper's results for those classes "
                   "cannot be reproduced from it. The file's 'Bosque_secudario_o_degradado' spelling "
                   "is normalised here (original kept in COBERTURA_RAW)."})


if __name__ == "__main__":
    main()
