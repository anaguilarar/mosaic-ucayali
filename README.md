# MOSAIC Ucayali Explorer

An interactive map of the forest–agriculture interface of Ucayali, Peru — terrain, Sentinel-2
imagery, co-produced vegetation classes (Cooley et al. 2024, CC0 dataset) and, in later phases,
GEDI spaceborne-lidar canopy structure, forest loss and land cover. Part of
[MOSAIC](https://mosaic-mfl.github.io/website/), the CGIAR Multifunctional Landscapes Science
Programme.

- `site/` — the static app (MapLibre GL + PMTiles; no backend)
- `data/` — the app's data (small files served from this repo; large tiles from the
  [Hugging Face dataset](https://huggingface.co/datasets/aaguilar90/mosaic-ucayali))
- `pipeline/` — the portable processing pipeline (see `pipeline/RUN.md` to run it on any machine)
- `prep/` — Earth Engine export scripts (input provenance)
- `tests/` — browser checks (menu, missing files, request session)
- `DATA_REPORT.md` — sources, licences and method notes for every layer

Local preview: `python pipeline/scripts/serve.py` → http://127.0.0.1:8765/site/

Every number shown in the app is either quoted from a cited paper as printed (page recorded in
`DATA_REPORT.md`) or labelled "this app's analysis".
