// HELPER EXPORT SCRIPT (to run in the Earth Engine code editor) - written 2026-11-04 because the
// published MapBiomas Peru direct-download links on storage.googleapis.com answer 403 to everyone
// (server-side permissions). This exports exactly the files the pipeline expects, clipped to the
// Ucayali bbox, from MapBiomas' own public GEE assets (CC BY 4.0, cite MapBiomas Peru).
//
// After the Drive exports finish, place the files here and re-run the steps:
//   peru_coverage-col4_<YEAR>.tif  -> <work_dir>\downloads\mapbiomas\        (step 21)
//   burned_area_<YEAR>.tif         -> <work_dir>\downloads\mapbiomas_fire\  (step 24)

var region = ee.Geometry.Rectangle([-75.95, -11.45, -70.49, -7.26], null, false);

// ---- land cover: Collection 4 coverage (one band per year: classification_YYYY)
var lulc = ee.Image('projects/mapbiomas-public/assets/peru/collection4/mapbiomas_peru_collection4_coverage_v1');
[2000, 2005, 2010, 2015, 2020, 2024].forEach(function (y) {
  Export.image.toDrive({
    image: lulc.select('classification_' + y).toUint8().clip(region),
    description: 'peru_coverage-col4_' + y,
    region: region, crs: 'EPSG:4326', scale: 30, maxPixels: 1e10, fileFormat: 'GeoTIFF'
  });
});

// ---- burned area: Fire Collection 2 annual burned (value 1 = burned); Collection 1's direct
// links are the broken ones. Using Col2 keeps the same 'burned that year' semantics.
var burned = ee.Image('projects/mapbiomas-public/assets/peru/fire/collection2/mapbiomas_peru_fire_collection2_annual_burned_v1');
for (var y = 2013; y <= 2024; y++) {
  Export.image.toDrive({
    image: burned.select('burned_area_' + y).toUint8().clip(region),
    description: 'burned_area_' + y,
    region: region, crs: 'EPSG:4326', scale: 30, maxPixels: 1e10, fileFormat: 'GeoTIFF'
  });
}
// Note: if the band names differ, print(burned.bandNames()) and adjust; Collection 2 also covers
// 1990-2025 if we later want the longer series.
