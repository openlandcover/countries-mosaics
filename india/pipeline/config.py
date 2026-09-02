"""
Configuration for the India annual mosaic rebuild.

Every tunable lives here. Nothing downstream should hardcode an asset id, a threshold,
or a band name.

See docs/design_decisions.md for the reasoning behind each choice; the
full method record is the ATBD (docs/atbd.md).
"""

# ============================================================================
# PROJECT / ASSETS
# ============================================================================

# THE FORK MODEL (owner rulings 2026-08-30): input assets are PUBLISHED
# cloud assets — a forker READS them where they live and never rebuilds
# them. So the INPUT root below is a FIXED literal (do not repoint it
# when forking), while the two things a forker actually changes are:
#   EE_PROJECT         — the project their ee.Initialize() bills to
#   OUTPUT_COLLECTION  — where their mosaics land (write access needed)
EE_PROJECT = 'mapbiomas-india'
# Fixed input root: the published IOLN asset space. NOT derived from
# EE_PROJECT on purpose — deriving it broke the fork model (a forker's
# empty project has none of these inputs; caught at review 2026-08-30).
ASSET_ROOT = 'projects/mapbiomas-india/assets'
# ONE input folder, one publication ACL (owner-approved structure,
# 2026-08-30 inventory interview; assets migrated by rename same day):
INPUTS_ROOT = ASSET_ROOT + '/mosaic_v2_inputs'
# OUTPUTS. The v2 mosaics' final resting place mirrors the legacy v1
# convention (owner ruling 2026-08-30; v1 lives at .../INDIA/mosaics-1):
PRODUCTION_COLLECTION = ('projects/mapbiomas-mosaics/assets/'
                         'LANDSAT/LULC/INDIA/mosaics-2')
# We do not hold write access there — the person running the national
# export does. This is the committed PR version: exports default to the
# production collection. Development runs go to the sandbox instead —
# point OUTPUT_COLLECTION at SANDBOX_COLLECTION (or pass an explicit
# collection_path) while testing:
SANDBOX_COLLECTION = ASSET_ROOT + '/shared_assets/ioln_mosaics_v2_sandbox'
OUTPUT_COLLECTION = PRODUCTION_COLLECTION

# The span a full national run covers, in phenological years. Chosen to match
# the published legacy collection, which runs 1986-2025, so that v2 covers the
# same ground as v1; owner approved this on 2026-09-02 by picking it from a
# list of options, so the reasoning here is the pipeline's, not a statement of
# his. Cells and years with no usable granules are skipped as archive gaps by
# build.export's zero-scene check, not exported empty.
PRODUCTION_FIRST_YEAR = 1986
PRODUCTION_LAST_YEAR  = 2025

# REPOINTED 2026-08-30 (owner instruction: everything a build reads
# comes from mosaic_v2_inputs): our own 283-cell India subset of the
# CIM grid (exported from the mapbiomas-workspace world grid the same
# day, filtered by the v2026 boundary — which added NC-46-Y-D vs the
# 282 listed in the legacy script. The published legacy collection
# itself holds 283 cells: those 282 plus NC-44-Y-B, which falls outside
# the v2026 boundary and is not built here, so both products hold 283
# cells, differing by one cell each way). The world grid stays the
# upstream authority; this is the
# pipeline's read path. Snapshot: data/vectors/grid_cells_india.geojson.
GRID_ASSET   = 'projects/mapbiomas-india/assets/mosaic_v2_inputs/grid'
GRID_ASSET_UPSTREAM = 'projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000'
# ROLE RULE (owner, 2026-08-12 — do not swap these two):
#   INDIA_ASSET   decides WHICH GRID CELLS exist (283 cells). Any cell
#                 enumeration — gate tables, export loops, coverage stats —
#                 filters the grid against the BOUNDARY.
#   REGIONS_ASSET clips the MOSAICS (the product's extent mask) and nothing
#                 else. Enumerating cells against it picked up 17 sea/collar
#                 cells (299 vs 282) in the first gate-table build.
INDIA_ASSET  = INPUTS_ROOT + '/boundary'
# Final spatial extent of every mosaic (owner decision 2026-08-09): the union
# of the classification regions (8 features, region_id/region_name). This
# SUPERSEDES the land + 5 km coastal collar construction -- the regions layer
# is now the single authority on where the product exists. Still static
# across all years, for the same reason as before: a per-year extent would
# inject apparent change into a change-detection product.
# CORRECTED 2026-08-30 (owner ruling): _v3 never existed in the project
# — production never noticed because the painted regions_mask_v1 raster
# is read instead. _v2 is the authoritative vector (the presumed source
# of the raster); the broken fallback path is thereby fixed. A GeoJSON
# snapshot of this vector is held in the private archive (not part of
# this release); the live asset is authoritative.
REGIONS_ASSET = INPUTS_ROOT + '/regions'
# The SAME union, pre-painted once as a 30 m byte raster (owner standing rule
# 2026-08-14: anything computable once and read forever becomes an asset).
# Saves re-rasterising the national polygons inside every one of ~10k export
# graphs. build.region_mask() probes it and falls back to painting live.
# Export once with build.export_region_mask(); version-stamp on any regions
# layer change.
REGIONS_MASK_ASSET = INPUTS_ROOT + '/regions_mask'
REGIONS_MASK_USE_PREPARED = True

DEM_ASSET    = 'COPERNICUS/DEM/GLO30_2024_1'      # ImageCollection of tiles, band 'DEM'
HAND_ASSET   = 'users/gena/global-hand/hand-100'  # ImageCollection, 30 m, threshold-100 network

# Prepared terrain asset (owner export, 2026-08-12; register C19-addendum):
# GLO-30 over India flattened to ONE image on the native 1" grid, slope/aspect
# precomputed (raw and DEM_SMOOTH_PX-smoothed) and HAND joined. Reading this
# keeps the tiled-mosaic-plus-gradient chain out of every per-scene graph.
# Band scales, verified by sampling 2026-08-12: slope/slope_smooth = deg x100;
# aspect_sin/aspect_cos = sin/cos damped by sin(slope), x10000 (the
# static_bands convention; atan2 recovers aspect since the damp cancels);
# aspect_smooth = deg x10; hand = metres x10. If the asset is unreadable,
# terrain.py falls back to the live rebuild from DEM_ASSET/HAND_ASSET.
TERRAIN_ASSET = INPUTS_ROOT + '/terrain'
TERRAIN_USE_PREPARED = True
# The asset's PRECOMPUTED slope/aspect bands are wired but OFF, deliberately
# (2026-08-12): EE computes gradients in the REQUEST projection, so live
# slope degrades with scale while a stored 30 m slope band does not. At the
# balance fit's 240 m reductions this is not a nuance -- measured on
# NH-44-V-C: steep fraction 0.83 (precomputed) vs 0.46 (live), south-facing
# steep 0.39 vs 0.17 -- and the fitted C moved x2-4 with blue going unusable,
# while flat NC-43-Z-D flipped from declining correction to grid-floor C.
# The C19 gates were validated under the live semantics, so gradients stay
# derived from the (prepared) DEM at request scale. Flipping this flag is an
# owner decision that reopens the C19 acceptance evidence.
TERRAIN_PRECOMPUTED_PRODUCTS = False

