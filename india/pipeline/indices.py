"""
Spectral indices and SMA fractions.

One storage convention (AMENDMENT 1, owner ruling 2026-09-01: the
legacy +1 shift is removed -- storage is Int16, signed, so the shift
bought nothing and created the level-vs-spread decoding trap):
  - every index stores signed: true = stored x 0.0001, never shifted
  - everything is multiplied back to x10000 integer space at the end

The band list for that final rescale is DERIVED from the index registry rather than
hardcoded. In the original it was a hand-maintained list, and an index registered in
only two of its three required places stayed silently in 0-1 space while everything
around it was scaled by 10000.

BOUNDS, ADDED 2026-08-08 AFTER THE INVARIANT-TARGET RUN
-------------------------------------------------------
Seven of the nine spectral indices were leaving their valid range in Era B, by many
orders of magnitude. Measured cell-wide on NC-43-Z-D with an exact minMax reducer, in
raw index units:

                      2005 (Era A)              2020 (Era B)
    ndvi        [ -0.198,    1.009 ]      [    -19.9,      21.6 ]
    ndmi        [ -0.239,    0.508 ]      [    -32.5,      27.5 ]
    cai         [  0.370,    1.157 ]      [     -9.4,      11.6 ]
    gcvi        [ -5.018,   20.190 ]      [    -39.1,      14.7 ]
    mndwi       [ -0.710,    0.581 ]      [ -2.87e+06,  8.76e+05 ]
    ui          [ -0.762,    0.109 ]      [ -5.24e+07,  4.70e+06 ]
    bsi         [ -0.414,    0.289 ]      [ -4.89e+06,  1.10e+07 ]

Only evi2 and savi came through clean, and they came through clean because each carries
a constant in its denominator -- +1 and +0.5 -- so it can never reach zero. That is the
whole mechanism: a ratio whose denominator can cross zero is unbounded, and in Era B it
does cross, because HLS delivers NEGATIVE surface reflectance over dark targets where
Collection 2 does not. Counted directly, the MNDWI denominator green_p5 + swir1_p5 has
zero pixels within +/-50 of zero in 2005 and 1,585 in 2020.

It hid because the MEDIAN survives -- it is a rank statistic and ignores the tails. Only
p5, p95, stdDev and range were destroyed, and only after 2013.

Two things follow. It blocks the integer band typing outright, since no integer type
holds 1e12. And ndvi is the band the whole dry/wet ranking is built on, so the damage was
not confined to the index suite.

The full account is in an internal findings note (not part of this
release).
"""

import ee

from . import config as C


# ----------------------------------------------------------------------------
# registry
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# physical bounds -- see the warning below
# ----------------------------------------------------------------------------

# Surface reflectance cannot be negative, and the Collection 2 valid range tops out at
# 1.6. HLS delivers negative retrievals over dark targets where the atmospheric
# correction over-subtracts; Collection 2 does not, because its DN valid range floors at
# 7273, which maps to exactly 0.0.
#
# These bounds are applied to a COPY used only for index arithmetic. The exported
# reflectance bands keep their original values, negatives and all, because a negative
# retrieval is real information about atmospheric correction quality and clipping it
# would put a positive bias on every dark surface in the product.
REFL_FLOOR = 0.0
REFL_CEIL = 1.6

