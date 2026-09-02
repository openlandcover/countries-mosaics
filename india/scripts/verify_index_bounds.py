"""
Index-bound checker for a FINISHED v2 mosaic asset.

Confirms every index band in an exported image sits inside its declared
stored range -- the cheap health check a runner points at any export.

    python -m scripts.verify_index_bounds                       # default asset
    python -m scripts.verify_index_bounds --asset <asset id>
    python -m scripts.verify_index_bounds --cell NC-43-X-D --year 2020

REWRITTEN 2026-09-01 for the v2 band contract (117 bands): the old
version still probed bands and statistics that left the product with
the 2026-08-13 rulings (hallcover, ebbi, p5/p95/stdDev, the '_range'
suffix) and crashed. Statistics now: median / median_dry / median_wet
/ swing / mad. ndfi is deliberately EXCLUDED here -- its reserved
codes (-10/-20/-999) are legal values outside the plain range and are
checked by scripts/validate_mosaic_asset.py instead.
"""

import argparse

import ee

from pipeline import config as C
from pipeline import indices

# Stored-unit bounds per index family.
# Ratio indices (INDEX_DEFS): level = lo*1e4 .. hi*1e4 (unshifted since
# AMENDMENT 1, 2026-09-01); mad = 0..width; swing = -width..width (signed).
# Tasselled cap: signed x1e4, never shifted; wide overflow guards (the
# checker's job is catching blow-ups, not precision).
TC_GUARDS = {'tcb': (-1000, 20000), 'tcg': (-10000, 10000),
             'tcw': (-10000, 10000)}
# bci/ibi ship on the 0-200 convention, median + mad only.
CODE200 = {'bci': (0, 200), 'ibi': (0, 200)}

LEVEL_STATS = ('median', 'median_dry', 'median_wet')


def expected_bounds():
    """band name -> (stored lo, stored hi), for every index band that may
    appear in a v2 image. Bands absent from the asset are simply skipped."""
    out = {}
    for name, (_expr, shift, (lo, hi)) in indices.INDEX_DEFS.items():
        if name == 'ndfi':      # codes checked elsewhere
            continue
        off = 1.0 if shift else 0.0
        s_lo, s_hi = (lo + off) * 1e4, (hi + off) * 1e4
        width = (hi - lo) * 1e4
        for s in LEVEL_STATS:
            out['{}_{}'.format(name, s)] = (s_lo, s_hi)
        out[name + '_mad'] = (0, width)
        out[name + '_swing'] = (-width, width)
    for name, (lo, hi) in TC_GUARDS.items():
        for s in LEVEL_STATS:
            out['{}_{}'.format(name, s)] = (lo, hi)
        out[name + '_mad'] = (0, hi - lo)
        out[name + '_swing'] = (lo - hi, hi - lo)
    for name, (lo, hi) in CODE200.items():
        out[name + '_median'] = (lo, hi)
        out[name + '_mad'] = (0, hi - lo)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', help='full asset id to check')
    ap.add_argument('--cell', default='NC-43-X-D')
    ap.add_argument('--year', type=int, default=2020)
    ap.add_argument('--scale', type=int, default=120)
    args = ap.parse_args()

    ee.Initialize(project=C.EE_PROJECT)

    # Default id follows the destination's naming rule (owner ruling
    # 2026-09-01): production assets are CELL_YEAR only; sandbox assets
    # keep the variant/version tail.
    if args.asset:
        asset = args.asset
    elif C.OUTPUT_COLLECTION == C.PRODUCTION_COLLECTION:
        asset = '{}/{}_{}'.format(C.OUTPUT_COLLECTION, args.cell, args.year)
    else:
        asset = '{}/{}_{}_c2_only_v{}'.format(
            C.OUTPUT_COLLECTION, args.cell, args.year, C.VERSION)
    img = ee.Image(asset)
    present = img.bandNames().getInfo()
    bounds = {b: v for b, v in expected_bounds().items() if b in present}
    print('checking {} index bands of {}'.format(len(bounds), asset))

    r = img.select(sorted(bounds)).reduceRegion(
        ee.Reducer.minMax(), geometry=img.geometry(), scale=args.scale,
        maxPixels=1e10, bestEffort=True, tileScale=4).getInfo()

    failed = []
    for b in sorted(bounds):
        lo, hi = bounds[b]
        a_lo, a_hi = r.get(b + '_min'), r.get(b + '_max')
        if a_lo is None:
            print('  {:22s} (fully masked)'.format(b))
            continue
        ok = a_lo >= lo - 1 and a_hi <= hi + 1
        print('  {:22s} [{:9.1f}, {:9.1f}]  legal [{:6.0f}, {:6.0f}]  {}'
              .format(b, a_lo, a_hi, lo, hi, 'ok' if ok else 'OUT OF RANGE'))
        if not ok:
            failed.append(b)

    if failed:
        print('\nFAIL -- out of declared range: ' + ', '.join(failed))
        return 1
    print('\nPASS -- all present index bands inside their declared ranges')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
