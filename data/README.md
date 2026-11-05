---
license: other
pretty_name: MOSAIC Ucayali Explorer data
---

# MOSAIC Ucayali Explorer data

The data served to the **MOSAIC Ucayali Explorer**, a static web map and story of the forest–agriculture
interface of Ucayali, Peru: GEDI spaceborne-lidar canopy height, co-produced vegetation classes, canopy
height, forest loss, land cover, fire, protected areas and climate (1981–2026), built for the MOSAIC
project around Cooley et al. (2024).

- App: https://anaguilarar.github.io/mosaic-ucayali/
- Code and full data report: https://github.com/anaguilarar/mosaic-ucayali (`DATA_REPORT.md`)

The files are prepared for the app (map tiles, click-query rasters, small JSON series), not as analysis-ready
datasets. Every layer keeps the licence of its source, listed below. **There is no single licence for this
repository** (`license: other`); reuse each file under its source's terms and cite the source.

## Folders

This dataset holds the large files. The small, often-requested ones are served from the GitHub repository's
`data/` folder and are listed here so the whole layer set is documented in one place.

| Folder | Content | Hosted on |
|---|---|---|
| `tiles/` | Map tiles (PMTiles): GEDI footprints and 1 km RH95 grid, ETH canopy height, GEOBOSQUES forest and loss, MapBiomas land cover 2000–2024 and burned area 2013–2024, VIIRS fire density 2012–2025 | this dataset |
| `tiles/terrain.pmtiles`, `tiles/s2_rgb.pmtiles` | Terrain and Sentinel-2 imagery | GitHub |
| `query/` | GeoTIFFs read on click: ETH canopy height (10 m), GEDI 1 km grid (mean RH95, shot count), MapBiomas land-cover stack (30 m, one band per year) | this dataset |
| `fire/` | VIIRS active-fire points per year (GeoJSON) | this dataset |
| `climate/` | Precipitation, temperature and SPI-3 rasters; `climate/app/` holds the cell series (`*_cells.bin`, read with HTTP range requests) and their metadata | GitHub |
| `series/` | Department time series and summaries (JSON): rainfall, temperature, SPI-3, fire and burned area, forest classes, land-cover areas, the paper's Table 2–4 values | GitHub |
| `vectors/` | Department outline and mask, provinces, districts, labels, vegetation-class polygons, protected areas (GeoJSON) | GitHub |
| `meta/` | Layer registry (`layers.json`), story chapters and study cards (`story_chapters.json`, `studies.json`) | GitHub |
| `fonts/` | Map label glyphs (Noto Sans, SIL Open Font License) | GitHub |

## Layers: source, licence, citation

