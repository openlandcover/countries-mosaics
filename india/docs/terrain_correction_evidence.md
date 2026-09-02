# Terrain correction — CLOSED (owner ruling, 2026-08-29)

**Ruling:** Option 1. The production terrain correction is **pure physics
(SCS+C with 6S-table C, sky view, cos-i floor 0.05) bounded by the shared
soft cap 0.25–4**. No damping of any kind. The correction question is
closed.

## What this means in practice

- **No pipeline change.** The current driver defaults (drop rule off,
  damping off, cap 0.25–4) already implement the ruling. Existing v3
  exports embody it.
- The 18-number vegetation damping table (an internal data file, not
  part of this release) is **shelved**, kept as evidence.
- The tuning lab (an internal code-editor script, not part of this
  release) stays as the instrument that produced the evidence; its knobs
  are lab-only.

## The evidence trail (owner-run experiments, 2026-08-29)

- Per-band strength multipliers: each band individually flatter, but
  terrain artefacts appear in NDVI — band pairs decorrelated.
- Per-band ceilings: same failure, smaller area, still visible in NDVI
  (the soft knee of a ceiling of 3 bends factors from ~2.5, which is
  ordinary deep shade, not just the tail).
- Light-dependent damping (cos-i ramp): NDVI-safe as predicted, but
  swaps the bright tail for dark patches — a sideways move.
- Conclusion: in the extreme-shade tail the model genuinely fails and no
  multiplier can choose the truth; every correction-side remedy either
  damages index integrity or repaints the artefact a different colour.

## ATBD text (approved in substance by the owner)

> Topographic correction applies the full physical SCS+C correction with
> per-scene, per-band C derived from 6S radiative-transfer tables
> (MERRA-2 aerosol and water vapour at pass time, per-pixel elevation),
> with the correction factor bounded to 0.25–4. The bound was retained
> after systematic testing showed that all band-selective damping schemes
> (per-band strengths, per-band factor ceilings) degrade index integrity
> by decorrelating band pairs, while illumination-dependent damping
> merely exchanges a bright artefact for a dark one. Residual
> over-brightening of a small fraction (< 1 %) of pixels in extreme
> terrain shadow is a known limitation.

## Filed for the future (not open questions)

- Three independent methods (scene calibration, median calibration, the
  owner's visual tuning) agree the physics is biased per band: red
  under-corrected, infrared over-corrected. Any future per-band remedy
  belongs in the **C tables themselves**, never in post-hoc multipliers.
- Related decisions that remain genuinely open are tracked elsewhere:
  cloud leakage through the QA mask, Tier 2 intake, and the three
  document reviews (property names, asset inventory v2, ATBD outline v2).
