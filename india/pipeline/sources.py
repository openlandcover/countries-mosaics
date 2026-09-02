"""
Collection building — Landsat Collection 2 Tier 1 Level-2 only
(the HLS/era-B direction was dropped 2026-08-23 and its code removed
2026-09-01; see the working notes on retired code, not part of this
release).

Output contract:
  bands  : blue green red nir swir1 swir2 tir SZA SAA VZA VAA + qa layer
  units  : reflectance x 10000, thermal Kelvin x 10
  props  : sensor, era, pass_key, system:time_start
"""

import ee

from . import config as C
from . import masking


# ----------------------------------------------------------------------------
# shared
# ----------------------------------------------------------------------------

def _pass_key(image):
    """
    Integer key identifying a satellite pass: (days since epoch) * 1000 + WRS path.

    Used for deduplicating observations. A pixel in the forward overlap of two
    adjacent ROWS of the same path is imaged once but delivered as two products;
    counting both double-counts. Adjacent PATHS are separate dates and stay distinct.
    """
    day = ee.Number(image.get('system:time_start')).divide(86400000).floor()
    path = ee.Number(image.get('WRS_PATH'))
    return day.multiply(1000).add(path)


def _tag(image, sensor, era, key=None):
    props = {'sensor': sensor, 'era': era}
    if key is not None:
        props['pass_key'] = key
    return image.set(props)


# ----------------------------------------------------------------------------
# Era A -- Landsat Collection 2, built in house
# ----------------------------------------------------------------------------

def _scale_c2(image):
    """
    C2 L2 scale factors: optical to reflectance x 10000, thermal to Kelvin x 10.

    Only the radiometric bands are cast to float. pixel_qa and radsat must stay
    integer or the bitwise mask operations downstream fail.
    """
    optical = (image.select(C.CORE_BANDS)
               .multiply(0.0000275).add(-0.2).multiply(C.REFL_SCALE).toFloat())
    thermal = (image.select('tir')
               .multiply(0.00341802).add(149.0).multiply(10).toFloat())
    return (image.addBands(optical, None, True)
            .addBands(thermal, None, True))


def era_a_collection(region, year, sensors=('l5', 'l7'), end_year=None,
                     date_range=None):
    """
    Landsat C2 T1 L2 for one phenological year, with per-pixel angle bands joined
    from the matching Level-1 product.

    Level-2 carries no angle rasters -- USGS treats acquisition geometry as belonging
    to the observation rather than the retrieval -- but system:index is preserved
    across processing levels, so the join is exact.

    date_range: narrow raw-source window (audit find 2026-08-15: a
    filter applied after per-granule preparation cannot stop the server
    walking every granule; a window at the raw catalogue query is the
    only cut that truly shrinks the job).
    """
    start, end = C.pheno_range(year, end_year)
    if date_range is not None:
        start, end = date_range
    merged = ee.ImageCollection([])

    for s in sensors:
        l2 = (ee.ImageCollection(C.ERA_A_L2[s])
              .filterDate(start, end)
              .filterBounds(region)
              .filterMetadata('CLOUD_COVER', 'less_than', C.SCENE_CLOUD_MAX))

        l1 = (ee.ImageCollection(C.ERA_A_L1[s])
              .filterDate(start, end)
              .filterBounds(region)
              .select(C.ANGLE_BANDS))

        # Inner join on system:index rather than constructing asset ids. A scene whose
        # Level-1 counterpart is missing is dropped rather than throwing mid-export.
        joined = ee.Join.inner('l2', 'l1').apply(
            l2, l1, ee.Filter.equals(leftField='system:index',
                                     rightField='system:index'))

        src, dst = C.SRC_BANDS_C2[s]

        def _prep(feature, src=src, dst=dst, sensor=s):
            image = ee.Image(ee.Feature(feature).get('l2'))
            angles = ee.Image(ee.Feature(feature).get('l1'))
            renamed = _scale_c2(image.select(src, dst))
            out = renamed.addBands(angles)
            return _tag(out.copyProperties(image, image.propertyNames()),
                        sensor, 'A', _pass_key(image))

        merged = merged.merge(ee.ImageCollection(joined.map(_prep)))

    return ee.ImageCollection(merged)


# ----------------------------------------------------------------------------
# dispatch
# ----------------------------------------------------------------------------

def c2_all_sensors(region, year, end_year=None):
    """
    Pure Landsat Collection 2 for any year, using every sensor flying that year.

    Exists to test whether HLS is needed at all. For 2013+ this pulls the SAME
    Landsat 8/9 scenes that HLS L30 is built from, so a comparison against L30 is a
    controlled test of our BRDF implementation against NASA's -- identical input,
    identical atmospheric correction, no bandpass transform on either side.
    """
    last = year if end_year is None else end_year
    sensors = tuple(s for s, (lo, hi) in C.SENSOR_YEARS.items()
                    if lo <= last and hi >= year)
    return era_a_collection(region, year, sensors, end_year)