# name -> (expression, shift_by_one, (valid_min, valid_max))
# Expressions operate on 0-1 reflectance. Bounds are in RAW index units.
# shift_by_one is False for every index since AMENDMENT 1 (2026-09-01);
# the mechanism is retained so the flag's meaning stays explicit.
#
# For a normalised difference of non-negative terms the bound [-1, +1] is exact algebra,
# not a taste judgement: the numerator is a difference of the same terms that make up the
# denominator, so it can never exceed it. The clamp is an assertion that the floor above
# did its job. For the open-ended ratios -- gcvi and cai -- no such bound exists, so the
# limits there are overflow guards set far outside anything measured (gcvi reached 20.2
# and cai 1.16 in a clean Era A year), and if one of them ever binds, the input is wrong.
# THE 2026-08-10 SET (section 2.3 of an internal band recommendation
# note, not part of this release). Six ratio
# indices: five independent normalised contrasts -- the full span available
# from six optical bands -- plus evi2, kept for MapBiomas cross-collection
# continuity, not on discrimination grounds.
#
# DROPPED, with the reason, so none is silently reopened (SS3):
#   savi       superseded by tcg -- TC greenness is orthogonal to a FITTED soil
#              line, the thing SAVI's heuristic L = 0.5 was approximating
#   gcvi       exact function of ndmi and mndwi
#   ui         exact function of ndmi and ndti; also a defect-2 blow-up
#              (ui_stdDev reached 3.25e12) -- dropping removes the problem
#   bsi        exact function of the kept set once bgi supplies blue
#   hallcover  North American conifer calibration, meaningless for teak/sal;
#              output reached 859,612 (the worst typing offender); its rotation
#              of red/nir/swir2 is covered by tcb+tcg with verified provenance
#   ebbi       numerator is the ndmi pair, denominator is tir, both exported;
#              thermal does not separate built from bare in India (Thar sand
#              runs 315-319 K, hotter than most roofs); also removes the
#              S30-has-no-thermal special case
INDEX_DEFS = {
    # --- kept ----------------------------------------------------------------
    'ndvi':  ('(b("nir") - b("red")) / (b("nir") + b("red"))', False, (-1.0, 1.0)),
    # Kept for cross-collection continuity ONLY; exempt from the class-relevance
    # test and carries the full statistic set, or the continuity reason is void.
    'evi2':  ('2.5 * (b("nir") - b("red")) / (b("nir") + 2.4 * b("red") + 1)',
              False, (-1.0, 2.5)),

    # --- renamed: this is a moisture index, not a water index ---------------
    # Was 'ndwi', which is actively misleading now that a real mndwi sits beside it.
    'ndmi':  ('(b("nir") - b("swir1")) / (b("nir") + b("swir1"))', False, (-1.0, 1.0)),

    # ndti DROPPED (owner ruling 2026-08-13, second sitting). History: began
    # as legacy 'cai' (swir2/swir1), renamed+reformed to NDTI in v2; the band
    # review kept it on the swir1<->swir2 case (IGP residue cycle, built-vs-
    # bare shape); the owner then dropped it outright. swir1/swir2 medians
    # remain exported, so the contrast is derivable downstream if ever missed.

    # Open water AND snow -- algebraically identical to NDSI. The single largest
    # gap in the previous product, which carried no water index at all.
    'mndwi': ('(b("green") - b("swir1")) / (b("green") + b("swir1"))',
              False, (-1.0, 1.0)),

    # bgi DROPPED (owner ruling 2026-08-13, C24-addendum; three-agent band
    # review, all three concurring): over the Indo-Gangetic Plain a blue-green
    # slope encodes the 40-year AEROSOL trend as slow fake land change, and
    # its legend value (turbid vs clear water, laterite colour) is unrewarded
    # -- one water class, one bare class. Raw blue/green medians remain, so
    # the contrast is recoverable downstream if ever needed.
}

ALL_INDEX_BANDS = list(INDEX_DEFS) + C.TC_BANDS


# ----------------------------------------------------------------------------
# scaling
# ----------------------------------------------------------------------------

def to_reflectance(image, bands=None):
    """Optical bands from x10000 integer space to 0-1."""
    bands = bands or C.CORE_BANDS
    return image.addBands(image.select(bands).divide(C.REFL_SCALE), None, True)


def to_working(image, bands=None):
    """Back to x10000. Band list derived, never hardcoded."""
    bands = bands or (C.CORE_BANDS + ALL_INDEX_BANDS)
    present = image.bandNames().filter(ee.Filter.inList('item', bands))
    return image.addBands(image.select(present).multiply(C.REFL_SCALE), None, True)


# ----------------------------------------------------------------------------
# Tasseled Cap -- Wang et al. (2026), surface-reflectance coefficients
# ----------------------------------------------------------------------------

def add_tasseled_cap(image):
    """
    tcb / tcg / tcw from the 5-band surface-reflectance coefficients in
    config.TC_COEFFS. Computed on 0-1 reflectance, SIGNED, no +1 shift --
    unlike the ratio indices these are magnitude-bearing rotations (wetness
    runs to about -0.8; brightness to ~1.8 over snow and salt) and the signed
    range is the information.

    Linear combinations have no denominator, so they CANNOT fail the way
    seven of nine ratio indices failed in Era B (defect 2) -- no clamp needed
    beyond the storage cast.

    Routing: everything takes the L8 matrix except native L9. L5/L7 are on
    the OLI basis after our bandpass, HLS after NASA's; the TC map is linear
    and linear maps compose, so OLI-matrix-after-bandpass IS the TM matrix.
    The 'sensor' property survives pass-merging (sources.merge_passes copies
    it from the distinct feature), so per-image routing is safe here.
    """
    def _tc(coeffs):
        out = []
        for name in C.TC_BANDS:
            img = ee.Image(0)
            for band, coef in zip(C.TC_INPUT_BANDS, coeffs[name]):
                img = img.add(image.select(band).multiply(coef))
            out.append(img.rename(name))
        return ee.Image.cat(out)

    is_l9 = ee.String(image.get('sensor')).compareTo('l9').eq(0)
    tc = ee.Image(ee.Algorithms.If(
        is_l9, _tc(C.TC_COEFFS['l9']), _tc(C.TC_COEFFS['l8'])))
    return image.addBands(tc.toFloat())