# PER-CELL L5<->L7 ALIGNMENT OFFSETS AS ONE STATIC CLOUD TABLE (owner
# ruling 2026-08-16 on a reviewer finding, register C31). The per-year
# "L7 median minus L5 median" residual is RETIRED: with a thin L5 archive
# the two yearly medians are different seasons and different cloud luck,
# so the difference measured phenology and haze, not the sensor -- and it
# changed every year, injecting wobble into a change record (measured:
# NC-43-X-A 2005, 5 L5 vs 24 L7 photos, raw offset ~-600, applied as the
# -150 clamp = a fake cell-wide darkening of L5). Replacement: the SAME
# pair method the national transform was derived from -- pixels both
# sensors saw within ALIGN_MAX_DT_DAYS, greenness-stable, pooled over the
# data-rich window ALIGN_PAIR_YEARS -- fitted ONCE PER CELL and stored;
# static across all years; applied to blue/green/red only (production
# rule unchanged); a cell with no row or too few pairs gets NOTHING
# applied. Rows: cell, off_<band> x6 (L7 minus L5, refl x10000; only the
# visible three are applied), n_pairs (scene pairs), n_pts, y0, y1, fp.
# ===========================================================================
# THE OFFSET IS RETIRED (owner decision 2026-08-21). MEASURED, NOT ASSUMED.
# ===========================================================================
# It does not work, and it was tested on the ground where it should work best.
#
# Blind national test: 14 cells across India, ~40,000 random points, SAME-DAY
# satellite pairs so that whatever is on the ground cancels and only the
# instrument difference is left. Restricted to the 13 cells holding their OWN
# sound offset row -- not a borrowed region median -- the offset made the L5/L7
# gap WORSE:
#
#     trees      +10.7% worse   (n=559)
#     grassland  +10.8% worse   (n=409)
#     cropland    +4.7% worse   (n=1277)
#     built       -3.8% better  (n=47 -- too few to lean on)
#
# Worse in three of the four cover types that reach a usable sample, clearly so
# in two. Water does not reach the sample threshold in the own-row subset, so
# it is not claimed either way here. The earlier single-cell failure in
# NC-43-Z-D was therefore NOT an artefact of that cell borrowing its row.
#
# The wider reason it cannot be rescued: the L5->L7 difference is not a
# national constant AND not stably estimable per cell. Fitted slope wobbles
# between anchor cells by 0.16-1.03 depending on band -- roughly ten times the
# difference between any two candidate coefficient sets. Refining the NATIONAL
# transform was also tested and also failed a held-out check (see
# the internal normalisation-decisions note and the refit script; neither
# is part of this release).
# Both the national and the regional route are now closed by measurement.
#
# A SWITCH, NOT A DELETION. The derivation code, the cloud table and the
# viewer all stay: the evidence and the history are worth keeping, and one
# line restores the old behaviour. Everything routes through
# radiometry.align_offsets_for(), so this single flag governs both call sites
# in build.py -- the mosaic assembly and the topo-fit preparation.
#
# THE STORED TOPO FITS DO NOT NEED REBUILDING -- measured, not assumed.
# terrain._fit_fingerprint() carries the tag 'align6', and stored Era A fits
# were made WITH the offset applied, so the question had to be asked. Fitting
# C both ways on six L5 scenes (NC-43-Z-D 2005, 30 m) moves it by a median of
# 0.11 in green, 0.06 in red, 0.02 or less elsewhere. Pushed through the SCS+C
# factor on a typical hillside (sun zenith 30, slope 25), that reaches the
# mosaic as +2 units on a well-lit face and -12 on a shaded one, in green, on
# L5 pixels only. The gap the offset was meant to close is 65-157 units and
# the corrections that DO work move things by 100-300. So the fingerprint tag
# is deliberately UNCHANGED: the stored fits stay valid and no refit campaign
# is triggered by this switch.
ALIGN_APPLY = False

ALIGN_OFFSETS_ROOT = (ASSET_ROOT + '/shared_assets/'
                      'align_offsets_v1')
ALIGN_OFFSETS_PARTS = ALIGN_OFFSETS_ROOT + '/parts'
ALIGN_OFFSETS_TABLE = ALIGN_OFFSETS_ROOT + '/offsets_all'
ALIGN_PAIR_YEARS = (1999, 2011)   # both sensors healthy-ish; L7 SLC-off ok
ALIGN_MAX_DT_DAYS = 2
ALIGN_POINTS_PER_PAIR = 150
ALIGN_NDVI_STABLE = 0.05          # |NDVI_l7 - NDVI_l5| below this = same ground state
ALIGN_MIN_PAIRS = 15              # fewer photo pairs -> cell row too thin (region fallback); owner 2026-08-16: ~7 pairs gave garbage, 13+ plausible in every arm
ALIGN_MIN_PTS = 500               # fewer surviving points -> cell row too thin (region fallback)
ALIGN_MIN_CELLS_REGION = 3        # region fallback needs this many sound cell rows
ALIGN_OFFSET_MAX = 150.0          # sanity bound: a larger offset is not a sensor artefact
ALIGN_MAD_K = 3.0                 # outlier rule: drop points > K * 1.4826 * MAD from the median
ALIGN_SAMPLE_SCALE_M = 90         # 3x3 block mean before sampling: washes out sub-pixel shifts
ALIGN_WATER_MNDWI_MAX = 0.0       # pixels with water index above this are NOT sampled (land only)

# RENAMED from witness_stats (owner 2026-08-30): these are the
# per-year clear-sky SURFACE TEMPERATURE records (median + wobble +
# count per pixel) — the witness MASK keeps its name; the ASSET now
# says what it holds. Asset renamed in the cloud the same day.
TEMPERATURE_RECORD_COLLECTION = INPUTS_ROOT + '/temperature_record'
WITNESS_STATS_SCALE_M = None
# Owner ruling 2026-08-14: the asset ships at 30 m (the C2 delivery grid,
# same grid the export evaluates on -- CLOSER to the live numbers than a
# coarser pin) and all bands are INTEGERS: mean and spread in the working
# Kelvin x10 scale rounded to whole units (0.1 K precision, far inside
# the witness thresholds), count as a plain integer.
WITNESS_STATS_EXPORT_SCALE_M = 30

PILOT_COLLECTION = ASSET_ROOT + '/shared_assets/mosaic_rebuild_pilot'

# v2 = the 2026-08-10 band specification (an internal recommendation
# note, not part of this release; the shipped bands are listed in
# docs/band_and_property_contract.md):
# Tasseled Cap added, cai->ndti, bgi added, savi/gcvi/ui/bsi/hallcover/ebbi and
# the gvs/veg/sefi/fnsc group dropped, quarterly NDVI, ndfi_range/shade_range,
# texture requantised, integer band typing. Bumping the version keeps the new
# band set from colliding with (or being skipped in favour of) v1 assets.
# v3 = the 2026-08-13 SMA family (register C24): 24-band SMA set, percent /
# 0-200 scales, -999 sentinel, water-map refusal, sma_rmse no longer exported.
VERSION = '3'

# ============================================================================
# TEMPORAL
# ============================================================================

# Phenological year: 1 Apr Y -> 31 Mar Y+1, labelled by start year Y.
PHENO_START_MONTH = 4
PHENO_START_DAY   = 1

ERA_A_LAST_YEAR  = 2012   # inclusive; Landsat C2 built in-house

# ============================================================================
# SOURCES
# ============================================================================

ERA_A_L2 = {
    'l5': 'LANDSAT/LT05/C02/T1_L2',
    'l7': 'LANDSAT/LE07/C02/T1_L2',
    'l8': 'LANDSAT/LC08/C02/T1_L2',
    'l9': 'LANDSAT/LC09/C02/T1_L2',
}
# Level-1 counterparts, joined by system:index for the per-pixel angle bands.
ERA_A_L1 = {
    'l5': 'LANDSAT/LT05/C02/T1',
    'l7': 'LANDSAT/LE07/C02/T1',
    'l8': 'LANDSAT/LC08/C02/T1',
    'l9': 'LANDSAT/LC09/C02/T1',
}

# OLI sensors are ALREADY on the reference basis that Roy et al. transform TM/ETM+ onto.
# Applying the bandpass transform to them would corrupt data that needs no correction.
BANDPASS_SENSORS = ('l5', 'l7')

# PRODUCTION POLICY: L7 is dropped once L8 is available. SLC-off gaps are fixed relative
# to the ground for a given path/row, so L7 imposes a STRIPED observation-count field --
# structured sparsity, which reads as spatial pattern, rather than uniform noise. L7 is
# retained only where it is the sole or a necessary sensor (1999-2012).
# It is also worth noting L7 was moved to a lower disposal orbit in 2022, drifting its
# overpass time and changing solar geometry systematically, so late L7 is not equivalent
# to mid-mission L7 regardless.
SENSOR_YEARS = {
    'l5': (1984, 2011),
    # L7 RESTORED TO 2013-2021 (owner ruling 2026-08-30): the 2012 cap
    # (2026-08-19) existed to keep C2-QA L7 out of HLS Era B years --
    # void now the product is C2-only. L7 rejoins every year it flew
    # USABLY, under exactly the rules that governed it 2005-2012: the
    # sensor-fill policy (apply_sensor_fill) self-gates striped L7 to
    # the pixel-quarters the clean sensors left thin, and healthy-L7
    # years pass untouched. End 2021 stands (register F4): the Apr-2022
    # disposal-orbit drift changed its solar geometry systematically.
    'l7': (1999, 2021),
    'l8': (2013, 2100),
    'l9': (2021, 2100),
}

