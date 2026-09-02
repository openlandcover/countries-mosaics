"""
Spectral mixture analysis, rebuilt 2026-08-09 to an owner-approved design
(the design pseudocode is an internal note, not part of this release;
the architecture is summarised below).

The architecture, and why the order matters:

  SCENE level     unmix UNCONSTRAINED (sumToOne=False, nonNegative=False).
                  Negatives stay for the SPREAD statistics, which need both
                  tails -- clamping censors stdDev/MAD. (CORRECTED 2026-08-13,
                  three-agent review: for the MEDIAN clamping is provably
                  neutral -- quantiles commute with monotone clamps, so
                  median(max(x,0)) == max(median(x),0); the earlier "truncating
                  biases the median" claim here was wrong. The water fix was
                  never the chop -- it was dropping sum-to-one, which
                  redistributes water's spectrum into fake GV, plus deriving
                  the ratios from medians.) No clamp, no max(0), no abs() at
                  scene level. gv/npv/soil (+rmse, diagnostic-only) and,
                  since band contract v2 (owner 2026-08-30), a TAMED
                  per-scene ndfi (fed only to the compositor's MAD -- see
                  get_fractions) survive the scene; every other quantity
                  is derived once, at composite level.

  COMPOSITE level the standard compositing reduces the raw fractions like any
                  other band (median, dry/wet medians, spread statistics on
                  UNCLAMPED inputs). Then derive_composite() applies the ONE
                  physical clamp to each median, recovers shade as the floored
                  deficit, and computes the index suite from the clamped
                  medians -- annual, dry and wet variants.

Why this kills the reservoir rail (invariant findings, defect 0): the OLD
constrained solver could not go below zero, so over water it left a speck of
positive GV, and NDFI's knife-edge (any gv > 0 with npv = soil = 0 forces
exactly +1) railed at 200 for fourteen Era A years. Unconstrained, per-scene gv
over water scatters AROUND zero, its yearly median lands at or below zero, the
composite clamp takes it to exactly 0, and the epsilon guard returns NEUTRAL --
the honest answer over water, in both eras, with no step at the join.

Index changes carried from the pseudocode, both confirmed by measurement
(findings, defect 1):
  fns  -> fnsc  shade is weighted by gvs before it counts as forest, so shaded
                forest still reads forest while water (gvs = 0) drops to
                neutral. RENAMED because it is not the published FNS.
  wefi -> veg   WEFI is algebraically 2*(gv+npv) - 1 wherever closure holds --
                the vegetation fraction in disguise, with a discontinuity above
                closure. Exported directly and honestly as veg.

Deviations from the pseudocode, each deliberate:
  - Windows: its standalone seasonal windows are replaced by this pipeline's
    phenological year + per-pixel dry/wet split; the composite-level algebra
    runs on the annual, dry and wet medians alike.
  - B1 cloud rejection: DISABLED (SMA_CLOUD_REJECT = None). With Amazonian
    endmembers it drops "surfaces too bright for the soil endmember" -- Thar
    sand, salt crust -- which is systematic bright-class data loss. Revisit
    with India-derived endmembers.
  - RMSE stays in production: it is the evidence base for the endmember work
    (misfit rises 9.6x from forest to beach).
  - No NODATA sentinel: Earth Engine masks already separate never-observed
    from measured-zero.
"""

import ee

from . import config as C


# ----------------------------------------------------------------------------
# endmembers
# ----------------------------------------------------------------------------

# Inherited Amazon-derived values, in reflectance x 10000: blue green red nir swir1 swir2.
#
# Provenance is thin: the source module cites Souza et al. (2005) -- inconsistently, as
# both RSE and JGR in the same file -- plus Adams et al. (1995) and "adapted from
# Carnegie Institution", with no DOI and no derivation script. All eight sensor keys in
# that module carry BYTE-IDENTICAL matrices, Landsat 4/5/7/8/9 and all three Sentinel-2
# variants, so the per-sensor structure was never populated.
#
# These are a placeholder until Indian endmembers are derived on corrected reflectance.
# A single soil endmember cannot span Thar sand, Deccan vertisols, laterite and the
# Rann's saline flats -- all separate classes in the legend.
ENDMEMBERS_INHERITED = [
    [119.0,  475.0,  169.0,  6250.0, 2399.0, 675.0],    # GV
    [1514.0, 1597.0, 1421.0, 3053.0, 7707.0, 1975.0],   # NPV
    [1799.0, 2479.0, 3158.0, 5437.0, 7707.0, 6646.0],   # soil
    [4031.0, 8714.0, 7900.0, 8989.0, 7002.0, 6607.0],   # cloud
]

