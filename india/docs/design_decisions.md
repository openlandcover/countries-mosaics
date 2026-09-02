# Design decisions — condensed record

This file explains why the pipeline is the way it is. It is a condensed
record of the design choices behind the v2 India annual Landsat mosaics,
including what was tested and not adopted. It is not a project diary:
each entry gives the decision, the reason, and — where a dead end
answers "was this tested?" — the upshot of the test, nothing more. The
full derivations, measurements and equations live in the ATBD
(Algorithm Theoretical Basis Document).

The v2 pipeline is a method evolution of the MapBiomas
countries-mosaics approach that produced the v1 India mosaics. Where v2
does something differently, that reflects new measurements made on the
Indian archive, not a fault in the original design.

## Sources and masking

- **Collection 2 Level-2 surface reflectance, Tier 1, for every year.**
  Landsat 5 (1984–2011), 7 (1999–2021), 8 (2013 on), 9 (2021 on). The
  Harmonized Landsat Sentinel-2 product (HLS) was built into an earlier
  version as the 2013-onward source, tested at length, and retired: the
  shipped pipeline reads Collection 2 alone. Upshot of the HLS testing:
  its blue and green bands are the weakest everywhere; readings over
  water are not comparable across sensors (the atmospheric correction
  does not retrieve aerosol over water); and a single Collection 2
  thermal quantity across all years removes a measured temperature step
  of up to 13.4 K at the 2013 join. Dropping HLS also removed an entire
  parallel processing branch.
- **Phenological year, not calendar year.** Each mosaic covers 1 April
  to 31 March, labelled by the start year, so one crop cycle is not
  split across two products.
- **Scene filtering is minimal by design.** Only scenes reporting more
  than 95 % cloud are refused; all real filtering happens per pixel.
  (A whole-scene cloud threshold discards scenes whose clear part sits
  exactly over the cell.)
- **Landsat 7 after 2003 only plugs holes.** Its scan-line failure
  leaves fixed stripes, so mixing it freely imprints a striped
  observation pattern. Rule: per pixel, per phenological quarter, if
  the clean sensors supplied fewer than three usable looks, Landsat 7's
  looks for that quarter are enlisted; otherwise they are dropped.
  Landsat 7 ends in 2021 — its 2022 orbit change altered its solar
  geometry systematically.
- **Cloud handling is a three-layer defence**, each layer covering a
  failure mode the others cannot, every case observed in this build:
  - The quality-bit mask removes firmly flagged cloud and shadow
    (shadow upheld only where the pixel is actually dark; snow kept by
    design).
  - The thermal witness additionally removes medium-confidence cloud
    flags wherever the look is anomalously cold against that pixel's
    own clear-sky temperature history (a precomputed national record,
    one per year). Where a year's history holds fewer than eight clear
    looks the witness fails closed and upholds every hesitant flag.
  - A stack trim excludes looks whose blue reflectance sits more than
    0.03 above the pixel's annual 25th percentile — catching bright
    cloud that carries no flag at all — but abstains when too few
    looks would survive, so it never calibrates against cloud.
- **Both per-look masks apply everywhere, in conjunction.** Measurement
  showed their blind spots are disjoint: the bit mask misses
  hesitantly flagged cold cloud, the witness misses firmly flagged
  warm cloud. Requiring both to keep a look won or tied every metric
  at a cost of 3–6 % of looks, so one rule applies to the whole
  archive and the earlier two-era mask split was abolished.
- **Accepted residual, disclosed not hidden:** warm unflagged cloud in
  stacks with no clean core (persistently overcast monsoon pixels)
  survives all three layers; the per-pixel observation counts disclose
  it.

## Radiometric harmonisation

- **BRDF correction (adjusting for sun and view angles) is kept
  unchanged.** Blind national testing with same-day image pairs showed
  it closes 50–100 % of the between-satellite gap on every sensor pair
  and cover type without inflating within-satellite scatter. The
  coefficient set is the same one NASA uses for HLS.
