"""
Physics-C topographic correction -- PRODUCTION since the 2026-08-30
fold-in (owner ruling 2026-08-29, docs/terrain_correction_evidence.md:
the correction question is CLOSED as pure physics + shared soft cap,
no damping, no drop rule).

Ported from the verified lab driver (an internal script, not part of this
release, which built and validated v3-v9 of NH-46-Z-D) with the lab arms
removed:
no S4 damping, no veg-w, no poorly-lit drop rule, no no-corr anchor.

The recipe, per PASS (sensor|pass_key):
  C per band from the 6S table of the pass's sensor family (oli/etm/tm):
    sun zenith of the pass (SUN_ELEVATION), aerosol optical thickness and
    water vapour from MERRA-2 at the pass hour (scene-wide mean, no
    per-cell seams), straight-line between table nodes;
  C per PIXEL: straight-line read of that profile at the pixel's own
    elevation (ee.Image.interpolate on the DEM);
  factor = (cos slope * cos z + C) / (max(cos i, PHYS_IC_FLOOR) + Vd * C),
    Vd = (1 + cos slope) / 2 (sky view); soft cap
    CORRECTION_FACTOR_MIN..MAX (terrain._cap_factor); no slope gate;
    terrain-reflected light OFF; cast shadow NOT masked.

Radiometric ORDER under this estimator: topo BEFORE BRDF and bandpass
(the C2-physics sequence, owner 2026-08-23) -- sequenced in
build.build_mosaic, not here; this module corrects and nothing else.

The 6S LUT tables are read from the cloud tables in mosaic_v2_inputs
(config.PHYS_LUT_ASSETS -- owner rule 2026-08-30: every input the
pipeline uses lives there), loaded client-side once per run. The
repo-bundled CSVs (config.PHYS_LUT_FILES) are the LOUD fallback only.
"""

import collections
import datetime as _dt
import os

import ee

from . import config as C
from . import sources
from . import terrain

BANDS = list(C.CORE_BANDS)
# LUT column mapping: the tables carry OLI-style names for every sensor
# family (B2..B7 = blue..swir2), matching the internal lab package that
# first read these tables (not part of this release).
_LUT_COL = dict(zip(BANDS, ['B2', 'B3', 'B4', 'B5', 'B6', 'B7']))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ----------------------------------------------------------------------------
# 6S LUT reading (self-contained port of the internal lab reader, which is
# not part of this release)
# ----------------------------------------------------------------------------

def _load_lut(path):
    import csv
    rows = {}
    axes = {'aot': set(), 'wv': set(), 'elev': set(), 'sunzen': set()}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            key = (float(r['aot']), float(r['wv']), float(r['elev']),
                   float(r['sunzen']))
            rows[key] = {b: float(r['C_' + _LUT_COL[b]]) for b in BANDS}
            for k, v in zip(('aot', 'wv', 'elev', 'sunzen'), key):
                axes[k].add(v)
    return {'axes': {k: sorted(v) for k, v in axes.items()}, 'rows': rows}


def _bracket_w(values, v):
    """(lo, hi, weight) around v; clamped at the axis ends."""
    if v <= values[0]:
        return values[0], values[0], 0.0
    if v >= values[-1]:
        return values[-1], values[-1], 0.0
    lo = max(x for x in values if x <= v)
    hi = min(x for x in values if x >= v)
    w = 0.0 if hi == lo else (v - lo) / (hi - lo)
    return lo, hi, w


def _profile(lut, sunzen, aot, wv):
    """C at EVERY elevation node for one pass: straight-line in sun
    zenith, AOT and water vapour (clamped at the ends). Returns
    (elevs, {elev: {band: C}})."""
    ax = lut['axes']
    z0, z1, wz = _bracket_w(ax['sunzen'], sunzen)
    a0, a1, wa = _bracket_w(ax['aot'], aot)
    v0, v1, wv_ = _bracket_w(ax['wv'], wv)
    rows = lut['rows']

    def lerp(x, y, t):
        return x + (y - x) * t

    prof = {}
    for el in ax['elev']:
        prof[el] = {}
        for b in BANDS:
            def r(z, a, v):
                return rows[(a, v, el, z)][b]
            c0 = lerp(lerp(r(z0, a0, v0), r(z0, a1, v0), wa),
                      lerp(r(z0, a0, v1), r(z0, a1, v1), wa), wv_)
            c1 = lerp(lerp(r(z1, a0, v0), r(z1, a1, v0), wa),
                      lerp(r(z1, a0, v1), r(z1, a1, v1), wa), wv_)
            prof[el][b] = lerp(c0, c1, wz)
    return list(ax['elev']), prof


