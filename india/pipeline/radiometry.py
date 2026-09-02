"""
Radiometric normalisation: BRDF c-factor, then the bandpass chain
(TM -> ETM+ in-house, ETM+ -> OLI published) onto the OLI reference
basis. Order: atmospheric correction (upstream, C2 L2), then BRDF,
then bandpass -- the published harmonisation sequence.
"""

import math
import ee

from . import config as C

PI = math.pi


# ----------------------------------------------------------------------------
# angle extraction
# ----------------------------------------------------------------------------

def _angles(image):
    """
    Pull the four per-pixel angle bands and return them in radians, plus the
    relative azimuth. Source bands are 0.01-degree integers in both C2 L1 and HLS.
    """
    d2r = PI / 180.0
    sza = image.select('SZA').multiply(0.01).multiply(d2r)
    vza = image.select('VZA').multiply(0.01).multiply(d2r)
    saa = image.select('SAA').multiply(0.01).multiply(d2r)
    vaa = image.select('VAA').multiply(0.01).multiply(d2r)
    raa = saa.subtract(vaa)            # relative azimuth
    return sza, vza, raa


# ----------------------------------------------------------------------------
# BRDF kernels
# ----------------------------------------------------------------------------

def _ross_thick(sza, vza, raa):
    """RossThick volumetric scattering kernel."""
    cos_xi = (sza.cos().multiply(vza.cos())
              .add(sza.sin().multiply(vza.sin()).multiply(raa.cos())))
    xi = cos_xi.clamp(-1, 1).acos()

    num = xi.multiply(-1).add(PI / 2).multiply(cos_xi).add(xi.sin())
    den = sza.cos().add(vza.cos())
    return num.divide(den).subtract(PI / 4)


def _li_sparse_r(sza, vza, raa, hb=C.BRDF_HB, br=C.BRDF_BR):
    """LiSparse-Reciprocal geometric-optical kernel."""
    # Crown-shape adjusted zenith angles
    szap = sza.tan().multiply(br).atan()
    vzap = vza.tan().multiply(br).atan()

    cos_xip = (szap.cos().multiply(vzap.cos())
               .add(szap.sin().multiply(vzap.sin()).multiply(raa.cos())))

    tan_s, tan_v = szap.tan(), vzap.tan()
    d_sq = (tan_s.pow(2).add(tan_v.pow(2))
            .subtract(tan_s.multiply(tan_v).multiply(raa.cos()).multiply(2)))
    d = d_sq.max(0).sqrt()

    sec_s = szap.cos().pow(-1)
    sec_v = vzap.cos().pow(-1)
    sec_sum = sec_s.add(sec_v)

    overlap_term = (d_sq.add(tan_s.multiply(tan_v).multiply(raa.sin()).pow(2))
                    .max(0).sqrt().multiply(hb))
    cos_t = overlap_term.divide(sec_sum).clamp(-1, 1)
    t = cos_t.acos()

    o = t.subtract(t.sin().multiply(cos_t)).multiply(sec_sum).divide(PI)

    return (o.subtract(sec_s).subtract(sec_v)
            .add(cos_xip.add(1).multiply(0.5).multiply(sec_s).multiply(sec_v)))


def _brdf_reflectance(band, sza, vza, raa):
    """f_iso + f_vol*K_vol + f_geo*K_geo for one band."""
    k = C.BRDF_COEFFS[band]
    kvol = _ross_thick(sza, vza, raa)
    kgeo = _li_sparse_r(sza, vza, raa)
    return (kvol.multiply(k['vol'])
            .add(kgeo.multiply(k['geo']))
            .add(k['iso']))


# ----------------------------------------------------------------------------
# c-factor
# ----------------------------------------------------------------------------

