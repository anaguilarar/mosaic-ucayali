# MOSAIC Ucayali Explorer

**Live app: https://anaguilarar.github.io/mosaic-ucayali/**

An interactive map and story of the forest–agriculture interface of Ucayali, Peru, built around
Cooley et al. (2024, *Ecology and Evolution* 14:e70116): the co-produced vegetation classes (CC0
dataset), GEDI spaceborne-lidar canopy height, ETH canopy height, GEOBOSQUES forest loss, MapBiomas
land cover and burned area, VIIRS active fires, protected areas, and CHIRPS/CHIRTS rainfall,
temperature and drought (SPI-3), over terrain and Sentinel-2 imagery. Part of
[MOSAIC](https://mosaic-mfl.github.io/website/), the CGIAR Multifunctional Landscapes Science
Programme.

- `site/` — the static app (MapLibre GL + PMTiles; no backend)
- `data/` — the app's data (small files served from this repo; large tiles from the
  [Hugging Face dataset](https://huggingface.co/datasets/aaguilar90/mosaic-ucayali))
- `pipeline/` — the portable processing pipeline (see `pipeline/RUN.md` to run it on any machine)
- `prep/` — Earth Engine export scripts (input provenance)
- `tests/` — browser checks (story, menu, climate switch, missing files, request session) and the climate encoding check
- `DATA_REPORT.md` — sources, licences and method notes for every layer

Local preview: `python pipeline/scripts/serve.py` → http://127.0.0.1:8765/site/

Every number shown in the app is either quoted from a cited paper as printed (page recorded in
`DATA_REPORT.md`) or labelled "this app's analysis".