- **The TM to ETM+ bandpass transform (matching Landsat 5's bands to
  Landsat 7's) is kept unchanged — a refit was tested and rejected.**
  The refit looked excellent in-sample (67 % residual cut) but was a
  coin flip on held-out cells: overfitting. The underlying reason is
  that the Landsat 5 to 7 relationship varies between regions by
  roughly ten times the difference between any candidate coefficient
  sets, so no national constant can be pinned tighter than the
  quantity actually varies.
- **The fit stays reduced-major-axis, not least squares.** Least
  squares gave lower residuals but would shrink Landsat 5's dynamic
  range by 7–30 % (regression dilution), making early years read
  calmer than late ones — a change that never happened on the ground.
- **The per-cell Landsat 5 to 7 offset was removed entirely.** Tested
  blind on ~40,000 national points restricted to the cells where it
  should work best, it made trees and grassland about 11 % worse and
  cropland 5 % worse. Removing it also deleted an asset dependency and
  all its fallback edge cases.

## Terrain correction

- **Pure physics, bounded.** The correction is SCS+C (a standard
  slope-aware illumination correction) with the C parameter derived
  per scene and per band from 6S radiative-transfer tables (a physical
  model of the atmosphere), driven by reanalysis aerosol and water
  vapour at pass time and per-pixel elevation, with a sky-view term
  and the correction factor bounded to 0.25–4.
- **Empirically fitted C coefficients were built, tested and
  retired.** Fit quality depended on which satellite happened to view
  each slope, not on physics, so the fitted route could not be made
  stable. The physical tables replaced it.
- **Every damping scheme tested was rejected.** Per-band strength
  multipliers and per-band factor ceilings both flattened single bands
  but decorrelated band pairs, printing terrain artefacts into NDVI;
  illumination-dependent damping merely exchanged a bright artefact
  for a dark one. Upshot: in extreme shade the model genuinely fails
  and no multiplier can choose the truth, so nothing dampens the
  physics.
- **Acceptance evidence:** on a test ridge (493 scenes, 2000–2025) the
  correction closes 57–80 % of the sunlit-versus-shaded gap in every
  band, leaves flat ground alone (within 0.5 %), and treats all four
  satellites even-handedly. Known limitation, disclosed: under 1 % of
  pixels in extreme terrain shadow over-brighten.

## Compositing and seasons

- **One asset per grid cell per year**, on the 1:250,000 map-sheet
  grid covering India (283 cells; a boundary update added one cell to
  the legacy 282). Annual products only — multi-year epoch composites
  were considered for thin early years and retired.
- **Median compositing with a per-pixel seasonal split.** Each pixel's
  annual stack of clean looks is reduced to a median; "dry" and "wet"
  medians come from the looks below the pixel's own 25th and above its
  75th NDVI percentile. The split is per pixel, so a single image can
  feed dry statistics in one field and wet in the next.
- **The statistic set is median, dry, wet, swing (wet minus dry) and
  MAD (median absolute deviation, a robust spread measure).** Extreme
  statistics — min, max, amplitude, 5th/95th percentiles, standard
  deviation — were dropped because order statistics grow with the
  number of looks, which steps at every sensor-era join: they encode
  the sensor history as fake land change. MAD replaces standard
  deviation for the same robustness reason.
- **Quarterly NDVI medians and per-quarter counts are carried.** The
  quarters are the product's only within-year sequence information
  (single versus double cropping) and half the built-up signature;
  the counts let a user tell a cloudy quarter from an anomalous one.
- **The product extent is static across all years** (the fixed union
  of the classification regions): a per-year extent would inject
  apparent change into a change-detection product.

## Band set and storage

- **117 bands and 26 image properties, under a sealed contract** (the
  band and property schema document is the authority; the pipeline
  configuration enforces it and the tests guard it).
- **The six optical bands ship at every statistic; thermal ships as
  median and MAD only.** Seasonal thermal statistics were dropped:
  temperature receives no corrections and did not earn a seasonal
  split.
- **Indices are kept only where they pre-compute a class boundary a
  tree classifier cannot form itself.** Every optical index is an
  exact function of the six bands, so "information" is never the
  argument. Kept: NDVI, EVI2, NDMI, MNDWI, the three tasselled-cap
  components (brightness, greenness, wetness — from the 2026
  surface-reflectance coefficient set), and the unmixing family below.
- **Dropped indices, with reasons.** A blue-green index was dropped
  because over the Indo-Gangetic Plain it would encode the 40-year
  aerosol trend as fake land change. Several legacy indices that are
  exact functions of shipped bands were dropped as redundant. One
  legacy index pair was dropped because its calibration was
  North-American conifer specific.
- **Spectral unmixing (SMA) fractions and NDFI are carried** (green
  vegetation, dry vegetation, soil, shade fractions, and the
  normalised difference fraction index built from them). NDFI carries
  two named refusal codes instead of misleading values: −10 where the
  year's water record shows water most of the year, −20 for snow. An
  earlier darkness-based refusal (shade above 0.8) was retired after
  it was measured refusing shaded Himalayan forest.
- **The built-up index (BCI) uses frozen national normalisation
  constants**, deliberately departing from the source paper's
  per-image normalisation: constants that change with image content
  would print fake change across a 40-year record. The constants are
  frozen and must never change — they renumber every stored value.
- **Storage is one rule: true value = stored value × 0.0001** for the
  whole index and tasselled-cap family, every band, every statistic
  (decided 2026-09-01, before the national build). A legacy +1
  shift on index level bands was removed: its stated purpose (unsigned
  storage) had been false since the product went to signed integers,
  and it created a documented decoding trap. Classifier output is
  provably unchanged by the shift. NDFI, BCI and IBI keep their 0–200
  convention because there the shift is load-bearing — it vacates the
  space below zero where the refusal codes live.
- **A pixel with no usable observations is masked, never coded.**
  Absence of data is the mask.
- **Bookkeeping bands (observation counts, quarters present) ship but
  must never be classifier features** — a tree splitting on a count
  learns the sensor eras in one cut. Longitude and latitude ship and
  may be used as features.

## Tested and not adopted — the remainder

- **Texture bands.** Dropped entirely, including a planned
  classification-time recipe. The reasoning: in India's highly
  interspersed landcovers, texture at the scales Landsat can resolve
  is rarely present.
- **Correcting HLS toward Landsat.** Rejected in favour of designing
  around the measured limits; the later move to Collection-2-only made
  it moot.
- **Alternative cloud masks** (a spectral cloud score, dark-object
  shadow detection, the Fmask-based family). Retired with
  measurement: the shipped three-layer defence outperformed or
  subsumed them.
- **Per-year sensor alignment offsets.** Retired before the per-cell
  version was: with a thin archive the two yearly medians sample
  different seasons and cloud luck, so the difference measured
  phenology, not the sensor.
- **A terrain-correction on/off gate per cell.** Retired; the bounded
  physical correction applies everywhere and leaves flat ground
  untouched, so gating became unnecessary.

The full derivation record — equations, measurements, figures and the
evidence behind every entry above — lives in the ATBD.
