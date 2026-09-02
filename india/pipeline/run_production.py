"""
The national production run: every grid cell, every year, into the published
collection.

This is the counterpart to run.py. That driver walks a handful of
lab cells and variants; this one walks the whole product:

    283 grid cells x config.PRODUCTION_FIRST_YEAR..PRODUCTION_LAST_YEAR

and queues one export task per cell-year into config.PRODUCTION_COLLECTION.
Production assets are named CELL_YEAR only (owner ruling 2026-09-01);
build.export refuses the sandbox naming machinery (label, non-default
variant, lite) when the destination is the production collection, so there is
no way to write a lab build under a product name.

Two safety rules, both deliberate:

1. `run()` does nothing unless it is passed the exact confirmation phrase.
   A run of this size costs real compute and writes into a published
   collection; it should never start by accident, from a stray Shift+Enter in
   a notebook or a mistyped flag.
2. Every cell-year is queued through build.export, which skips assets that
   already exist and assets that are mid-export. So an interrupted run is
   resumed by simply starting it again: it picks up where it stopped.

Command line:

    python -m pipeline.run_production --plan
    python -m pipeline.run_production --run --confirm "QUEUE THE NATIONAL RUN"
    python -m pipeline.run_production --progress
"""

import argparse
import io
import json
import os

import ee

from . import config as C
from . import build, run as run_module


# The exact words `run()` needs before it will queue anything.
CONFIRM_PHRASE = 'QUEUE THE NATIONAL RUN'

# Stop after this many cell-years fail one after another. A run of 11,320
# cannot tell a bad cell from a bad set-up on its own; this is what turns
# "wrong credentials" or "no write access" into one message rather than
# eleven thousand.
CONSECUTIVE_FAILURE_LIMIT = 20

# Earth Engine will not hold an unlimited number of pending tasks, and the
# ceiling depends on the account. Rather than guess it, watch for the refusal
# and stop cleanly when it comes: the run is meant to be done in sittings, and
# "come back later" is the right answer, not a failure.
_QUEUE_FULL_SIGNS = ('too many', 'quota', 'rate limit', 'resource exhausted',
                     'concurrent', 'exceeded')


def looks_like_a_full_queue(message):
    """Is this Earth Engine saying 'not now', rather than 'this is broken'?"""
    text = str(message).lower()
    return any(sign in text for sign in _QUEUE_FULL_SIGNS)

# The words that go on the collection itself, set once at the front of a run.
_DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'docs')
DESCRIPTION_FILE = os.path.join(_DOCS, 'collection_description.txt')

# Snapshot of the grid, used only if the Earth Engine asset cannot be read.
_GRID_SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'vectors', 'grid_cells_india.geojson')


def cell_names(strict=False):
    """The product's grid cells, in name order.

    Read from config.GRID_ASSET, which is the pipeline's read path for the
    283-cell India subset of the CIM 1:250,000 grid. If Earth Engine cannot
    be reached, fall back to the shipped snapshot of the same grid and say
    so. That fallback is for planning and for the tests, which run offline.

    strict=True refuses the fallback and raises instead. A real run passes
    strict=True: a warning printed once at the top of an 11,320-line log is
    not a safeguard, and a run must never build a different set of cells from
    the one the asset defines.
    """
    try:
        names = (ee.FeatureCollection(C.GRID_ASSET)
                 .aggregate_array('name').getInfo())
    except Exception as e:
        if strict:
            raise RuntimeError(
                'cannot read the grid asset {}: {}. Refusing to queue a run '
                'from the local snapshot, which may not match it.'
                .format(C.GRID_ASSET, e))
        with open(_GRID_SNAPSHOT) as fh:
            snapshot = json.load(fh)
        names = [f['properties']['name'] for f in snapshot['features']]
        print('WARNING: could not read {} ({}); using the local snapshot '
              '{} ({} cells)'.format(C.GRID_ASSET, e, _GRID_SNAPSHOT,
                                     len(names)))
    return sorted(set(names))


