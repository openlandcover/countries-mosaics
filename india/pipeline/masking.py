"""
Cloud, shadow and saturation masking.

Strict per-pixel masking; the scene-level cloud filter in sources.py is a
compute guard only. Production rule (owner 2026-08-30): BOTH masks
everywhere -- the plain QA-bit mask chained with the thermal witness.
Retired mechanisms (spectral cloud score, TDOM, the HLS Fmask family, the
per-year mode chooser, the era-B snow rescue) were excised 2026-09-01;
they live in the private archive's history and its working notes on
retired code (not part of this release).
"""

import ee

from . import config as C


# ----------------------------------------------------------------------------
# bit helpers
# ----------------------------------------------------------------------------

def _bit(image, pos):
    """True where the single bit at `pos` is set."""
    return image.rightShift(pos).bitwiseAnd(1).eq(1)


def _conf(image, pos, minimum=C.QA_CONF_MIN):
    """True where the two-bit confidence field at `pos` is >= `minimum`."""
    return image.rightShift(pos).bitwiseAnd(3).gte(minimum)


def _radsat_bad(image):
    """
    True where any USED optical band is saturated, with the bitmask chosen per
    sensor (config.RADSAT_BITS): thermal and unused bands do not veto optical
    pixels. Unknown sensor falls back to the conservative blanket mask.
    """
    # Null-safe: diagnostic scripts feed raw, untagged collections, and a null
    # dictionary key crashes. Missing tag -> conservative blanket mask.
    key = ee.String(ee.Algorithms.If(image.get('sensor'),
                                     image.get('sensor'), 'unknown'))
    bits = ee.Number(ee.Dictionary(C.RADSAT_BITS).get(key, 127))
    return image.select('radsat').bitwiseAnd(bits).gt(0)


# ----------------------------------------------------------------------------
# Era A -- Collection 2 QA_PIXEL
# ----------------------------------------------------------------------------

def qa_pixel_mask(image):
    """
    Cloud/shadow/snow mask from Collection 2 QA_PIXEL, using the confidence fields
    rather than only the binary flags. The binary flags alone are more permissive
    than the confidence fields and let medium-confidence cloud through.

    Returns a mask image: 1 = keep.
    """
    qa = image.select('pixel_qa')

    # Snow is NOT masked. Snow and ice are a target land-cover class, so discarding
    # those observations discards the class. What separates permanent ice from
    # seasonal cover is how OFTEN a pixel is snow, which is why snow_count is
    # exported alongside usable_count rather than the flag being thrown away.
    bad = (
        _bit(qa, C.QA_BITS['fill'])
        .Or(_bit(qa, C.QA_BITS['dilated_cloud']))
        .Or(_bit(qa, C.QA_BITS['cloud'])).Or(_conf(qa, C.QA_CONF['cloud']))
        .Or(_bit(qa, C.QA_BITS['cloud_shadow'])).Or(_conf(qa, C.QA_CONF['cloud_shadow']))
        .Or(_bit(qa, C.QA_BITS['cirrus'])).Or(_conf(qa, C.QA_CONF['cirrus']))
    )

    # Saturation in any USED optical band -- garbage reflectance, clusters at
    # cloud edges. Per-sensor bitmask (task #11): the old blanket 127 let a
    # fire-saturated TM thermal band mask the optical pixel.
    return bad.Or(_radsat_bad(image)).Not()


def snow_flag(image, era):
    """
    1 where the QA layer calls the pixel snow or ice: flag OR confidence,
    matching the cloud/shadow reads. Every production image carries
    Collection 2 QA (`era` retained for signature stability).
    """
    qa = ee.Image(image).select('pixel_qa')
    return _bit(qa, C.QA_BITS['snow']).Or(_conf(qa, C.QA_CONF['snow']))


# ----------------------------------------------------------------------------
# witness mask -- production since 2026-08-09
# ----------------------------------------------------------------------------
# Confidence fields only; every cloud/shadow flag must produce independent
# physical evidence before it masks. Rationale, thresholds and the measured
# history live with the WITNESS_* constants in config.py.

def witness_stats_hash():
    """Stamp identifying what the stats DEPEND on (C25 ladder rung 5 rule:
    version-stamp precomputed stats so a mask/config change cannot serve a
    stale history silently). The stats depend on the QA clear-sky
    definition, the statistics themselves, and the grid -- not on the
    witness thresholds, which are applied downstream in witness_mask, so
    threshold tuning never invalidates the saved file."""
    import hashlib
    parts = ('witness-stats', str(C.VERSION), 'qa_pixel_mask-v1',
             'median-mad-v1',    # owner ruling 2026-08-14 (register C27)
             str(C.WITNESS_STATS_EXPORT_SCALE_M))
    return hashlib.sha1('|'.join(parts).encode()).hexdigest()[:12]


