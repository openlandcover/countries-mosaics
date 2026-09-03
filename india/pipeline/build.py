"""
Assembly: one CIM cell, one phenological year, one variant -> one mosaic image.

Pipeline order, and why it is this order:

  mask            clean pixels are a precondition for the correction and BRDF
  topographic     physics C, before BRDF (the C2-physics order, 2026-08-23)
  BRDF            then bandpass, on the corrected reflectance
  SMA             runs in x10000 space, where the endmembers are calibrated
  indices         run in 0-1 space, hence divide then multiply back
  composite       percentile dry/wet over the phenological year
  static bands    terrain, coordinates, provenance counts
  region mask     last: clip to the union of the classification regions
"""

import os

import ee

from . import config as C
from . import sources, masking, radiometry, terrain, sma, indices, compositing


# ----------------------------------------------------------------------------
# variants
# ----------------------------------------------------------------------------

# variant -> (force_era, do_brdf, do_bandpass, do_topo, mode)
#
# PRODUCTION IS 'c2_only' (fold-in 2026-08-30): the v2 product is the
# Collection 2 Level 2 stack, every sensor flying that year, no HLS
# (owner ruling 2026-08-23) -- so 'c2_only' is the default variant of
# build_mosaic and export below. The owner's schema drops the 'variant'
# PROPERTY (one public recipe); everything else in this dict is a lab
# comparator and still callable by name.
VARIANTS = {
    # lab comparators (corrections toggled) -- workshop only; the public
    # fork ships 'c2_only' alone (owner ruling 2026-09-01)
    'nocorr':    (None, False, False, False, 'c2'),  # corrections off
    'brdf':      (None, True,  True,  False, 'c2'),  # radiometric only
    'full':      (None, True,  True,  True,  'c2'),  # everything on
    'notopo':    (None, True,  True,  False, 'c2'),  # no terrain correction

    # explicit sensor sets (lab comparators)
    'c2_l5l7':   (None, True,  True,  True,  ('l5', 'l7')),
    'c2_l7':     (None, True,  True,  True,  ('l7',)),
    'c2_l7l8':   (None, True,  True,  True,  ('l7', 'l8')),
    'c2_l8':     (None, True,  True,  True,  ('l8',)),
    'c2_l8l9':   (None, True,  True,  True,  ('l8', 'l9')),

    # PRODUCTION: the Collection 2 Level 2 stack, every sensor flying
    # that year (owner ruling 2026-08-23; HLS retired and excised)
    'c2_only':   (None, True,  True,  True,  'c2'),

    # the measured witness-vs-strict cost pair (C26 ruling 1) -- the
    # '_strict' suffix routes masking.apply_mask(mode='strict').
    # MEASUREMENT ONLY.
    'full_strict': (None, True, True, True, 'c2'),
}


_CELL_BOUNDS = {}


def cell_geometry(cell_name):
    """Buffered CIM cell. Bounds, matching the existing export convention.

    Owner rule 2026-08-16: no pipeline input lives on disk. The rectangle
    is looked up in the CIM grid ASSET (buffered GRID_BUFFER_M, then
    bounds), pulled ONCE per cell per process as literal coordinates so
    every recipe that uses it stays small (a computed geometry would ride
    into each export as a filter over the whole grid). Same expression
    that built the retired on-disk cell-bounds file (an earlier internal
    data file, not part of this release), so the numbers are identical.
    """
    ring = _CELL_BOUNDS.get(cell_name)
    if ring is None:
        cell = ee.Feature(
            ee.FeatureCollection(C.GRID_ASSET)
            .filter(ee.Filter.eq('name', cell_name)).first())
        geom = cell.geometry().buffer(C.GRID_BUFFER_M).bounds().getInfo()
        ring = geom['coordinates'][0]
        _CELL_BOUNDS[cell_name] = ring
    return ee.Geometry.Polygon([ring], 'EPSG:4326', False)


_REGIONS_MASK = {'checked': False, 'img': None}


def _painted_region_mask():
    return (ee.Image().byte()
            .paint(ee.FeatureCollection(C.REGIONS_ASSET), 1)
            .unmask(0))