def plan(cells=None, first_year=None, last_year=None, strict=False):
    """The full list of (cell, year) pairs a production run would export."""
    first = C.PRODUCTION_FIRST_YEAR if first_year is None else first_year
    last = C.PRODUCTION_LAST_YEAR if last_year is None else last_year
    if last < first:
        raise ValueError('last_year {} is before first_year {}'
                         .format(last, first))
    cells = cell_names(strict=strict) if cells is None else list(cells)
    years = range(first, last + 1)
    return [(cell, year) for cell in cells for year in years]


def describe_destination(collection_path):
    """Make the collection if needed, and put its description on it.

    Done once, at the front of a run, because an export makes images and
    not the folder they sit in: nothing else would ever write it. A run
    that stops half way has still left the collection describing itself.

    Never fatal. A run that cannot write a description can still build
    the product, and the description can be set afterwards with
    scripts/set_collection_description.py. So this reports and carries on.
    """
    try:
        ee.data.getAsset(collection_path)
    except Exception:
        try:
            ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, collection_path)
            print('  created the collection {}'.format(collection_path))
        except Exception as e:
            print('  could not create {}: {}'.format(collection_path, e))
            return False

    try:
        with io.open(DESCRIPTION_FILE, encoding='utf-8') as handle:
            text = handle.read().strip('\n')
    except Exception as e:
        print('  no description written: cannot read {} ({})'
              .format(DESCRIPTION_FILE, e))
        return False
    if not text:
        print('  no description written: {} is empty'.format(DESCRIPTION_FILE))
        return False

    try:
        existing = (ee.data.getAsset(collection_path)
                    .get('properties', {}).get('description'))
        if existing == text:
            print('  the collection already carries this description')
            return True
        ee.data.updateAsset(collection_path,
                            {'properties': {'description': text}},
                            ['properties.description'])
        print('  description written to the collection ({} characters)'
              .format(len(text)))
        return True
    except Exception as e:
        print('  could not write the description: {}'.format(e))
        print('  the run can go ahead; set it afterwards with '
              'scripts/set_collection_description.py')
        return False


