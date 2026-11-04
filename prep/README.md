# prep/ — Earth Engine export scripts (provenance record)

This folder holds the Google Earth Engine scripts that produced the raster inputs, so the
inputs can be regenerated and their provenance is on record (DATA_REPORT §2).

Expected files (to be provided):

- `gee_s2_mosaic_2025.js` — the export that made `Sentinel2_uyacali_Mosaic_2025.tif`
  (harmonized L2A collection expected; B4/B3/B2 at 30 m, EPSG:4326).
- `gee_dem_export.js` — the export that made `dem_ucayali_basin_extent.tif`
  (**DEM source still to be confirmed** — the registry and DATA_REPORT carry a
  "provenance to confirm" caveat until this script is filed).

The processing pipeline itself lives in `pipeline/` (see `pipeline/RUN.md`).