def apply_brdf(image, bands=None):
    """
    Roy et al. (2016) c-factor NBAR normalisation.

        c = R(theta_s, view=nadir) / R(theta_s, theta_v, phi)
        rho_nbar = rho_observed * c

    Because the correction is a ratio, errors in the absolute BRDF coefficients
    largely cancel -- which is why fixed global coefficients work for Landsat's
    narrow +/-7.5 degree field of view.

    View angle is normalised to nadir. The solar zenith is normalised to a
    SCENE-CONSTANT value rather than left per-pixel -- see below.

    Solar zenith, and what HLS actually does (User Guide v2.0 section 4.4, read
    directly). HLS sets view zenith to 0 but adjusts solar zenith "only by a trivial
    amount": for a given tile and day it computes the solar zenith at the TILE
    CENTRE's latitude for the Landsat overpass time and for the Sentinel-2 overpass
    time, and uses the mean of the two for every pixel in that tile that day. The
    guide states elsewhere that BRDF adjustment "mainly normalizes the view angle
    effects, with the solar zenith angle largely intact".

    So HLS does NOT remove seasonal solar-zenith variation, and the register's claim
    that the two eras "diverge systematically with season and latitude" was wrong.
    Measured on a Punjab granule: observed mean 32.87 deg, NBAR 31.69 deg -- a 1.2 deg
    adjustment. Its purpose is narrow: to remove the east-west solar-time gradient
    across a swath, so the same ground imaged in two overlapping passes is not
    corrected to two different sun angles, and to reconcile the 30-minute gap between
    the Landsat and Sentinel-2 overpasses.

    Only the first of those applies before 2013, there being no Sentinel-2 to
    reconcile with. The faithful Era A analogue is therefore a scene-constant solar
    zenith taken from SUN_ELEVATION -- the scene-centre value, which is what HLS's
    tile-centre value is -- rather than the per-pixel observed angle.
    """
    bands = bands or C.CORE_BANDS
    sza, vza, raa = _angles(image)

    zero = vza.multiply(0)   # nadir view, zero relative azimuth, same footprint/mask

    if C.BRDF_NORMALISE_SOLAR_ZENITH:
        # Scene-centre solar zenith as a constant, masked to the image footprint so
        # the c-factor ratio keeps the same coverage as the observation.
        sza_target = (ee.Image.constant(
            ee.Number(90).subtract(ee.Number(image.get('SUN_ELEVATION'))))
            .multiply(PI / 180.0).updateMask(sza.mask()))
    else:
        sza_target = sza

    out = image
    for b in bands:
        target   = _brdf_reflectance(b, sza_target, zero, zero)
        observed = _brdf_reflectance(b, sza, vza, raa)
        c = target.divide(observed)
        out = out.addBands(image.select(b).multiply(c).rename(b), None, True)

    return out


# ----------------------------------------------------------------------------
# bandpass transform
# ----------------------------------------------------------------------------

def apply_tm_to_etm(image, bands=None):
    """
    India-derived TM -> ETM+ continuity transform (config.TM_TO_ETM), applied
    to L4/L5 only, AFTER BRDF and BEFORE the ETM+ -> OLI step -- the exact
    point in the chain the transform was derived at. Intercepts are already in
    the x10000 working space.
    """
    bands = bands or C.CORE_BANDS
    out = image
    for b in bands:
        k = C.TM_TO_ETM[b]
        adj = (image.select(b)
               .multiply(k['slope'])
               .add(k['intercept'])
               .rename(b))
        out = out.addBands(adj, None, True)
    return out


def apply_bandpass(image, bands=None):
    """
    Roy et al. (2016) ETM+ -> OLI continuity transform, per band linear.

        OLI = intercept + slope * ETM+

    TM is treated as ETM+. Applied AFTER BRDF, matching HLS's order.

    Coefficients in config are expressed for 0-1 reflectance; the intercept is
    rescaled here for the 0-10000 integer working space.
    """
    bands = bands or C.CORE_BANDS
    out = image
    for b in bands:
        k = C.ETM_TO_OLI[b]
        adj = (image.select(b)
               .multiply(k['slope'])
               .add(k['intercept'] * C.REFL_SCALE)
               .rename(b))
        out = out.addBands(adj, None, True)
    return out


# ----------------------------------------------------------------------------
# Era A entry point
# ----------------------------------------------------------------------------

