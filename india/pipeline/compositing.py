"""
Temporal compositing over a phenological year.

Carries one amendment to the original getMosaic, confirmed in the spec:

    min / max / amp  ->  p5 / p95 / (p95 - p5)

The original amp was max - min. Extreme order statistics grow with sample size by
construction -- expected range scales as sigma * d2(n), and d2(15) ~ 3.47 against
d2(100) ~ 5.02. Between a sparse Era A year and a dense post-2016 year that inflates
amp by roughly 45 percent with no land-surface change at all, in exactly the direction
a classifier reads as "this landscape became more variable". Percentile range is
N-stable.

The dry/wet split stays percentile-based rather than date-based. India has two green
peaks (kharif ~Sep-Oct, rabi ~Jan-Feb) and two dry troughs, with timing differing
between Kerala and Punjab, so no fixed date window is valid nationally. The per-pixel
percentile method adapts automatically and degrades gracefully when observations are
few.
"""

import ee

from . import config as C


def cloud_trim(collection):
    """Blue-anchored right-clip of each pixel's annual stack (owner
    recipe FROZEN 2026-08-30; constants and rationale at
    config.CLOUD_TRIM). Maths identical to the v9-verified lab wrapper.

    PLACEMENT (owner ruling 2026-08-30, second sitting): called from
    build_mosaic UPSTREAM of both the compositor and the quarterly
    bands, so the seasonal-anatomy block is protected too. The annual
    observation counts are captured BEFORE this runs (usable_count stays
    pre-trim, the honest disclosure channel); the quarterly counts run
    AFTER, so they count the looks their own medians actually used.
    Anchor and trigger are identical wherever the trim sits: SMA and
    index stages only add bands, never touch blue.
    """
    if not C.CLOUD_TRIM:
        return collection
    coll = ee.ImageCollection(collection)
    blue = coll.select('blue')
    bp = blue.reduce(ee.Reducer.percentile([25, 75]))
    anchor = bp.select('blue_p25')
    spread = bp.select('blue_p75').subtract(anchor)
    delta = C.CLOUD_TRIM_DELTA * C.REFL_SCALE

    def _survives(i):
        return ee.Image(i).select('blue').lte(anchor.add(delta))

    n_surv = (coll.map(lambda i: _survives(i).rename('s'))
              .select('s').sum().unmask(0))
    n_tot = blue.count().unmask(0)
    min_surv = (n_tot.divide(2).ceil()
                .min(C.CLOUD_TRIM_MAX_FLOOR).max(2))
    trigger = (spread.gt(C.CLOUD_TRIM_SPREAD * C.REFL_SCALE)
               .And(n_surv.gte(min_surv)))
    return coll.map(
        lambda i: ee.Image(i).updateMask(
            trigger.Not().Or(_survives(i))))


def _snow_free_quarters(rank, percentile_band):
    """
    How many quarters of the phenological year hold at least one SNOW-FREE
    observation, 0-4. Four explicit any-observation flags, summed.

    REWRITTEN 2026-08-09: the countDistinct version counted the masked state
    as one more distinct value (+1 nearly everywhere), so the
    SNOW_FREE_MIN_QUARTERS = 2 fallback was really enforcing a one-quarter
    span. Task #7's invariant test exposed the reducer bug.
    """
    # ONE traversal emitting all four flags (efficiency audit 2026-08-12,
    # same fusion as observation_counts): four passes -> one, identical
    # values by construction.
    def _qflags(image):
        img = ee.Image(image)
        free = img.select(C.SNOW_BAND).Not()
        month = ee.Number(ee.Date(img.get('system:time_start')).get('month'))
        # +12 before the mod: EE's mod keeps the DIVIDEND'S sign, so
        # (1 - 4).mod(12) is -3, not 9 -- Jan/Feb/Mar mapped to a
        # nonexistent quarter 0 and were invisible to this count.
        # Found 2026-08-10 when ndvi_q4 came back empty (P-v2-5).
        qq = month.subtract(C.PHENO_START_MONTH).add(12).mod(12).divide(3) \
            .floor().add(1)
        base = img.select([percentile_band]).mask().And(free)
        return ee.Image.cat([
            base.And(ee.Image.constant(qq).eq(q)).rename('q{}'.format(q))
            for q in (1, 2, 3, 4)])

    return (rank.map(_qflags).max()
            .reduce(ee.Reducer.sum()).rename('q'))


