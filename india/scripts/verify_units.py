"""
Units audit: sample every ingested band and assert it sits in its expected
range. Standing rule since 2026-08-09, after the THIRD instance of GEE serving
HLS bands pre-scaled (reflectance 0-1, thermal Celsius, angles degrees) while
the pipeline assumed raw integers -- the angles one silently broke every Era B
cos(i) and produced negative topographic C in every cell and year.

Run whenever a source is added, a collection version changes, or GEE looks at
you funny. Exit code 1 on any FAIL.

    python -m scripts.verify_units
"""

import sys

import ee

from pipeline import config as C, sources, build, terrain

CELL = 'NC-43-Z-D'

# band -> (lo, hi), in the pipeline's WORKING units after sources._prep:
# reflectance x10000, thermal Kelvin x10, angles 0.01-degree, QA integers.
RANGES = {
    **{b: (-3000, 12000) for b in C.CORE_BANDS},
    'tir': (2300, 3400),
    # Azimuths: C2 L1 serves SIGNED azimuths (-180..180, x0.01); HLS serves
    # 0..360. Both are fine -- downstream only takes cosines of differences.
    # Learnt from this audit's own first run (Era A VAA = -3646).
    'SZA': (1000, 8000), 'SAA': (-18000, 36000),
    'VZA': (0, 1500),    'VAA': (-18000, 36000),
    'pixel_qa': (1, 65535), 'radsat': (0, 65535), 'fmask': (0, 255),
}
TERRAIN_RANGES = {'elevation': (-100, 9000), 'slope': (0, 90),
                  'hand': (0, 2000)}


def check(label, image, bands, geom, failures):
    vals = ee.Image(image).select(bands).reduceRegion(
        ee.Reducer.mean(), geom, 90, maxPixels=1e8,
        bestEffort=True, tileScale=4).getInfo()
    for b in bands:
        v = vals.get(b)
        lo, hi = RANGES.get(b) or TERRAIN_RANGES[b]
        if v is None:
            status = 'SKIP (masked)'
        elif lo <= v <= hi:
            status = f'pass  {v:12.1f}'
        else:
            status = f'FAIL  {v:12.1f}  expected [{lo}, {hi}]'
            failures.append((label, b, v))
        print(f'  {label:16s} {b:10s} {status}')


def run():
    ee.Initialize(project='mapbiomas-india')
    region = build.cell_geometry(CELL)
    failures = []

    def probe(img):
        return ee.Image(img).geometry().centroid(1).buffer(2000)

    a, _ = sources.build(region, 2005, None, None, None)
    img = ee.Image(a.first())
    check('era A (2005)', img,
          C.CORE_BANDS + ['tir'] + list(C.ANGLE_BANDS) + ['pixel_qa', 'radsat'],
          probe(img), failures)

    b, _ = sources.build(region, 2020, None, None, None)
    l30 = ee.Image(b.filter(ee.Filter.eq('sensor', 'l30')).first())
    check('era B L30 (2020)', l30,
          C.CORE_BANDS + ['tir'] + list(C.ANGLE_BANDS)
          + ['pixel_qa', 'radsat', 'fmask'],
          probe(l30), failures)

    s30 = ee.Image(b.filter(ee.Filter.eq('sensor', 's30')).first())
    check('era B S30 (2020)', s30,
          C.CORE_BANDS + list(C.ANGLE_BANDS) + ['fmask'],
          probe(s30), failures)

    dem = terrain.dem().rename('elevation')
    slope, _ = terrain.terrain_products()
    hand = terrain.hand().rename('hand') if hasattr(terrain, 'hand') else None
    terr = dem.addBands(slope.rename('slope'))
    tb = ['elevation', 'slope']
    if hand is not None:
        terr = terr.addBands(hand)
        tb.append('hand')
    check('terrain', terr, tb, region.centroid(1).buffer(2000), failures)

    if failures:
        print(f'\n{len(failures)} FAILURE(S):')
        for label, band, v in failures:
            print(f'  {label} / {band} = {v}')
        return 1
    print('\nall units in range')
    return 0


if __name__ == '__main__':
    sys.exit(run())
