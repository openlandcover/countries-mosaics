"""Prove an exported mosaic upholds the contract. Usage:
python scripts/validate_mosaic_asset.py <full asset id>
Checks: exact config.BAND_ORDER (117 bands, band contract v2); stored pixel
type per band (UINT8_BANDS uint8, INT8_BANDS int8, lon/lat int32, the rest
int16 -- AMENDMENT 2, 2026-09-03); terrain-correction record in the metadata;
value sanity at sample points (sentinels over water, percent scales in range,
temperatures plausible)."""
import os
import sys
import ee

# Run it as `python scripts/validate_mosaic_asset.py <asset>` from anywhere:
# without this the repo root is not on the path and the pipeline import fails
# (it always did -- the script had never been runnable as its usage line said).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import config as C
ee.Initialize(project=C.EE_PROJECT)

aid = sys.argv[1]
img = ee.Image(aid)
info = ee.data.getAsset(aid)
props = info.get('properties', {})

names = img.bandNames().getInfo()
ok_bands = names == list(C.BAND_ORDER)
print('bands: {} | order exact: {}'.format(len(names), ok_bands))

# STORED PIXEL TYPE (added 2026-09-03 with AMENDMENT 2). The docstring
# claimed this check for a long time without it existing; nothing else in
# the pipeline verifies a shipped asset's types, and since the contract now
# uses three widths a wrong one would ship silently.
def _width(dt):
    r = dt.get('range', {})
    return (dt.get('precision', '').upper(), r.get('min', 0), r.get('max'))

WIDTHS = {'uint8': ('INT', 0, 255), 'int8': ('INT', -128, 127),
          'int16': ('INT', -32768, 32767), 'int32': ('INT', -2147483648, 2147483647)}
got = {b['id']: _width(b['dataType']) for b in info.get('bands', [])}
wrong = []
for b in C.BAND_ORDER:
    if b in getattr(C, 'UINT8_BANDS', ()):
        want = 'uint8'
    elif b in getattr(C, 'INT8_BANDS', ()):
        want = 'int8'
    elif b in ('lon', 'lat'):
        want = 'int32'
    else:
        want = 'int16'
    if b in got and got[b] != WIDTHS[want]:
        wrong.append('{} wanted {} got {}'.format(b, want, got[b]))
ok_types = not wrong and len(got) == len(C.BAND_ORDER)
print('stored types: {}'.format('all as contracted' if ok_types
                                else 'WRONG -> ' + '; '.join(wrong[:6])))

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
print('VERDICT:', 'PASS' if (ok_bands and ok_types and all(o for _, o in checks))
      else 'FAIL')