def composite(collection,
              percentile_dry=C.PERCENTILE_DRY,
              percentile_wet=C.PERCENTILE_WET,
              percentile_band=C.PERCENTILE_BAND,
              range_low=C.RANGE_LOW_PCT,
              range_high=C.RANGE_HIGH_PCT,
              snow_free_stacks=True,
              stats='full'):
    """
    Reduce a masked, corrected collection to one image of seasonal statistics.

    `stats` chooses which statistics are CONSTRUCTED (register C26 ruling 7):

      'full' (default) -- everything, as always. Existing callers change
          nothing. LITE depends on this default: it calls composite() and
          selects ndvi_stdDev afterwards (config.LITE_BANDS), so stdDev must
          exist on the default path.
      'product' -- the per-band p5/p95 percentile reducer and the stdDev
          reducer are never built, matching the global stat prune (owner
          ruling 2026-08-13, C24-addendum) at the source instead of dropping
          the bands after computation. The product-path bands -- median,
          median_dry, median_wet, range, mad, and the threshold machinery --
          are identical in either mode; range is wet median minus dry median
          and never touched the percentiles.

    Whether skipping the reducers here actually saves export compute is being
    settled empirically (C26): two audit reviewers argue EE never schedules a
    reducer whose outputs are unreferenced at export time, in which case the
    drop-after-compute in build.py already cost nothing. The measured exports
    decide; this parameter exists so the experiment can be run at all.

    Note what the dry/wet split actually is: the thresholds are computed PER PIXEL
    across the whole stack, then each image is masked where its percentile band falls
    below or above them. Seasons are decided pixel by pixel, so a single acquisition
    can feed the dry stack in one place and the wet stack in another. That is a
    feature -- it tracks local phenology without assuming when the seasons occur.

    ONE RANKING DRIVES EVERY BAND. The thresholds come from NDVI alone, and each whole
    image is then kept or dropped by ITS OWN NDVI. So swir1_median_dry is not the 25th
    percentile of SWIR1 -- it is the median of SWIR1 over the least-green observations.
    Deliberate: it keeps all bands describing the same moments in time. But it makes
    the ranking band a single point of leverage over the entire product.

    Which is why snow is excluded from it. Snow sits at the bottom of every pixel's
    NDVI distribution, so above the seasonal snowline "dry" silently became
    "snow-covered" -- a different meaning from the same band name in Punjab, and at
    the Himalayan probe 63% of usable observations were snow. Thresholds are therefore
    computed on snow-free observations where there are enough of them, and snow still
    counts toward snow_count and still contributes to the plain median.

    The fallback needs two conditions because they guard different failures: a minimum
    COUNT so the percentile is stable, and a minimum QUARTER SPAN so the snow-free
    observations represent the year rather than one summer window. A pixel can have 8
    snow-free observations that all fall in August, which is enough to compute a
    percentile from and useless as a seasonal split.
    """
    if stats not in ('full', 'product'):
        raise ValueError(
            "stats must be 'full' or 'product', got {!r}".format(stats))

    bands = ee.Image(collection.first()).bandNames().remove(C.SNOW_BAND)
    stats_coll = collection.select(bands)

    rank = collection.select([percentile_band, C.SNOW_BAND])
    snow_free = rank.map(
        lambda i: ee.Image(i).updateMask(ee.Image(i).select(C.SNOW_BAND).Not())
    ).select([percentile_band])

    # Both percentiles in ONE accumulation per source (efficiency audit
    # 2026-08-12): EE's percentile reducer computes multiple percentiles in
    # a single pass, and the previous per-pct form traversed each stack
    # twice. Identical values. The snow-free observation count now rides the
    # same pass (register C26 ruling 7): combine(sharedInputs=True) tallies
    # the very inputs the percentiles accumulate, retiring the separate
    # count() traversal. combine names its output '<band>_count'; renamed
    # back to 'n', so the fallback logic reads what it always read.
    both_pcts = [int(percentile_dry), int(percentile_wet)]
    free_pcts = snow_free.reduce(
        ee.Reducer.percentile(both_pcts)
        .combine(ee.Reducer.count(), sharedInputs=True))
    n_free = free_pcts.select(
        ['{}_count'.format(percentile_band)]).rename('n')
    allo_pcts = (collection.select([percentile_band])
                 .reduce(ee.Reducer.percentile(both_pcts)))

    q_free = _snow_free_quarters(rank, percentile_band)
    use_free = (n_free.gte(C.SNOW_FREE_MIN_OBS)
                .And(q_free.gte(C.SNOW_FREE_MIN_QUARTERS)))

    def _threshold(pct):
        band = '{}_p{}'.format(percentile_band, int(pct))
        return free_pcts.select([band]).where(
            use_free.Not(), allo_pcts.select([band]))

    dry_thresh = _threshold(percentile_dry)
    wet_thresh = _threshold(percentile_wet)

    # THE STACKS MUST BE SNOW-FREE TOO, not only the thresholds (fixed
    # 2026-08-09). Snow sits at the bottom of every pixel's NDVI distribution,
    # so with thresholds alone the snow observations still pass lte(dry) and
    # flood the dry stack above the snowline: median_dry was snow reflectance,
    # and _range measured snow duration instead of vegetation amplitude --
    # "dry" meant a different thing either side of the snowline, the exact
    # trap the threshold fix was meant to close. The exclusion mirrors the
    # threshold fallback: where snow-free observations are too few or too
    # seasonal (use_free = 0), behaviour is unchanged, so thin Himalayan
    # pixels cannot end up with empty stacks. Snow still feeds the plain
    # median and snow_count -- it is a class, not noise.
    def _season_stack(cmp_fn, thresh):
        def _one(i):
            img = ee.Image(i)
            in_season = cmp_fn(img.select([percentile_band]), thresh)
            if not snow_free_stacks:        # pre-2026-08-09 behaviour, kept
                return img.updateMask(in_season)   # for regression comparison
            not_snow = img.select(C.SNOW_BAND).Not().Or(use_free.Not())
            return img.updateMask(in_season.And(not_snow))
        return collection.map(_one).select(bands)

    dry_stack = _season_stack(lambda b, t: b.lte(t), dry_thresh)
    wet_stack = _season_stack(lambda b, t: b.gte(t), wet_thresh)

    collection = stats_coll
    median = collection.reduce(ee.Reducer.median())
    median_dry = dry_stack.reduce(ee.Reducer.median()).rename(
        bands.map(lambda b: ee.String(b).cat('_median_dry')))
    median_wet = wet_stack.reduce(ee.Reducer.median()).rename(
        bands.map(lambda b: ee.String(b).cat('_median_wet')))

    # Constructed on the 'full' path only (register C26 ruling 7): the
    # product dropped p5/p95/stdDev for every quantity (C24-addendum), and
    # with stats='product' the reducers are never built rather than built
    # and discarded. See the docstring for the open question this settles.
    if stats == 'full':
        # N-stable range, replacing min/max/amp. Both percentiles in ONE
        # accumulation over the 21-band stack (efficiency audit 2026-08-12);
        # the regex selects are full-match, so _p5 cannot catch _p95.
        pcts = collection.reduce(
            ee.Reducer.percentile([range_low, range_high]))
        p_low = pcts.select('.*_p{}$'.format(range_low)).rename(
            bands.map(lambda b: ee.String(b).cat('_p{}'.format(range_low))))
        p_high = pcts.select('.*_p{}$'.format(range_high)).rename(
            bands.map(lambda b: ee.String(b).cat('_p{}'.format(range_high))))
    # Intra-annual range. NOT p95 - p5, which was retired: at the ~16 observations of
    # a thin year those percentiles sit almost on the minimum and maximum, and extremes
    # grow with sample size by construction, so the band partly measured how many looks
    # the year got. Measured spread across depth bins, sigma-scaled (Punjab / Thar):
    #
    #   p95 - p5                    74.1 / 87.6
    #   p75 - p25                  287.5 / 59.4
    #   wet median - dry median     33.6 / 34.9   <-- this
    #
    # IQR fails in Punjab because a double-cropped NDVI distribution is multi-modal,
    # so quartile boundaries sit in unstable places and jump between modes. Wet minus
    # dry wins because each end is a MEDIAN OF A QUARTILE rather than a single extreme,
    # so neither end drifts systematically with sample size -- and it is free, both
    # parents already existing.
    #
    # Named _swing since band contract v2 (owner ruling 2026-08-30): the
    # quantity is SIGNED wet-minus-dry, and '_range' misled readers into
    # expecting max-minus-min (the rename request came from exactly that
    # confusion). Was '_range' from 2026-08-13 to the fold-in; before
    # that, the _amp trap this comment used to warn about.
    seasonal_range = median_wet.subtract(median_dry).rename(
        bands.map(lambda b: ee.String(b).cat('_swing')))

    if stats == 'full':
        # Same C26-ruling-7 gate as the percentiles above.
        std = collection.reduce(ee.Reducer.stdDev())

    # Scaled median absolute deviation, as an N-robust companion to amp.
    #
    # amp is p95 - p5, and percentiles that far into the tails are only stable when
    # the stack is deep. At the ~16 observations of a thin year the 5th percentile is
    # barely distinguishable from the minimum, so amp quietly degenerates back into
    # the max-minus-min statistic it was introduced to replace -- and any sensor that
    # imposes a STRUCTURED observation count, such as SLC-off Landsat 7, prints that
    # structure straight into the band.
    #
    # MAD is a rank statistic too, but a central one: it depends on the middle of the
    # distribution rather than its tails, so it degrades gracefully as n falls. The
    # 1.4826 factor puts it on the same scale as a standard deviation for
    # well-behaved data, so it stays directly interpretable.
    #
    # Cost is one extra pass: the median must exist before the deviations can be
    # taken. Roughly twice a percentile band, and far less than fitting anything.
    median_raw = median.rename(bands)
    deviations = collection.map(
        lambda i: ee.Image(i).subtract(median_raw).abs())
    # RAW MAD, no consistency factor (owner ruling 2026-08-19). The x1.4826
    # that used to sit here put MAD on a standard-deviation scale so it could
    # be read beside amp and stdDev -- and BOTH of those left the product in
    # the 2026-08-13 stat prune, so the factor was rescaling to match a band
    # that no longer ships. It carried no information either way (a constant
    # multiplier is invisible to any classifier) and it silently assumed a
    # bell-shaped spread, which a double-cropped pixel's year is not.
    # NOT to be confused with masking.MAD_TO_SIGMA, which is the SAME number
    # doing a REAL job: the witness mask's cold threshold was tuned on a
    # standard-deviation scale, so that one is load-bearing and stays.
    mad = (deviations.reduce(ee.Reducer.median())
           .rename(bands.map(lambda b: ee.String(b).cat('_mad'))))

    # Band ORDER on the 'full' path is unchanged from before the stats
    # parameter existed; 'product' is the same sequence with the two
    # percentile blocks and stdDev absent.
    out = (median
           .addBands(median_dry)
           .addBands(median_wet))
    if stats == 'full':
        out = out.addBands(p_low).addBands(p_high)
    out = out.addBands(seasonal_range).addBands(mad)
    if stats == 'full':
        out = out.addBands(std)
    return out.addBands(dry_thresh).addBands(wet_thresh)