def run(confirm=None, cells=None, first_year=None, last_year=None,
        collection_path=None, max_tasks=None, verbose=True,
        describe=True):
    """
    Queue the national run. Returns a summary dictionary.

    confirm         must equal CONFIRM_PHRASE, or nothing is queued.
    cells           default: every cell in the grid asset.
    first_year,
    last_year       default: config.PRODUCTION_FIRST_YEAR / _LAST_YEAR.
    collection_path default: config.PRODUCTION_COLLECTION. Point it at the
                    sandbox to rehearse the same loop harmlessly.
    max_tasks       stop after this many tasks have been queued. You do not
                    need to set this: Earth Engine's ceiling on pending tasks
                    depends on the account, and the run watches for the refusal
                    and stops cleanly by itself. Set it only if you want a
                    short sitting on purpose. None means no limit.
    describe        make the collection and put its description on it before
                    queueing anything (default). The description says what
                    the product is and how to read it, and nothing in an
                    export writes it, so it is done here, once, at the front
                    of the run. Already correct, and it is left alone.
    """
    if confirm != CONFIRM_PHRASE:
        raise ValueError(
            'nothing was queued. To start the national run, pass the exact '
            'phrase: confirm={!r}'.format(CONFIRM_PHRASE))

    destination = (C.PRODUCTION_COLLECTION if collection_path is None
                   else collection_path)
    work = plan(cells, first_year, last_year, strict=True)

    print('national run: {} cell-years -> {}'.format(len(work), destination))

    if describe:
        try:
            describe_destination(destination)
        except Exception as e:
            # The product matters more than its label. A description
            # can be set afterwards; a run of days should not be lost
            # because of it.
            print('  could not describe the collection: {}'.format(e))
            print('  carrying on; set it later with '
                  'scripts/set_collection_description.py')

    if max_tasks is not None:
        print('  stopping after {} queued task(s) this sitting'
              .format(max_tasks))

    queued, skipped, failed = [], 0, []
    consecutive_failures = 0
    for i, (cell, year) in enumerate(work, 1):
        if max_tasks is not None and len(queued) >= max_tasks:
            print('\nreached the {}-task limit; {} of {} cell-years looked '
                  'at. Run this again to continue.'
                  .format(max_tasks, i - 1, len(work)))
            break
        if verbose:
            print('[{}/{}] {} {}'.format(i, len(work), cell, year))
        try:
            task = build.export(cell, year, collection_path=destination,
                                verbose=verbose)
        except KeyboardInterrupt:
            print('\nstopped by hand after {} queued task(s). Nothing is '
                  'lost: start again to continue.'.format(len(queued)))
            break
        except Exception as e:
            if looks_like_a_full_queue(e):
                print('\nEarth Engine will not take any more tasks just now '
                      '({}).'.format(str(e)[:120]))
                print('{} task(s) were queued this sitting, and {} of {} '
                      'cell-years were looked at. Nothing is lost: let the '
                      'queue drain and run this again to carry on.'
                      .format(len(queued), i - 1, len(work)))
                break
            # One bad cell-year must not end a run of thousands. Record it,
            # keep going, report the list at the end.
            failed.append((cell, year, str(e)))
            print('    FAILED {} {}: {}'.format(cell, year, e))
            consecutive_failures += 1
            if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                # Something is wrong with the run itself rather than with this
                # cell-year: wrong credentials, no write access to the
                # destination, a missing input asset. Grinding through
                # thousands more would waste hours and bury the cause.
                print('\nSTOPPED: {} cell-years failed one after another. '
                      'That is a fault with the run, not with one cell. Fix '
                      'the cause and start again; nothing already queued is '
                      'lost.'.format(consecutive_failures))
                break
            continue
        consecutive_failures = 0
        if task is None:
            skipped += 1        # already exported, already exporting, or no
        else:                   # usable granules (an honest archive gap)
            queued.append(task)

    print('\nqueued {} task(s), skipped {}, failed {}'
          .format(len(queued), skipped, len(failed)))
    if failed and len(failed) > len(queued):
        print('MORE FAILED THAN WERE QUEUED. Read the failures before '
              'treating this run as done.')
    if failed:
        print('failures (re-run to retry them):')
        for cell, year, msg in failed:
            print('  {:12s} {}  {}'.format(cell, year, msg))
    print('watch progress in the Tasks tab of the Earth Engine Code Editor, '
          'or with: earthengine task list')

    return {'destination': destination, 'planned': len(work),
            'queued': queued, 'skipped': skipped, 'failed': failed}