| Layer | Files | Source | Licence | Citation |
|---|---|---|---|---|
| GEDI canopy height | `tiles/gedi_footprints.pmtiles`, `tiles/gedi_grid.pmtiles`, `query/gedi_rh95_1km.tif` | NASA GEDI L2A (GEDI02_A v002), full-power beams, 2019-04-20 → 2025-07-09; Cooley et al. (2024) filters plus GEDI's quality flags, inside the department; RH95 per footprint and 1 km means (this app's analysis) | NASA Earth science data: free and open; cite the product DOI | Dubayah, R., et al. (2021). GEDI L2A Elevation and Height Metrics Data Global Footprint Level V002. NASA EOSDIS LP DAAC, doi:10.5067/GEDI/GEDI02_A.002; Dubayah et al. (2020), *Science of Remote Sensing* 1:100002 |
| Vegetation classes | `vectors/veg_classes.geojson` | Cooley et al., Vegetation typology classification and data set in Ucayali, Peru, v4.0 (324 polygons, co-produced with local experts) | **CC0** | Cooley, S., Pinto, N., Aguilar-Amuchastegui, N., Vela Alvarado, J. & Fahlen, J. (2021). CaltechDATA, doi:10.22002/D1.2318 |
| Canopy height (model) | `tiles/canopy.pmtiles`, `query/canopy_height_10m.tif` | ETH Global Canopy Height 2020, 10 m, clipped to the department | **CC BY 4.0** | Lang, N., Jetz, W., Schindler, K. & Wegner, J.D. (2023). *Nature Ecology & Evolution* 7:1778–1789, doi:10.1038/s41559-023-02206-6; data doi:10.3929/ethz-b-000609802 |
| Forest and forest loss | `tiles/forest_loss.pmtiles`, `series/forest_classes.json` | GEOBOSQUES (MINAM PNCBMCC + MIDAGRI SERFOR), Mapa del Bosque Húmedo Amazónico Peruano 2000–2024, 30 m; loss 2001–2024 includes natural losses | No licence stated in the product metadata (field LICENCIA: "-"); citation required as below | MINAM (PNCBMCC) y MIDAGRI (SERFOR). "Mapa del Bosque Húmedo Amazónico Peruano, 2000–2024". Acceso a través de GEOBOSQUES (geobosques.minam.gob.pe) |
| Land cover | `tiles/lulc_*.pmtiles`, `query/lulc_stack_30m.tif`, `series/lulc_areas.json` | MapBiomas Perú Collection 4, 30 m, 2000/2005/2010/2015/2020/2024 | **CC BY 4.0** ("de uso público, abierto y gratuito, sujetos a citación") | MapBiomas Perú, Colección 4 de mapas anuales de cobertura y uso del suelo (peru.mapbiomas.org) |
| Burned area | `tiles/burned_*.pmtiles`, `series/fire.json` | MapBiomas Perú Fuego Collection 2, annual burned area, 30 m, 2013–2024; zoomed-out tiles show the share of each pixel that burned | **CC BY 4.0** | MapBiomas Perú, Colección 2 de fuego (peru.mapbiomas.org) |
| Active fires | `tiles/fire_density_*.pmtiles`, `fire/points_*.geojson`, `series/fire.json` | NASA FIRMS VIIRS 375 m active fires (S-NPP), confidence nominal/high, 2012–2025 | NASA FIRMS: freely available; cite FIRMS | NASA FIRMS, VIIRS 375 m active fire product (VNP14IMGT), firms.modaps.eosdis.nasa.gov; Schroeder et al. (2014), *Remote Sensing of Environment* 143:85–96 |
| Protected areas | `vectors/protected_areas.geojson` | SERNANP: Áreas Naturales Protegidas (definitive) and Áreas de Conservación Regional, clipped to Ucayali and simplified (~90 m) | SERNANP terms: the information is public domain and may not be sold for profit by third parties; derived maps are authorised with SERNANP cited as the source. This is a clipped, simplified derivative, not the original service data | SERNANP, geoservicios.sernanp.gob.pe |
| Precipitation | `climate/precip_*`, `climate/app/precip_*`, `series/precip_dept.json` | CHIRPS v3.0 daily, 0.05° | **CC BY 4.0** | Funk et al. (2015), *Scientific Data* 2:150066; CHIRPS v3.0, UCSB Climate Hazards Center |
| Temperature | `climate/tm*`, `climate/app/t*`, `series/temp_dept.json` | CHIRTS-ERA5 daily Tmax/Tmin, 0.05° | **CC BY 4.0** | Funk et al. (2019), *Journal of Climate* 32:5639–5658; CHIRTS-ERA5, UCSB CHC |
| Drought (SPI-3) | `climate/app/spi3*`, `series/spi3_dept.json` | Computed from CHIRPS v3.0 monthly totals, calibration 1991–2020 | Derived from CHIRPS v3.0 (CC BY 4.0) | McKee, Doesken & Kleist (1993); WMO (2012), SPI User Guide, WMO-No. 1090 |
| Satellite imagery | `tiles/s2_rgb.pmtiles` | Sentinel-2 L2A RGB mosaic 2025, 30 m | Copernicus Sentinel data: free use with attribution | Contains modified Copernicus Sentinel-2 data [2025] |
| Terrain | `tiles/terrain.pmtiles` | 30 m DEM exported from Earth Engine; the source product is still being confirmed (see the data report) | As the source DEM (to be confirmed) | See `DATA_REPORT.md` |
| Admin boundaries | `vectors/department*.geojson`, `vectors/provinces.geojson`, `vectors/districts.geojson`, `vectors/admin_labels.geojson` | IGN (Instituto Geográfico Nacional) departmental and district limits, datosabiertos.gob.pe; provinces dissolved from districts | **ODC-By** (Open Data Commons Attribution) | Instituto Geográfico Nacional, Límites Departamentales / Distritales, Plataforma Nacional de Datos Abiertos |
| Story and study cards | `meta/story_chapters.json`, `meta/studies.json`, `series/cooley_tables.json` | Text written for the app; numbers quoted from the cited studies (page recorded) or labelled as this app's analysis | — | Cooley, S.S., et al. (2024). *Ecology and Evolution* 14:e70116, doi:10.1002/ece3.70116 (CC BY); other studies in the data report |

**Not included.** No HydroSHEDS-derived material is used or distributed. RAISG Indigenous territories are
**not** in this dataset or in the app: RAISG's licence requires unaltered data and non-profit use, and the
layer includes territories of peoples in voluntary isolation; the app links to RAISG's own map instead. The
farm-level cacao plots mapped with women farmers in Cooley et al. (2024) are not public and are not here.

**Caveats.** GEDI heights and 1 km means are this app's processing, not the paper's values; the paper's
numbers are quoted from its tables in the app's story. Forest loss includes natural losses. Burned area is
Landsat-based and misses small or low-severity burns. Details and known artefacts are in the data report
(`DATA_REPORT.md`).