FRACTION_NAMES = ['gv', 'npv', 'soil', 'cloud']

# The three fractions that leave the scene stage; cloud is solved for (it must
# be available to absorb cloud spectra) but not carried -- with B1 disabled it
# has no consumer, and the witness mask owns cloud detection.
SCENE_FRACTIONS = ['gv', 'npv', 'soil']

ENDMEMBERS_VERIFIED = False   # set True once Indian endmembers are derived


# ----------------------------------------------------------------------------
# scene level
# ----------------------------------------------------------------------------

def get_fractions(image, endmembers=None):
    """
    Unconstrained unmixing. Adds gv/npv/soil (fraction x 10000, UNCLAMPED apart
    from the int-overflow guard) and sma_rmse (reflectance x 10000 units).

    The overflow guard at +/-SMA_OVERFLOW_CAP is NOT a physical constraint: it
    sits far outside any meaningful value and exists only so a pathological
    pixel cannot wrap an integer export. If it binds often, the endmember
    table is wrong.
    """
    endmembers = endmembers or ENDMEMBERS_INHERITED

    obs = image.select(C.CORE_BANDS)

    # sumToOne=False: shade is a zero-reflectance photometric endmember and is
    # unidentifiable inside the matrix; it is recovered as the deficit at
    # composite level. Forcing sum-to-one destroys the shade estimate.
    # nonNegative=False: negatives are signal -- see module docstring.
    fractions = (obs.unmix(endmembers, sumToOne=False, nonNegative=False)
                 .rename(FRACTION_NAMES))

    # Reconstruction residual against the observed spectrum -- the diagnostic
    # the original threw away, and the evidence base for the endmember task.
    recon = ee.Image(0)
    for i, band in enumerate(C.CORE_BANDS):
        contrib = ee.Image(0)
        for j, name in enumerate(FRACTION_NAMES):
            contrib = contrib.add(
                fractions.select(name).multiply(endmembers[j][i]))
        recon = recon.add(obs.select(band).subtract(contrib).pow(2))
    rmse = recon.divide(len(C.CORE_BANDS)).sqrt().rename('sma_rmse')

    scaled = (fractions.select(SCENE_FRACTIONS)
              .clamp(-C.SMA_OVERFLOW_CAP, C.SMA_OVERFLOW_CAP)
              .multiply(C.REFL_SCALE).toFloat())

    # Per-scene lit sum, carried ONLY so the compositor's MAD pass can
    # measure shade's wobble (shade = 1 - sum, so MAD(shade) == MAD(sum)).
    # Every other lit_* statistic is pruned in build.py.
    lit = scaled.reduce(ee.Reducer.sum()).rename('lit').toFloat()

    # Per-scene ndfi, carried ONLY so the compositor's MAD pass can
    # measure its wobble (band contract v2, owner ruling 2026-08-30:
    # ndfi_mad ships -- more outlier-robust than the swing). The C24
    # review (2-of-3) warned per-scene ratios from unconstrained
    # fractions have wild tails; three tamings answer it here: fractions
    # clamped to [0,1] first, the NDFI_DENOM_FLOOR damps speck ratios,
    # the result is clamped to the legal 0-200 -- and MAD itself is a
    # central rank statistic, blind to whatever the tails still do.
    # LEVEL bands remain derived from medians (design unchanged); every
    # per-scene-ndfi composite level is overwritten in derive_composite.
    fr01 = (fractions.select(SCENE_FRACTIONS).clamp(0, 1))
    s_gv, s_npv, s_soil = (fr01.select(b) for b in SCENE_FRACTIONS)
    s_sum = s_gv.add(s_npv).add(s_soil)
    s_gvs = s_gv.divide(s_sum.max(C.SMA_EPS))
    s_npvsoil = s_npv.add(s_soil)
    s_ndfi = (s_gvs.subtract(s_npvsoil)
              .divide(s_gvs.add(s_npvsoil).max(C.NDFI_DENOM_FLOOR))
              .add(1).multiply(C.NDFI_SCALE).clamp(0, 200)
              .rename('ndfi').toFloat())

    return (image.addBands(scaled).addBands(lit)
            .addBands(s_ndfi).addBands(rmse.toFloat()))


def apply_sma(collection, endmembers=None):
    """Raw fractions on every image. Indices happen after compositing."""
    def _one(image):
        img = get_fractions(ee.Image(image), endmembers)
        return img.copyProperties(image, image.propertyNames())
    return collection.map(_one)