def progress(collection_path=None, cells=None, first_year=None,
             last_year=None, show_failures=10, keep_failures_in=None):
    """How far along is the run? Counts, not guesses.

    Answers the three questions someone tracking a run of days actually has:
    how many of the planned mosaics are finished and sitting in the
    collection, how many are being worked on right now, and what has gone
    wrong. Queues nothing and changes nothing, so it is safe to run at any
    time, from a notebook or a terminal.

    Returns a dictionary with the counts, and prints a readable summary.

    keep_failures_in: a file to append failure rows to. Earth Engine does not
    keep finished operations for ever, so on a run spanning days the reason a
    task failed can age out before anyone reads it. What landed is always
    recoverable from the assets themselves; why something failed is the
    perishable part. Passing a path here saves those reasons as a side effect
    of checking progress, with no separate logging step to remember.
    """
    destination = (C.PRODUCTION_COLLECTION if collection_path is None
                   else collection_path)
    work = plan(cells, first_year, last_year)
    expected = {'{}_{}'.format(cell, year) for cell, year in work}

    # What has landed in the collection already.
    try:
        listed = ee.data.listAssets({'parent': destination}).get('assets', [])
        present = {a['id'].rsplit('/', 1)[-1] for a in listed}
    except Exception as e:
        raise RuntimeError('cannot read the destination collection {}: {}'
                           .format(destination, e))
    done = expected & present

    # What Earth Engine is working on, and what it has refused.
    running, pending, failed = [], [], []
    try:
        for op in ee.data.listOperations():
            meta = op.get('metadata', {})
            name = meta.get('description', '')
            if name not in expected:
                continue
            state = meta.get('state')
            if state == 'RUNNING':
                running.append(name)
            elif state == 'PENDING':
                pending.append(name)
            elif state == 'FAILED':
                failed.append((name, meta.get('error', {}).get('message', '')
                               if isinstance(meta.get('error'), dict)
                               else op.get('error', {}).get('message', '')))
    except Exception as e:
        print('could not read the task list ({}); counts below cover the '
              'collection only'.format(e))

    todo = len(expected) - len(done) - len(running) - len(pending)
    share = 100.0 * len(done) / len(expected) if expected else 0.0

    print('run progress -> {}'.format(destination))
    print('  planned      {}'.format(len(expected)))
    print('  finished     {}  ({:.1f}%)'.format(len(done), share))
    print('  running now  {}'.format(len(running)))
    print('  waiting      {}'.format(len(pending)))
    print('  not started  {}'.format(max(todo, 0)))
    print('  failed       {}'.format(len(failed)))
    if failed:
        print('\n  failures (re-running the driver retries them):')
        for name, message in failed[:show_failures]:
            print('    {:20s} {}'.format(name, (message or '')[:90]))
        if len(failed) > show_failures:
            print('    ... and {} more'.format(len(failed) - show_failures))
    if todo > 0 and not running and not pending:
        print('\n  nothing is queued at the moment: run the driver again to '
              'queue the next sitting.')
    if failed and keep_failures_in:
        import datetime
        stamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        try:
            with open(keep_failures_in, 'a') as fh:
                for name, message in failed:
                    fh.write('{}\t{}\t{}\n'.format(
                        stamp, name, (message or '').replace('\n', ' ')))
            print('\n  failure reasons appended to {}'.format(keep_failures_in))
        except Exception as e:
            print('\n  could not write {}: {}'.format(keep_failures_in, e))

    if len(done) == len(expected):
        print('\n  every planned mosaic is present. The run is complete.')

    return {'destination': destination, 'planned': len(expected),
            'finished': sorted(done), 'running': sorted(running),
            'pending': sorted(pending), 'failed': failed,
            'not_started': max(todo, 0)}


def main():
    ap = argparse.ArgumentParser(
        description='Queue the national production run.')
    ap.add_argument('--plan', action='store_true',
                    help='print what would be exported and stop')
    ap.add_argument('--progress', action='store_true',
                    help='report how far along the run is and stop')
    ap.add_argument('--keep-failures-in', default=None,
                    help='append failure reasons to this file, which Earth '
                         'Engine will not keep for ever')
    ap.add_argument('--run', action='store_true',
                    help='queue the exports (needs --confirm)')
    ap.add_argument('--confirm', default=None,
                    help='the exact phrase: "{}"'.format(CONFIRM_PHRASE))
    ap.add_argument('--first-year', type=int, default=None)
    ap.add_argument('--last-year', type=int, default=None)
    ap.add_argument('--cell', action='append', default=None,
                    help='limit to this cell (repeatable)')
    ap.add_argument('--collection', default=None,
                    help='destination collection (default: the production '
                         'collection)')
    ap.add_argument('--max-tasks', type=int, default=None)
    args = ap.parse_args()

    ee.Initialize(project=C.EE_PROJECT)
    run_module.preflight()

    if args.progress:
        progress(collection_path=args.collection, cells=args.cell,
                 first_year=args.first_year, last_year=args.last_year,
                 keep_failures_in=args.keep_failures_in)
        return

    work = plan(args.cell, args.first_year, args.last_year)
    cells = sorted({c for c, _ in work})
    years = sorted({y for _, y in work})
    print('\n{} cell(s) x {} year(s) = {} cell-years'
          .format(len(cells), len(years), len(work)))
    print('years {}..{}'.format(years[0], years[-1]))
    print('destination: {}'.format(args.collection or C.PRODUCTION_COLLECTION))

    if not args.run:
        print('\n(nothing queued -- pass --run --confirm "{}" to start)'
              .format(CONFIRM_PHRASE))
        return

    run(confirm=args.confirm, cells=args.cell,
        first_year=args.first_year, last_year=args.last_year,
        collection_path=args.collection, max_tasks=args.max_tasks)


if __name__ == '__main__':
    main()
