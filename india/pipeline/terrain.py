"""
Terrain: DEM handling, illumination geometry, SCS+C topographic correction, and the
static terrain bands that go into the mosaic.

The projection handling here is load-bearing. GLO-30 is an ImageCollection of tiles;
`.mosaic()` produces an image carrying the default WGS84 1-degree projection, and
`ee.Terrain.slope` operates in the image's projection -- so the gradient gets computed
over a 1-degree neighbourhood and returns nonsense. It fails silently: measured slope
in the Zanskar was 0.28 degrees against a true ~26.7. Always setDefaultProjection first.
"""

import math
import ee

from . import config as C

PI = math.pi
D2R = PI / 180.0


# ----------------------------------------------------------------------------
# DEM and derivatives
# ----------------------------------------------------------------------------

_PREPARED = {'checked': False, 'img': None}


def _prepared_terrain():
    """The prepared terrain asset (config.TERRAIN_ASSET), or None. Probed once.

    The probe is a real getAsset rather than trust in config: if the asset is
    absent or renamed the pipeline must fall back to the live rebuild and say
    so, not die mid-export. Band scales are documented at the config entry
    and were verified by sampling (2026-08-12).
    """
    if not _PREPARED['checked']:
        _PREPARED['checked'] = True
        if getattr(C, 'TERRAIN_USE_PREPARED', False):
            try:
                ee.data.getAsset(C.TERRAIN_ASSET)
                _PREPARED['img'] = ee.Image(C.TERRAIN_ASSET)
            except Exception:
                print('terrain: prepared asset unreadable; live rebuild in use')
    return _PREPARED['img']


def dem():
    """GLO-30 with its native projection asserted and bilinear resampling set.

    Bilinear matters: cos(i) gets resampled into the computation grid, and
    nearest-neighbour introduces sub-pixel jitter that is terrain-correlated -- the
    illumination term ends up offset from the terrain it is meant to correct, which
    is the artefact the correction exists to remove.
    """
    prep = _prepared_terrain()
    if prep is not None:
        # single-image asset: carries a real projection, no mosaic needed
        return prep.select('DEM').resample('bilinear')
    coll = ee.ImageCollection(C.DEM_ASSET).select('DEM')
    native = ee.Image(coll.first()).projection()
    return coll.mosaic().setDefaultProjection(native).resample('bilinear')


def terrain_products(smooth=False):
    """slope and aspect in degrees, from GLO-30.

    smooth=True applies a light focal mean (config.DEM_SMOOTH_PX) BEFORE the
    gradient -- used by the correction geometry only (register C19): DEM
    pixel noise otherwise becomes per-pixel correction speckle. The exported
    terrain bands stay on the raw DEM.

    The asset's PRECOMPUTED slope/aspect bands are used only when
    config.TERRAIN_PRECOMPUTED_PRODUCTS is on -- and it is OFF by default.
    EE derives gradients in the request projection, so live slope DEGRADES
    with scale while a stored 30 m slope band does not; at the balance fit's
    240 m reductions the two describe different terrain populations (steep
    fraction 0.83 vs 0.46 on NH-44-V-C) and the fitted C moved x2-4. The C19
    gates were validated under the request-scale semantics, so by default the
    gradients are computed here from the prepared DEM exactly as they were
    from the tiled mosaic -- the asset still removes the tile-mosaic graph
    cost, which is the Era B win. Details in the register (C19-addendum-2).

    When the precomputed bands ARE enabled: raw aspect is recovered from the
    damped sin/cos pair by atan2 -- the sin(slope) damping factor cancels
    (it is positive wherever aspect means anything; dead-flat pixels read
    aspect 0 and every consumer damps by slope anyway). aspect_smooth is
    stored in degrees and read WITHOUT bilinear resampling on purpose:
    interpolating across the 0/360 wrap would invent ~180-degree aspects.
    """
    prep = _prepared_terrain()
    if prep is not None and getattr(C, 'TERRAIN_PRECOMPUTED_PRODUCTS', False):
        if smooth and C.DEM_SMOOTH_PX > 0:
            slope = (prep.select('slope_smooth').resample('bilinear')
                     .multiply(0.01).rename('slope'))
            aspect = prep.select('aspect_smooth').multiply(0.1).rename('aspect')
        else:
            slope = (prep.select('slope').resample('bilinear')
                     .multiply(0.01).rename('slope'))
            s = prep.select('aspect_sin').resample('bilinear')
            cc = prep.select('aspect_cos').resample('bilinear')
            # EE atan2 takes the CALLER as X: a.atan2(b) = atan2(y=b, x=a) --
            # the reverse of math.atan2. Probed numerically 2026-08-12; the
            # swapped form read ~87 deg off on every slope.
            aspect = (cc.atan2(s).multiply(1.0 / D2R)
                      .add(360).mod(360).rename('aspect'))
        return slope, aspect
    d = dem()
    if smooth and C.DEM_SMOOTH_PX > 0:
        d = (d.focalMean(C.DEM_SMOOTH_PX, 'square', 'pixels')
             .setDefaultProjection(dem().projection()))
    t = ee.Terrain.products(d)
    return t.select('slope'), t.select('aspect')