def build(region, year, force_era=None, mode=None, end_year=None,
          date_range=None, thermal_join=None):
    """
    Collection for one (region, phenological year).

    `mode` selects the source explicitly:
        'c2'        pure Landsat Collection 2, every sensor flying that year
        (sensor tuple)  an explicit sensor set, e.g. ('l7', 'l8')
    Production is 'c2'; with no mode, the same Collection 2 chain serves.
    `force_era` and `thermal_join` are retained for signature stability;
    every source is era 'A' since the 2026-08-23 Collection-2-only ruling.
    """
    if mode == 'c2' or mode is None:
        return c2_all_sensors(region, year, end_year), 'A'
    if isinstance(mode, tuple):          # explicit sensor set, e.g. ('l7', 'l8')
        return era_a_collection(region, year, mode, end_year), 'A'
    raise ValueError(
        'unknown source mode {!r} — the HLS modes were retired with the '
        'Collection-2-only ruling (2026-08-23)'.format(mode))


def merge_passes(collection):
    """
    One image per satellite pass (task #7, 2026-08-09).

    A pixel in the forward overlap of two adjacent products of the SAME pass is
    imaged once but delivered twice. pass_key deduplicated the COUNTS long ago;
    the percentile thresholds, medians, MAD and stdDev still saw the pixel
    twice, and the depth-sensitivity work showed banding along exactly those
    overlaps. Mosaicking each pass_key group makes every physical observation
    enter every reducer exactly once.

    MUST run after the per-scene steps (masking, BRDF, topographic correction
    all need per-scene context and angles) and before the snow flag, band
    selection and compositing. The QA layer survives the mosaic, so the snow
    flag still reads per pass.
    """
    # One saveAll join, not one filter per key: the filter-per-key version
    # scanned the whole collection once per pass (~100 scans for an Era B
    # year) and pushed working 2020 graphs into the memory ceiling.
    distinct = collection.distinct('pass_key')
    joined = ee.Join.saveAll('same').apply(
        distinct, collection,
        ee.Filter.equals(leftField='pass_key', rightField='pass_key'))

    def _one(f):
        f = ee.Feature(f)
        return (ee.ImageCollection.fromImages(ee.List(f.get('same'))).mosaic()
                .copyProperties(f, ['system:time_start', 'sensor', 'era',
                                    'pass_key']))

    return ee.ImageCollection(joined.map(_one))


def observation_counts(collection, era, year):
    """
    Per-pixel provenance bands.

      usable_count     : distinct satellite passes contributing a clear observation,
                         deduplicated by pass_key so same-path adjacent rows collapse
      tir_count        : clear thermal observations, which differ from the optical
                         count because thermal comes from Landsat only
      snow_count       : clear observations the QA layer calls snow or ice. Snow is
                         retained rather than masked, so this is what separates
                         permanent ice from seasonal cover -- a single annual
                         composite cannot distinguish them
      quarters_present : how many quarters of the phenological year contributed at
                         least one clear observation, 0-4

    On quarters_present: a plain count cannot tell you whether a pixel's composite
    was built from the whole year or from one season pretending to be a year. Thirty
    observations crammed into the dry half is more misleading than eight spread
    evenly, and only this band distinguishes them.
    """
    # REWRITTEN 2026-08-09, after the pass-merge invariant test (task #7)
    # caught it: ee.Reducer.countDistinct over an ImageCollection counts the
    # MASKED state as one more distinct value, so usable_count and
    # quarters_present in every prior export are inflated by ~1 wherever any
    # image was masked at the pixel -- nearly everywhere (measured: 15 valid
    # observations, countDistinct 16). With the collection PASS-MERGED before
    # counting, a plain count is exact and no distinct-counting is needed;
    # this function now REQUIRES a pass-merged collection.
    usable = collection.select('nir').count().rename('usable_count')
    tir = collection.select('tir').count().rename('tir_count')

    snow = collection.map(
        lambda i: masking.snow_flag(ee.Image(i), era)
        .And(ee.Image(i).select('nir').mask())
        .rename('snow')).sum().rename('snow_count')

    # Quarters as four explicit any-observation flags, summed -- deterministic
    # and mask-safe, unlike countDistinct. Quarter 1 starts at the
    # phenological year's first month, so the monsoon sits almost wholly in Q2.
    # ONE traversal emitting all four flags (efficiency audit 2026-08-12):
    # the previous form mapped the whole collection once per quarter -- four
    # passes over the witness-masked stack where one suffices. Values are
    # identical: per-quarter any-observation flag -> max over the collection
    # -> sum of the four flag bands.
    def _qflags(image):
        img = ee.Image(image)
        month = ee.Number(ee.Date(img.get('system:time_start')).get('month'))
        # +12 before the mod: EE's mod keeps the dividend's sign, so
        # Jan/Feb/Mar mapped to a nonexistent quarter 0 and were invisible
        # to quarters_present. Found 2026-08-10 (P-v2-5, empty ndvi_q4).
        qq = month.subtract(C.PHENO_START_MONTH).add(12).mod(12).divide(3) \
            .floor().add(1)
        obs = img.select('nir').mask()
        return ee.Image.cat([
            obs.And(ee.Image.constant(qq).eq(q)).rename('q{}'.format(q))
            for q in (1, 2, 3, 4)])

    quarters = (collection.map(_qflags).max()
                .reduce(ee.Reducer.sum()).rename('quarters_present'))

    return ee.Image.cat([usable.toInt16(), tir.toInt16(),
                         snow.toInt16(), quarters.toInt8()])