# MAD -> spread factor: for well-behaved (normal-shaped) data the middle
# absolute wobble is 0.6745 of the standard deviation; dividing by that
# (x1.4826) makes the MAD read on the same scale the thresholds were
# tuned on.
MAD_TO_SIGMA = 1.4826


def witness_stats_image(collection):
    """The 3-band history image (tir_median / tir_mad / tir_clear_count).

    OWNER RULING 2026-08-14 (register C27): the reference is the MEDIAN
    (middle value) with the MAD (middle wobble), not mean/stdDev -- a
    middle value cannot be dragged by the few clouds that sneak through
    "clear", which was the average's weakness. tir_clear_count = how many
    plain-QA-clear looks the history rests on (the mask fails closed when
    it is thin) -- named to avoid confusion with the mosaic's tir_count,
    which counts FULLY-masked usable looks.
    """
    clear = collection.map(
        lambda i: ee.Image(i).select('tir')
        .updateMask(qa_pixel_mask(ee.Image(i))))
    # Seed with one fully-masked dummy: an EMPTY collection otherwise reduces
    # to a zero-band image and the witness crashes (found on NC-43-Z-D 2000,
    # which has no usable L5 -- and every empty pre-2000 annual would hit it).
    # The dummy is masked everywhere, so stats stay masked and count stays 0:
    # the witness then fails closed, which is the designed thin-history
    # behaviour.
    clear = clear.merge(ee.ImageCollection(
        [ee.Image(0).toFloat().rename('tir').selfMask()]))
    med = clear.reduce(
        ee.Reducer.median()
        .combine(ee.Reducer.count(), sharedInputs=True))
    median = med.select('tir_median')
    mad = (clear.map(lambda i: ee.Image(i).subtract(median).abs())
           .reduce(ee.Reducer.median()).rename('tir_mad'))
    return ee.Image.cat([
        median,
        mad,
        med.select('tir_count').rename('tir_clear_count'),
    ])


_WITNESS_ASSET_CACHE = {}


def _witness_stats_asset(cell, year):
    """The precomputed stats image for (cell, year), or None.

    Probes {collection}/{cell}_{year}, then the national INDIA_{year}.
    A wrong-stamp asset is IGNORED with a warning -- never silently used
    (a cell-scoped asset read under the wrong key would mask-fail whole
    cells closed; the stamp and the exact-id probe prevent both).
    """
    key = (cell, year)
    if key in _WITNESS_ASSET_CACHE:
        return _WITNESS_ASSET_CACHE[key]
    img = None
    if getattr(C, 'TEMPERATURE_RECORD_COLLECTION', None) and cell and year:
        for name in ('{}_{}'.format(cell, year), 'INDIA_{}'.format(year)):
            asset_id = '{}/{}'.format(C.TEMPERATURE_RECORD_COLLECTION, name)
            try:
                info = ee.data.getAsset(asset_id)
            except Exception:
                continue
            stamp = (info.get('properties', {}) or {}).get('witness_hash')
            if stamp != witness_stats_hash():
                print('witness stats asset {}: stale stamp {} != {}; '
                      'IGNORED (live compute)'.format(
                          name, stamp, witness_stats_hash()))
                continue
            img = ee.Image(asset_id)
            print('    witness stats: precomputed asset {} in use'
                  .format(name))
            break
    _WITNESS_ASSET_CACHE[key] = img
    return img


def witness_stats(collection, cell=None, year=None):
    """
    Per-pixel CLEAR-SKY thermal history: mean, std and count of `tir` over the
    observations the plain QA mask calls clear. Computed once per (cell, year).

    Reads the PRECOMPUTED asset when (cell, year) are given, the asset
    exists, and its stamp matches (C25 ladder rung 5; the deepest shared
    branch leaves the export graph). Otherwise computes live; the live
    path honours WITNESS_STATS_SCALE_M as the ladder's rung-4 grid pin
    (near-lossless, NOT number-identical -- equivalence-test before
    production use).
    """
    prep = _witness_stats_asset(cell, year)
    if prep is not None:
        stats = prep
    else:
        stats = witness_stats_image(collection)
        pin = getattr(C, 'WITNESS_STATS_SCALE_M', None)
        if pin:
            # the C15-texture / 600 m-sensor-fill precedent: pin the deep
            # branch to a coarse grid so shards stop re-evaluating it at
            # full resolution (thermal is ~100 m native)
            stats = stats.reproject(C.EXPORT_CRS, None, pin)
    # The dict keys keep their old names so witness_mask is untouched:
    # 'mean' now carries the MEDIAN, 'std' the MAD scaled to read like a
    # standard deviation (register C27). Same thresholds, sturdier centre.
    return {
        'mean':  stats.select(['tir_median']).rename('tir'),
        'std':   (stats.select(['tir_mad']).multiply(MAD_TO_SIGMA)
                  .rename('tir')),
        'count': stats.select(['tir_clear_count']).rename('tir'),
    }