# ============================================================================
# SENSOR MIXING POLICY (owner ruling 2026-08-11, register C18)
# ============================================================================
# One sentence: THE CLEAN SENSOR VOTES BY RIGHT; THE STRIPED ONE ONLY PLUGS
# SEASONAL HOLES. Calibration fixes how brightly the sensors see; it cannot
# fix WHEN they look, and the mixing stripes come from both (measured: after
# full calibration the mean L5-L7 disagreement is ~3 x1e-4 but the pixel
# scatter is ~200 -- crop timing, untouchable by radiometry).
#
#   to 1998    | L5 alone (nothing else exists)
#   1999-2002  | L5 + L7 freely -- L7's scanner still healthy, no stripes
#   2003-2011  | L5 by right, gappy L7 fills holes      <- this rule
#   2012       | L7 alone, stripes and all (no alternative; legacy too)
#   2013-2016  | L8 by right, gappy L7 fills holes         <- same rule
#   2017-2021  | L8 (+L9 from 2021) by right, gappy L7 fills  <- same rule
#   2022 on    | L8 + L9, both clean; no L7 in the pool (withdrawn)
#
# The rule (sources.apply_sensor_fill): per PIXEL, per PHENOLOGICAL QUARTER --
# if the clean sensors supplied fewer than SENSOR_FILL_MIN_OBS usable (masked)
# looks in that quarter, L7's looks from that quarter are enlisted; otherwise
# they are dropped. Quarter, not month or half-year: the coarsest block that
# still protects the quarterly bands and the dry/wet split -- coarser blocks
# hide empty quarters, finer ones enlist stripes for products we do not make.
# Self-handling edges: 2012 and L5-void regions (zero clean looks everywhere)
# enlist ALL of L7 -- correct, and single-sensor composites do not stripe.
# BAP-family precedent: Griffiths et al. 2013 / White et al. 2014 score
# SLC-off L7 down so it is used only where nothing better exists.
SENSOR_FILL_ENABLED = True
SENSOR_FILL_MIN_OBS = 3      # K: a median needs 3 looks to shrug off one bad one
# The thin/thick eligibility ledger is computed on THIS grid, not at 30 m.
# It is a clouds-and-coverage field -- smooth over kilometres -- and pinning
# it coarse caps the per-tile graph depth (the same reproject trick as the
# C15 texture fix). Without it, Era B (180+ granules whose masks each carry
# the witness history) exceeded interactive memory the moment the fill rule
# was on. 600 m = 20 Landsat pixels; enlistment boundaries are blocky at
# that scale, which is irrelevant to a decision about season coverage.
SENSOR_FILL_COUNT_SCALE = 600
SLC_OFF_FIRST_YEAR  = 2003   # pheno 2003 starts Apr 2003; SLC died 31 May 2003.
                             # Pheno 2002 (Apr 02 - Mar 03) is fully healthy.


# Scene-level guard only. All real filtering happens per pixel.
SCENE_CLOUD_MAX = 95

# ============================================================================
# BAND EQUIVALENCE
# ============================================================================

CORE_BANDS = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']

# Collection 2 Level-2, TM / ETM+
_C2_TM  = (['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'ST_B6',
            'QA_PIXEL', 'QA_RADSAT'], CORE_BANDS + ['tir', 'pixel_qa', 'radsat'])
# OLI band numbering is shifted: B1 is coastal aerosol, so blue starts at B2.
_C2_OLI = (['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'ST_B10',
            'QA_PIXEL', 'QA_RADSAT'], CORE_BANDS + ['tir', 'pixel_qa', 'radsat'])

SRC_BANDS_C2 = {'l5': _C2_TM, 'l7': _C2_TM, 'l8': _C2_OLI, 'l9': _C2_OLI}


ANGLE_BANDS = ['SZA', 'SAA', 'VZA', 'VAA']    # 0.01 degree integers in both C2 L1 and HLS

# Working radiometric scale: reflectance x 10000, integer space.
REFL_SCALE = 10000

# ============================================================================
# MASKING
# ============================================================================

# QA_PIXEL bit positions, Collection 2
QA_BITS = {
    'fill': 0, 'dilated_cloud': 1, 'cirrus': 2, 'cloud': 3,
    'cloud_shadow': 4, 'snow': 5, 'clear': 6, 'water': 7,
}
# Two-bit confidence fields; value >= 2 means medium or high.
QA_CONF = {'cloud': 8, 'cloud_shadow': 10, 'snow': 12, 'cirrus': 14}
QA_CONF_MIN = 2

# QA_RADSAT bitmasks, per sensor (task #11): saturation should mask on the
# OPTICAL bands we use, not on bands we do not. The old blanket 127 included
# TM/ETM+ bit 5 -- the THERMAL band -- so a fire-saturated thermal pixel
# masked the optical bands too; on OLI it included the unused coastal band.
#   TM/ETM+ : bands 1-5,7  -> bits 0-4,6 = 0b1011111 = 95
#   OLI     : bands 2-7    -> bits 1-6   = 0b1111110 = 126 (l30 = OLI via C2)
RADSAT_BITS = {'l4': 95, 'l5': 95, 'l7': 95, 'l8': 126, 'l9': 126, 'l30': 126}


# ============================================================================
# Witness mask -- the production mask since 2026-08-09
# ============================================================================
# Owner decision after the NC-43-Z-D inspector sessions and the NH-44-V-C gate:
# confidence fields only (no binary bits, no TDOM, no dilation), with every
# cloud/shadow flag required to produce independent physical evidence. Owner's
# stated tolerance: leak some cloud, never over-mask. Measured: built-up +13-15%
# observations at unchanged survivor NDVI; Himalayan snow observations kept
# +67% (2005) / +106% (2023); forest within 0.020 NDVI of the old mask.
#
# Thermal verdict is three-zone, in Kelvin x 10:
#   above WITNESS_CLOUD_CEIL      -> never cloud (no real cloud top is 303 K;
#                                    this is what rescues 315 K roofs)
#   below the pixel-adaptive floor min(WITNESS_COLD_FLOOR, clear_mean - DROP)
#                                 -> certainly cloud-cold
#   between                       -> z < -1 against the pixel's CLEAR-SKY
#                                    thermal history, and only where that
#                                    history holds >= WITNESS_MIN_OBS. Thinner
#                                    history FAILS CLOSED (flag upheld): failing
#                                    open let cool cloud flood 2005 forest,
#                                    survivor NDVI 0.805 -> 0.684.
# The history must be CLEAR-SKY: computed on the raw year it is itself full of
# cold cloudy retrievals, and witness-all forest NDVI fell 0.834 -> 0.598.
WITNESS_CLOUD_CEIL = 3030
WITNESS_COLD_FLOOR = 2850
WITNESS_FLOOR_DROP = 150
WITNESS_MIN_OBS    = 8
WITNESS_Z_THRESH   = -1.0

# Snow witness: a flagged pixel that looks like snow is rescued -- snow is a
# kept class, snow-as-cloud is CFMask's signature Himalayan error, and thermal
# cannot arbitrate it (snow is cloud-cold). NDSI in raw ratio units; SWIR1 in
# reflectance x 10000 (snow is dark in SWIR1, cloud is bright).
SNOW_NDSI_MIN   = 0.4
SNOW_SWIR1_MAX  = 1200


# THE MASK RULE (owner ruling 2026-08-30): a look survives only if the
# plain QA bit AND the thermal witness both keep it -- one conjunctive
# rule for the whole archive, no era split, no processing_track
# property. Verified on NH-46-Z-D_2022_c2_only_v9 (cloud-bright fraction
# halved vs v8 at ~3% look cost). 'both' is production; 'plain',
# 'witness', 'strict', 'fmask' remain callable as explicit lab modes.
MASK_RULE = 'both'

# CLOUD-TRIM (owner recipe FROZEN 2026-08-30): blue-anchored right-clip
# of each pixel's annual stack before every composite statistic. Anchor
# = stack p25 of blue; a look is kept where blue <= anchor + DELTA.
# Fires only where the stack looks contaminated (blue p75-p25 > SPREAD)
# AND enough looks survive: adaptive floor min(MAX_FLOOR, ceil(n/2)),
# never below 2 -- so the trim can refuse to help but never harm.
# Values in TRUE reflectance, scaled by REFL_SCALE at the point of use.
# Catches warm unflagged bright cloud (the 2023-03-18 monster) and the
# median-strays-onto-cloud failure in majority-cloudy stacks; cannot see
# dark (shadow) contamination -- that stays the masks' job.
CLOUD_TRIM = True
CLOUD_TRIM_DELTA = 0.03
CLOUD_TRIM_SPREAD = 0.03
CLOUD_TRIM_MAX_FLOOR = 5

