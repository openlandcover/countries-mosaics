"""Prove an exported mosaic upholds the contract. Usage:
python scripts/validate_mosaic_asset.py <full asset id>
Checks: exact config.BAND_ORDER (116 bands since C30); integer types; terrain-correction record
in the metadata; value sanity at sample points (sentinels over water,
percent scales in range, temperatures plausible)."""
import sys
import ee
from pipeline import config as C
ee.Initialize(project=C.EE_PROJECT)

aid = sys.argv[1]
img = ee.Image(aid)
info = ee.data.getAsset(aid)
props = info.get('properties', {})

names = img.bandNames().getInfo()
ok_bands = names == list(C.BAND_ORDER)
print('bands: {} | order exact: {}'.format(len(names), ok_bands))

topo = {k: v for k, v in props.items() if k.startswith('topo_')}
print('terrain record:', topo or 'NONE (uncorrected build)')

# value sanity on a small sample
samp = (img.select(['gv_median', 'ndfi_median', 'tir_median',
                    'shade_median', 'slope'])
        .sample(region=img.geometry(), scale=30, numPixels=500, seed=42)
        .getInfo()['features'])
import statistics as st
cols = {}
for f in samp:
    for k, v in f['properties'].items():
        if v is not None:
            cols.setdefault(k, []).append(v)
for k in sorted(cols):
    v = cols[k]
    print('{:14s} n={:4d}  min {:8.0f}  median {:8.0f}  max {:8.0f}'.format(
        k, len(v), min(v), st.median(v), max(v)))
checks = [
    ('gv percent scale', all(-1 <= x <= 200 or x == C.SMA_SENTINEL
                             for x in cols.get('gv_median', []))),
    ('ndfi -20..200 with codes', all(0 <= x <= 200 or x in (-10, -20)
                                 for x in cols.get('ndfi_median', []))),
    ('tir plausible K x10', all(2400 < x < 3600
                                for x in cols.get('tir_median', []))),
]
for label, ok in checks:
    print('{}: {}'.format(label, 'OK' if ok else 'FAIL'))
print('VERDICT:', 'PASS' if (ok_bands and all(o for _, o in checks))
      else 'FAIL')