def _interp_elev(prof, elevs, e, b):
    lo = max([x for x in elevs if x <= e] or [elevs[0]])
    hi = min([x for x in elevs if x >= e] or [elevs[-1]])
    if hi == lo:
        return prof[lo][b]
    w = (e - lo) / (hi - lo)
    return prof[lo][b] + (prof[hi][b] - prof[lo][b]) * w


def _load_lut_asset(asset_id):
    """Same structure as _load_lut, from the cloud table. Paged reads:
    a single getInfo aborts at 5000 elements and the tables hold
    26680 rows."""
    feats = []
    params = {'assetId': asset_id, 'pageSize': 5000}
    while True:
        page = ee.data.listFeatures(params)
        feats.extend(page.get('features', []))
        token = page.get('nextPageToken')
        if not token:
            break
        params = {'assetId': asset_id, 'pageSize': 5000,
                  'pageToken': token}
    rows = {}
    axes = {'aot': set(), 'wv': set(), 'elev': set(), 'sunzen': set()}
    for f in feats:
        r = f['properties']
        key = (float(r['aot']), float(r['wv']), float(r['elev']),
               float(r['sunzen']))
        rows[key] = {b: float(r['C_' + _LUT_COL[b]]) for b in BANDS}
        for k, v in zip(('aot', 'wv', 'elev', 'sunzen'), key):
            axes[k].add(v)
    return {'axes': {k: sorted(v) for k, v in axes.items()}, 'rows': rows}


_LUT_CACHE = {}


def lut_for(sensor):
    kind = C.PHYS_LUT_BY_SENSOR[sensor]
    # PRECOMPUTED FIRST (owner rule 2026-08-30, applied to the LUTs
    # 2026-08-31): the authoritative tables live in mosaic_v2_inputs,
    # like every other pipeline input. LOUD local-CSV fallback only.
    asset_id = C.PHYS_LUT_ASSETS[kind]
    if asset_id in _LUT_CACHE:
        return _LUT_CACHE[asset_id], asset_id.rsplit('/', 1)[-1]
    try:
        lut = _load_lut_asset(asset_id)
        name = asset_id.rsplit('/', 1)[-1]
        print('    6S table: precomputed asset {} in use ({} rows)'
              .format(name, len(lut['rows'])))
        _LUT_CACHE[asset_id] = lut
        return lut, name
    except Exception as e:
        print('    WARNING: cloud 6S table {} unreadable ({}) — falling '
              'back to the repo CSV'.format(asset_id, e))
    path = os.path.join(_REPO_ROOT, C.PHYS_LUT_FILES[kind])
    if not os.path.exists(path):
        # LOUD, not silent (reviewer find 2026-08-30): the v1 spare is
        # coarser — a stripped data/lut/ would otherwise degrade the
        # correction without a word.
        print('    WARNING: 6S table {} missing — falling back to the '
              'coarser {} for sensor {}'.format(
                  C.PHYS_LUT_FILES[kind], C.PHYS_LUT_FALLBACK, sensor))
        path = os.path.join(_REPO_ROOT, C.PHYS_LUT_FALLBACK)
    if path not in _LUT_CACHE:
        _LUT_CACHE[path] = _load_lut(path)
    return _LUT_CACHE[path], os.path.basename(path)


# ----------------------------------------------------------------------------
# pass table
# ----------------------------------------------------------------------------