def region_mask():
    """
    Final extent: the union of the classification regions (config.REGIONS_ASSET),
    painted as a mask. Owner decision 2026-08-09, superseding the previous
    land + 5 km coastal collar -- the regions layer is now the single authority
    on where the product exists, and whatever coastal margin the product needs
    is expressed there, not reconstructed here. Static across all years: a
    per-year extent would inject apparent change into a change-detection
    product.

    Reads the pre-painted raster (config.REGIONS_MASK_ASSET) when present --
    owner standing rule 2026-08-14: compute once, read forever. Probed once
    per process, live paint as the fallback (same numbers by construction;
    the asset IS the painted image, exported).
    """
    if not _REGIONS_MASK['checked']:
        _REGIONS_MASK['checked'] = True
        if getattr(C, 'REGIONS_MASK_USE_PREPARED', False):
            try:
                ee.data.getAsset(C.REGIONS_MASK_ASSET)
                _REGIONS_MASK['img'] = ee.Image(C.REGIONS_MASK_ASSET)
            except Exception:
                print('regions mask: prepared asset unreadable; '
                      'painting live')
    if _REGIONS_MASK['img'] is not None:
        return _REGIONS_MASK['img']
    return _painted_region_mask()


def export_witness_stats(cell_name, year):
    """One-time export of the clear-sky thermal history for (cell, year).

    C25 fallback ladder rung 5, machinery landed 2026-08-14: moves the
    deepest shared branch of the export graph into its own BATCH job (the
    memory regime the 876-scene interactive path cannot survive). Reads
    back automatically in masking.witness_stats via the stamped probe.
    cell_name='INDIA' exports the national annual (serves all cells --
    the C26 per-year rescope); any CIM cell name exports that cell only.
    """
    if cell_name == 'INDIA':
        # The HLS-JOIN national shape is retired (C28-addendum: cancelled
        # at 752.6 EECU-h unfinished). The DIRECT-C2 national export is
        # the production route since 2026-08-16 (owner ruling):
        return export_witness_stats_national(year)
    region = cell_geometry(cell_name)
    coll, _era = sources.build(region, year)
    stats = masking.witness_stats_image(coll)

    name = '{}_{}'.format(cell_name, year)
    try:
        ee.data.getAsset(C.TEMPERATURE_RECORD_COLLECTION)
    except Exception:
        ee.data.createAsset({'type': 'ImageCollection'},
                            C.TEMPERATURE_RECORD_COLLECTION)
    # Integers at 30 m (owner rulings 2026-08-14, register C27): median
    # and MAD are in Kelvin x10 working units, so whole numbers keep
    # 0.1 K precision -- far finer than any witness threshold needs.
    stats = ee.Image.cat([
        stats.select('tir_median').round().toInt16(),
        stats.select('tir_mad').round().toInt16(),
        stats.select('tir_clear_count').toInt16(),
    ])
    stats = stats.set({'witness_hash': masking.witness_stats_hash(),
                       'cell': cell_name, 'pheno_year': year})
    task = ee.batch.Export.image.toAsset(
        image=stats,
        description='witness_stats_{}'.format(name.replace('-', '_')),
        assetId='{}/{}'.format(C.TEMPERATURE_RECORD_COLLECTION, name),
        region=region,
        crs=C.EXPORT_CRS,
        scale=C.WITNESS_STATS_EXPORT_SCALE_M,
        maxPixels=C.EXPORT_MAX_PIXELS,
    )
    task.start()
    print('queued witness stats -> {}/{}'.format(
        C.TEMPERATURE_RECORD_COLLECTION, name))
    return task


def witness_sensors(year):
    """The thermal-carrying sensors the record is built from in that
    year: L5/L7 to 2012, L8/L9 after."""
    year = int(year)
    if year <= C.ERA_A_LAST_YEAR:
        return [s for s in ('l5', 'l7')
                if C.SENSOR_YEARS[s][0] <= year <= C.SENSOR_YEARS[s][1]]
    return [s for s in ('l8', 'l9')
            if C.SENSOR_YEARS[s][0] <= year <= C.SENSOR_YEARS[s][1]]