def hand():
    """
    Height above nearest drainage, 30 m, threshold-100 drainage network.

    Nodata is masked explicitly -- the sibling GlobalHAND/30m/hand-1000 product returns
    -35945 over the Sundarbans, an unmasked sentinel, and this family shares lineage.
    The prepared asset stores hand as metres x10; the same guard is applied after
    rescaling (harmless where the export already carried the mask).
    """
    prep = _prepared_terrain()
    if prep is not None:
        h = prep.select('hand').multiply(0.1).rename('hand')
        return h.updateMask(h.gte(0).And(h.lt(10000)))
    h = ee.ImageCollection(C.HAND_ASSET).mosaic().rename('hand')
    return h.updateMask(h.gte(0).And(h.lt(10000)))


def static_bands():
    """
    Time-invariant terrain bands for the mosaic.

    Aspect is emitted as sin/cos rather than degrees: raw aspect wraps at north, so
    359 and 1 degrees are adjacent on the ground but maximally distant numerically,
    and any classifier reads that discontinuity as a real edge. Aspect is also
    undefined as slope approaches zero, so both components are damped by slope.
    """
    # STORED BANDS FOR THE EXPORT (owner push 2026-08-14, checked same
    # day on NH-44-V-C at 30 m: slope / aspect_sin / aspect_cos / hand
    # mean |difference| = 0 against the live computation; only isolated
    # grid-edge pixels differ). The prepared asset already holds these
    # four in the exact export scales, so the export reads them instead
    # of recomputing gradients every time. Elevation keeps the live read
    # (same asset's DEM, smoothed between grid points -- the shipped
    # convention). Live fallback when the asset is absent. NOTE: this is
    # the EXPORT bands only -- correction geometry keeps its own
    # request-scale semantics (C19-addendum-2), untouched.
    prep = _prepared_terrain()
    elev = dem().rename('elevation')
    if prep is not None:
        return ee.Image.cat([
            elev.toInt16(),
            prep.select('slope').rename('slope').toInt16(),
            prep.select('aspect_sin').rename('aspect_sin').toInt16(),
            prep.select('aspect_cos').rename('aspect_cos').toInt16(),
            prep.select('hand').rename('hand').toInt16(),
        ])

    slope, aspect = terrain_products()

    aspect_rad = aspect.multiply(D2R)
    # Damp by sin(slope) so flat ground -- where aspect is arbitrary -- contributes ~0
    damp = slope.multiply(D2R).sin()

    return ee.Image.cat([
        elev.toInt16(),
        slope.multiply(100).toInt16().rename('slope'),
        aspect_rad.sin().multiply(damp).multiply(10000).toInt16().rename('aspect_sin'),
        aspect_rad.cos().multiply(damp).multiply(10000).toInt16().rename('aspect_cos'),
        hand().multiply(10).toInt16().rename('hand'),
    ])


