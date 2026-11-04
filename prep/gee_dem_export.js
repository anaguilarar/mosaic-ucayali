// RECONSTRUCTION - not the original export script. Rebuilt 2026-11-04 from the properties of
// inputs/ucayali/dem_ucayali_basin_extent.tif, to be replaced by the real script when found.
// Evidence used (checked against the file):
//   - grid: EPSG:4326, 20237 x 15535, 0.00026949458523585647 deg (= GEE scale:30 on EPSG:4326),
//     bounds -75.9482, -11.4484 -> -70.4944, -7.2618 - the SAME grid as the S2 mosaic
//   - one float32 band whose description is 'DEM' - the band name of COPERNICUS/DEM/GLO30 in GEE
//   - covers the full bbox rectangle (not masked to the department)
// DEM source assumed Copernicus GLO-30 per Andres' instruction (2026-11-04) - the 'DEM' band name
// supports it; CONFIRM before citing the product in the app (DATA_REPORT open item).

var region = ee.Geometry.Rectangle([-75.9482, -11.4484, -70.4944, -7.2618], null, false);

var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30')
  .filterBounds(region)
  .select('DEM')
  .mosaic()
  .toFloat();

Export.image.toDrive({
  image: dem,
  description: 'dem_ucayali_basin_extent',
  region: region,
  crs: 'EPSG:4326',
  scale: 30,
  maxPixels: 1e10,
  fileFormat: 'GeoTIFF'
});