def witness_mask(image, tstats):
    """
    The thermal-witness mask, for scenes carrying C2 QA + thermal.
    Returns 1 = keep.

    Cloud >= medium confidence, upheld only with the thermal witness; flagged
    pixels that look like snow are rescued (kept class). Shadow >= medium,
    upheld only where actually dark. Cirrus high-confidence only -- no witness
    can testify for a see-through cloud, and medium cirrus is the kind of
    unverifiable aggression the owner ruled out. Missing thermal fails closed:
    unmask(1) makes an unknown temperature read as cold, upholding the flag.
    """
    qa = image.select('pixel_qa')
    tir = image.select('tir')

    n_ok = tstats['count'].gte(C.WITNESS_MIN_OBS)
    z_cold = (tir.subtract(tstats['mean']).divide(tstats['std'])
              .lt(C.WITNESS_Z_THRESH).And(n_ok))
    floor = tstats['mean'].subtract(C.WITNESS_FLOOR_DROP) \
        .min(C.WITNESS_COLD_FLOOR)
    cold = (z_cold.Or(tir.lt(floor)).Or(n_ok.Not())) \
        .And(tir.lt(C.WITNESS_CLOUD_CEIL)).unmask(1)

    # SNOW RESCUE, TIGHTENED 2026-08-10 (register C17.2). NDSI + dark-SWIR1
    # cannot separate snow from ice-topped cloud -- measured: winter Himalayan
    # scenes kept up to 65% of cloud-flagged pixels, all above 3000 m, at
    # blue 4200-5400 and tir 252-263 K. An elevation gate is useless (the
    # leak IS the snow zone). The discriminator that works is the pixel's own
    # clear-sky thermal history: surface snow shares the ground's climate,
    # a cloud top is far colder than the same pixel's usual clear reading.
    # So the rescue additionally requires the pixel NOT to be anomalously
    # cold against its own history (>= clear_mean - FLOOR_DROP). Thin
    # history (n < WITNESS_MIN_OBS) fails closed: no rescue. Cost accepted:
    # genuinely fresh-snow days in extreme cold snaps may lose the rescue --
    # a few snow observations traded against structural cloud leakage.
    not_cloud_cold = (tir.gte(tstats['mean'].subtract(C.WITNESS_FLOOR_DROP))
                      .And(n_ok).unmask(0))
    snow = (image.normalizedDifference(['green', 'swir1']).gt(C.SNOW_NDSI_MIN)
            .And(image.select('swir1').lt(C.SNOW_SWIR1_MAX))
            .And(not_cloud_cold))
    dark = (image.select(['nir', 'swir1']).reduce(ee.Reducer.sum())
            .lt(C.SHADOW_DARK_SUM))

    bad = (
        _bit(qa, C.QA_BITS['fill'])
        .Or(_conf(qa, C.QA_CONF['cloud']).And(cold).And(snow.Not()))
        .Or(_conf(qa, C.QA_CONF['cloud_shadow']).And(dark))
        .Or(_conf(qa, C.QA_CONF['cirrus'], 3))
    )
    return bad.Or(_radsat_bad(image)).Not().rename('keep')


def strict_conf_mask(image):
    """
    DIAGNOSTIC COMPARATOR, not production: every confidence flag is obeyed
    unconditionally -- no witnesses, no rescues. Exists so the lab notebook
    can compare the production witness mask against obey-all-flags WITHOUT
    carrying its own masking logic (owner rule 2026-08-11: all
    mosaic-affecting code lives in pipeline/, the notebook only calls it).
    Returns 1 = keep.
    """
    qa = ee.Image(image).select('pixel_qa')
    bad = (_conf(qa, C.QA_CONF['cloud'])
           .Or(_conf(qa, C.QA_CONF['cloud_shadow']))
           .Or(_conf(qa, C.QA_CONF['cirrus'], 3)))
    return bad.Not().rename('keep')


# ----------------------------------------------------------------------------
# plain mask -- one half of the production 'both' rule
# ----------------------------------------------------------------------------
# Bits, not confidence fields, for cloud and shadow -- deliberately more
# liberal than the witness alone. Three guards ride along because they are
# free. Full rationale with the PLAIN_* constants in config.py.

