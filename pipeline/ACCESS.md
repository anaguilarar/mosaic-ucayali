# Accounts, credentials and input provenance

**No secret value is ever written to a file, log or script in this repo.** The publish
check (91) scans for secret-like text before anything is pushed.

## Credentials

| Steps | Service | How the pipeline reads it |
|---|---|---|
| 10–13 (GEDI) | NASA Earthdata (urs.earthdata.nasa.gov) — free account, earthdata.nasa.gov/users/new | either the environment variables `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`, or a `~/.netrc` (Windows: also `~/_netrc`) entry `machine urs.earthdata.nasa.gov login <user> password <pass>`. earthaccess and harmony-py pick these up themselves; 00_check_setup reports presence only, never values. |
| all others | none | — |

Note for Windows/conda users: `$env:EARTHDATA_USERNAME = '...'` set in a PowerShell session
does **not** persist. Use the `.netrc`/`_netrc` file, or `conda env config vars set` on the
environment, or set user-level environment variables.

## Inputs (config `[paths]` + `[inputs]`)

| File | What | Where it comes from |
|---|---|---|
| `dem_ucayali_basin_extent.tif` | 30 m DEM, department extent, EPSG:4326, 20237×15535 | Earth Engine export — **script to be filed in `prep/`; provenance to confirm** |
| `Sentinel2_uyacali_Mosaic_2025.tif` | Sentinel-2 L2A RGB (B4,B3,B2) mosaic 2025, same grid | Earth Engine export — **script to be filed in `prep/`** |
| `ucayali.shp` | Ucayali department boundary (FUENTE=INEI) | Peruvian government boundaries; same referential boundaries published by IGN on datosabiertos.gob.pe under ODC-By |
| `DEPARTAMENTOS.shp` | all 25 departments | as above |
| `cooley_dir/_VegTypol_Ucayali_v4__Feb2022.geojson` | 324 vegetation-class polygons | CaltechDATA doi:10.22002/D1.2318 (**CC0**), v4.0 |
| downloaded by step 01 | `DISTRITOS_LIMITES.zip` (districts) | IGN dataset "Limites Departamentales", datosabiertos.gob.pe (ODC-By) — cached in `<work_dir>/downloads/` |
| downloaded by step 04 | Protomaps daily OSM basemap extract | build.protomaps.com (OSM data, ODbL) |
| downloaded by step 11 | GEDI02_A v002 Harmony subsets | NASA LP DAAC via Harmony (needs the Earthdata login) |

## Tools

- **go-pmtiles** (step 04 only): single binary from
  https://github.com/protomaps/go-pmtiles/releases — put its path in config
  `[paths].pmtiles_cli`.
