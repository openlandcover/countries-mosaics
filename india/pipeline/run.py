"""
Runner: build or queue mosaics for cells and years.

Usage
    python -m pipeline.run --smoke          # graph + tiny-region compute check
    python -m pipeline.run --list           # what would be exported
    python -m pipeline.run --export         # queue the export tasks
    python -m pipeline.run --export --cell NH-43-X-C --year 2023
    python -m pipeline.run --thin-years CELL --export
                                                  # queue the thin pre-2000 annuals

(The HLS pilot drivers were retired with the Collection-2-only ruling
and removed 2026-09-01; see the working notes on retired code, not part
of this release.)
"""

import argparse
import ee

from . import config as C
from . import build, radiometry, sma


def preflight():
    """Loud about what has not been verified. None of these block a run."""
    print('preflight')
    issues = radiometry.warn_if_unverified() + sma.warn_if_unverified()
    if not issues:
        print('  all coefficient sets marked verified')
    return issues


def runs(cell=None, year=None):
    for y, variants in C.PILOT_RUNS:
        if year and y != year:
            continue
        for c in C.PILOT_CELLS:
            if cell and c != cell:
                continue
            for v in variants:
                yield c, y, v


def smoke(cell='NH-43-X-C', year=2023, variant='full'):
    """
    Build the graph and force a tiny computation, so failures surface here rather
    than three hours into an export.
    """
    print('\nsmoke test: {} {} [{}]'.format(cell, year, variant))
    mosaic, meta = build.build_mosaic(cell, year, variant)

    names = mosaic.bandNames().getInfo()
    print('  bands: {}'.format(len(names)))
    print('  sample: {}'.format(names[:8]))

    pt = build.cell_geometry(cell).centroid(1000).buffer(150)
    probe = [b for b in ('ndvi_median', 'mndwi_median', 'usable_count',
                         'elevation') if b in names]
    vals = mosaic.select(probe).reduceRegion(
        ee.Reducer.mean(), pt, 30, maxPixels=1e8).getInfo()
    print('  values at cell centre:')
    for k in sorted(vals):
        v = vals[k]
        print('    {:24s} {}'.format(k, round(v, 2) if isinstance(v, float) else v))
    return mosaic


def run_thin_years(cell, collection_path, export=False, annual_from=1986,
                   annual_to=1998, lite=False):
    """
    Queue the thin pre-2000 ANNUALS for one cell (renamed from the retired
    run_epochs, 2026-09-01 -- multi-year epoch composites left the product
    with the 2026-08-30 annuals-only ruling).

    Before 2000 the archive is thin over much of India; some years will be
    empty, which is the honest outcome (build.export's zero-scene skip
    logs each as an archive gap rather than failing).
    """
    years = list(range(annual_from, annual_to + 1))
    print('\nthin years for {}: {} annual mosaics -> {}'.format(
        cell, len(years), collection_path))
    for y in years:
        if export:
            build.export(cell, y, collection_path=collection_path,
                         verbose=True, lite=lite)
        else:
            print('  {:12s} {}'.format(cell, y))
    return years


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--export', action='store_true')
    ap.add_argument('--thin-years', metavar='CELL',
                    help='queue the thin pre-2000 annuals for one cell')
    ap.add_argument('--cell')
    ap.add_argument('--year', type=int)
    args = ap.parse_args()

    ee.Initialize(project=C.EE_PROJECT)
    preflight()

    if args.smoke:
        smoke(args.cell or 'NH-43-X-C', args.year or 2023)
        return

    if args.thin_years:
        run_thin_years(args.thin_years, C.OUTPUT_COLLECTION,
                       export=args.export)
        return

    plan = list(runs(args.cell, args.year))
    print('\n{} run(s):'.format(len(plan)))
    for c, y, v in plan:
        print('  {:12s} {}  {}'.format(c, y, v))

    if args.export:
        print('\nqueuing exports to {}'.format(C.PILOT_COLLECTION))
        for c, y, v in plan:
            build.export(c, y, v)
    elif not args.list:
        print('\n(nothing queued -- pass --export to run)')


if __name__ == '__main__':
    main()
