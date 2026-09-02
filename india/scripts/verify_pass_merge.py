"""
Acceptance test for single-pass mosaicking (task #7, 2026-08-09).

INVARIANT: after merge_passes, the plain per-pixel image count equals the
pass_key-deduplicated usable_count computed before the merge. If they agree,
every physical observation enters the reducers exactly once.

PRE-REGISTERED PREDICTIONS:
  P-p1  count difference (merged plain count - usable_count) is ~0 everywhere:
        |mean| < 0.05, max <= 1 at 480 m aggregation.
  P-p2  collection shrinks: images > passes (row overlaps collapse), by
        roughly the overlap share of the cell.

    python -m scripts.verify_pass_merge
"""

import ee

from pipeline import sources, masking, build

CELL = 'NC-43-Z-D'
YEARS = [2005, 2020]


def run():
    ee.Initialize(project='mapbiomas-india')
    region = build.cell_geometry(CELL)

    for year in YEARS:
        coll, era = sources.build(region, year, None, None, None)
        coll = masking.apply_mask(coll, era)

        usable = sources.observation_counts(coll, era, year) \
            .select('usable_count')
        merged = sources.merge_passes(coll)
        plain = merged.select('nir').count().rename('n')

        diff = plain.subtract(usable).rename('d')
        r = (diff.addBands(diff.abs().rename('ad'))
             .reduceRegion(
                 ee.Reducer.mean().combine(ee.Reducer.max(),
                                           sharedInputs=True),
                 region, 480, maxPixels=1e9, bestEffort=True,
                 tileScale=16).getInfo())
        n_img = coll.size().getInfo()
        n_pass = merged.size().getInfo()
        print(f'{year} (era {era}): images {n_img} -> passes {n_pass} | '
              f'count diff mean {r.get("d_mean", float("nan")):+.3f}  '
              f'|diff| max {r.get("ad_max", float("nan")):.1f}')


if __name__ == '__main__':
    raise SystemExit(run())