def export_witness_stats_national(year):
    """ONE national temperature record per year (owner ruling 2026-08-16,
    replacing the per-cell fleet: 41 exports, not 11,500).

    Why national is fine here although the 2023 attempt died: that job
    built the record THROUGH the HLS granules, each joined to its same-day
    C2 scene -- nationally that join scans a huge pool per granule and
    burnt 752 EECU-h. The record needs no HLS: it is C2 thermal + C2 QA,
    read DIRECTLY (LT05/LE07/LC08/LC09 C2 L2, same-year sensor set as
    production), so a national year is a plain per-pixel reduction over
    the scenes overlapping each shard -- the shape of the existing
    landsat_usable_pixels asset. Same ST_B10, same QA as the mosaic's
    joined thermal (a fuller population, if anything: scenes without an
    HLS granule count too). Masked to the India boundary + 20 km so sea
    and neighbours do not inflate storage. Read automatically: the reader
    probes <CELL>_<YEAR> then INDIA_<YEAR>.
    """
    year = int(year)
    start, end = C.pheno_range(year)
    land = ee.FeatureCollection(C.INDIA_ASSET).geometry()
    region = land.bounds()
    coll = ee.ImageCollection([])
    for s in witness_sensors(year):
        # per-sensor thermal band: ST_B6 on L4/5/7, ST_B10 on L8/9 (the
        # SRC_BANDS_C2 map already knows) -- plus the two QA bands the
        # clear-sky mask reads (pixel_qa AND radsat)
        src, dst = C.SRC_BANDS_C2[s]
        st_band = src[dst.index('tir')]
        c = (ee.ImageCollection(C.ERA_A_L2[s])
             .filterDate(start, end).filterBounds(region)
             .filterMetadata('CLOUD_COVER', 'less_than', C.SCENE_CLOUD_MAX)
             .select([st_band, 'QA_PIXEL', 'QA_RADSAT'],
                     ['tir', 'pixel_qa', 'radsat'])
             .map(lambda i: ee.Image(i).addBands(
                 ee.Image(i).select('tir').multiply(0.00341802).add(149.0)
                 .multiply(10).toFloat().rename('tir'), None, True)))
        coll = coll.merge(c)
    stats = masking.witness_stats_image(ee.ImageCollection(coll))
    keep = (ee.Image().byte().paint(land.buffer(20000), 1).unmask(0).gt(0))
    stats = ee.Image.cat([
        stats.select('tir_median').round().toInt16(),
        stats.select('tir_mad').round().toInt16(),
        stats.select('tir_clear_count').toInt16(),
    ]).updateMask(keep)
    stats = stats.set({'witness_hash': masking.witness_stats_hash(),
                       'cell': 'INDIA', 'pheno_year': year,
                       'sensors': ','.join(witness_sensors(year)),
                       'source': 'C2 L2 direct (no HLS join)'})
    try:
        ee.data.getAsset(C.TEMPERATURE_RECORD_COLLECTION)
    except Exception:
        ee.data.createAsset({'type': 'ImageCollection'},
                            C.TEMPERATURE_RECORD_COLLECTION)
    name = 'INDIA_{}'.format(year)
    # EXPORT REGION = the boundary POLYGON (+20 km), not its bounding
    # rectangle (owner ruling 2026-08-17): INDIA_2023 exported over the
    # rectangle cost 454.5 EECU-h -- the server computes every tile in
    # the region before the mask, and the rectangle is 2-3x the land.
    task = ee.batch.Export.image.toAsset(
        image=stats, description='witness_stats_{}'.format(name),
        assetId='{}/{}'.format(C.TEMPERATURE_RECORD_COLLECTION, name),
        region=land.buffer(20000).simplify(1000), crs=C.EXPORT_CRS,
        scale=C.WITNESS_STATS_EXPORT_SCALE_M,
        maxPixels=C.EXPORT_MAX_PIXELS)
    task.start()
    print('queued NATIONAL witness stats {} (sensors {}) -> {}/{} (task {})'
          .format(year, witness_sensors(year), C.TEMPERATURE_RECORD_COLLECTION,
                  name, task.id))
    return task


def export_region_mask():
    """One-time export of the painted regions union as a 30 m byte raster.

    Run once, ever (re-run only if the regions layer itself changes, with a
    version bump in config.REGIONS_MASK_ASSET). India bounds from the
    boundary asset; unmasked zeros ride along so updateMask semantics match
    the live paint exactly.
    """
    india = ee.FeatureCollection(C.INDIA_ASSET).geometry().bounds()
    task = ee.batch.Export.image.toAsset(
        image=_painted_region_mask(),
        description='regions_mask_v1',
        assetId=C.REGIONS_MASK_ASSET,
        region=india,
        crs=C.EXPORT_CRS,
        scale=C.EXPORT_SCALE,
        maxPixels=C.EXPORT_MAX_PIXELS,
    )
    task.start()
    print('queued one-time regions mask export -> {}'.format(
        C.REGIONS_MASK_ASSET))
    return task


