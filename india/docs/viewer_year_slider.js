// v2 mosaic time-series slider — one cell, every available year,
// drag the year slider to cycle. Whatever visualisation you set
// (composite choice, min/max/gamma) is re-applied to every year you
// slide to. Missing years (zero-scene gaps: 1986, 1988 here) are
// announced rather than erroring.
// Paste into the Earth Engine Code Editor and Run.

var CELL = 'NC-43-X-D';                 // <- change cell here
var COLL = 'projects/mapbiomas-india/assets/shared_assets/' +
           'ioln_mosaics_v2_sandbox';
var SUFFIX = '_c2_only_v3';             // sandbox asset-name suffix
var S = 1e-4;                           // stored reflectance scale

// shared stretches; edit live via the boxes below
var VISES = {
  NRG:  {bands: ['nir_median', 'red_median', 'green_median'],
         max: [0.45 / S, 0.15 / S, 0.15 / S]},
  SNR:  {bands: ['swir1_median', 'nir_median', 'red_median'],
         max: [0.30 / S, 0.45 / S, 0.15 / S]},
  RGB:  {bands: ['red_median', 'green_median', 'blue_median'],
         max: [0.15 / S, 0.15 / S, 0.15 / S]},
  NDVI: {} // computed band, palette below
};
var NDVI_PALETTE = ['ffffff', 'f5e79e', '74c476', '238b45', '00441b'];

// ---------------------------------------------------------------------------
var map = ui.Map();
ui.root.clear(); ui.root.add(map);

var years = [];                          // filled by the listing below
var yearLabel = ui.Label('loading years...', {fontWeight: 'bold'});
var viewSel = ui.Select({items: Object.keys(VISES), value: 'NRG',
                         onChange: redraw});
var gammaBox = ui.Textbox({value: '1.2', style: {width: '48px'},
                           onChange: redraw});
var scaleBox = ui.Textbox({value: '1.0', style: {width: '48px'},
                           onChange: redraw});   // multiplies the max stretch
var slider = ui.Slider({min: 1987, max: 2025, step: 1, value: 2022,
                        style: {stretch: 'horizontal'}});
slider.onChange(function (y) { redraw(); });

function currentYear() {
  // snap to the nearest AVAILABLE year at or below the slider
  var y = slider.getValue();
  if (years.indexOf(y) !== -1) { return y; }
  var best = null;
  years.forEach(function (yy) {
    if (best === null || Math.abs(yy - y) < Math.abs(best - y)) best = yy;
  });
  return best;
}

function redraw() {
  if (!years.length) { return; }
  var y = currentYear();
  var wanted = slider.getValue();
  yearLabel.setValue(wanted === y ? 'year: ' + y
      : 'year ' + wanted + ' has no mosaic (archive gap) -> showing ' + y);
  var img = ee.Image(COLL + '/' + CELL + '_' + y + SUFFIX);
  var view = viewSel.getValue();
  var g = parseFloat(gammaBox.getValue()) || 1.2;
  var k = parseFloat(scaleBox.getValue()) || 1.0;
  var layer;
  if (view === 'NDVI') {
    var nd = img.select('nir_median').subtract(img.select('red_median'))
        .divide(img.select('nir_median').add(img.select('red_median')));
    layer = ui.Map.Layer(nd, {min: 0, max: 0.9, palette: NDVI_PALETTE},
                         CELL + ' ' + y + ' NDVI');
  } else {
    var v = VISES[view];
    layer = ui.Map.Layer(img, {
      bands: v.bands, min: 0,
      max: v.max.map(function (m) { return m * k; }), gamma: g
    }, CELL + ' ' + y + ' ' + view);
  }
  map.layers().reset([layer]);
}

map.add(ui.Panel([
  ui.Label(CELL + ' — v2 time series', {fontWeight: 'bold'}),
  yearLabel, slider,
  ui.Panel([ui.Label('view'), viewSel,
            ui.Label('gamma'), gammaBox,
            ui.Label('stretch x'), scaleBox],
           ui.Panel.Layout.flow('horizontal'))
], null, {position: 'top-left', padding: '6px', width: '340px'}));

// discover the available years once, then draw
ee.data.listAssets(COLL, {}, function (res) {
  var re = new RegExp('^' + CELL + '_(\\d{4})' + SUFFIX + '$');
  (res.assets || []).forEach(function (a) {
    var m = a.id.split('/').pop().match(re);
    if (m) { years.push(parseInt(m[1], 10)); }
  });
  years.sort();
  yearLabel.setValue('years available: ' + years.length +
                     ' (' + years[0] + '-' + years[years.length - 1] + ')');
  redraw();
});

map.setCenter(76.8416, 10.1703, 12);