# ============================================================================
# PROPERTY CONTRACT v2 (owner sign-off 2026-08-30;
# docs/band_and_property_contract.md is the authority)
# ============================================================================
# 26 properties per image, nothing else (AMENDMENT 1, 2026-09-01):
# Identity(6) + Time Window(5) + Inputs(3) + Processing(1) +
# Decoding Formulas(9) + Build Record(2).
# The static ones live here; build.build_mosaic assembles the rest
# (year/window facts, sensors_used, n_scenes, built_utc, git_commit).
# The COLLECTION asset carries the one human-readable description;
# individual images carry none (owner ruling: one cheat sheet maintained
# once beats ~11,000 copies drifting out of sync).
PRODUCT = 'IOLN annual Landsat mosaic, India'
PRODUCT_VERSION = '2'
CONTACT = 'mdmadhu@gmail.com'
CITATION = 'India Open LandCover Network'
INPUT_COLLECTION = 'Landsat Collection 2 Level 2'
CORRECTIONS = 'Topographic Correction + BRDF + Sensor Harmonisation'
DECODE_PROPS = {
    'decode_reflectance': ('reflectance = stored x 0.0001 '
                           '(red/green/blue/nir/swir1/swir2, every '
                           'statistic)'),
    'decode_temperature': 'kelvin = stored x 0.1 (tir bands)',
    'decode_fractions': ('percent = stored; fraction = stored / 100 '
                         '(gv/npv/soil/shade, every statistic)'),
    # AMENDMENT 1 (owner ruling 2026-09-01): the legacy +1 shift is
    # removed from the four ratio indices; one rule covers the whole
    # x0.0001 family, tasselled cap included, and the two decode
    # properties are MERGED (props 27 -> 26, decode props 10 -> 9).
    'decode_indices': ('index = stored x 0.0001, every statistic, '
                       'never shifted -- ndvi, evi2, ndmi, mndwi, '
                       'tcb, tcg, tcw'),
    'decode_ndfi': ('ndfi = stored / 100 - 1 (levels); ndfi units = '
                    'stored / 100 (swing, mad). Codes: -10 refused '
                    'water, -20 refused snow (levels, mad); -999 no '
                    'real pair (swing)'),
    'decode_bci_ibi': ('index = stored / 100 - 1 (median); spread = '
                       'stored / 100 (mad)'),
    'decode_terrain': ('elevation: metres. slope: degrees = stored / '
                       '100. aspect_sin/cos = stored / 10000, '
                       'slope-damped -- use directly, never rebuild '
                       'the angle. hand: metres = stored / 10'),
    'decode_position': 'degrees = stored / 10000 (lon, lat)',
    'decode_counts': ('plain integers, no conversion. Quality signals '
                      'only -- never classifier features'),
}

# ---------------------------------------------------------------------------
# THE PLAIN MASK (owner ruling 2026-08-19) -- production from 2016
# ---------------------------------------------------------------------------
# Deliberately MORE LIBERAL than either older mask: it reads the plain binary
# cloud and shadow BITS, not the confidence fields, because the bits let
# medium-confidence cloud through and the owner's rule is to lose no data the
# median can survive. Past 2016 there are enough looks per pixel that a median
# absorbs what leaks; what it cannot absorb is a mask that eats the monsoon.
#
# THREE GUARDS RIDE ALONG, because none of them costs anything worth counting
# -- the expensive part of the witness was the thermal history, never the
# guards:
#   cirrus      -- masked at HIGH confidence only. No witness can testify for
#                  see-through cloud, and medium cirrus is unverifiable
#                  aggression. C2 QA only; Fmask has no confidence field.
#   saturation  -- one bitwise test on QA_RADSAT. Saturated pixels are garbage
#                  reflectance and they cluster at cloud edges. C2 QA only;
#                  HLS publishes no saturation flag.
#   shadow dark -- a shadow flag masks ONLY where the pixel really is dark
#                  (SHADOW_DARK_SUM). The flag over-fires on water and dense
#                  forest. Both sensors.
#
PLAIN_QA_CIRRUS_MIN = 3       # C2 QA cirrus confidence: 3 = high only
PLAIN_QA_RADSAT     = True    # honour QA_RADSAT saturation


# ---------------------------------------------------------------------------
# THERMAL BANDS FROM THE TEMPERATURE RECORD (owner ruling 2026-08-19)
# ---------------------------------------------------------------------------
# tir_median / tir_mad / tir_count are read straight from
# TEMPERATURE_RECORD_COLLECTION/INDIA_<year> instead of being reduced out of the
# image stack. The record already holds exactly those three numbers, built
# from C2 DIRECTLY with no HLS join, for all 40 years.
#
# WHY, IN ONE LINE: it is the only way to keep ONE thermal quantity across the
# whole archive once the join goes. HLS's own B10 is TOA BRIGHTNESS
# temperature; C2's ST is SURFACE temperature. Measured 2026-08-18 on same-day
# pixels the gap runs +1.6 K (cropland) to +4.4 K (forest) and varies with
# humidity and cover, so no fixed conversion exists. And S30 has no thermal at
# all, so from 2016 a stack-derived thermal would rest on a shrinking minority
# of looks.
#
# BAND SEMANTICS CHANGE, RECORDED: tir_count now means "clear thermal looks by
# the RECORD's own clear definition (qa_pixel_mask)", not "looks that survived
# this mosaic's mask". The two populations are close but not identical, and
# the record's is the fuller one (it counts C2 scenes with no HLS granule).
THERMAL_FROM_RECORD = True


# Shadow witness: a shadow flag is upheld only where the pixel is actually dark.
# NIR + SWIR1 in reflectance x 10000; same threshold TDOM used for "absolutely
# dark", kept under its own name now that TDOM itself is retired.
SHADOW_DARK_SUM = 4000

# ============================================================================
# BRDF -- Roy et al. (2016) c-factor
# ============================================================================

# RossThick-LiSparse-Reciprocal spectral model parameters, per band.
#
# VERIFIED 2026-08-06 against BOTH primary sources, all six bands, exact match.
#
# Source of record: Roy et al. (2016), "A general method to normalize Landsat
# reflectance data to nadir BRDF adjusted reflectance", RSE 176:255-271, the
# "Global 12 months" parameter set, fitted over ~16 billion MODIS pixels per band.
# See docs/. This file previously cited RSE 185:57-70 (the bandpass paper) and was
# then wrongly corrected to RSE 199 (the Sentinel-2 paper). RSE 176 is correct.
#
# AND HLS USES THE IDENTICAL SET. Ju et al. (2025), RSE 324:114723, Table 2 lists
# NASA's BRDF parameters per HLS band and they match these values exactly, citing
# Roy et al. (2016) as the source. So NASA does not fit its own coefficients --
# the earlier assumption that they did, and that this explained our residual
# difference against HLS L30, was wrong.
#
# What that leaves: our BRDF and NASA's share the same method, the same two
# kernels, the same nadir target and now demonstrably the same coefficients. The
# only remaining difference is the solar-zenith reference, measured below at
# 0.0005 NDVI. Any residual beyond that is NOT BRDF -- look to masking (we retain
# ~8% more observations, so the medians are over different subsets), to HLS being
# resampled twice against our once, or to the LaSRC build.
#
# BEWARE THE COLUMN ORDER. The published table runs fiso, fgeo, fvol -- geometric
# BEFORE volumetric -- while this dict lists vol before geo. Secondary sources
# routinely transpose the last two headers. The physical check is that fvol > fgeo
# for every band: the volumetric (RossThick) term dominates the geometric-optical
# (LiSparse) one over most surfaces. If that ever inverts, the columns were swapped.
BRDF_COEFFS_VERIFIED = True

BRDF_COEFFS = {
    'blue':  {'iso': 0.0774, 'vol': 0.0372, 'geo': 0.0079},
    'green': {'iso': 0.1306, 'vol': 0.0580, 'geo': 0.0178},
    'red':   {'iso': 0.1690, 'vol': 0.0574, 'geo': 0.0227},
    'nir':   {'iso': 0.3093, 'vol': 0.1535, 'geo': 0.0330},
    'swir1': {'iso': 0.3430, 'vol': 0.1154, 'geo': 0.0453},
    'swir2': {'iso': 0.2658, 'vol': 0.0639, 'geo': 0.0387},
}

# Normalise the solar zenith to the SCENE-CENTRE value rather than leaving it
# per-pixel, mirroring what HLS does per tile (User Guide v2.0 section 4.4). This is
# a small correction -- ~1 deg, measured -- and it removes the east-west solar-time
# gradient across a swath, not seasonal variation. HLS does not remove seasonal
# variation either, so matching it means matching this and nothing more.
#
# HOW MUCH THIS MATTERS, measured analytically rather than by pilot. The c-factor is
# a ratio and only its numerator depends on the target angle, so the fractional
# change in output reflectance is exactly R(sza_a, nadir) / R(sza_b, nadir).
# For the 1.2 deg that separates our convention from NASA's:
#
#   reflectance   +0.28% to +0.61% per band, across SZA 20-60
#   NDVI          -0.0003 to -0.0008
#
# That is 25x smaller than the era-join divergence this was meant to address and
# 75x smaller than the S30 shift. Register A1 is therefore REAL BUT IMMATERIAL:
# correctly identified, worth documenting, not worth engineering around. There is a
# clean way to match NASA exactly -- NBAR_SOLAR_ZENITH is published on every HLS
# granule from 2013, so the offset could be fitted on the overlap and extrapolated
# back to 1985 -- and it is not worth building for half a thousandth of an NDVI unit.
#
# Note also what the same numbers say about our diagnostics generally: a 5 deg
# zenith error moves NIR 1.8% and RED 2.4% while moving NDVI only 0.0024. The bands
# move together and the ratio cancels them. Any NDVI-only test therefore UNDERSTATES
# what a classifier reading raw reflectance would see.
BRDF_NORMALISE_SOLAR_ZENITH = True