def normalise_era_a(collection, do_brdf=True, do_bandpass=True):
    """
    Apply BRDF then bandpass to an Era A collection.

    Both are switchable so the pilot can isolate their individual effects --
    see config.PILOT_RUNS.
    """
    if not do_brdf and not do_bandpass:
        return collection

    def _one(image):
        img = ee.Image(image)
        if do_brdf:
            img = apply_brdf(img)
        if do_bandpass:
            # Chain: TM -> ETM+ (India-derived, L4/L5 only), then ETM+ -> OLI
            # (Roy RMA, L4/L5/L7). OLI is already the reference basis --
            # transforming it would corrupt data that needs no correction.
            # Decided per image because a single collection can mix sensors.
            is_tm5 = ee.List(list(C.TM_SENSORS)).contains(image.get('sensor'))
            img = ee.Image(ee.Algorithms.If(is_tm5, apply_tm_to_etm(ee.Image(img)), img))
            is_tm = ee.List(list(C.BANDPASS_SENSORS)).contains(image.get('sensor'))
            img = ee.Image(ee.Algorithms.If(is_tm, apply_bandpass(ee.Image(img)), img))
        return ee.Image(img).copyProperties(image, image.propertyNames())

    return collection.map(_one)


def warn_if_unverified():
    """Loud reminder that the published coefficients have not been checked."""
    msgs = []
    if not C.BRDF_COEFFS_VERIFIED:
        msgs.append('BRDF_COEFFS not verified against Roy et al. (2016) RSE 185')
    if not C.BANDPASS_COEFFS_VERIFIED:
        msgs.append('ETM_TO_OLI not verified -- check values AND direction')
    for m in msgs:
        print('  !! {}'.format(m))
    return msgs


# ---------------------------------------------------------------------------
# STATIC PER-CELL ALIGNMENT OFFSETS (register C31, 2026-08-16)
# ---------------------------------------------------------------------------
_ALIGN_TABLE_STATE = {'probed': False, 'table_exists': False, 'parts': None,
                      'rows': {}}
# ALL SIX bands applied (owner ruling 2026-08-16, choice A): the visible-only
# rule of 2026-08-10 was made for the retired per-year median estimator,
# whose nir difference measured phenology; the pair method compares the
# same ground within two days on greenness-stable pixels, so its infrared
# residuals are sensor (plus day-weather) and are corrected like the rest.
# Watch-item after the fleet: infrared neighbour coherence (sample: nir
# -90/-18/-81/-33 across four neighbours vs ~15 spread in the visible);
# if noisy nationally, switch infrared to the region row (reader-side).
ALIGN_BANDS_APPLIED = tuple(C.CORE_BANDS)


def _land_mask():
    """1 on land inside the official India boundary (owner rule
    2026-08-16: the BOUNDARY, not the regions outline). Shared with the
    slope-correction fits (terrain.india_land_mask)."""
    from . import terrain
    return terrain.india_land_mask()