def apply_band_types(mosaic):
    """
    Integer band typing (owner-confirmed 2026-08-10; exceptions may stay
    float for now -- currently there are none).

    Everything is int16 except:
      - lon/lat        int32 upstream (97.4 deg x 10000 overflows int16) --
                       preserved, NOT recast, or they would truncate
      - C.UINT8_BANDS  uint8 (owner ruling 2026-09-03) -- small numbers,
                       see config.py for the evidence behind the list
      - C.INT8_BANDS   int8 (owner ruling 2026-09-03) -- same, signed
    (The evi2 int32 exception died with AMENDMENT 1, 2026-09-01: the
    unshifted ceiling 2.5 x 10000 = 25000 fits int16.)

    Earth Engine casts SATURATE rather than wrap (the legacy product relied on
    exactly that in byte()), so a pathological value pins at the type edge
    instead of corrupting neighbours. (sma_rmse, the one band that exploited
    this, left the export set 2026-08-13 -- register C24.)

    Bands already typed upstream (entropy, terrain) pass through their own
    cast unchanged. This function is the ONLY place that decides a band's
    stored type -- it is a blanket recast, so a per-band cast set upstream
    (e.g. sources.observation_counts's quarters.toInt8()) is overwritten
    here regardless; the narrow-type lists above are what actually take
    effect on export.
    """
    names = mosaic.bandNames()
    coord = ee.List(['lon', 'lat'])
    uint8 = ee.List(C.UINT8_BANDS)
    int8 = ee.List(C.INT8_BANDS)
    narrow = uint8.cat(int8).cat(coord)
    rest = names.removeAll(narrow)
    # ROUND BEFORE CASTING (C26 ruling 7): EE casts truncate toward zero,
    # which biases every band up to half a unit -- sign-dependently on the
    # signed range bands. One round removes it for every band in the contract.
    return ee.Image.cat([
        mosaic.select(rest).round().toInt16(),
        mosaic.select(uint8).round().toUint8(),
        mosaic.select(int8).round().toInt8(),
        mosaic.select(coord),
    ])


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def build_mosaic(cell_name, year, variant='c2_only', verbose=True,
                 lite=False):
    """
    Returns (mosaic_image, metadata_dict) for one cell-year-variant.

    Nothing is computed until something pulls on the result -- this only assembles
    the graph.

    ANNUALS ONLY since the fold-in (owner ruling 2026-08-30): the
    end_year/label epoch machinery (multi-pheno-year composites for the
    thin pre-2000 archive) left the product with the property schema v2
    interview -- pre-2000 years ship as honest thin annuals instead.
    """
    force_era, do_brdf, do_bandpass, do_topo, mode = VARIANTS[variant]

    region = cell_geometry(cell_name)
    collection, era = sources.build(region, year, force_era, mode)

    # Topographic correction scope: NO GATE (owner ruling 2026-08-30) --
    # the physics correction runs on EVERY cell. Flat ground is
    # ~identity under the physics factor, one-sided escarpments are no
    # longer barred, no cell-border seams, and the 'corrections'
    # property is true everywhere. Cost: one pass-table build per
    # cell-year and a near-1 multiply on flat land.
    topo_applies = do_topo and not C.TOPO_DISABLED

    if verbose:
        if not do_topo:
            topo_note = 'off (variant)'
        elif C.TOPO_DISABLED:
            topo_note = 'off (C17.3 interim kill-switch)'
        else:
            topo_note = 'on'
        print('  {} {} [{}] era {} | topo {}'.format(
            cell_name, year, variant, era, topo_note))

    # THE MASK SWITCH: None = config.MASK_RULE ('both') decides in
    # masking.apply_mask. The '_strict' variants force the strict
    # comparator, because they exist to MEASURE against a fixed mask.
    mask_mode = 'strict' if variant.endswith('_strict') else None

    collection = masking.apply_mask(collection, era, mask_mode,
                                    cell=cell_name, year=year)

    # SENSOR POLICY (C18): striped L7 votes only in the pixel-quarters
    # the clean sensors left thin. After masking (thin = USABLE
    # looks), before anything that reads the collection. Self-gating:
    # healthy-L7 years and L7-free years pass through untouched.
    collection = sources.apply_sensor_fill(collection, year, era)

    def _radiometry(coll):
        if do_brdf or do_bandpass:
            coll = radiometry.normalise_era_a(coll, do_brdf,
                                              do_bandpass)
            # Kill the SLC-off striping at source: remove the REGIONAL
            # residual the national TM->ETM+ line leaves between L5 and
            # L7 (C17.1). No-op unless both sensors are present in the
            # year. STATIC per-cell offsets from the cloud table (C31);
            # the per-year median-difference estimator is retired --
            # and config.ALIGN_APPLY is OFF (owner 2026-08-21), so
            # this is a recorded no-op kept for lab measurement.
            if do_bandpass:
                coll = radiometry.align_tm_residual(
                    coll, region, cell=cell_name)
        return coll

    # RADIOMETRIC ORDER (owner 2026-08-23, native at the fold-in):
    # mask -> L7 fill -> TOPO -> BRDF -> bandpass -- radiometry runs
    # AFTER the correction (the C2-physics sequence, verified v3-v9).
    if topo_applies:
        collection = terrain.apply_topographic(collection, region, True,
                                               cell=cell_name, year=year)

    collection = _radiometry(collection)

    # One image per satellite pass: same-pass product overlaps otherwise enter
    # every composite statistic twice (pass_key fixed only the counts). After
    # the per-scene corrections, before anything that feeds the reducers.
    collection = sources.merge_passes(collection)

    # Counts AFTER the merge: on a pass-merged collection a plain count is
    # exact, which retired the countDistinct reducer and its masked-state
    # off-by-one (see observation_counts).
    counts = sources.observation_counts(collection, era, year)

    # Input facts for property contract v2 (owner 2026-08-30), captured
    # on the pass-merged collection: one image per pass, so size() IS the
    # distinct-pass count. Server-side values; the export resolves them.
    n_scenes = collection.size()
    _up = ee.Dictionary({'l4': 'L4', 'l5': 'L5', 'l7': 'L7',
                         'l8': 'L8', 'l9': 'L9',
                         'l30': 'L30', 's30': 'S30'})
    sensors_used = ee.String(
        ee.List(collection.aggregate_array('sensor').distinct().sort()
                .map(lambda s: _up.get(s, s))).join(','))

    # The snow flag has to survive as far as compositing, because the dry/wet ranking
    # is computed on snow-free observations only. It is read from the QA layer here,
    # while the QA layer still exists, and dropped again inside composite().
    collection = collection.map(
        lambda i: ee.Image(i).addBands(
            masking.snow_flag(ee.Image(i), era).rename(C.SNOW_BAND)))

    # Drop the angle and QA layers before compositing -- they are inputs, not outputs,
    # and each surviving band costs seven statistics downstream.
    keep = C.CORE_BANDS + ['tir', C.SNOW_BAND]
    collection = collection.select(keep)

    # CLOUD-TRIM, UPSTREAM (owner ruling 2026-08-30, second sitting):
    # applied here so EVERYTHING downstream -- annual/dry/wet medians,
    # swings, mads, season thresholds AND the quarterly greenness bands
    # -- sees the trimmed stack. usable_count (captured above) stays
    # pre-trim; the quarterly counts (below) run post-trim and count the
    # looks their own medians used. A thin quarter whose only look is
    # cloud now reads as an honest masked gap, not a cloudy value.
    collection = compositing.cloud_trim(collection)

    if lite:
        # Radiometric agreement and observation density only. SMA unmixing and the
        # 15-index suite are dead weight for that question, and dominate both compute
        # and asset size -- 12 bands against 223.
        def _ndvi_only(image):
            img = ee.Image(image)
            r = img.select(C.CORE_BANDS).divide(C.REFL_SCALE)
            ndvi = r.normalizedDifference(['nir', 'red']) \
                    .multiply(C.REFL_SCALE).rename('ndvi')
            return img.addBands(ndvi)
        collection = collection.map(_ndvi_only)
        mosaic = compositing.composite(collection)
        mosaic = mosaic.addBands(counts).select(C.LITE_BANDS)
    else:
        collection = sma.apply_sma(collection)
        collection = collection.map(lambda i: indices.add_indices(ee.Image(i)))

        # stats='product' (C26 ruling 7): the p5/p95/stdDev reducer nodes are
        # never built on the product path -- their bands were dropped below
        # anyway. Whether this saves export compute is settled empirically by
        # the measured exports (the audit argues EE never scheduled them).
        mosaic = compositing.composite(collection, stats='product')

        # Fraction indices are DERIVED here, from the clamped fraction medians,
        # not composited from per-scene values -- the 2026-08-09 SMA design,
        # upheld 2-of-3 in the 2026-08-13 review (register C24). The year
        # routes the post-2021 water-refusal supplement (C26 ruling 4).
        mosaic = sma.derive_composite(mosaic, year=year, region=region)

        # SMA-FAMILY PRUNE (owner ruling 2026-08-13, register C24): the family
        # ships EXACTLY 24 bands -- 5 quantities x {median, dry, wet, range}
        # + 4 MAD wobbles. sma_rmse is diagnostic-only and NEVER exported
        # (owner overrode the reviewers' export suggestion); lit_* only
        # existed to give shade its wobble; fraction p5/p95/stdDev leave the
        # product with the same ruling.
        all_stats = ('median', 'median_dry', 'median_wet',
                     'p{}'.format(C.RANGE_LOW_PCT),
                     'p{}'.format(C.RANGE_HIGH_PCT),
                     'swing', 'mad', 'stdDev')
        sma_drop = (['sma_rmse_' + s for s in all_stats]
                    + ['lit_' + s for s in all_stats]
                    + ['{}_{}'.format(b, s)
                       for b in ('gv', 'npv', 'soil')
                       for s in ('p{}'.format(C.RANGE_LOW_PCT),
                                 'p{}'.format(C.RANGE_HIGH_PCT), 'stdDev')])
        mosaic = mosaic.select(mosaic.bandNames().removeAll(sma_drop))

        # GLOBAL STAT PRUNE (owner ruling 2026-08-13, C24-addendum): p5, p95
        # and stdDev leave the product for EVERY quantity. Order statistics of
        # n draws step at every era join by construction (n: ~10 to ~50 across
        # 1985-2025), and stdDev drifted +43% with stack depth on invariant
        # sand -- the count-robust survivors are median/dry/wet/range/mad.
        # evi2 follows ndvi (continuity exemption retired). ndvi_p25/p75 are
        # the SEASON THRESHOLDS, not spread stats -- the suffix match spares
        # them. Since C26.7 the product path never BUILDS the p5/p95/stdDev
        # nodes (stats='product' above); these drops now catch only the
        # residual carriers (lit_*, sma_rmse_*) and cost nothing when a
        # name is absent (removeAll ignores missing entries).
        names = mosaic.bandNames()
        spread_drop = (names
                       .filter(ee.Filter.stringEndsWith('item', '_p5'))
                       .cat(names.filter(ee.Filter.stringEndsWith('item', '_p95')))
                       .cat(names.filter(ee.Filter.stringEndsWith('item', '_stdDev'))))
        mosaic = mosaic.select(names.removeAll(spread_drop))

        mosaic = mosaic.addBands(compositing.quarterly_ndvi(collection))
        mosaic = mosaic.addBands(compositing.quarterly_counts(collection))
        # BCI and IBI ship MEDIAN + MAD only (owner ruling 2026-08-13):
        # both are computed per scene (indices._bci_scene/_ibi_scene), so the
        # compositor emits their full stat set -- the seasonal cells leave
        # here (the built classes they exist for have no seasons).
        built_drop = ['{}_{}'.format(b, s) for b in ('bci', 'ibi')
                      for s in ('median_dry', 'median_wet', 'swing')]
        mosaic = mosaic.select(mosaic.bandNames().removeAll(built_drop))
        # TEXTURE RETIRED ENTIRELY (owner ruling 2026-09-01, superseding
        # C24-addendum's keep-for-classification plan): in India's highly
        # complex, highly interspersed landcovers, texture at scales
        # Landsat can resolve is rarely present, so the classification-
        # time entropy recipe is dropped with the bands. The old
        # add_texture recipe is recoverable from the private archive.
        mosaic = compositing.add_coordinates(mosaic)
        mosaic = mosaic.addBands(terrain.static_bands()).addBands(counts)

        # THERMAL FROM THE RECORD (owner ruling 2026-08-19). tir_median,
        # tir_mad and tir_count are OVERWRITTEN with the national temperature
        # record's own three bands, rather than reduced out of this stack.
        # It is the only way to keep ONE thermal quantity across all 40 years
        # once the C2 join goes: HLS's B10 is TOA brightness temperature, C2's
        # ST is surface temperature, the gap varies with humidity and cover,
        # and S30 has no thermal at all. Placed BEFORE apply_band_types so the
        # substituted bands get the same typing as everything else.
        if getattr(C, 'THERMAL_FROM_RECORD', False):
            mosaic = mosaic.addBands(
                masking.thermal_bands_from_record(cell_name, year),
                None, True)

        mosaic = apply_band_types(mosaic)
        # THE EXPORT CONTRACT (owner ruling 2026-08-13): stat-major order,
        # true-colour opening, position last -- and an assertion: a missing
        # or extra band fails HERE, not in a shipped asset.
        mosaic = mosaic.select(C.BAND_ORDER)

    mosaic = mosaic.updateMask(region_mask())

    # PROPERTY CONTRACT v2 (owner sign-off 2026-08-30; the schema doc is
    # the authority; AMENDMENT 1 merged the tct decode into
    # decode_indices, so 26 properties since 2026-09-01): the old bag
    # (pheno_year, epoch, variant, era, *_applied flags, territory,
    # collection, version) and the C22 dbg ledger all die here --
    # production assets carry no development ledger (owner ruling);
    # git_commit + built_utc carry reproducibility instead.
    import datetime as _dt2
    import subprocess as _sp
    start_str, end_excl = C.pheno_range(year)
    end_incl = (_dt2.date(year + 1, C.PHENO_START_MONTH,
                          C.PHENO_START_DAY)
                - _dt2.timedelta(days=1)).isoformat()
    try:
        _commit = _sp.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ).decode().strip()
    except Exception:
        _commit = 'unknown'
    meta = {
        # Identity
        'product': C.PRODUCT,
        'product_version': C.PRODUCT_VERSION,
        'grid_name': cell_name,
        'region': 'India',
        'contact': C.CONTACT,
        'citation': C.CITATION,
        # Time Window (phenological year, 1 April - 31 March)
        'year': year,
        'start_date': start_str,
        'end_date': end_incl,
        'system:time_start': ee.Date(start_str).millis(),
        'system:time_end': ee.Date(end_excl).millis(),
        # Inputs
        'input_collection': C.INPUT_COLLECTION,
        'sensors_used': sensors_used,
        'n_scenes': n_scenes,
        # Processing
        'corrections': C.CORRECTIONS,
        # Build Record
        'built_utc': _dt2.datetime.now(_dt2.timezone.utc)
                     .strftime('%Y-%m-%dT%H:%M:%SZ'),
        'git_commit': _commit,
    }
    # Decoding Formulas (9)
    meta.update(C.DECODE_PROPS)
    return mosaic.set(meta), meta