# LiSparse-R geometry constants (crown shape ratios), standard MODIS values.
BRDF_HB = 2.0   # h/b, crown centre height over vertical radius
BRDF_BR = 1.0   # b/r, vertical over horizontal crown radius

# ============================================================================
# BANDPASS -- Roy et al. (2016) ETM+ -> OLI continuity
# ============================================================================

# OLI = intercept + slope * ETM+, applied to SURFACE reflectance.
# TM is treated as ETM+ (see the note on sensor coverage below).
#
# VERIFIED 2026-08-07 against the paper itself: Roy et al. (2016), "Characterization of
# Landsat-7 to Landsat-8 reflective wavelength and normalized difference vegetation index
# continuity", RSE 185:57-70, TABLE 2 (surface reflectance; Table 1 is top-of-atmosphere
# and does not apply here). See docs/.
#
# RMA, NOT OLS. The paper publishes both, and the reason to prefer RMA is stated in it:
# "The RMA regression results are symmetric so that a single line defines the bivariate
# relationship, regardless of which variable is the dependent... The RMA regression allows
# for both the dependent and independent variables to have error... which is useful because
# of the sensor calibration uncertainty and because the TOA and surface sensor reflectance
# data have non-negligible atmospheric effects and residual atmospheric correction errors."
#
# Both variables carry error here, so the OLS slope is attenuated by the correlation
# coefficient. Table 2's OLS slopes run 0.847-0.907 against RMA's 0.954-1.017 -- so OLS
# compresses transformed Era A reflectance by roughly 8-16%, worst in NIR and blue. Every
# variance-like band (stdDev, mad, the seasonal range, texture) would then carry a
# manufactured step at the 2013 join from the transform alone, which is precisely what
# objective 6 exists to prevent. OLS would be right if the goal were the best single
# predicted value per pixel; it is the wrong tool for putting two distributions on one
# basis across a 41-year change product.
#
# For the record, the OLS set previously used here, from the same table and the same
# direction -- correct direction, wrong estimator:
#   blue 0.0003/0.8474  green 0.0088/0.8483  red 0.0061/0.9047
#   nir  0.0412/0.8462  swir1 0.0254/0.8937  swir2 0.0172/0.9071
BANDPASS_COEFFS_VERIFIED = True

# TM -> ETM+ continuity transform, DERIVED FROM INDIA'S OWN 1999-2011 OVERLAP
# (2026-08-09, by an internal one-off derivation script that is not part
# of this release; see docs/evidence_sensor_harmonisation.md). Roy characterises
# ETM+ against OLI only, so L5 previously received a transform derived for a
# different instrument, leaving ~+86 blue / +95 green x10000 uncorrected.
#
# Derivation: 3,952 sidelap pixel pairs (same ground, both sensors, <= 2 days
# apart, witness-masked, BRDF-corrected, NDVI-stable), balanced across nine
# regions x four years x four elevation bins x three NDVI classes (cap 40 per
# stratum) so no landscape dominates. RMA per band. Applied AFTER BRDF and
# BEFORE ETM_TO_OLI -- the exact quantity it was derived on.
#
# BLUE IS OFFSET-ONLY BY EVIDENCE: its fitted slope swung 0.40-1.01 across
# strata (TM blue channel noise breaking the spread-ratio), while the offset
# stayed well-behaved. Slope forced to 1.
#
# Two recorded caveats, judged acceptable and NOT corrected for:
#   - LEDAPS aerosol errors (DDV-scarce arid India) hit both sensors of a pair
#     and largely cancel; any sensor-asymmetric LEDAPS residual inside these
#     numbers is IN every L5 scene we process, so correcting it is right for
#     record continuity either way.
#   - L5 orbital drift (2007-2011) shifts overpass time and solar zenith; fit
#     years stop at 2009 (drift moderate). A per-year stability panel remains
#     available in the derivation script if late-L5 dispersion shows at the
#     invariant targets.
#
# Units: intercepts in reflectance x 10000 (applied directly, no rescale).
TM_TO_ETM = {
    'blue':  {'slope': 1.0,    'intercept': -43.5},   # offset-only, see above
    'green': {'slope': 0.9852, 'intercept': -54.9},   # r 0.945
    'red':   {'slope': 1.0234, 'intercept': -48.4},   # r 0.962
    'nir':   {'slope': 0.9918, 'intercept': -16.2},   # r 0.918
    'swir1': {'slope': 1.0132, 'intercept': -63.3},   # r 0.944
    'swir2': {'slope': 1.0189, 'intercept': -35.3},   # r 0.960
}
TM_SENSORS = ('l4', 'l5')   # instruments that receive TM_TO_ETM

ETM_TO_OLI = {
    'blue':  {'intercept': -0.0095, 'slope': 0.9785},
    'green': {'intercept': -0.0016, 'slope': 0.9542},
    'red':   {'intercept': -0.0022, 'slope': 0.9825},
    'nir':   {'intercept': -0.0021, 'slope': 1.0073},
    'swir1': {'intercept': -0.0030, 'slope': 1.0171},
    'swir2': {'intercept':  0.0029, 'slope': 0.9949},
}


# ============================================================================
# TOPOGRAPHIC CORRECTION -- SCS+C
# ============================================================================


# Which estimator picks C (register C19):
#   'temporal' -- within-pixel invariance: the same location observed under
#                 different sun angles must read the same after correction.
#                 Immune to the shaded-slopes-are-different-land confound
#                 that broke both cross-sectional estimators (C17.3).
#   'search'   -- the cross-sectional zero-correlation search. Kept as the
#                 comparison baseline; known to over-correct in mountains.
# 'balance' (register C19, FINAL): calibrate C per band so the corrected
# annual composite reproduces the steep-slope south/north balance measured
# from HIGH-SUN months uncorrected -- when the sun stands near zenith,
# illumination is aspect-blind and the remaining asymmetry IS the land
# cover. Measured on NH-44-V-C 2005: summer baseline 0.952; annual raw
# 1.616; C=0.3 corrected 0.969. Every scatter-based estimator (regression,
# cross-sectional search, two-way-demeaned temporal) pushed C toward 0.01
# and overshot to 0.835 -- their residual correlations (0.06-0.20 at best)
# show the single-C model never fully fits point scatter, so argmin-of-r is
# the wrong summary. The balance anchor asks the only question the product
# cares about and answers it on the product itself.
# 'perscene' is PRODUCTION as of 2026-08-12 (register C22): the owner's
# per-scene JS core amended by the nine C22 rulings. 'balance' (C19),
# 'temporal' and 'pooled' remain in code as retired comparators.
#
# 'physics' is PRODUCTION as of the fold-in (owner ruling 2026-08-29,
# docs/terrain_correction_evidence.md, closed question): C per band from
# the 6S lookup tables (per sensor; sun zenith + MERRA-2 AOT/WV at the
# pass hour; per-pixel elevation interpolation), SCS+C with sky view,
# shared soft cap CORRECTION_FACTOR_MIN..MAX, NO damping, NO drop rule.
# Radiometric order under 'physics': topo BEFORE BRDF and bandpass (the
# C2-physics sequence, owner 2026-08-23). Implementation:
# pipeline/topo_physics.py. Earlier estimators stay as lab comparators.
TOPO_C_ESTIMATOR = 'physics'
# 6S LUT tables for the physics C, one per sensor family. AUTHORITATIVE
# copies are the cloud tables in mosaic_v2_inputs (owner rule 2026-08-30:
# EVERY input the pipeline uses lives there); read once per run,
# client-side. The repo CSVs below are the LOUD fallback only, kept so a
# run can survive a broken asset read.
PHYS_LUT_ASSETS = {'oli': INPUTS_ROOT + '/lut_oli',
                   'etm': INPUTS_ROOT + '/lut_etm',
                   'tm': INPUTS_ROOT + '/lut_tm'}
PHYS_LUT_FILES = {'oli': 'data/lut/lut_oli.csv',
                  'etm': 'data/lut/lut_etm.csv',
                  'tm': 'data/lut/lut_tm.csv'}
PHYS_LUT_FALLBACK = 'data/lut/lut_v1_spare.csv'
PHYS_LUT_BY_SENSOR = {'l8': 'oli', 'l9': 'oli', 'l7': 'etm',
                      'l5': 'tm', 'l4': 'tm'}
PHYS_AOT_CLIM = 0.15     # MERRA-2 fallbacks when the hour has no value
PHYS_WV_CLIM = 2.0
PHYS_IC_FLOOR = 0.05     # cos-i floor inside the physics factor


# Soft cap (register C19): the hard clamp at CORRECTION_FACTOR_MAX printed
# flat plateaus on the darkest faces. The soft cap keeps the factor identical
# up to a knee at 75% of the way to the limit, then rolls it asymptotically
# toward the limit -- no plateau edge, same worst-case bound.
TOPO_SOFT_CAP = True