def align_pairs_stack(region, cell, years=None):
    """Every L7/L5 photo pair within ALIGN_MAX_DT_DAYS over the cell in
    the pooled window, as one FeatureCollection of sampled points. Each
    point carries d_<band> = L7 minus L5 (both photos strict-masked,
    BRDF-normalised and on the modern colour basis -- the exact quantity
    the offset is later applied to) on greenness-stable pixels
    (|dNDVI| < ALIGN_NDVI_STABLE). Same recipe as the national transform
    derivation (an internal one-off script, not part of this release;
    see docs/evidence_sensor_harmonisation.md)."""
    from . import sources, masking
    y0, y1 = years or C.ALIGN_PAIR_YEARS
    bands = list(C.CORE_BANDS)
    dt_ms = C.ALIGN_MAX_DT_DAYS * 86400000
    out = None
    for year in range(int(y0), int(y1) + 1):
        coll = sources.era_a_collection(region, year, ('l5', 'l7'))
        coll = masking.apply_mask(coll, 'A', mode='strict')
        coll = normalise_era_a(coll, True, True)
        l7 = coll.filter(ee.Filter.eq('sensor', 'l7'))
        l5 = coll.filter(ee.Filter.inList('sensor', list(C.TM_SENSORS)))
        join = ee.Join.inner('l7', 'l5').apply(
            l7, l5, ee.Filter.maxDifference(
                dt_ms, leftField='system:time_start',
                rightField='system:time_start'))

        def _sample(f):
            a = ee.Image(ee.Feature(f).get('l7'))
            b = ee.Image(ee.Feature(f).get('l5'))
            inter = (a.geometry().intersection(b.geometry(), 100)
                     .intersection(region, 100))
            stable = (a.normalizedDifference(['nir', 'red'])
                      .subtract(b.normalizedDifference(['nir', 'red']))
                      .abs().lt(C.ALIGN_NDVI_STABLE))
            # LAND ONLY (owner, 2026-08-16): the cell rectangle includes
            # sea for coastal cells and both sensors read water as dark
            # and "stable", so sea pixels were being sampled. Keep only
            # land inside the INDIA BOUNDARY (not the regions outline)
            # and drop water pixels (water index > 0 on the L7 photo) --
            # inland water is dark and uninformative for a land sensor
            # comparison too.
            land = (_land_mask()
                    .And(a.normalizedDifference(['green', 'swir1'])
                          .lte(C.ALIGN_WATER_MNDWI_MAX)))
            diff = (a.select(bands).subtract(b.select(bands))
                    .rename(['d_' + x for x in bands])
                    .updateMask(stable.And(land)).toFloat())
            # 3x3 block mean at 30 m, sampled at ALIGN_SAMPLE_SCALE_M:
            # sub-pixel co-registration jitter averages out over the
            # block on homogeneous ground (C31-addendum, choice A.2)
            diff = diff.focalMean(1, 'square', 'pixels')
            pts = diff.sample(region=inter, scale=C.ALIGN_SAMPLE_SCALE_M,
                              numPixels=C.ALIGN_POINTS_PER_PAIR, seed=11,
                              dropNulls=True, tileScale=4)
            pair_id = ee.String(a.get('system:index')).cat('|') \
                .cat(ee.String(b.get('system:index')))
            return pts.map(lambda p: ee.Feature(p).set('pair', pair_id))

        fc = ee.FeatureCollection(join.map(_sample)).flatten()
        out = fc if out is None else out.merge(fc)
    return out


def _robust_mean(pts, col):
    """Robust cell offset for column col: MAD outlier rejection across
    POINTS (drop points farther than ALIGN_MAD_K * 1.4826 * MAD from the
    median), then the mean. DECIDED 2026-08-16 by a pre-registered
    three-arm split-half run on the four sample cells (score = odd/even
    disagreement + held-out bias, land-only yardstick): point-level trim
    58.4 beat across-pair weighted 62.1 and across-pair equal-weight
    88.5 -- so the across-pair variants (C31-addendum-2a) are RETIRED;
    the equal-weight one was the round-2 regression. Returns
    (mean, n_points_used) as server-side numbers; nulls when empty."""
    med = ee.Number(ee.Algorithms.If(
        pts.size().gt(0),
        pts.reduceColumns(ee.Reducer.median(), [col]).get('median'), 0))
    dev = pts.map(lambda f: ee.Feature(f).set(
        '_dev', ee.Number(ee.Feature(f).get(col)).subtract(med).abs()))
    mad = ee.Number(ee.Algorithms.If(
        pts.size().gt(0),
        dev.reduceColumns(ee.Reducer.median(), ['_dev']).get('median'), 0))
    # a zero MAD (all points identical) must not reject everything
    tol = mad.multiply(1.4826).multiply(C.ALIGN_MAD_K).max(1e-6)
    inl = dev.filter(ee.Filter.lte('_dev', tol))
    mean = inl.reduceColumns(ee.Reducer.mean(), [col]).get('mean')
    return mean, inl.size()


def _cell_region_id(region):
    """The classification region with the LARGEST OVERLAP with the cell
    (region_id), or -1 if none touches it. Owner 2026-08-16: the earlier
    cell-CENTRE lookup put coastal cells at sea (region -1) -- exactly the
    thin cells that need the region fallback."""
    regs = ee.FeatureCollection(C.REGIONS_ASSET).filterBounds(region)
    scored = regs.map(lambda f: ee.Feature(f).set(
        '_ov', ee.Feature(f).geometry().intersection(region, 100).area(100)))
    best = scored.sort('_ov', False).first()
    return ee.Number(ee.Algorithms.If(best, ee.Feature(best).get('region_id'),
                                      -1))