def quarterly_ndvi(collection):
    """
    Median NDVI per quarter of the phenological year, four bands, no further
    statistics: ndvi_q1 (Apr-Jun) .. ndvi_q4 (Jan-Mar).

    Why (recommendation SS2.6): every exported statistic is an order statistic,
    and sorting destroys sequence -- a single long kharif crop and a
    kharif-rabi double crop have IDENTICAL median/dry/wet/range/p5/p95/stdDev.
    Four points in calendar order carry peak quarter, trough quarter, number
    of green cycles and curve shape. The phenological year starts 1 April, so
    the quarter boundaries land on India's agricultural calendar for free.

    Depth caveat (SS5.13): one observation vs eight per quarter -- condition on
    quarters_present downstream. Empty quarters stay masked: honest gaps.
    """
    # ONE traversal emitting all four quarter bands (register C26 ruling 7),
    # the same fusion as _snow_free_quarters: four map+median chains over the
    # collection become one map and one median. Identical values by
    # construction -- each observation's ndvi reaches exactly the quarter
    # accumulator its date selects, and the other three bands stay masked,
    # just as the per-quarter updateMask left them.
    def _qbands(image):
        img = ee.Image(image)
        month = ee.Number(ee.Date(img.get('system:time_start')).get('month'))
        # +12 before the mod -- see _snow_free_quarters for the sign trap
        # (register C14: EE's mod keeps the dividend's sign).
        qq = month.subtract(C.PHENO_START_MONTH).add(12).mod(12).divide(3) \
            .floor().add(1)
        ndvi = img.select(['ndvi'])
        # '_median' suffix since band contract v2 (owner 2026-08-30):
        # these ARE quarterly medians, and the bare qN name hid that.
        return ee.Image.cat([
            ndvi.updateMask(ee.Image.constant(qq).eq(q))
            .rename('ndvi_q{}_median'.format(q))
            for q in (1, 2, 3, 4)])

    return collection.map(_qbands).median()