# Light smoothing of the elevation model before slope/aspect FOR THE
# CORRECTION GEOMETRY ONLY (exported terrain bands stay raw): pixel-level DEM
# noise otherwise becomes per-pixel correction speckle. Radius in pixels.
DEM_SMOOTH_PX = 1


# ============================================================================
# SMA -- pseudocode design, implemented 2026-08-09
# ============================================================================
# Scene level unmixes UNCONSTRAINED and keeps negatives -- because the SPREAD
# statistics need both tails (clamping censors stdDev/MAD) and because the
# constrained solve redistributes water's spectrum into fake GV. (For the
# MEDIAN itself clamping is neutral -- quantiles commute with monotone clamps;
# the old "median needs both tails" claim was disproved in review, 2026-08-13.)
# Fractions composite raw; the single physical clamp happens to the medians at
# composite level, and the index suite is derived from those.
# Full rationale in pipeline/sma.py (the design pseudocode it was built
# from is an internal note, not part of this release).

# Denominator guard for the derived indices, in fraction units. Provably safe:
# every guarded denominator vanishes only when its numerator does, so the
# guard only ever yields 0/EPS = 0 -- neutral (pseudocode part C, note 1).
SMA_EPS = 1e-6

# Int-overflow guard on scene-level fractions, NOT a physical constraint: set
# far outside any meaningful value so a pathological pixel cannot wrap an
# integer export. If it binds often, the endmember table is wrong.
SMA_OVERFLOW_CAP = 3.0

# The pseudocode's B1 filter (drop observations whose cloud fraction exceeds a
# threshold) is DISABLED: with Amazonian endmembers the cloud fraction lights
# up over surfaces too bright for the soil endmember -- Thar sand, salt crust
# -- so the filter becomes systematic bright-class data loss. The witness mask
# owns cloud detection. Revisit with India-derived endmembers.
SMA_CLOUD_REJECT = None

# FRACTION_INDEX_MIN_SUM retired 2026-08-09: the per-scene guard is superseded
# by the composite-level derivation below.

# Fraction indices are masked where the composite shade fraction exceeds this.
# MEASURED NECESSITY, not caution: the unconstrained-median route was predicted
# to take water GV to exactly zero and neutralise the reservoir rail; it does
# not -- the yearly median lands a hair ABOVE zero (gv_median 4-70 x10000 over
# the owner's reservoirs) and any positive speck rails the ratios (sefi read a
# flat 20000 over water in every year tested). Shade separates cleanly where
# GV cannot: water 9915-9936, built ~7400, forest ~6300 (x10000), in BOTH
# eras. Indices are statements about the lit fraction of a pixel; above 80%
# shade there is no lit fraction worth describing.
SHADE_INDEX_MAX = 0.8

# ============================================================================
# SMA FAMILY RULINGS, owner 2026-08-13 (register C24; three-agent review)
# ============================================================================
# The shipped family is 24 bands: {gv, npv, soil, shade, ndfi} x {annual, dry,
# wet, amplitude} + {gv, npv, soil, shade}_mad. sma_rmse and scene counts are
# diagnostic-only, NEVER exported (owner ruling overrides reviewer advice).

# Export scales (owner: whole numbers, legacy-portable; noise >> 1 count):
SMA_PCT_SCALE = 100   # fractions & shade: 0-100 percent; amplitudes -100..100
NDFI_SCALE    = 100   # ndfi: (value+1)*100 -> 0-200; amplitude -200..200

# Refused-index fill (the RF classifier cannot take blanks). Out-of-range
# sentinel, unanimous across all three reviewers: never 0 (the legacy chop's
# face), never 200 (the reservoir rail's face), never neutral 100 (India's
# degraded-forest zone). -999 is impossible for EVERY band in the family,
# including the signed amplitudes. TREES-ONLY encoding: unsafe for linear or
# distance-based learners -- revisit if the classifier family ever changes.
SMA_SENTINEL = -999

# Rail-ring fix (review find): just under the shade gate the NDFI denominator
# is a sum of specks and the ratio slams to +-1 (a thin ring of fake extremes
# around every gated water body). A MEANINGFUL floor -- not epsilon -- damps
# speck ratios toward 0 while leaving ordinary pixels untouched (their
# denominator is far above it).
NDFI_DENOM_FLOOR = 0.05

# Independent water evidence in the refusal test (review find: the 0.8 shade
# gate was calibrated on CLEAR reservoirs at ~0.99 shade; turbid monsoon water
# is brighter and can duck under it, reviving the knife-edge). JRC Global
# Surface Water occurrence: % of observed months a pixel held water.
WATER_OCCURRENCE_ASSET = 'JRC/GSW1_4/GlobalSurfaceWater'
WATER_OCCURRENCE_MIN   = 50

# SUPERSEDED BY THE YEARLY JRC HISTORY (owner find, 2026-08-15): the JRC
# yearly water classification now runs 1984-2024 across two versions, so
# the refusal becomes a pure per-year LOOKUP for the whole period -- no
# static-map blind spot, no DSWx computation, no mndwi fallback. The
# DSWx machinery above is retired (exports cancelled, assets deleted).
# v1.5's band arrives unnamed ('b1'); classes verified by sampling
# 2026-08-15: 1 = not water, 2 = seasonal water, 3 = permanent water.
# THE MONTHS-OF-WATER SERIES (owner design, 2026-08-15): for each year,
# how many months (0-12) the pixel held water. Not one coherent dataset
# -- assembled from three pieces, all stored files, all verified by
# probing (bands/values checked; the v1.5 pieces ship per-year images
# with a 'year' property and an unnamed band, values 0-12):
#   1984-2015  counted from the monthly water maps (12 images/year)
#   2016-2021  ready-made per-year seasonality (v1.5, RECOMPUTED -- the
#              release notes say it corrects overestimation; preferred
#              over counting the old monthlies for these years)
#   2022-2024  ready-made per-year seasonality (v1.5)
#   2025+      repeats 2024 (owner ruling)
GSW_MONTHLY_V14  = 'JRC/GSW1_4/MonthlyHistory'
GSW_SEAS_FIRST, GSW_LAST_YEAR = 2016, 2024
# THE UNIFORM REFUSAL RULE (owner ruling 2026-08-26, replacing the
# 2026-08-15 month-count rule and the 2026-08-24 occurrence backstops):
# ONE metric for every year, counted over the mosaic's own pheno window
# (Apr y -> Mar y+1) from the JRC MONTHLY maps -- v1.4 to Dec 2021, the
# v1.5 continuation for 2022-2024. A pixel is refused when it held water
# in at least GSW_WATER_FRACTION_MIN of the months JRC actually OBSERVED
# that window, provided at least GSW_WATER_MIN_OBS months were observed
# (one wet look must not stamp a whole year). Fraction-of-OBSERVED fixes
# the failure that started all this: in cloudy single-track years JRC saw
# a pixel ~5 months, so a permanently wet river scored "5 of 12" and
# escaped the old 6-month bar entirely (measured: 100% of occurrence>=80
# water escaped in ND-43-V-D 2005 and 2010). Years past the record repeat
# the last pheno window. The per-year seasonality tables (GSW_SEAS_*) and
# the 6-month/occurrence constants below them are SUPERSEDED by this rule.
GSW_MONTHLY_V15 = 'projects/JRC/GSW1_5/MonthlyHistory_2022_2024'
GSW_WATER_FRACTION_MIN = 0.5
GSW_WATER_MIN_OBS = 3

# SNOW REFUSAL (owner rulings 2026-08-15/16, register C29-addendum):
# permanent snow/ice breaks the unmix like water does (measured: ndfi
# -500..106 over permafrost, incl. values outside the legal scale), and
# the quality sheet MISSES shadowed northern-aspect snow. Rule chosen by
# the owner on the slider viewer ("the safe region"): snow-index bright
# AND cold year, OR above the no-forest elevation (5000 m sits above
# every Indian treeline, so no forest pixel can be lost to it -- which
# is why one national number needs no west-east tuning).
SNOW_REFUSE_NDSI_MIN = 0.2      # mndwi_median, raw index scale
SNOW_REFUSE_TIR_MAX_K = 280     # tir_median, Kelvin
SNOW_REFUSE_ELEV_M = 5000       # metres

# REFUSAL CODES (owner ruling 2026-08-16): the ndfi level bands carry
# named codes instead of one blind sentinel -- the classifier learns
# refused-water and refused-snow as separate facts. Level bands
# (median/dry/wet) therefore span exactly -20..200. Where a pixel is
# BOTH (a glacial lake), water wins: it is the more specific evidence.
# ndfi_range keeps the old -999 sentinel: its legal span is signed
# -200..200, where -10/-20 are REAL values and would collide.
NDFI_REFUSE_WATER = -10
NDFI_REFUSE_SNOW = -20