# ----------------------------------------------------------------------------
# illumination geometry
# ----------------------------------------------------------------------------

def _cap_factor(f):
    """Soft (or hard) bound on the correction factor -- see config C19."""
    lo, hi = C.CORRECTION_FACTOR_MIN, C.CORRECTION_FACTOR_MAX
    if not C.TOPO_SOFT_CAP:
        return f.clamp(lo, hi)
    hi_k = 1.0 + 0.75 * (hi - 1.0)
    lo_k = 1.0 - 0.75 * (1.0 - lo)
    over = f.subtract(hi_k).max(0)
    f_hi = over.divide(hi - hi_k).multiply(-1).exp()         .multiply(-(hi - hi_k)).add(hi)
    under = ee.Image(lo_k).subtract(f).max(0)
    # (a dead first assignment of f_lo was removed 2026-08-12 -- it was
    # immediately overwritten and never serialized; audit cruft)
    f_lo = ee.Image(lo_k).subtract(
        under.divide(lo_k - lo).multiply(-1).exp()
        .multiply(-(lo_k - lo)).add(lo_k - lo))
    return f.where(f.gt(hi_k), f_hi).where(f.lt(lo_k), f_lo)


def _sun_angles_deg(image):
    """Scene sun azimuth and zenith in degrees, null-safe across eras."""
    img = ee.Image(image)
    az = ee.Number(ee.Algorithms.If(
        img.get('SUN_AZIMUTH'), img.get('SUN_AZIMUTH'),
        ee.Algorithms.If(img.get('MEAN_SUN_AZIMUTH_ANGLE'),
                         img.get('MEAN_SUN_AZIMUTH_ANGLE'), 140)))
    zen = ee.Number(ee.Algorithms.If(
        img.get('SUN_ELEVATION'),
        ee.Number(90).subtract(ee.Number(img.get('SUN_ELEVATION'))),
        ee.Algorithms.If(img.get('MEAN_SUN_ZENITH_ANGLE'),
                         img.get('MEAN_SUN_ZENITH_ANGLE'), 40)))
    return az, zen


# Diagnostic ledger of the most recent correction run, THREAD-LOCAL
# (C26 ruling 7: a module global let one parallel export driver stamp
# another driver's cell onto its asset). Written by
# topo_physics.apply_physics; must survive any cleanup.
import threading as _threading
_LEDGER_TLS = _threading.local()


def _perscene_terrain():
    """Smoothed terrain for the C22 core: stored bands, else live rebuild."""
    prep = _prepared_terrain()
    if prep is not None:
        slope = prep.select('slope_smooth').multiply(0.01)
        aspect = prep.select('aspect_smooth').multiply(0.1)
    else:
        slope, aspect = terrain_products(smooth=True)
    return slope, aspect


def _illum_terrain_linear():
    """The terrain half of cos(i), stored as THREE LINEAR quantities.

    cos(i) = cos(zen)*cos(slope)
           + sin(zen)*[ cos(azi)*(sin(slope)*cos(aspect))
                      + sin(azi)*(sin(slope)*sin(aspect)) ]

    Every term is linear in these three bands with scene-constant scalar
    weights, so a coarse reduction is the reduction of a SUM -- exact at any
    scale. The old route fed `aspect_smooth` (compass BEARINGS in degrees)
    into a cosine that Earth Engine evaluated at the reduction scale, so the
    bearings were averaged first: north at 350 and north at 10 average to due
    south. Measured on NI-43-Z-A hillside pixels (sun az 150, zen 40): 30 m
    old == truth (0.6527); 300 m old 0.7209 vs truth 0.6533; 600 m old 0.7629
    vs truth 0.6542.

    Reads config.TERRAIN_ILLUM_ASSET when present (built once by
    scripts/export_terrain_illum_asset.py); otherwise computes the same
    products live and PINS them to the terrain grid, which is equivalent but
    costs a full-resolution read.

    Returns (cos_slope, sinslope_sinaspect, sinslope_cosaspect).
    """
    prep = _prepared_terrain()
    asset = getattr(C, 'TERRAIN_ILLUM_ASSET', None)
    if asset:
        try:
            ill = ee.Image(asset)
            ee.data.getAsset(asset)
            # ALL THREE come from the asset. Computing cos(slope) live here
            # instead re-introduced the fault on the slope term: at 300 m EE
            # averaged degrees and then took the cosine (measured gap 0.0039
            # at 300 m, 0.0069 at 600 m, growing with scale).
            return (ill.select('cos_slope_smooth').multiply(1e-4),
                    ill.select('sinslope_sinaspect_smooth').multiply(1e-4),
                    ill.select('sinslope_cosaspect_smooth').multiply(1e-4))
        except Exception:
            pass
    slope, aspect = _perscene_terrain()
    s_r = slope.multiply(D2R)
    a_r = aspect.multiply(D2R)
    nat = (prep.select('slope_smooth').projection() if prep is not None
           else dem().projection())
    return (s_r.cos().reproject(nat),
            s_r.sin().multiply(a_r.sin()).reproject(nat),
            s_r.sin().multiply(a_r.cos()).reproject(nat))