def align_offsets_row(region, cell, years=None):
    """ONE table row for the cell: MAD-robust mean L7-minus-L5 per band
    over all land-only pair points (90 m block means); n_pts_raw (land
    points sampled), n_pts (points surviving the trim, min over the
    applied bands), n_pairs (distinct photo pairs), region
    (classification region id), the
    window and the fingerprint. ok=1 when the offsets exist and every
    APPLIED band's offset is inside +/-ALIGN_OFFSET_MAX (a larger number
    is not a sensor artefact -- haze/phenology -- and must not be
    applied). Thinness (pairs/points) is judged by the READER, which
    then falls back to the region. Dummy point geometry."""
    y0, y1 = years or C.ALIGN_PAIR_YEARS
    bands = list(C.CORE_BANDS)
    pts = align_pairs_stack(region, cell, (y0, y1))
    props = {'cell': cell, 'kind': 'cell', 'y0': int(y0), 'y1': int(y1),
             'n_pairs': pts.aggregate_count_distinct('pair'),
             'region': _cell_region_id(region),
             'fp': _align_fingerprint()}
    n_used = []
    within = ee.Number(1)
    for b in bands:
        mean, n = _robust_mean(pts, 'd_' + b)      # n = points surviving
        props['off_' + b] = mean
        props['n_' + b] = n
        if b in ALIGN_BANDS_APPLIED:
            n_used.append(n)
            v = ee.Number(ee.Algorithms.If(mean, mean, 1e9))
            within = within.multiply(v.abs().lte(C.ALIGN_OFFSET_MAX))
    props['n_pts_raw'] = pts.size()                 # raw land points
    props['n_pts'] = ee.List(n_used).reduce(ee.Reducer.min())   # surviving
    props['ok'] = within
    return ee.Feature(ee.Geometry.Point([0, 0]), props)


def _align_fingerprint():
    import hashlib
    parts = ('align_v4_india_point', str(C.ALIGN_PAIR_YEARS), str(C.ALIGN_MAX_DT_DAYS),
             str(C.ALIGN_POINTS_PER_PAIR), str(C.ALIGN_NDVI_STABLE),
             str(C.ALIGN_OFFSET_MAX), str(C.ALIGN_MAD_K),
             str(C.ALIGN_SAMPLE_SCALE_M), str(C.ALIGN_WATER_MNDWI_MAX),
             str(sorted(C.TM_TO_ETM.items())), str(C.BANDPASS_COEFFS_VERIFIED))
    return hashlib.sha1('|'.join(parts).encode()).hexdigest()[:12]


def export_align_offsets(cell, region, years=None):
    """BATCH job: this cell's offset row -> a one-row part table in
    config.ALIGN_OFFSETS_PARTS. Roll parts into the big table with
    the internal roll-up script (not part of this release)."""
    for aid in (C.ALIGN_OFFSETS_ROOT, C.ALIGN_OFFSETS_PARTS):
        try:
            ee.data.getAsset(aid)
        except Exception:
            ee.data.createAsset({'type': 'Folder'}, aid)
    row = align_offsets_row(region, cell, years)
    task = ee.batch.Export.table.toAsset(
        collection=ee.FeatureCollection([row]),
        description='align_offsets_{}'.format(cell.replace('-', '_')),
        assetId='{}/{}'.format(C.ALIGN_OFFSETS_PARTS, cell))
    task.start()
    print('queued align offsets {} -> {}/{} (task {})'.format(
        cell, C.ALIGN_OFFSETS_PARTS, cell, task.id))
    return task


def region_rows(fc):
    """STORED REGION ROWS (owner 2026-08-16): for each classification
    region 1..7 (0 is a demo region, left out), one row cell='REGION:<id>'
    holding the per-band MEDIAN of that region's SOUND cell rows (ok, >=
    ALIGN_MIN_PAIRS pairs, >= ALIGN_MIN_PTS points, current fp). ok=1 when
    >= ALIGN_MIN_CELLS_REGION cells contribute. Called by the roll-up on
    the merged table, so region rows are recomputed from whatever cell
    rows exist at that moment (kind='region'; cell rows kind='cell')."""
    fp = _align_fingerprint()
    cells = (fc.filter(ee.Filter.eq('fp', fp))
               .filter(ee.Filter.neq('kind', 'region'))
               .filter(ee.Filter.eq('ok', 1))
               .filter(ee.Filter.gte('n_pairs', C.ALIGN_MIN_PAIRS))
               .filter(ee.Filter.gte('n_pts', C.ALIGN_MIN_PTS)))
    bands = list(C.CORE_BANDS)

    def _one(rid):
        rid = ee.Number(rid)
        sub = cells.filter(ee.Filter.eq('region', rid))
        n = sub.size()
        props = {'cell': ee.String('REGION:').cat(rid.format('%d')),
                 'kind': 'region', 'region': rid, 'n_cells': n,
                 'ok': n.gte(C.ALIGN_MIN_CELLS_REGION), 'fp': fp}
        for b in bands:
            props['off_' + b] = ee.Algorithms.If(
                n.gt(0),
                sub.reduceColumns(ee.Reducer.median(), ['off_' + b])
                   .get('median'), None)
        return ee.Feature(ee.Geometry.Point([0, 0]), props)

    return ee.FeatureCollection(ee.List.sequence(1, 7).map(_one))


