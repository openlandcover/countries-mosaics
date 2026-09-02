// Legacy (mosaics-1) vs v2 (sandbox) swipe comparison — one cell, one
// year, common composites and bands on both sides. Derived from
// an earlier internal one-cell comparison script for NH-46-Z-D (kept as
// an evidence tool in the private archive; not part of this release). The band names and storage scales that BOTH products
// share (verified in the 2026-08-13 band sheet: reflectance x1e-4,
// index levels (x+1)x1e4) make one stretch set honest for both sides.
// Drag the bar to swipe; each side has its own source + view dropdown;
// the year selector drives BOTH sides.
// Paste into the Earth Engine Code Editor and Run.

var CELL = 'NC-43-X-D';                 // <- change cell here
var LEGACY = 'projects/mapbiomas-mosaics/assets/LANDSAT/LULC/INDIA/mosaics-1';
var V2COLL = 'projects/mapbiomas-india/assets/shared_assets/' +
             'ioln_mosaics_v2_sandbox';
var SUFFIX = '_c2_only_v3';
var S = 1e-4;

var VISES = {
  NRG: {bands: ['nir_median', 'red_median', 'green_median'],
        min: 0, max: [0.45 / S, 0.15 / S, 0.15 / S], gamma: 1.2},
  SNR: {bands: ['swir1_median', 'nir_median', 'red_median'],
        min: 0, max: [0.30 / S, 0.45 / S, 0.15 / S], gamma: 1.2},
  RGB: {bands: ['red_median', 'green_median', 'blue_median'],
        min: 0, max: [0.15 / S, 0.15 / S, 0.15 / S], gamma: 1.3}
};
var NDVI_VIS = {min: 0, max: 0.9,
                palette: ['ffffff', 'f5e79e', '74c476', '238b45', '00441b']};

var yearSel = ui.Select({
  items: (function () {
    var ys = [];
    for (var y = 1987; y <= 2025; y++) { ys.push(String(y)); }
    return ys;
  })(),
  value: '2022'
});

function sourceImage(srcKey, year) {
  if (srcKey === 'legacy (mosaics-1)') {
    return ee.ImageCollection(LEGACY)
        .filter(ee.Filter.eq('grid_name', CELL))
        .filter(ee.Filter.eq('year', year)).mean();
  }
  return ee.Image(V2COLL + '/' + CELL + '_' + year + SUFFIX);
}

function layerFor(srcKey, view, year) {
  var img = sourceImage(srcKey, year);
  var label = srcKey + ' ' + year + ' · ' + view;
  if (view === 'NDVI') {
    // computed from the SAME two median bands on both sides, so the
    // comparison is of the mosaics, not of stored-index conventions
    var nd = img.select('nir_median').subtract(img.select('red_median'))
        .divide(img.select('nir_median').add(img.select('red_median')));
    return ui.Map.Layer(nd, NDVI_VIS, label);
  }
  return ui.Map.Layer(img, VISES[view], label);
}

var mapL = ui.Map(), mapR = ui.Map();
ui.Map.Linker([mapL, mapR]);
var redraws = [];

function controls(map, srcDefault, label) {
  var srcSel = ui.Select({items: ['legacy (mosaics-1)', 'v2 (sandbox)'],
                          value: srcDefault});
  var viewSel = ui.Select({items: ['NRG', 'SNR', 'RGB', 'NDVI'],
                           value: 'NRG'});
  var redraw = function () {
    map.layers().reset([layerFor(srcSel.getValue(), viewSel.getValue(),
                                 parseInt(yearSel.getValue(), 10))]);
  };
  srcSel.onChange(redraw); viewSel.onChange(redraw);
  map.add(ui.Panel(
    [ui.Label(label, {fontWeight: 'bold', fontSize: '12px'}),
     srcSel, viewSel],
    ui.Panel.Layout.flow('horizontal'),
    {position: label === 'left' ? 'top-left' : 'top-right',
     padding: '4px'}));
  redraws.push(redraw);
  redraw();
}

controls(mapL, 'legacy (mosaics-1)', 'left');
controls(mapR, 'v2 (sandbox)', 'right');
yearSel.onChange(function () {
  redraws.forEach(function (r) { r(); });
});
mapL.add(ui.Panel([ui.Label('year', {fontWeight: 'bold'}), yearSel],
                  ui.Panel.Layout.flow('horizontal'),
                  {position: 'bottom-left', padding: '4px'}));

ui.root.clear();
ui.root.add(ui.SplitPanel({firstPanel: mapL, secondPanel: mapR,
                           orientation: 'horizontal', wipe: true}));
mapL.setCenter(76.8416, 10.1703, 12);