def asset_name(cell_name, year, variant, version=C.VERSION, label=None):
    return '{}_{}_{}_v{}'.format(cell_name, label or year, variant, version)


def production_asset_name(cell_name, year):
    """Production asset id leaf: CELL_YEAR only (owner ruling 2026-09-01).

    Example: NC-43-X-D_2019. No variant tail, no version suffix — the
    product version lives in the image properties and the collection
    address, not the name.
    """
    return '{}_{}'.format(cell_name, year)


_ACTIVE_TASKS = {'at': 0.0, 'descs': set()}


def _active_export_descriptions(max_age_s=60):
    """Descriptions of PENDING/RUNNING export tasks, memoised briefly.

    Closes the resume gap measured 2026-08-14: an asset mid-export reads
    as absent to getAsset, so skip_existing alone re-queued a duplicate
    task (two identical exports burning compute; the loser dies late on
    "asset already exists"). One listOperations per minute covers a whole
    submission loop.
    """
    import time
    now = time.time()
    if now - _ACTIVE_TASKS['at'] > max_age_s:
        try:
            _ACTIVE_TASKS['descs'] = {
                o.get('metadata', {}).get('description', '')
                for o in ee.data.listOperations()
                if o.get('metadata', {}).get('state')
                in ('PENDING', 'RUNNING')}
            _ACTIVE_TASKS['at'] = now
        except Exception:
            pass    # advisory only; the getAsset check still ran
    return _ACTIVE_TASKS['descs']