def _align_probe():
    st = _ALIGN_TABLE_STATE
    if not st['probed']:
        st['probed'] = True
        try:
            ee.data.getAsset(C.ALIGN_OFFSETS_TABLE)
            st['table_exists'] = True
        except Exception:
            st['table_exists'] = False
        try:
            listing = ee.data.listAssets({'parent': C.ALIGN_OFFSETS_PARTS})
            st['parts'] = [a['name'] for a in listing.get('assets', [])]
        except Exception:
            st['parts'] = []
    return st


def _align_rows():
    """The whole offsets table (big table + staged parts) as
    {cell: props}, read ONCE per process (~282 small rows, no geometry).
    Only rows with the current fingerprint are kept."""
    st = _align_probe()
    if st.get('all') is not None:
        return st['all']
    fp = _align_fingerprint()
    fc = ee.FeatureCollection([])
    if st['table_exists']:
        fc = ee.FeatureCollection(C.ALIGN_OFFSETS_TABLE)
    for pid in st['parts']:
        fc = fc.merge(ee.FeatureCollection(pid))
    cols = ['cell', 'kind', 'ok', 'n_pairs', 'n_pts', 'n_cells', 'region',
            'fp'] + ['off_' + b for b in C.CORE_BANDS]
    rows = {}
    try:
        feats = fc.filter(ee.Filter.eq('fp', fp)) \
                  .select(cols, None, False).getInfo()['features']
        for f in feats:
            p = f['properties']
            rows[p['cell']] = p
    except Exception as e:
        print('    tm-l7 align: offsets table unreadable ({})'
              .format(str(e)[:60]))
    st['all'] = rows
    return rows


def _row_sound(p):
    """A cell row usable on its own: ok, enough photo pairs, enough
    surviving points, and offsets present."""
    return p.get('kind') != 'region' and bool(p.get('ok')) \
        and (p.get('n_pairs') or 0) >= C.ALIGN_MIN_PAIRS \
        and (p.get('n_pts') or 0) >= C.ALIGN_MIN_PTS \
        and all(p.get('off_' + b) is not None for b in ALIGN_BANDS_APPLIED)


