# Running the pipeline on a new machine

The pipeline is portable: every path and parameter comes from `pipeline/config.toml`,
and `run_all.ps1` (Windows) / `run_all.sh` (Linux/macOS) are the only places the full
command sequence lives. Never retype step flags from here — this file explains, the
run scripts execute.

## Setup (once per machine)

1. **Environment** (conda):
   ```
   conda env create -f pipeline/environment.yml
   conda activate mosaic-ucayali
   ```
   (or `pip install -r pipeline/requirements.txt` into any Python ≥ 3.11.)
2. **Config**: copy `pipeline/config.example.toml` → `pipeline/config.toml`; edit `[paths]`:
   - `inputs_dir`, `cooley_dir`: where the inputs live (see ACCESS.md for what they are
     and where each comes from);
   - `work_dir`: a big, fast disk **outside synced folders** (OneDrive/Dropbox);
   - `pmtiles_cli`: the go-pmtiles binary (only step 04 needs it).
3. **Credentials** (GEDI steps only): see ACCESS.md. Nothing else needs an account.
4. **Check**: `python scripts/00_check_setup.py` — it verifies all of the above,
   the inputs' CRS/extent, and free disk, and names the first missing piece.

## Running

```
cd pipeline
.\run_all.ps1 -Area pilot                      # smoke test, minutes (small box near Pucallpa)
.\run_all.ps1 -Area full -GediMonth 2020-06    # base layers + one-month GEDI pilot
.\run_all.ps1 -Area full                       # everything incl. the full GEDI period
./run_all.sh pilot                             # the same three on Linux/macOS
./run_all.sh full 2020-06
./run_all.sh full skipgedi                     # base layers only
```

Every step can also run alone: `python scripts/NN_name.py [--area pilot|full] [--force]`.

## Step table

| Step | What | Needs | Expected (full area) | Output |
|---|---|---|---|---|
| 00_check_setup | config/env/inputs/credentials check | — | seconds | console |
| 01_boundary | department outline+mask, provinces, districts | internet (IGN zip, once, ~25 MB) | 1–2 min | data/vectors/*.geojson |
| 02_terrain | DEM → terrain-rgb PMTiles z5–11 | DEM input | 20–40 min, ~8 GB work, tiles ~80–100 MB | data/tiles/terrain.pmtiles |
| 03_s2 | S2 mosaic → WebP PMTiles z5–12 | S2 input | 30–60 min, ~6 GB work, tiles ~150–250 MB | data/tiles/s2_rgb.pmtiles |
| 04_osm_labels | Protomaps bbox extract | go-pmtiles + internet | 2–5 min, ~30–60 MB | data/tiles/osm_basemap.pmtiles |
| 05_cooley_polygons | veg classes GeoJSON (typo fixed) | cooley_dir | seconds | data/vectors/veg_classes.geojson |
| 10_gedi_search | CMR granule inventory | internet | ~1 min | work/gedi/search.json |
| 11_gedi_subset | Harmony spatial+variable subsets, per month | Earthdata login | pilot month ~10–60 min wall (Harmony queue); full period = 33 such jobs | work/gedi/subsets/YYYY-MM/*.h5 |
| 12_gedi_filter | filters → Parquet per granule | step 11 | minutes per month | work/gedi/parquet/ |
| 13_gedi_stats | shots vs Cooley polygons, projections | steps 05+12 | ~1 min | work/gedi/stats.json |
| 91_publish_check | sizes, SITE vs HF split, secret scan | — | seconds | console (exit 1 on blockers) |

## How to resume

- Steps skip outputs that are **fresh** (newer than their inputs); `--force` rebuilds.
- GEDI subsetting is one Harmony job per month; a month with its `job.json` present is
  skipped, so re-running after an interruption continues with the next month.
- `12_gedi_filter` skips granules whose Parquet already exists.
- memwatch (wrapped around every step by run_all) stops a step cleanly if free RAM drops
  below 4 GB (exit 99); re-run and it resumes.
- Outputs are listed in `<work_dir>/manifest.jsonl` (file, size, sha256, step, date):
  copy outputs between machines and check them with `python scripts/common.py verify`.

## Disk & memory

- Work dir: pilot < 2 GB; full base layers ~15 GB; full GEDI subsets ~30–60 GB (measure
  with the one-month pilot first — 13_gedi_stats projects the full-run size).
- `GDAL_CACHEMAX` and the memwatch threshold come from `config.toml [memory]`.
- The app (`site/`, `data/`) only reads pipeline outputs; the pipeline never edits `site/`.
