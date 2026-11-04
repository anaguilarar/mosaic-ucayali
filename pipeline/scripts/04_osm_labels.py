"""Step 04 - OSM place names and water labels: extract the Protomaps daily basemap to the
department bbox with the go-pmtiles CLI (path in config [paths].pmtiles_cli; a small single
binary from https://github.com/protomaps/go-pmtiles/releases).

    pmtiles extract https://build.protomaps.com/<build>.pmtiles data/tiles/osm_basemap.pmtiles \
            --bbox=<full bbox> --maxzoom=<osm_maxzoom>

Only label layers are styled in the app (places, water names, natural areas); roads and
buildings stay in the archive unstyled. Glyph fonts (Noto Sans) are already in data/fonts/
(from protomaps/basemaps-assets, copied with the scaffold).

Usage:  python scripts/04_osm_labels.py [--area pilot|full] [--force]
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import log


def main():
    args = common.setup("04_osm_labels")
    cfg = common.CFG
    cli = cfg["paths"].get("pmtiles_cli", "")
    if not cli:
        sys.exit("pmtiles_cli is not set in config.toml: download go-pmtiles "
                 "(github.com/protomaps/go-pmtiles/releases) and point [paths].pmtiles_cli at it.")
    out = common.DATA / "tiles" / "osm_basemap.pmtiles"
    if out.exists() and not args.force:
        log.info("osm_basemap.pmtiles exists; --force to re-extract")
        return
    build = cfg["tiles"]["osm_build"]
    bbox = common.bbox()
    cmd = [cli, "extract", f"https://build.protomaps.com/{build}.pmtiles", str(out),
           "--bbox=" + ",".join(f"{v}" for v in bbox), f"--maxzoom={cfg['tiles']['osm_maxzoom']}"]
    log.info("running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    log.info("osm_basemap.pmtiles: %.1f MB", out.stat().st_size / 1e6)
    common.record("04_osm_labels", out, f"protomaps build {build}")
    common.update_registry("osm_labels", {
        "title": "Place names", "group": "Base", "type": "vector",
        "urls": {"tiles": "tiles/osm_basemap.pmtiles", "glyphs": "fonts/{fontstack}/{range}.pbf"},
        "minzoom": 0, "maxzoom": cfg["tiles"]["osm_maxzoom"],
        "source": f"OpenStreetMap via the Protomaps daily basemap (build {build}, schema v4)",
        "period": f"OSM data as of {build[:4]}-{build[4:6]}-{build[6:]}",
        "units": "labels only: cities, towns, villages, rivers, lakes, protected areas",
        "licence": "ODbL 1.0 - (c) OpenStreetMap contributors",
        "citation": "(c) OpenStreetMap contributors (openstreetmap.org/copyright). Basemap tiles: "
                    "Protomaps (protomaps.com). Fonts: Noto Sans (SIL OFL) via protomaps/basemaps-assets.",
        "caveats": "Volunteered geographic information: coverage and spelling vary; label positions "
                   "are OSM points, not authoritative gazetteer locations."})


if __name__ == "__main__":
    main()