def align_offsets_for(cell, verbose=True, force=False):
    """The cell's APPLIED offsets, one per core band, and their source:
    the cell's own row when sound; else the MEDIAN of the sound rows of
    the cell's classification region (>= ALIGN_MIN_CELLS_REGION of them,
    C31-addendum A.3); else None (nothing applied). Cached per process.

    RETIRED 2026-08-21: with config.ALIGN_APPLY off this returns None for
    every cell, so nothing is applied anywhere. The full reasoning and the
    measurements sit with the flag in config.py. `force=True` bypasses the
    switch and is for DIAGNOSTICS ONLY -- the offsets map viewer still needs
    to read the table it is drawing.
    """
    if not getattr(C, 'ALIGN_APPLY', True) and not force:
        if verbose:
            print('    tm-l7 align: RETIRED (config.ALIGN_APPLY off) '
                  '-> nothing applied')
        return None
    st = _align_probe()
    if cell in st['rows']:
        return st['rows'][cell]
    rows = _align_rows()
    vals, source = None, None
    p = rows.get(cell)
    if p is not None and _row_sound(p):
        vals = [float(p['off_' + b]) for b in ALIGN_BANDS_APPLIED]
        source = 'cell ({} pairs, {} pts)'.format(p['n_pairs'], p['n_pts'])
    else:
        rid = p.get('region') if p is not None else None
        if rid is not None and rid != -1:
            stored = rows.get('REGION:{}'.format(int(rid)))
            if stored is not None and stored.get('ok') and \
                    all(stored.get('off_' + b) is not None
                        for b in ALIGN_BANDS_APPLIED):
                vals = [float(stored['off_' + b]) for b in ALIGN_BANDS_APPLIED]
                source = 'REGION {} stored row ({} cells)'.format(
                    int(rid), stored.get('n_cells'))
            else:
                # no stored region row yet (before the first roll-up):
                # compute it from the sound cell rows on the fly
                peers = [q for q in rows.values()
                         if q.get('kind') != 'region'
                         and q.get('region') == rid and _row_sound(q)]
                if len(peers) >= C.ALIGN_MIN_CELLS_REGION:
                    vals = []
                    for b in ALIGN_BANDS_APPLIED:
                        v = sorted(float(q['off_' + b]) for q in peers)
                        vals.append(v[len(v) // 2])
                    source = 'REGION {} median of {} cells (on the fly)'.format(
                        int(rid), len(peers))
    if verbose:
        if vals is None:
            print('    tm-l7 align: no usable row for {} (cell thin/absent, '
                  'region too thin) -> nothing applied'.format(cell))
        else:
            print('    tm-l7 align offsets ({}): {}'.format(
                source, {b: round(v, 1) for b, v in
                         zip(ALIGN_BANDS_APPLIED, vals)}))
    st['rows'][cell] = vals
    return vals


def align_tm_residual(collection, region, cell=None, offsets=None,
                      measure_from=None):
    """
    Per-CELL, STATIC offset alignment of TM (L4/L5) onto ETM+ (L7),
    applied AFTER the national TM->ETM+ transform, on ALL SIX optical
    bands (ALIGN_BANDS_APPLIED; owner choice A, 2026-08-16 -- an older
    version applied blue/green/red only). RETIRED BY SWITCH: a no-op
    while config.ALIGN_APPLY is False.

    Why it exists: the national RMA line removes the India-wide mean
    difference between the sensors, but the residual varies regionally
    and SLC-off gaps decide where L7 votes in the median, so any residual
    prints as diagonal stripes in exactly the gap geometry.

    HOW THE NUMBER IS FOUND (register C31, owner ruling 2026-08-16 on a
    reviewer finding): from the cloud table config.ALIGN_OFFSETS_TABLE --
    one row per cell, the mean L7-minus-L5 difference over greenness-
    stable pixels both sensors saw within two days, pooled over
    ALIGN_PAIR_YEARS. STATIC across years. The old per-year "L7 yearly
    median minus L5 yearly median" is RETIRED: on thin-L5 years the two
    medians were different seasons and cloud luck (NC-43-X-A 2005: raw
    ~-600, clamped -150, applied = fake darkening), and a number that
    changed every year injected wobble into a change record.

    No row / row not ok / cell unknown -> NOTHING applied (loud print).
    offsets=[b,g,r] literals bypass the table (tests only).
    VISIBLE BANDS ONLY (measured 2026-08-10): a cell-wide offset on nir
    flipped the plains -8 -> +69 -- the cell-wide nir difference is
    phenology, not radiometry.
    """
    align_bands = list(ALIGN_BANDS_APPLIED)
    if offsets is None:
        if cell is None:
            print('    tm-l7 align: no cell given -> nothing applied')
            return collection
        offsets = align_offsets_for(cell)
        if offsets is None:
            return collection
    vals = [float(v) for v in offsets]
    tm = collection.filter(ee.Filter.inList('sensor', list(C.TM_SENSORS)))
    rest = collection.filter(
        ee.Filter.inList('sensor', list(C.TM_SENSORS)).Not())
    offs = ee.Image.constant(vals).rename(align_bands).toFloat()

    def _one(img):
        img = ee.Image(img)
        shifted = img.select(align_bands).add(offs)
        return ee.Image(img.addBands(shifted, None, True)
                        .copyProperties(img, img.propertyNames()))
    return ee.ImageCollection(tm.map(_one).merge(rest))