def export(cell_name, year, variant='c2_only',
           collection_path=None,
           verbose=True, lite=False, label=None,
           skip_existing=True, shard_size=None):
    """
    Queue one export task. Returns the task, or None if skipped.

    skip_existing (adopted from the legacy loop, task #18): an asset already
    present under collection_path is not re-exported, so a crashed or
    interrupted batch resumes cleanly instead of duplicating work.

    shard_size: Earth Engine shardSize in pixels (default None = EE's 256).
    The first lever against the Era B per-shard out-of-memory (register C25:
    876 scene masks held per shard; smaller shards, smaller working set).
    """
    # Default output = config.OUTPUT_COLLECTION (the sandbox until the
    # pre-publication flip to PRODUCTION_COLLECTION — owner 2026-08-30).
    if collection_path is None:
        collection_path = C.OUTPUT_COLLECTION

    # NAMING (owner ruling 2026-09-01): production assets are CELL_YEAR
    # only. Lab tails (label, non-default variant) would collide on that
    # name — and a lite build would claim the full product's name, then
    # skip_existing would silently block the real export forever — so all
    # three are refused outright, before any network call.
    if collection_path == C.PRODUCTION_COLLECTION:
        if label is not None or variant != 'c2_only' or lite:
            raise ValueError(
                'production exports are named CELL_YEAR only; label, '
                'variant and lite are sandbox machinery (got variant={!r}, '
                'label={!r}, lite={!r})'.format(variant, label, lite))
        name = production_asset_name(cell_name, year)
    else:
        name = asset_name(cell_name, year, variant, label=label)

    # BCI FREEZE GATE (C26 ruling 8): BCI is baked per scene with the
    # BCI_NORM constants; an asset exported on unfrozen constants can never
    # be patched, only rebuilt. Refuse rather than poison the archive.
    if not lite and not getattr(C, 'BCI_NORM_VERIFIED', False):
        raise RuntimeError(
            'BCI_NORM is not frozen (config.BCI_NORM_VERIFIED is False); '
            'refusing to export. Freeze the constants under an owner '
            'ruling before queuing mosaics.')

    # Ensure the destination ImageCollection exists (reviewer find
    # 2026-08-30: a fork's first export died at runtime because nothing
    # ever created it — createAsset is idempotent-safe here).
    try:
        ee.data.getAsset(collection_path)
    except Exception:
        try:
            ee.data.createAsset({'type': 'IMAGE_COLLECTION'},
                                collection_path)
            if verbose:
                print('    created collection {}'.format(collection_path))
        except Exception as e:
            print('    WARNING: could not create {}: {}'
                  .format(collection_path, e))

    if skip_existing:
        # 404-AWARE (C26 ruling 7): only a real "not found" means absent.
        # A transient auth/network error used to read as "not there" and
        # queue a duplicate task doomed to fail on the existing assetId.
        asset_id = '{}/{}'.format(collection_path, name)
        for attempt in (1, 2):
            try:
                ee.data.getAsset(asset_id)
                if verbose:
                    print('    exists, skipped {}'.format(name))
                return None
            except Exception as e:
                msg = str(e).lower()
                # EE's translated EEException drops the HTTP status; the
                # absence wording is "does not exist or doesn't allow this
                # operation" (observed 2026-08-14)
                if ('does not exist' in msg or 'not found' in msg
                        or '404' in msg):
                    break               # genuinely absent: proceed to export
                if attempt == 2:
                    raise               # persistent non-404: surface it
                # transient: one retry before deciding
        if name.replace('-', '_') in _active_export_descriptions():
            if verbose:
                print('    already exporting, skipped {}'.format(name))
            return None

    # (The 2026-08-09 EPOCH ADEQUACY GATE lived here until the fold-in:
    # annuals only, owner ruling 2026-08-30, so there are no epochs to
    # gate. Thin years ship as honest thin annuals, disclosed by the
    # per-pixel counts. `label` survives ONLY as an asset-naming hook for
    # lab trial exports; it no longer changes what is built.)

    # ZERO-SCENE SKIP (owner ruling 2026-08-30, reviewer find): a
    # cell-year with NO usable granules cannot be built -- the compositor
    # reduces an empty collection to a zero-band image and the export
    # task dies hours in with an opaque server error. Many pre-2000
    # cell-years are like this (single-track archive gaps). One cheap
    # client-side count here turns that into a named, logged skip: the
    # honest gap IS the product for that cell-year.
    _mode = VARIANTS[variant][4]
    _probe, _era = sources.build(cell_geometry(cell_name), year, mode=_mode)
    n_granules = _probe.size().getInfo()
    if n_granules == 0:
        print('    ZERO-SCENE cell-year: no usable granules for {} {} -- '
              'skipped (honest gap; archive hole, not a failure)'
              .format(cell_name, year))
        return None

    mosaic, meta = build_mosaic(cell_name, year, variant, verbose, lite)

    export_args = dict(
        image=mosaic,
        description=name.replace('-', '_'),
        assetId='{}/{}'.format(collection_path, name),
        region=cell_geometry(cell_name),
        crs=C.EXPORT_CRS,
        scale=C.EXPORT_SCALE,
        maxPixels=C.EXPORT_MAX_PIXELS,
    )
    if shard_size is not None:
        export_args['shardSize'] = shard_size
    task = ee.batch.Export.image.toAsset(**export_args)
    task.start()
    if verbose:
        print('    queued {}{}'.format(
            name, ' (shardSize={})'.format(shard_size) if shard_size else ''))
    return task
