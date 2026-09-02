# ATBD evidence — TM→ETM+ transform derivation, recovered (2026-09-01)

Evidence job (spec Part F, debt 5 — RULED: recover). Read-only dig
over pipeline/, scripts/, docs/, data/ and git history. The
derivation is substantially ON RECORD; the few gaps are listed and
must be disclosed as such.

## Coefficients as applied (config.py:863–870; radiometry.py:159–175)

ETM+ = slope × TM + intercept, intercepts in reflectance ×10000,
applied to L4/L5 after BRDF, before the published ETM+→OLI step:
- blue: slope 1.0, intercept −43.5 (offset-only by ruling)
- green: 0.9852, −54.9 (r 0.945)
- red: 1.0234, −48.4 (r 0.962)
- nir: 0.9918, −16.2 (r 0.918)
- swir1: 1.0132, −63.3 (r 0.944)
- swir2: 1.0189, −35.3 (r 0.960)
Order enforced in radiometry.normalise_era_a: BRDF → TM→ETM+ (L4/L5)
→ ETM+→OLI (L5/L7; Roy et al. 2016 Table 2 RMA set, verified against
the paper 2026-08-07). OLI is the reference basis, never transformed.
Coefficients entered at commit 028aeb9 (2026-08-09); untouched since.

## The derivation (an internal one-off derivation script, not part of
this release, + config comments + register C8)

- Pairing: L7×L5 scenes over the same ground ≤ 2 days apart (the
  sidelap of adjacent WRS-2 paths). Both sides identically
  preprocessed up to the application point: witness mask + BRDF, no
  bandpass ("fitted on the quantity it is applied to").
- Change/cloud filter: pixel kept only if |ΔNDVI| < 0.05 in the pair.
- Sampling: 150 random points per pair, 30 m, seed 11.
- Stratification: ten anchor sites across India × four years (2000,
  2003, 2006, 2009 — later years excluded against L5 orbital drift)
  × four elevation bins (500/1500/3000 m) × three NDVI classes
  (0.2/0.5), each stratum capped at 40 samples.
- Result: 3,952 balanced pixel pairs (recorded as nine regions —
  one anchor produced no sidelap data; kerala is the likely one from
  the later refit CSV, but that is inference, not record).
- Fit: reduced major axis per band (slope = sign(r)·sd(L7)/sd(L5)),
  chosen because both sensors carry error; OLS slopes (0.70–0.98)
  would shrink L5's range 7–30%.
- Blue ruling: fitted blue slope swung 0.40–1.01 across strata (TM
  blue noise); offset stable; slope forced to 1, offset −43.5.
- Verification at adoption: L5 2005 cell medians shifted blue −42.6
  / green −67.5 / red −20.6, as composed.

## Independent retention audit (2026-08-21)

Refit on same-path pairs 7–9 days apart found a small
viewing-geometry imprint in the originals but FAILED a held-out test
(fit on five anchors, test on five, 20 splits: current 99.9 vs refit
109.0 median total residual) — originals kept. Independent residuals
of the current transform: median corrected-L5 minus L7 within about
±50 units (×10000) per band on samples of 2,854/3,293 points.
Report and samples: the refit report and the 18,689-row pair sample
(plain QA mask — NOT the original fit's input) are internal data files,
not part of this release.

## Relation to legacy MapBiomas

The countries-mosaics clone contains NO bandpass harmonisation of any
kind. TM→ETM+ is fully in-house; ETM+→OLI is Roy et al. directly.

## NOT recoverable (disclose as [not on record])

The 3,952-sample fitting table (printed, never written); the original
run's console output (per-stratum counts, stability tables); blue's
correlation r; residual statistics beyond r (no RMSE/CI computed);
which anchor dropped out (inference only); the anchor→cell mapping of
the original run; the first-pass (23,441-pair, desert-weighted,
superseded) coefficients.

## Draft ATBD paragraph (recovered facts only — drafter may use
verbatim; gaps stay marked)

"The Landsat 5 TM to Landsat 7 ETM+ continuity transform was derived
in-house from India's own 1999–2011 dual-operation period, using
sidelap pairs: scenes from the two sensors acquired over the same
ground no more than two days apart, where adjacent WRS-2 paths
overlap. Both members of each pair received identical preprocessing
up to the point at which the transform is applied (cloud/shadow
masking and BRDF normalisation, no bandpass), and pixels were
retained only where NDVI differed by less than 0.05 between the
pair, suppressing residual cloud and real surface change. Candidate
pixels were sampled at 150 points per pair and balanced by capping
every region × year × elevation × land-cover stratum at 40 samples —
nine regions across India, four years (2000, 2003, 2006, 2009; later
years excluded to avoid Landsat 5 orbital drift), four elevation
bins (breaks at 500, 1500 and 3000 m) and three NDVI classes (breaks
at 0.2 and 0.5) — yielding 3,952 pixel pairs, on which a
reduced-major-axis regression was fitted per band; RMA was preferred
over ordinary least squares because both sensors carry error and OLS
demonstrably shrinks the noisier Landsat 5 distribution. In the blue
band the fitted slope was unstable across strata (0.40–1.01,
attributed to TM blue channel noise) while the offset was stable, so
blue is corrected by offset only. Recorded per-band correlations
range r = 0.918 (NIR) to 0.962 (red) [blue r and per-band residual
statistics: not on record; the original sample table was not
archived]. A subsequent re-derivation on same-path pairs (identical
viewing geometry, 7–9 days apart) detected a small viewing-geometry
imprint in the original coefficients but failed a held-out test
across regions, so the original coefficients were retained; on those
independent samples the transform leaves median residuals within
roughly ±50 reflectance ×10000 units per band."