def pass_table(region, year):
    """One row per PASS (sensor|pass_key): sun zenith of the first frame,
    MERRA-2 AOT and water vapour at the frame's hour over the frame
    footprint (scene-wide mean), plus the date.

    PRECOMPUTED FIRST (owner-approved 2026-08-30): reads the national
    overpass-conditions table for the year (one row per frame, same
    derivation, built once by scripts/export_overpass_conditions.py)
    filtered to this region -- one small query instead of dozens of
    MERRA reductions per export. LOUD live fallback when the year's
    table is absent: the live path is the verified lab driver's own
    (sources.build mode='c2', captured before any masking).
    """
    rows = None
    table_id = '{}/overpass_conditions/INDIA_{}'.format(
        C.INPUTS_ROOT, year)
    try:
        ee.data.getAsset(table_id)
        feats = (ee.FeatureCollection(table_id).filterBounds(region)
                 .getInfo()['features'])
        rows = [x['properties'] for x in feats]
        print('    overpass conditions: precomputed table INDIA_{} '
              'in use ({} frame rows)'.format(year, len(rows)))
    except Exception:
        print('    WARNING: no overpass-conditions table INDIA_{} -- '
              'falling back to live MERRA queries (slow; build it: '
              'scripts/export_overpass_conditions.py)'.format(year))

    if rows is None:
        coll, _era = sources.build(region, year, mode='c2')
        aer = ee.ImageCollection('NASA/GSFC/MERRA/aer/2')
        slv = ee.ImageCollection('NASA/GSFC/MERRA/slv/2')

        def f(im):
            im = ee.Image(im)
            t = ee.Date(im.get('system:time_start'))
            _az, zen = terrain._sun_angles_deg(im)
            geom = im.geometry()
            # NULL-SAFE (pheno-2025 find: MERRA-2 lags months; an empty
            # hour made mean() a zero-band image — a missing value must
            # become the climatology fallback, not a crash)
            aer_h = (aer.filterDate(t.advance(-1, 'hour'),
                                    t.advance(1, 'hour'))
                     .select('TOTEXTTAU'))
            slv_h = (slv.filterDate(t.advance(-1, 'hour'),
                                    t.advance(1, 'hour'))
                     .select('TQV'))
            a = ee.Algorithms.If(
                aer_h.size().gt(0),
                aer_h.mean().reduceRegion(ee.Reducer.mean(), geom, 5000,
                                          bestEffort=True).get('TOTEXTTAU'),
                None)
            w = ee.Algorithms.If(
                slv_h.size().gt(0),
                slv_h.mean().reduceRegion(ee.Reducer.mean(), geom, 5000,
                                          bestEffort=True).get('TQV'),
                None)
            return ee.Feature(None, {
                'sensor': im.get('sensor'), 'pass_key': im.get('pass_key'),
                'idx': im.get('system:index'), 'zen': zen,
                't': im.get('system:time_start'), 'aot': a, 'tqv': w})

        rows = [x['properties'] for x in
                ee.FeatureCollection(coll.map(f)).getInfo()['features']]
    passes = collections.OrderedDict()
    n_frames = 0
    for r in sorted(rows, key=lambda r: (r['t'], r.get('idx') or '')):
        n_frames += 1
        k = '{}|{}'.format(r['sensor'], int(r['pass_key']))
        if k in passes:
            passes[k]['frames'] += 1
            continue
        aot = r.get('aot')
        tqv = r.get('tqv')
        passes[k] = {
            'gkey': k, 'sensor': r['sensor'],
            'pass_key': int(r['pass_key']),
            'date': _dt.datetime.fromtimestamp(
                r['t'] / 1000.0, _dt.timezone.utc).strftime('%Y-%m-%d'),
            'sun_zen': float(r['zen']),
            'aot': float(aot) if aot is not None else None,
            'wv': float(tqv) / 10.0 if tqv is not None else None,
            'frames': 1}
    return passes, n_frames


def profiles_for(passes):
    """Attach the C profile (every elevation node, six bands) to each
    pass. Returns (reference elevation grid, table names used, number of
    passes that fell back to the AOT/WV climatology)."""
    elevs_ref = None
    tables = set()
    n_fallback = 0
    for p in passes.values():
        lut, name = lut_for(p['sensor'])
        tables.add('{}:{}'.format(p['sensor'], name))
        aot = p['aot'] if p['aot'] is not None else C.PHYS_AOT_CLIM
        wv = p['wv'] if p['wv'] is not None else C.PHYS_WV_CLIM
        if p['aot'] is None or p['wv'] is None:
            n_fallback += 1
        elevs, prof = _profile(lut, p['sun_zen'], aot, wv)
        if elevs_ref is None:
            elevs_ref = elevs
        if elevs != elevs_ref:
            # tables on different elevation grids (v1 fallback vs v2):
            # resample onto the reference grid
            prof = {e: {b: _interp_elev(prof, elevs, e, b) for b in BANDS}
                    for e in elevs_ref}
        p['profile'] = prof
        p['aot_used'] = aot
        p['wv_used'] = wv
    return elevs_ref, sorted(tables), n_fallback