# ============================================================================
# BCI -- Biophysical Composition Index (owner ruling 2026-08-13, C24-addendum)
# ============================================================================
# Deng & Wu 2012 (RSE 127): BCI = ((H+L)/2 - V) / ((H+L)/2 + V) on tasseled-cap
# brightness (H), greenness (V), wetness (L), each min-max normalised to [0,1].
# Built = positive, bare soil = near zero, vegetation = negative -- the
# built-vs-bare margin is the index's designed contrast.
#
# DELIBERATE DEVIATION from the paper, owner-approved: the paper normalises
# PER IMAGE, which is temporally inconsistent by construction (a new reservoir
# in a cell would shift every other pixel's BCI that year). We normalise with
# the FROZEN NATIONAL CONSTANTS below -- same principle as the texture
# quantisation bounds (fixed and global so the same landscape reads the same
# in every cell and year). No published BCI time-series citation exists for
# this (searched 2026-08-13); the deviation is documented in
# docs/band_value_ranges.md.
#
# Constants are (min, max) in the x10000 TC working space. FROZEN 2026-08-13:
# derived as p2/p98 of the annual TC medians over 9 cell-year samples --
# 5 contrasting cells (Ghats forest, Himalaya, NW plains, era-join cell,
# southern invariant) x both eras (2005 witness-masked; 2023 strict-masked,
# a documented dodge around the Era B interactive memory wall -- mask choice
# is invisible at whole-cell p2/p98 of a median; one 2023 cell OOMed and was
# dropped). Measured envelope tcb (59, 13647), tcg (-308, 2200),
# tcw (-4665, 1429); frozen values rounded OUTWARD. Never touch again --
# changing these renumbers every BCI value in the archive.
BCI_NORM = {
    'tcb': (0, 14000),
    'tcg': (-500, 2500),
    'tcw': (-5000, 1500),
}
# The freeze gate (C26 ruling 8): build.export() REFUSES to queue a mosaic
# while this is False, so no asset can ever ship on unfrozen constants.
# Flip only alongside a BCI_NORM change under an owner ruling.
BCI_NORM_VERIFIED = True
BCI_SCALE = 100        # ships (value+1)*100 -> 0-200, matching ndfi

# BANDS NEVER TOPOGRAPHICALLY CORRECTED (owner ruling 2026-08-14, register
# C26-addendum): blue's haze-flattened illumination slope makes its fitted C
# nonsense roughly half the time (the -17.7 class of blow-up, C16), and
# under pass-atomic rejection those failures took the five healthy bands
# down with them (42-59% of passes uncorrected on the smoke cells).
# Ruled: blue is UNIFORMLY uncorrected -- every scene, every year, every
# cell -- so its yearly statistics stay one clean population (no mixed
# corrected/uncorrected stacks, no haze-dependent year-to-year flicker);
# the OTHER bands decide each pass atomically. Chosen over widening blue's
# bounds (lets inverted corrections through) and over accepting the
# coverage loss (mixes all six bands' populations, varying by year).
# SUPERSEDED UNDER 'physics' (fold-in 2026-08-30): the blue blow-ups
# were a FITTED-C failure mode; the physics C is read from tables and
# cannot invert, so blue is corrected like every band -- the closed
# ruling (docs/terrain_correction_evidence.md) and every verified v3-v9
# export corrected all six (the lab driver forced this tuple empty).
# The '(blue,)' rule applies only if a fitted estimator is ever re-run.
TOPO_UNCORRECTED_BANDS = ()


# TOPOGRAPHIC CORRECTION INTERIM KILL-SWITCH (2026-08-10, C17.3 interim).
# BOTH estimators tried for C are falsified for Himalayan winter terrain:
# the regression's C inverted the corrected terrain asymmetry (south/north
# steep red 1.33 raw -> 0.72), and the direct search picks even SMALLER C
# (its r(C) curves never cross zero -- shaded slopes are genuinely
# different land, so zeroing the cross-sectional correlation flattens real
# vegetation differences, not just illumination). Until the estimator is
# rebuilt on WITHIN-PIXEL TEMPORAL invariance (same pixel, different sun
# angles, same corrected value), the correction is OFF everywhere: a clean
# uncorrected mosaic beats an inside-out corrected one. Re-enable by
# setting False once the temporal estimator passes the NH/NC gates.
# RE-ENABLED 2026-08-11 after the balance estimator passed its registered
# gates (register C19): NH-44-V-C corrected annual balance 1.031 against its
# own east-sun anchor 0.952, inside [0.95, 1.10]; NC-43-Z-D declines
# correction (annual asymmetry 1.2% -- nothing to correct) and passes
# through unchanged, in range. Inversion cannot recur by construction: the
# acceptance is anchored to the very metric that exposed it.
TOPO_DISABLED = False


# Final belt-and-braces guard on the multiplicative correction factor itself, in case a
# plausible C still produces an extreme ratio for individual pixels.
CORRECTION_FACTOR_MIN = 0.25
CORRECTION_FACTOR_MAX = 4.0

# ============================================================================
# TASSELED CAP -- Wang, Yang, Shi & Chen (2026), Sci. Remote Sens. 13:100353
# ============================================================================
# Table 3, FIVE-BAND set (blue excluded on the paper's own recommendation,
# quoting USGS: blue SR is an output of the aerosol inversion, not an
# independent measurement; the 5- and 6-band sets agree to R^2 > 0.998).
# Derived from Collection 2 Level-2 SURFACE reflectance -- the correct domain
# for this pipeline -- via the Nov 2021 L8/L9 underfly, 43 pairs, modified
# Gram-Schmidt. Coefficients apply to 0-1 reflectance.
#
# Routing: L5/L7/L30/S30 all take the L8 matrix (they sit on the OLI basis
# after bandpass -- ours for TM/ETM+, NASA's for HLS; linear maps compose, so
# OLI-matrix-after-bandpass IS the TM-specific matrix). L9 takes its own.
#
# Single-study caveat recorded in the band recommendation SS5: published
# Dec 2025, no independent replication yet; the soil line is global, so tcg ~ 0
# over Indian bare surfaces is a prediction to verify, not a certainty.
TC_COEFFS = {
    'l8': {                     # green     red      nir     swir1    swir2
        'tcb': [0.4556, 0.5656, 0.5453, 0.0106, 0.4184],
        'tcg': [-0.2419, -0.3931, 0.8355, -0.0567, -0.2927],
        'tcw': [0.1858, 0.1190, -0.0499, -0.9345, -0.2747],
    },
    'l9': {
        'tcb': [0.4326, 0.5191, 0.5420, 0.0421, 0.4978],
        'tcg': [-0.2328, -0.3810, 0.8380, -0.0604, -0.3077],
        'tcw': [0.1966, 0.0883, -0.0295, -0.9646, -0.1492],
    },
}
TC_INPUT_BANDS = ['green', 'red', 'nir', 'swir1', 'swir2']
TC_BANDS = ['tcb', 'tcg', 'tcw']
TC_COEFFS_VERIFIED = True   # transcribed 2026-08-09 from the paper's Table 3,
                            # acceptance-tested on its own Table 2 sample means

# ============================================================================
# COMPOSITING
# ============================================================================

PERCENTILE_DRY  = 25
PERCENTILE_WET  = 75
PERCENTILE_BAND = 'ndvi'

# Amendment to the original getMosaic: min/max/amp replaced by p5/p95/(p95-p5).
# max-min is an extreme order statistic and grows with sample size by construction,
# inflating amp by ~45% between a sparse Era A year and a dense post-2016 year with
# no real change. Percentile range is N-stable. See spec 3.5 and predictions B1.
RANGE_LOW_PCT  = 5
RANGE_HIGH_PCT = 95

# MAD_SCALE RETIRED 2026-08-19 (owner ruling). It was 1.4826, the constant that
# puts a median absolute deviation on a standard-deviation scale for normally
# distributed data, and it existed so the exported *_mad bands could be read
# beside amp and stdDev. Both of those LEFT THE PRODUCT in the 2026-08-13 stat
# prune, so the factor was matching a scale nothing else used. The *_mad bands
# now ship the RAW median absolute deviation.
#   - no information was lost: a constant multiplier is invisible to any
#     classifier, and only changed what a human read off the number
#   - the normality it assumed is false for a double-cropped pixel's year
#   - safe to do now and only now: no mosaic assets exist to renumber
# DO NOT confuse this with masking.MAD_TO_SIGMA, which is the same number
# doing a real job -- the witness mask's cold threshold was tuned on a
# standard-deviation scale, so removing it there would silently make the
# witness 48% stricter about calling cloud. That one stays.