def quarterly_counts(collection):
    """
    Usable observations per phenological quarter: q1_count .. q4_count.

    Why (owner ruling 2026-08-13, C24-addendum; India-review find): the
    monsoon quarter (q2, Jul-Sep) is structurally the thinnest -- worst in
    the Ghats/NE belt where natural forest vs plantation vs tea-coffee must
    be decided -- and a quarterly NDVI built from one hazy look is
    indistinguishable from a changed one without the count beside it.
    QA/conditioning bands ONLY, never classifier features (a tree splitting
    on counts learns the sensor eras).
    """
    # ONE traversal, one count (register C26 ruling 7) -- the same fusion as
    # quarterly_ndvi above. The previous form counted the quarter-masked ndvi
    # four times over, once per quarter; counting four quarter-masked bands in
    # one pass tallies exactly the same unmasked observations per band, so the
    # values are identical.
    def _qbands(image):
        img = ee.Image(image)
        month = ee.Number(ee.Date(img.get('system:time_start')).get('month'))
        # +12 before the mod -- see _snow_free_quarters for the sign trap
        # (register C14: EE's mod keeps the dividend's sign).
        qq = month.subtract(C.PHENO_START_MONTH).add(12).mod(12).divide(3) \
            .floor().add(1)
        ndvi = img.select(['ndvi'])
        return ee.Image.cat([
            ndvi.updateMask(ee.Image.constant(qq).eq(q))
            .rename('q{}_count'.format(q))
            for q in (1, 2, 3, 4)])

    return collection.map(_qbands).count().toInt16()


def add_coordinates(mosaic):
    """
    Pixel-centre longitude and latitude.

    int32, not int16: 97.4 degrees x 10000 overflows a signed 16-bit band.

    Known risk, recorded rather than hidden -- coordinate bands let a classifier learn
    place instead of spectra. That suppresses change detection, since a pixel's
    coordinates never change, and it hides training-data gaps. Spatially-blocked
    cross-validation is the only way to detect it; ordinary random-split CV will show
    the accuracy gain and conceal the cost.
    """
    ll = ee.Image.pixelLonLat().multiply(10000).toInt32()
    return mosaic.addBands(ll.select(['longitude', 'latitude'], ['lon', 'lat']))