def _perscene_trig(slope, aspect):
    """Scene-invariant terrain trig, computed ONCE per call site and shared
    across every scene's graph (efficiency audit 2026-08-12: the per-scene
    rebuild inflated the topo subgraph ~6x for identical arithmetic)."""
    s_r = slope.multiply(D2R)
    return s_r.cos(), s_r.sin(), aspect.multiply(D2R)


def _perscene_ic(img, slope, aspect, trig=None):
    """Illumination condition with SCENE-CONSTANT sun angles (C22 core).

    config.TOPO_ILLUM_LINEAR (default False) switches to the aggregation-safe
    linear form -- see _illum_terrain_linear for the measured reason.
    """
    az, zen = _sun_angles_deg(img)
    zen_r = zen.multiply(D2R)
    az_r = az.multiply(D2R)
    cos_z = zen_r.cos()
    sin_z = zen_r.sin()
    if getattr(C, 'TOPO_ILLUM_LINEAR', False):
        t1, t_sin, t_cos = _illum_terrain_linear()
        raw = (t1.multiply(cos_z)
               .add(t_cos.multiply(az_r.cos())
                    .add(t_sin.multiply(az_r.sin()))
                    .multiply(sin_z)))
        return raw, cos_z
    cos_s, sin_s, asp_r = trig if trig is not None \
        else _perscene_trig(slope, aspect)
    # cos is even, so aspect - azimuth == azimuth - aspect under cos; the
    # image must be the caller (Image.subtract(Number) is valid, not vice versa)
    cos_azi_diff = asp_r.subtract(az_r).cos()
    raw = (cos_s.multiply(cos_z)
           .add(sin_s.multiply(sin_z).multiply(cos_azi_diff)))
    return raw, cos_z


_INDIA_LAND = {'img': None}


def india_land_mask():
    """1 on land inside the OFFICIAL INDIA BOUNDARY (config.INDIA_ASSET),
    0 elsewhere -- sea, and anything across the border. Owner rule
    2026-08-16: every fit or calibration SAMPLE is land-only, and the
    land is the India boundary, NOT the classification-regions outline.
    Painted once per process from the boundary vector."""
    if _INDIA_LAND['img'] is None:
        _INDIA_LAND['img'] = (ee.Image().byte()
                              .paint(ee.FeatureCollection(C.INDIA_ASSET), 1)
                              .unmask(0).gt(0))
    return _INDIA_LAND['img']