# ----------------------------------------------------------------------------
# composite level
# ----------------------------------------------------------------------------

def _water_refused(year=None, mosaic=None, region=None):
    """
    1 where the independent water map calls the pixel water (JRC occurrence
    >= WATER_OCCURRENCE_MIN percent of observed months). Review find
    2026-08-13: the shade gate was calibrated on CLEAR reservoirs (~0.99
    shade); turbid monsoon water is brighter and can duck under 0.8 with a
    residual fraction speck -- the knife-edge configuration. The water map is
    evidence independent of the unmix it guards. unmask(0): never-observed
    pixels are not water.

    Years past the end of the JRC record repeat the last available
    window (the uniform rule below; the old DSWx/mndwi supplements are
    retired).
    """
    # THE UNIFORM RULE, ALL YEARS (owner rulings 2026-08-26; rationale at
    # config GSW_WATER_FRACTION_MIN): over a THREE-pheno-year moving
    # window centred on the mosaic year (Apr y-1 -> Mar y+2), refused
    # when water in >= half the months JRC actually OBSERVED, needing
    # >= 3 observed months. The 3-year window is the owner's guard
    # against thin years: pheno 2010 held ZERO observed months over the
    # Kali reach and the single-year rule leaked 100% of the cell's
    # definite water; the moving window cuts that to 0.3 km2. Monthly
    # maps: v1.4 to Dec 2021, v1.5 continuation 2022-2024; band 'water'
    # in both, 0 = not observed, 1 = not water, 2 = water. Years past
    # the record repeat the last window.
    if year is None:
        # lab calls with no year: the old static multi-decade rule
        return (ee.Image(C.WATER_OCCURRENCE_ASSET).select('occurrence')
                .unmask(0).gte(C.WATER_OCCURRENCE_MIN))
    y = min(int(year), C.GSW_LAST_YEAR)
    monthly = (ee.ImageCollection(C.GSW_MONTHLY_V14)
               .merge(ee.ImageCollection(C.GSW_MONTHLY_V15))
               .filter(ee.Filter.Or(
                   ee.Filter.And(ee.Filter.eq('year', y - 1),
                                 ee.Filter.gte('month', C.PHENO_START_MONTH)),
                   ee.Filter.eq('year', y),
                   ee.Filter.eq('year', y + 1),
                   ee.Filter.And(ee.Filter.eq('year', y + 2),
                                 ee.Filter.lt('month', C.PHENO_START_MONTH)))))
    wet = (monthly.map(lambda i: ee.Image(i).select([0]).eq(2))
           .sum().unmask(0).rename('wet'))
    obs = (monthly.map(lambda i: ee.Image(i).select([0]).gt(0))
           .sum().unmask(0).rename('obs'))
    return (obs.gte(C.GSW_WATER_MIN_OBS)
            .And(wet.divide(obs.max(1)).gte(C.GSW_WATER_FRACTION_MIN)))


def _stamp_codes(img, water, snow):
    """Refusal codes onto an ndfi level band: snow -20, then water -10
    on top (water wins where both)."""
    if snow is not None:
        img = img.where(snow, C.NDFI_REFUSE_SNOW)
    if water is not None:
        img = img.where(water, C.NDFI_REFUSE_WATER)
    return img