# Snow is retained in the stack but must not decide the dry/wet split: it sits at the
# bottom of every pixel's NDVI distribution, so above the snowline "dry" would mean
# "snow-covered" -- a different meaning from the same band name elsewhere in India.
# Thresholds are computed on snow-free observations where there are enough of them.
#
# Two conditions, guarding different failures. The COUNT guards the percentile
# estimate. The QUARTER SPAN guards representativeness: a pixel can have 8 snow-free
# observations that all fall in August, which is enough to compute a percentile from
# and useless as a seasonal split.
SNOW_BAND               = 'snow'
SNOW_FREE_MIN_OBS       = 6
SNOW_FREE_MIN_QUARTERS  = 2


# ============================================================================
# GEOMETRY / EXPORT
# ============================================================================

EXPORT_CRS       = 'EPSG:4326'
EXPORT_SCALE     = 30
EXPORT_MAX_PIXELS = int(1e13)
GRID_BUFFER_M    = 100        # applied to the cell before use as export region


# ============================================================================
# PILOT
# ============================================================================

PILOT_CELLS = {
    'NH-44-V-C': 'Uttarakhand - plain to high Himalaya, terrain test',
    'NG-42-X-D': 'Thar - three WRS paths, flat, seam test',
    'NH-43-X-C': 'Punjab - flat, data-rich, null control',
}


# Minimal band set for fast iteration. 12 bands against 223.
LITE_BANDS = [
    'blue_median', 'green_median', 'red_median',
    'nir_median', 'swir1_median', 'swir2_median',
    'ndvi_median', 'ndvi_median_dry', 'ndvi_median_wet',
    'ndvi_swing', 'ndvi_mad', 'ndvi_stdDev',
    'usable_count', 'snow_count', 'quarters_present', 'tir_median',
]

# (pheno_year, [variants]) -- lab comparison plan; the retired
# era-split entries left with the 2026-09-01 excision
PILOT_RUNS = [
    (2005, ['nocorr', 'brdf', 'full']),
    (2023, ['notopo', 'full']),
]


def pheno_range(year, end_year=None):
    """
    ('YYYY-MM-DD', 'YYYY-MM-DD') spanning phenological years `year` to `end_year`.

    With end_year omitted this is one pheno-year, as before. With it set the
    window covers several (a lab convenience; the product is annuals only).
    """
    last = year if end_year is None else end_year
    start = '{}-{:02d}-{:02d}'.format(year, PHENO_START_MONTH, PHENO_START_DAY)
    end   = '{}-{:02d}-{:02d}'.format(last + 1, PHENO_START_MONTH, PHENO_START_DAY)
    return start, end


def era_of(year):
    """Always 'A' since the Collection-2-only ruling (2026-08-23): every
    year is built from the in-house Landsat C2 chain. Kept for signature
    stability; ERA_A_LAST_YEAR survives as the sensor-history boundary
    (L5/L7 to 2012, L8/L9 after) used by build.witness_sensors."""
    return 'A'

# ============================================================================
# EXPORT BAND ORDER (owner ruling 2026-08-13, second sitting)
# ============================================================================
# STAT-MAJOR: all medians first, then dry medians, wet medians, amplitudes,
# wobbles -- so the exported file OPENS AS TRUE COLOUR (bands 1-3 are
# red/green/blue medians; QGIS and most viewers paint bands 1-2-3 as RGB) and
# the first 20 bands are the whole "typical year". Within each stat block the
# quantities run SEMANTICALLY, never alphabetically: raw light (display
# colours first, then outward in wavelength), SMA family (living -> dead ->
# soil -> dark -> derived index), indices (greenness pair, moisture, water,
# tasseled cap, built). Single-stat groups follow: season anatomy, terrain,
# bookkeeping; position dead last -- machine bands no one visualises.
# The final .select(BAND_ORDER) in build.py doubles as a CONTRACT: a missing
# or misnamed band fails the build instead of shipping silently.
_ORDER_RAW = ['red', 'green', 'blue', 'nir', 'swir1', 'swir2', 'tir']
_ORDER_SMA = ['gv', 'npv', 'soil', 'shade', 'ndfi']
# bci and ibi carry MEDIAN + MAD only (owner 2026-08-13): the built classes
# they exist for have no seasons, so seasonal cells would be dead weight.
_ORDER_IDX = ['ndvi', 'evi2', 'ndmi', 'mndwi', 'tcb', 'tcg', 'tcw',
              'bci', 'ibi']
_BUILT = ('bci', 'ibi')
# tir carries MEDIAN + MAD only (owner ruling 2026-08-16, C30): temperature
# receives no corrections and its seasonal split adds little the classifier
# can use -- tir_median, tir_mad and tir_count suffice. The C27 push-back
# (tir_range in the urban recipe, tir_median_dry irrigation signal) was
# heard and overruled; classification-time recipes must adapt.
_SEASONLESS = ('tir',)
# BAND CONTRACT v2 (owner rulings 2026-08-30, band_and_property_contract doc):
#   'range' -> 'swing' (it is SIGNED wet-median-minus-dry-median, not
#     max-minus-min; the old name misled);
#   ndfi_mad ADDED (116 -> 117; more outlier-robust than the swing;
#     carries the same -10/-20 refusal codes, legal because a real mad
#     is >= 0; the C24 wild-tails objection to per-scene ndfi is
#     answered by MAD's own tail-robustness -- flagged for review);
#   ndvi_q1..q4 -> ndvi_q1_median..q4_median;
#   position (lon/lat) is a CLASSIFIER INPUT (C29 "export only"
#     reversed by owner) and moves before the bookkeeping block, which
#     is dead last and never a classifier feature.
_STAT_CARRIERS = {
    'median':     _ORDER_RAW + _ORDER_SMA + _ORDER_IDX,
    'median_dry': [q for q in _ORDER_RAW if q not in _SEASONLESS] + _ORDER_SMA
                  + [i for i in _ORDER_IDX if i not in _BUILT],
    'median_wet': [q for q in _ORDER_RAW if q not in _SEASONLESS] + _ORDER_SMA
                  + [i for i in _ORDER_IDX if i not in _BUILT],
    'swing':      [q for q in _ORDER_RAW if q not in _SEASONLESS] + _ORDER_SMA
                  + [i for i in _ORDER_IDX if i not in _BUILT],
    'mad':        _ORDER_RAW + _ORDER_SMA + _ORDER_IDX,
}
BAND_ORDER = (
    ['{}_{}'.format(q, s)
     for s in ('median', 'median_dry', 'median_wet', 'swing', 'mad')
     for q in _STAT_CARRIERS[s]]
    + ['ndvi_q1_median', 'ndvi_q2_median', 'ndvi_q3_median',
       'ndvi_q4_median', 'ndvi_p25', 'ndvi_p75']
    + ['elevation', 'slope', 'aspect_sin', 'aspect_cos', 'hand']
    + ['lon', 'lat']
    + ['usable_count', 'tir_count', 'snow_count', 'quarters_present',
       'q1_count', 'q2_count', 'q3_count', 'q4_count']
)   # 117 bands: 21+18+18+18+21 stats + 6+5+2+8 singles (band contract
    # v2, owner 2026-08-30 -- was 116)

# ============================================================================
# AGGREGATION-SAFE ILLUMINATION TERM (2026-08-20)
# ============================================================================
# cos(i) expands into a form LINEAR in three terrain-only quantities with
# scene-constant scalar weights, so a coarse reduction is the reduction of a
# sum -- exact at any scale. The old route fed aspect_smooth (compass
# BEARINGS in degrees) into a cosine evaluated at the reduction scale, so the
# bearings were averaged BEFORE the cosine: north at 350 deg and north at
# 10 deg average to due south.
#
# MEASURED, NI-43-Z-A hillside pixels, sun azimuth 150 deg zenith 40 deg:
#     30 m   old 0.6527   truth 0.6527   (identical -- no error at native)
#    300 m   old 0.7209   truth 0.6533   median gap 0.066, 90th pct 0.309
#    600 m   old 0.7629   truth 0.6542   median gap 0.105, 90th pct 0.418
# Effect on ACCEPTED fits (L7 2005, same fitter, only this term changed):
#    red 1.064->0.933  nir 1.056->0.929  swir1 0.592->0.533  swir2 0.528->0.463
# ~10% and NOT a constant offset (an L30 2021 test at 600 m moved +0.851), so
# stored C values cannot be patched -- they have to be made again.
#
# DEFAULT OFF was the fitted-C rule (turning it on changes every fitted
# C, so it demanded a refit). ON since the fold-in (2026-08-30): the
# 'physics' estimator has no fitted C to invalidate, and every verified
# physics export (v3-v9, the lab driver) forced this True -- the linear
# terrain read is the aggregation-safe form the physics factor was
# validated on. Re-running a FITTED estimator against stored fits would
# need this False again; those are lab comparators now.
TOPO_ILLUM_LINEAR = True
TERRAIN_ILLUM_ASSET = INPUTS_ROOT + '/terrain_illum'