# ----------------------------------------------------------------------------
# application
# ----------------------------------------------------------------------------

def apply_physics(collection, region, cell=None, year=None, verbose=True):
    """SCS+C with the physics C, mapped over the collection. Correction
    only -- BRDF and bandpass are sequenced AFTER this in build_mosaic
    (the C2-physics order). Passes missing from the table (a frame that
    slipped the acquisition query) ship uncorrected rather than wrongly
    corrected; non-positive red (bad retrieval) keeps the raw value.
    """
    if year is None:
        raise ValueError('physics topo needs the year to build its '
                         'pass table')
    passes, n_frames = pass_table(region, year)
    elevs, tables, n_fallback = profiles_for(passes)
    if verbose:
        print('    physics C: {} passes / {} frames; tables {}; '
              'MERRA-2 fallback on {}'.format(
                  len(passes), n_frames, tables, n_fallback))

    # LOUD when the collection carries passes the table does not
    # (reviewer find 2026-08-30): an unmatched pass ships UNCORRECTED by
    # the missing-pass fallback below — right behaviour, but never
    # silently. Catches lab collections built with different filters
    # (e.g. HLS variants, whose gkeys can never match a c2 pass table).
    try:
        coll_sensors = collection.aggregate_array('sensor').getInfo()
        coll_keys = collection.aggregate_array('pass_key').getInfo()
        coll_gkeys = {'{}|{}'.format(s, int(k))
                      for s, k in zip(coll_sensors, coll_keys)}
        unmatched = sorted(coll_gkeys - set(passes.keys()))
        if unmatched:
            print('    WARNING: {} pass(es) in the collection have no '
                  'row in the physics table and ship UNCORRECTED: {}'
                  .format(len(unmatched), unmatched[:10]))
    except Exception as e:
        print('    (pass-match check skipped: {})'.format(e))

    n = len(elevs)
    flat = {k: [float(p['profile'][e][b]) for b in BANDS for e in elevs]
            for k, p in passes.items()}
    table = ee.Dictionary(flat)
    elev_list = ee.List([float(e) for e in elevs])
    dem = terrain.dem()
    slope, aspect = terrain._perscene_terrain()
    trig = terrain._perscene_trig(slope, aspect)
    t1, _, _ = terrain._illum_terrain_linear()
    svf = t1.add(1).divide(2)          # sky view Vd = (1 + cos slope)/2

    def _one(image):
        img = ee.Image(image)
        raw_ic, cos_z = terrain._perscene_ic(img, slope, aspect, trig)
        ic = raw_ic.max(C.PHYS_IC_FLOOR)
        num_base = t1.multiply(cos_z)  # cos slope * cos z
        gkey = (ee.String(img.get('sensor')).cat('|')
                .cat(ee.Number(img.get('pass_key')).format('%d')))
        vec = ee.List(table.get(gkey, ee.List.repeat(-1, n * len(BANDS))))
        missing = ee.Number(vec.get(0)).lt(0)
        valid = img.select('red').gt(0)
        out = img
        for i, b in enumerate(BANDS):
            ys = vec.slice(i * n, (i + 1) * n)
            c = dem.interpolate(elev_list, ys, 'clamp')
            f = num_base.add(c).divide(ic.add(svf.multiply(c)))
            f = terrain._cap_factor(f)
            corrected = img.select(b).multiply(f)
            keep_raw = valid.Not().Or(ee.Image.constant(missing))
            out = out.addBands(
                corrected.where(keep_raw, img.select(b)).rename(b),
                None, True)
        return ee.Image(out.copyProperties(image, image.propertyNames()))

    terrain._LEDGER_TLS.last = {
        'topo_estimator': 'physics', 'topo_passes': len(passes),
        'topo_merra_fallback_passes': n_fallback}
    return collection.map(_one)