# ----------------------------------------------------------------------------
# assembly
# ----------------------------------------------------------------------------

def add_indices(image):
    """
    All spectral indices, in the order the scaling conventions require.

    SMA runs before this on x10000 data (endmembers are calibrated in that space);
    the index formulas assume 0-1 reflectance. Hence divide, compute, multiply back.

    Indices are computed from a reflectance copy floored at zero, and each one is clamped
    to its valid range. See the warning below for why, and what it cost to find out.
    """
    img = to_reflectance(image)

    # The floored copy. Everything from here to the restore at the bottom is index
    # arithmetic only.
    src = img.addBands(
        img.select(C.CORE_BANDS).clamp(REFL_FLOOR, REFL_CEIL), None, True)

    for name, (expr, shift, bounds) in INDEX_DEFS.items():
        band = src.expression(expr).rename(name).clamp(*bounds)
        if shift:
            band = band.add(1)
        src = src.addBands(band)

    # Tasseled Cap on the SAME floored copy: the coefficients were derived on
    # Collection 2 L2, which floors reflectance at zero, so the floored copy is
    # the derivation domain. (TC would not blow up on negatives -- no
    # denominator -- but extrapolating outside the fit domain gains nothing.)
    src = add_tasseled_cap(src)

    # BCI and IBI per scene (owner ruling 2026-08-13: median + mad each, so
    # both must exist per observation). Already on their FINAL 0-200 scale --
    # neither is in ALL_INDEX_BANDS, so to_working leaves them alone.
    src = src.addBands(_bci_scene(src)).addBands(_ibi_scene(src))

    # Put the untouched reflectance back. Only the indices were computed on the floored
    # copy; the exported bands must keep their negatives.
    out = src.addBands(img.select(C.CORE_BANDS), None, True)

    return to_working(out)


def _bci_scene(src):
    """
    Biophysical Composition Index (Deng & Wu 2012) per scene, from the
    per-scene tasseled-cap bands: BCI = ((H+L)/2 - V)/((H+L)/2 + V), H/V/L =
    tcb/tcg/tcw normalised to [0,1]. Built positive, bare ~zero, vegetation
    negative. Normalisation uses the FROZEN national constants in
    config.BCI_NORM (a documented deviation from the paper's per-image
    min-max, which cannot be temporally consistent -- see the band sheet);
    here the TC bands are still in 0-1-reflectance units, so the x10000
    constants are scaled down. Ships (x+1)*BCI_SCALE -> 0-200.
    """
    def _norm(key):
        lo, hi = (v / C.REFL_SCALE for v in C.BCI_NORM[key])
        return src.select(key).subtract(lo).divide(hi - lo).clamp(0, 1)

    h, v, l = _norm('tcb'), _norm('tcg'), _norm('tcw')
    hl = h.add(l).divide(2)
    bci = hl.subtract(v).divide(hl.add(v).max(C.SMA_EPS)).clamp(-1, 1)
    return bci.add(1).multiply(C.BCI_SCALE).toFloat().rename('bci')


def _ibi_scene(src):
    """
    Index-based Built-up Index (Xu 2008) per scene, with one documented
    deviation: the three component indices are rescaled to [0,1] BEFORE the
    ratio, so the denominator is a sum of non-negatives and the index is
    BOUNDED -- Xu's raw form has a sign-crossing denominator, exactly the
    blow-up anatomy that destroyed ui/bsi in Era B (module header). Note for
    the record: NDBI == -NDMI (same band pair, sign flipped), so IBI adds no
    new measurement -- it axis-aligns a built-up composite the owner wants
    explicit. Ships (x+1)*BCI_SCALE -> 0-200.
    """
    def _unit(img):
        return img.clamp(-1, 1).add(1).divide(2)

    ndbi = _unit(src.expression(
        '(b("swir1") - b("nir")) / (b("swir1") + b("nir"))'))
    savi = _unit(src.expression(
        '1.5 * (b("nir") - b("red")) / (b("nir") + b("red") + 0.5)'))
    mndwi = _unit(src.expression(
        '(b("green") - b("swir1")) / (b("green") + b("swir1"))'))

    other = savi.add(mndwi).divide(2)
    ibi = (ndbi.subtract(other)
           .divide(ndbi.add(other).max(C.SMA_EPS)).clamp(-1, 1))
    return ibi.add(1).multiply(C.BCI_SCALE).toFloat().rename('ibi')