def _derive_one(mosaic, suffix, water=None, snow=None):
    """
    The pseudocode's B4-B7 for one composite variant ('', '_dry' or '_wet'):
    clamp the fraction medians, recover shade, derive ndfi.

    Scales (owner 2026-08-13, register C24): fractions and shade ship as
    WHOLE PERCENT 0-100; ndfi ships 0-200 ((value+1)*100, the legacy scale).
    Refused ndfi carries a NAMED CODE, never a blank (the RF cannot take
    blanks) -- C29 + addenda, owner rulings 2026-08-15/16: -10 = WATER
    (the three-pheno-year JRC window: water in >= half of the months
    JRC actually observed, minimum 3 observed months);
    -20 = SNOW (snow index >= 0.2 AND year temperature <= 280 K, OR
    elevation >= 5000 m); water wins where both. Level bands span exactly
    -20..200. The C24 shade>0.8 darkness test is RETIRED from the refusal
    (it refused shaded Himalayan forest; kept only for bare lab calls).
    Pixels with no observations at all in the variant stay masked, like
    every other band in the product.
    """
    # ndfi refusal codes (C29 + addenda, owner rulings 2026-08-15/16):
    #   -10  WATER -- the three-pheno-year JRC window shows water in
    #        >= half of the OBSERVED months (minimum 3 observed)
    #   -20  SNOW  -- snow index >= 0.2 AND year temperature <= 280 K,
    #        OR elevation >= 5000 m
    # Water wins where both apply. Level bands span exactly -20..200.
    src = ['gv_median' + suffix, 'npv_median' + suffix, 'soil_median' + suffix]
    fr = (mosaic.select(src, ['gv', 'npv', 'soil'])
          .divide(C.REFL_SCALE).clamp(0, 1))
    gv, npv, soil = (fr.select(b) for b in ('gv', 'npv', 'soil'))

    summed = gv.add(npv).add(soil)
    # Floor, NOT abs(): abs() reports overshoot as positive shade, labelling
    # bright surfaces shadow -- and topographic correction makes overshoot
    # MORE common, exactly where that bug would fire hardest.
    shade = ee.Image(1).subtract(summed).clamp(0, 1)

    gvs = gv.divide(summed.max(C.SMA_EPS))
    npvsoil = npv.add(soil)
    # NDFI_DENOM_FLOOR, not epsilon (review find, register C24): just under
    # the gate the denominator is a sum of SPECKS and the ratio slams to +-1
    # -- a ring of fake extremes around every gated water body. A meaningful
    # floor damps speck ratios toward 0; ordinary pixels sit far above it.
    ndfi = (gvs.subtract(npvsoil)
            .divide(gvs.add(npvsoil).max(C.NDFI_DENOM_FLOOR)))

    # REFUSAL (owner rulings 2026-08-15/16, registers C29 + addenda):
    # water by the yearly map, snow by physics; the old darkness test
    # survives only for bare lab calls with no evidence supplied.
    # NAMED CODES, not one blind sentinel: refused water = -10, refused
    # snow = -20, so level bands span exactly -20..200 and the
    # classifier learns the two refusals as separate facts. Where both
    # apply (a glacial lake), water wins -- the more specific evidence.
    if water is None and snow is None:
        dark = shade.gt(C.SHADE_INDEX_MAX)
        water, snow = dark, None

    derived = ee.Image.cat([
        shade.multiply(C.SMA_PCT_SCALE).rename('shade_median' + suffix),
        # clamp to the legal 0-200 BEFORE the code stamps (measured
        # 2026-08-15: unclamped snow pixels shipped -500); snow stamps
        # first so water overrides where both apply
        (_stamp_codes(ndfi.add(1).multiply(C.NDFI_SCALE).clamp(0, 200),
                      water, snow)
         .rename('ndfi_median' + suffix)),
    ]).toFloat()

    # The exported fraction MEDIANS are the clamped versions (the single
    # physical clamp); spread statistics stay on unclamped inputs, so
    # overshoot remains recoverable at diagnostic time.
    # overwrite=True on BOTH addBands is LOAD-BEARING since the fold-in
    # (two reviewers, same find, 2026-08-30): the per-scene ndfi means
    # the compositor now emits its own ndfi_median{,_dry,_wet}; without
    # the overwrite, EE renames THESE derived bands to ndfi_median_1 and
    # the contract select ships the compositor's median-of-ratios with
    # NO refusal codes -- the exact knife-edge design this module exists
    # to prevent.
    clamped = fr.multiply(C.SMA_PCT_SCALE).rename(src).toFloat()
    return (mosaic.addBands(clamped, None, True)
            .addBands(derived, None, True))


