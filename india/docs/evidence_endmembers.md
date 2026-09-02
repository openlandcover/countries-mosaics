# ATBD evidence — SMA endmember table and provenance (2026-09-01)

Evidence job (spec Part F, endmember table). Read-only dig over
pipeline/sma.py, pipeline/config.py, the legacy clone
countries-mosaics/, docs/ and git history. Facts only; nothing
invented.

## The table

Units: surface reflectance × 10000. Band order blue, green, red,
nir, swir1, swir2. Source pipeline/sma.py:81–86
(ENDMEMBERS_INHERITED). One matrix serves every sensor.

- GV (green vegetation): 119, 475, 169, 6250, 2399, 675
- NPV (dry vegetation): 1514, 1597, 1421, 3053, 7707, 1975
- Soil: 1799, 2479, 3158, 5437, 7707, 6646
- Cloud: 4031, 8714, 7900, 8989, 7002, 6607 (solved, then
  discarded — cloud screening belongs to the masking stage)

Shade is NOT a matrix endmember: it is recovered after compositing
as the floored closure deficit 1 − (GV+NPV+Soil), clamped to [0,1]
(sma.py:265–269; abs() deliberately avoided — it would label bright
overshoot as shadow).

## Constraints and special handling (exact)

- Scene unmixing UNCONSTRAINED (sumToOne=False, nonNegative=False,
  sma.py:120); negatives kept for the spread statistics; overflow
  cap ±3.0 (config SMA_OVERFLOW_CAP) is a guard, not physics.
- Composite-level clamp of fraction medians to [0,1] (sma.py:261–262).
- NDFI: gvs = gv/max(sum, 1e-6); NDFI = (gvs−(npv+soil)) /
  max(gvs+npv+soil, 0.05) — the 0.05 denominator floor damps fake
  extremes ringing gated water; stored (NDFI+1)×100 clamped 0–200;
  refusal codes −10 water / −20 snow; ndfi_swing keeps −999.
- Tamed per-scene NDFI (clamped fractions + floor) feeds ndfi_mad
  only (sma.py:143–161).
- Cloud-fraction rejection disabled (SMA_CLOUD_REJECT=None): with
  Amazonian endmembers it mistakes Thar sand and salt crust for
  cloud.
- Unmixing misfit RMSE computed internally, never exported (C24).

## Provenance verdict

IDENTICAL to the legacy MapBiomas clone, value for value — all 24
numbers match countries-mosaics/modules/SmaAndNdfi.py exactly. The
legacy module carries byte-identical matrices under all eight sensor
keys, so our single-matrix collapse changes nothing numerically.
What differs is the algorithm around the values: legacy clamps
fractions ≥0 per scene and uses |100−sum| for shade, no NDFI
denominator floor; ours is unconstrained per scene, floored-deficit
shade, floored denominator.

Attribution (their comments): Souza et al. (2005) NDFI methodology,
Adams et al. (1995), "adapted from Carnegie Institution". Neither
repo contains a derivation script, site description, DOI or table
reference for the 24 numbers — their empirical derivation is NOT ON
RECORD and the ATBD must say so.

Recorded owner ruling (in the internal spec-amendments log, not part
of this release): the endmember choice is FINAL — the inherited Amazonian set
ships, for cross-country comparability; recorded as the product's
largest known scientific compromise; the India derivation dropped,
not deferred.

## Draft ATBD caption + provenance sentence (for the drafter)

Caption: "Spectral endmembers used for linear unmixing, in surface
reflectance × 10 000, band order blue/green/red/NIR/SWIR1/SWIR2. One
matrix serves all sensors. Shade is not a matrix endmember: it is
recovered after compositing as the floored closure deficit
1 − (GV+NPV+Soil), clamped to [0,1]. The cloud endmember is solved
for but discarded; cloud screening is handled by the masking stage."

Provenance: "The endmember values are inherited unchanged from the
MapBiomas countries-mosaics codebase used for the predecessor
product, whose source module attributes them to the NDFI methodology
of Souza et al. (2005), with additional citations of Adams et al.
(1995) and an 'adapted from Carnegie Institution' note; that module
provides no derivation script, site description, or DOI for the
numeric values, so their empirical derivation is not on record. They
are Amazon-derived, not re-derived for India; retaining them is a
recorded decision (final, for cross-country comparability), logged
as the product's largest known scientific compromise, with the
unmixing misfit computed internally as its evidence base."
