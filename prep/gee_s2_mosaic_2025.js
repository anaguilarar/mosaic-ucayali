// RECONSTRUCTION - not the original export script. Rebuilt 2026-11-04 from the properties of
// inputs/ucayali/Sentinel2_uyacali_Mosaic_2025.tif, to be replaced by the real script when found.
// Evidence used (checked against the file):
//   - grid: EPSG:4326, 20237 x 15535, 0.00026949458523585647 deg (= GEE scale:30 on EPSG:4326),
//     bounds -75.9482, -11.4484 -> -70.4944, -7.2618 (the Ucayali department bbox)
//   - bands: B4, B3, B2 (band descriptions in the GeoTIFF), uint16
//   - reflectance: darkest sampled percentile ~217 => HARMONIZED L2A (no +1000 offset), x10000 scale
//   - masked to the department polygon (0.000 % empty inside, 100 % empty outside)
//   - 0 % cloud gaps inside the department => a full-year (or longer) cloud-masked median composite
// Unknowns marked TODO: the exact date range, cloud threshold and the department asset used.

var dept = ee.FeatureCollection('TODO/ucayali_department_asset');   // INEI boundary (inputs/ucayali.shp)
var region = ee.Geometry.Rectangle([-75.9482, -11.4484, -70.4944, -7.2618], null, false);

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(region)
  .filterDate('2025-01-01', '2026-01-01')                            // TODO confirm range
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60));              // TODO confirm threshold

function maskS2(img) {                                               // SCL-based cloud/shadow mask
  var scl = img.select('SCL');
  var good = scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  return img.updateMask(good);
}

var mosaic = s2.map(maskS2)
  .median()
  .select(['B4', 'B3', 'B2'])
  .clip(dept)                                                        // masked to the department
  .toUint16();

Export.image.toDrive({
  image: mosaic,
  description: 'Sentinel2_uyacali_Mosaic_2025',
  region: region,
  crs: 'EPSG:4326',
  scale: 30,
  maxPixels: 1e10,
  fileFormat: 'GeoTIFF'
});