def plain_qa_mask(image, sensor=None):
    """The plain mask for anything carrying Collection 2 QA. 1 = keep.

    fill | cloud bit | shadow bit ONLY where dark | cirrus at HIGH
    confidence | saturation.

    `sensor` picks the QA_RADSAT bitmask; None falls back to the
    conservative blanket mask, exactly as _radsat_bad does.
    """
    img = ee.Image(image)
    qa = img.select('pixel_qa')
    dark = (img.select(['nir', 'swir1']).reduce(ee.Reducer.sum())
            .lt(C.SHADOW_DARK_SUM))
    bad = (_bit(qa, C.QA_BITS['fill'])
           .Or(_bit(qa, C.QA_BITS['cloud']))
           .Or(_bit(qa, C.QA_BITS['cloud_shadow']).And(dark))
           .Or(_conf(qa, C.QA_CONF['cirrus'], C.PLAIN_QA_CIRRUS_MIN)))
    if C.PLAIN_QA_RADSAT:
        bad = bad.Or(_radsat_bad(img) if sensor is None
                     else img.select('radsat')
                     .bitwiseAnd(C.RADSAT_BITS.get(sensor, 127)).gt(0))
    return bad.Not().rename('keep')


def thermal_bands_from_record(cell, year):
    """tir_median / tir_mad / tir_count straight from the national
    temperature record (config.THERMAL_FROM_RECORD).

    Raises if the record is absent or stale-stamped: shipping a mosaic with
    silently empty thermal bands is the failure this replaces, so it must
    STOP with a named job rather than degrade.
    """
    rec = _witness_stats_asset(cell, year)
    if rec is None:
        raise RuntimeError(
            'thermal record for {}_{} is absent or stale-stamped; the '
            'mosaic\'s tir bands are read from it since 2026-08-19. '
            'Export it first (build.export_witness_stats).'.format(cell, year))
    return ee.Image.cat([
        rec.select('tir_median'),
        rec.select('tir_mad'),
        rec.select('tir_clear_count').rename('tir_count'),
    ])


# ----------------------------------------------------------------------------
# assembly
# ----------------------------------------------------------------------------

def apply_mask(collection, era, mode=None, cell=None, year=None):
    """
    Mask every image in a collection. Every production image carries
    Collection 2 QA + thermal (`era` retained for signature stability).

    mode='strict' swaps in the strict-confidence comparator mask --
    MEASUREMENT ONLY. Production is 'both'; mask SEMANTICS are
    owner-final (C23).
    """
    # THE MASK RULE (owner ruling 2026-08-30, superseding the 2026-08-19
    # year switch): with no explicit mode, config.MASK_RULE decides --
    # 'both' for every year, the era split abolished. An explicit mode
    # still wins, so lab comparators are untouched. No year and no mode
    # keeps the old witness default for legacy diagnostic calls
    # (apply_mask(coll, era)) that predate the cell/year plumbing.
    if mode is None:
        mode = 'witness' if year is None else C.MASK_RULE

    # 'both' (production): a look survives only if the plain QA bit AND
    # the thermal witness both keep it. Implemented as the two existing
    # paths CHAINED -- byte-identical to the measured 'both' arm
    # (docs/cloud_masking_evidence.md) and to the verified v9 lab
    # wrapper: masks compose by updateMask, so chaining IS conjunction.
    if mode == 'both':
        plained = apply_mask(collection, era, mode='plain',
                             cell=cell, year=year)
        return apply_mask(plained, era, mode='witness',
                          cell=cell, year=year)

    props = ['system:time_start', 'sensor', 'era', 'pass_key']

    if mode == 'plain':
        def _plain_qa(i, sensor):
            img = ee.Image(i)
            return (img.updateMask(plain_qa_mask(img, sensor))
                    .copyProperties(img, props))
        return collection.map(lambda i: _plain_qa(i, None))

    if mode == 'strict':
        return collection.map(
            lambda i: ee.Image(i)
            .updateMask(strict_conf_mask(ee.Image(i)))
            .copyProperties(ee.Image(i), props))

    # 'witness'
    # LOUD when the stamped history file is absent (reviewer find
    # 2026-08-30): the silent live fallback rebuilds the history
    # inside every shard — slow, memory-risky, and a subtly
    # different mask. The thermal-record step raises later anyway;
    # this warns at the point the mask itself degrades.
    if cell and year and _witness_stats_asset(cell, year) is None:
        print('    WARNING: no stamped witness history for {}_{} — '
              'the mask will LIVE-COMPUTE its thermal history '
              '(slow; export it first: build.export_witness_stats)'
              .format(cell, year))
    tstats = witness_stats(collection, cell, year)
    return collection.map(
        lambda i: ee.Image(i)
        .updateMask(witness_mask(ee.Image(i), tstats))
        .copyProperties(ee.Image(i), props))
