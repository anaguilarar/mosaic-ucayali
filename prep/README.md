# prep/ — Earth Engine export scripts (provenance record)

This folder holds the Google Earth Engine scripts that produced the raster inputs, so the
inputs can be regenerated and their provenance is on record (DATA_REPORT §2).

Current files — both are **RECONSTRUCTIONS** (see each header), rebuilt from the exported
files' properties because the originals were not found. Replace them with the real scripts
when located; the reconstructions have not been run.

- `gee_s2_mosaic_2025.js` — matches `Sentinel2_uyacali_Mosaic_2025.tif` (harmonized L2A,
  B4/B3/B2, scale 30 on EPSG:4326, masked to the department; date range and cloud threshold
  are TODO guesses).
- `gee_dem_export.js` — matches `dem_ucayali_basin_extent.tif` (float32, band 'DEM', full
  bbox). **DEM assumed Copernicus GLO-30** (band name agrees); registry and DATA_REPORT keep
  a "to confirm" caveat until confirmed.

The processing pipeline itself lives in `pipeline/` (see `pipeline/RUN.md`).