def derive_composite(mosaic, year=None, region=None):
    """
    Post-composite derivation of the 25-band SMA family (register C24;
    ndfi_mad added by band contract v2, owner 2026-08-30):

      {gv, npv, soil, shade, ndfi} x {median, median_dry, median_wet, swing}
      + {gv, npv, soil, shade, ndfi}_mad

    Scales: fractions/shade 0-100 percent; ndfi LEVEL bands -20..200 with
    NAMED refusal codes (C29 + addenda: -10 = water, three-pheno-year
    JRC window, >= half of OBSERVED months, min 3; -20 = snow, index >= 0.2
    AND year <= 280 K, OR elevation >= 5000 m; water wins where both);
    ranges (wet - dry) SIGNED, -100..100 and -200..200; MAD in percent
    points 0-100. ndfi_range keeps SMA_SENTINEL and obeys the
    BOTH-PARENTS rule: sentinel unless dry AND wet are both REAL (>= 0)
    -- never a half-real subtraction, and never arithmetic on codes.

    Overwrites the compositor's raw-scale gv/npv/soil _swing and _mad bands
    with the percent-scale versions; shade's wobble comes from the per-scene
    lit sum (MAD(1 - sum) == MAD(sum)).

    ndfi_mad SHIPS since band contract v2 (owner ruling 2026-08-30,
    superseding the C24 "no per-scene ndfi" stance recorded here before):
    the wobble comes from the compositor's MAD over the tamed per-scene
    ndfi (see get_fractions -- clamped fractions, denominator floor,
    0-200 clamp; MAD itself is tail-robust, which answers the C24
    wild-tails objection). Refused pixels carry the same named codes as
    the levels (-10 water, -20 snow -- legal in a mad band, whose real
    values are >= 0). Level bands stay derived from medians, unchanged.
    """
    water = _water_refused(year, mosaic, region)
    # SNOW (C29-addendum): index-bright AND cold, OR above the no-forest
    # elevation. All three inputs are the mosaic's own annual bands (the
    # DEM read matches the exported elevation band's source); aspect-
    # blind by design -- shadowed northern snow is still cold.
    from . import terrain as _terrain
    # AMENDMENT 1 (2026-09-01): mndwi levels store UNSHIFTED, so the
    # stored threshold is the raw index value x REFL_SCALE (the old
    # (1 + x) form encoded the retired +1 shift).
    snow = (mosaic.select('mndwi_median')
            .gte(C.SNOW_REFUSE_NDSI_MIN * C.REFL_SCALE)
            .And(mosaic.select('tir_median')
                 .lte(C.SNOW_REFUSE_TIR_MAX_K * 10))
            .Or(_terrain.dem().gte(C.SNOW_REFUSE_ELEV_M)))
    for suffix in ('', '_dry', '_wet'):
        mosaic = _derive_one(mosaic, suffix, water, snow)

    # Swings on the final scales (renamed from _range, band contract v2).
    # Fractions and shade are always real, so a plain subtraction is
    # safe; overwrite the compositor's raw-scale versions.
    for base in ('gv', 'npv', 'soil', 'shade'):
        swing = (mosaic.select(base + '_median_wet')
                 .subtract(mosaic.select(base + '_median_dry'))
                 .rename(base + '_swing').toFloat())
        mosaic = mosaic.addBands(swing, None, True)

    wet = mosaic.select('ndfi_median_wet')
    dry = mosaic.select('ndfi_median_dry')
    # real values are >= 0; the refusal codes (-10 water, -20 snow) are
    # not parents a subtraction may touch. The SWING keeps the old -999
    # sentinel: its legal span is signed -200..200, where -10/-20 are
    # real values and would collide (config note at the code constants).
    both = wet.gte(0).And(dry.gte(0))
    ndfi_swing = (wet.subtract(dry).where(both.Not(), C.SMA_SENTINEL)
                  .rename('ndfi_swing').toFloat())
    mosaic = mosaic.addBands(ndfi_swing, None, True)

    # Wobble bands: compositor MADs are in x10000 raw-fraction units ->
    # percent points, capped to keep the 0-100 contract on out-of-model
    # pixels. shade_mad rides on the per-scene lit sum (see get_fractions).
    for b in ('gv', 'npv', 'soil'):
        mad = (mosaic.select(b + '_mad').divide(100).clamp(0, 100)
               .rename(b + '_mad').toFloat())
        mosaic = mosaic.addBands(mad, None, True)
    shade_mad = (mosaic.select('lit_mad').divide(100).clamp(0, 100)
                 .rename('shade_mad').toFloat())
    mosaic = mosaic.addBands(shade_mad)

    # ndfi_mad (band contract v2, owner 2026-08-30): the compositor's MAD
    # over the tamed per-scene ndfi arrives already in 0-200 units (mad
    # >= 0 there). Refused pixels get the SAME named codes as the level
    # bands -- a wobble computed across looks a land index refuses to
    # judge would be noise wearing a number. Snow stamps first, water
    # wins where both, mirroring _stamp_codes.
    ndfi_mad = _stamp_codes(
        mosaic.select('ndfi_mad').clamp(0, 200), water, snow)
    return mosaic.addBands(ndfi_mad.rename('ndfi_mad').toFloat(),
                           None, True)


def warn_if_unverified():
    if not ENDMEMBERS_VERIFIED:
        print('  !! SMA endmembers are the inherited Amazon values, not derived for India')
        return ['endmembers not derived for India']
    return []