def consolidate_table(parts_folder, table_id, distinct_keys,
                      description, verbose=True, keep_fp=None,
                      augment=None):
    """GENERIC ROLL-UP (owner design 2026-08-16): merge every staged part
    in parts_folder into the big table table_id. Batch jobs cannot append
    to a table asset, so this exports big-table + parts to a STAGING
    table; when the job finishes, finalise_table() swaps it in and
    deletes the parts. Where a part re-states a row already in the big
    table, the PART wins (parts merged first, distinct keeps first).
    Returns (task, part_ids)."""
    try:
        listing = ee.data.listAssets({'parent': parts_folder})
        parts = [a['name'] for a in listing.get('assets', [])]
    except Exception:
        parts = []
    exists = True
    try:
        ee.data.getAsset(table_id)
    except Exception:
        exists = False
    if not parts and not (keep_fp and exists):
        if verbose:
            print('consolidate: no staged parts in {}'.format(parts_folder))
        return None, []
    fc = None
    for pid in parts:
        fc = ee.FeatureCollection(pid) if fc is None \
            else fc.merge(ee.FeatureCollection(pid))
    if exists:
        fc = ee.FeatureCollection(table_id) if fc is None \
            else fc.merge(ee.FeatureCollection(table_id))
    fc = fc.distinct(list(distinct_keys))
    if keep_fp is not None:
        # PRUNE (owner 2026-08-16): drop rows of retired settings versions;
        # the reader only ever sees the current fingerprint anyway
        fc = fc.filter(ee.Filter.eq('fp', keep_fp))
    if augment is not None:
        # derived rows recomputed from the merged table at every roll-up
        # (e.g. the offsets table's REGION rows): old derived rows out,
        # fresh ones in
        fc = fc.filter(ee.Filter.neq('kind', 'region')).merge(augment(fc))
    staging = table_id + '__staging'
    try:
        ee.data.deleteAsset(staging)     # a stale staging table from
    except Exception:                    # an abandoned earlier roll-up
        pass
    task = ee.batch.Export.table.toAsset(
        collection=fc, description=description, assetId=staging)
    task.start()
    if verbose:
        print('consolidate: {} part(s) {} the big table{} -> {} (task {})'
              .format(len(parts), '+' if exists else 'into',
                      ', PRUNED to fp ' + keep_fp if keep_fp else '',
                      staging, task.id))
    return task, parts


def finalise_table(parts_folder, table_id, verbose=True):
    """Second half of the roll-up, AFTER the staging export succeeded:
    swap staging in as the big table, delete every part CREATED BEFORE
    the staging table was (exactly the ones the roll-up merged; parts
    queued later stay for the next round). Refuses if staging is not
    there (job not finished)."""
    staging = table_id + '__staging'
    try:
        st_info = ee.data.getAsset(staging)
    except Exception:
        raise RuntimeError('finalise: {} not found -- has the '
                           'consolidate job finished?'.format(staging))
    made = st_info.get('updateTime', '')
    listing = ee.data.listAssets({'parent': parts_folder})
    part_ids = [a['name'] for a in listing.get('assets', [])
                if a.get('updateTime', 'z') < made]
    try:
        ee.data.deleteAsset(table_id)
    except Exception:
        pass
    ee.data.renameAsset(staging, table_id)
    for pid in part_ids:
        try:
            ee.data.deleteAsset(pid)
        except Exception as e:
            print('    could not delete part {}: {}'.format(pid, str(e)[:60]))
    if verbose:
        print('finalise: {} is live; {} part(s) removed'
              .format(table_id, len(part_ids)))


def apply_topographic(collection, region, enabled=True, cell=None,
                      year=None):
    """
    Topographic correction: SCS+C with the physics C from the 6S tables
    (production since the 2026-08-30 fold-in; owner ruling 2026-08-29 —
    the correction question is CLOSED). The empirical fitted-C
    estimators ('perscene', 'pooled', 'balance', 'temporal') were
    removed 2026-09-01 (owner ruling; see the working notes on retired
    code, not part of this release — recoverable from the private
    archive's history).
    """
    if not enabled:
        return collection

    if C.TOPO_C_ESTIMATOR != 'physics':
        raise RuntimeError(
            "TOPO_C_ESTIMATOR is {!r}, but only 'physics' remains -- the "
            'fitted estimators were excised 2026-09-01'.format(
                C.TOPO_C_ESTIMATOR))
    # The import lives here because topo_physics imports this module.
    from . import topo_physics
    return topo_physics.apply_physics(collection, region,
                                      cell=cell, year=year)