def apply_sensor_fill(collection, year, era):
    """
    The sensor mixing policy (config, register C18): striped L7 votes only
    in the pixel-quarters the clean sensors left thin.

    Applies to MASKED collections -- "thin" must mean usable looks, not raw
    ones, so this runs right after masking. Clean = every sensor except l7;
    filler = l7. Self-handling edges, by construction rather than special
    cases: 2012 has no clean sensor, so every pixel-quarter is thin and all
    of L7 serves; L5-void regions likewise; 2017+ has no L7 in the
    collection, so the filter yields nothing and the merge is a no-op.
    Years before SLC_OFF_FIRST_YEAR pass through untouched -- healthy L7
    needs no policing.
    """
    if not C.SENSOR_FILL_ENABLED or year < C.SLC_OFF_FIRST_YEAR:
        return collection

    filler = collection.filter(ee.Filter.eq('sensor', 'l7'))
    clean = collection.filter(ee.Filter.neq('sensor', 'l7'))

    def _quarter_of(image):
        month = ee.Number(ee.Date(
            ee.Image(image).get('system:time_start')).get('month'))
        # +12 before mod: EE mod keeps the dividend's sign (register C14)
        return (month.subtract(C.PHENO_START_MONTH).add(12).mod(12)
                .divide(3).floor().add(1))

    # The ledger counts DISTINCT PASSES, not frames (C26 ruling 6). A pixel
    # in the forward overlap of two same-pass frames is imaged once but
    # delivered twice; counted per frame it read 2 where the composite sees
    # 1, so overlap strips looked adequate and L7 fill was wrongly withheld
    # there. Same one-image-per-pass principle as merge_passes, same idiom:
    # one saveAll join on pass_key, max of the per-frame flags within each
    # group, so every physical observation votes exactly once. This closes
    # the last frame-vs-pass double vote; expected effect is a slight rise
    # in L7 fill in the overlap strips of SLC-off years only (prediction
    # pre-registered in an internal predictions note, not part of this
    # release).
    clean_passes = clean.distinct('pass_key')
    clean_joined = ee.Join.saveAll('same').apply(
        clean_passes, clean,
        ee.Filter.equals(leftField='pass_key', rightField='pass_key'))

    def _pass_look(f):
        f = ee.Feature(f)
        look = (ee.ImageCollection.fromImages(ee.List(f.get('same')))
                .map(lambda i: ee.Image(i).select(['nir']).mask()
                     .toUint8().rename('n'))
                .max())
        # Frames sharing a pass_key share the day (the key encodes it), so
        # the representative's timestamp gives the group's quarter exactly.
        return look.copyProperties(f, ['system:time_start'])

    pass_looks = ee.ImageCollection(clean_joined.map(_pass_look))

    # Usable clean PASSES per pixel for each phenological quarter, as four
    # bands q1..q4. unmask(0): "no clean data at all" must read as thin,
    # not as missing.
    def _clean_count(q):
        # toUint8 on BOTH: constants carry their value-range in the type
        # (Float<0,0> vs Float<0,1> refuse to merge); a fixed-range integer
        # cast normalises them.
        flagged = pass_looks.map(lambda i: ee.Image(i)
                                 .multiply(ee.Image.constant(
                                     _quarter_of(i).eq(q))).toUint8().rename('n'))
        # Masked dummy seed: an EMPTY clean collection (2012, L5-void cells)
        # would otherwise sum to a band-less image and kill the graph -- the
        # same trap witness_stats hit. The dummy is fully masked, so it
        # contributes nothing; unmask(0) then reads "no clean data" as thin.
        seed = ee.ImageCollection([ee.Image(0).toUint8().rename('n').selfMask()])
        return ee.ImageCollection(flagged).merge(seed).sum().unmask(0)

    # Reprojection is LOAD-BEARING (config SENSOR_FILL_COUNT_SCALE): the
    # ledger is consulted by every filler pixel, and unpinned it forces each
    # tile to re-evaluate every clean granule's mask at native scale --
    # which broke Era B interactive use outright.
    coarse = ee.Projection(C.EXPORT_CRS).atScale(C.SENSOR_FILL_COUNT_SCALE)
    thin = ee.Image.cat([
        _clean_count(q).lt(C.SENSOR_FILL_MIN_OBS).rename('q{}'.format(q))
        for q in (1, 2, 3, 4)]).reproject(coarse)

    def _gate(image):
        img = ee.Image(image)
        q = _quarter_of(img)
        allowed = (thin.select('q1').multiply(q.eq(1))
                   .add(thin.select('q2').multiply(q.eq(2)))
                   .add(thin.select('q3').multiply(q.eq(3)))
                   .add(thin.select('q4').multiply(q.eq(4))))
        return img.updateMask(allowed)

    return ee.ImageCollection(clean.merge(filler.map(_gate)))
