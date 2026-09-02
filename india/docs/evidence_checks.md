# ATBD evidence — small checks, accumulating (2026-09-01)

One file per small evidence job as each lands; the two large recovered
digs live in their own files (evidence_endmembers,
evidence_sensor_harmonisation).

## Year-2000 atmosphere-input check — CLEAN (done 2026-09-01)

Question: the MERRA-2 aerosol input changes character around 2000
(satellite aerosol data starts being folded in); aerosol drives the
physics C, so a step could imprint on corrected reflectance in
mountains as fake change.

Method: cached stable-point series (700 invariant points, NC-43-X-D —
hilly Anamalai cell; sample file held in the private archive, not part
of this release).
Per band, the class-pooled median annual reflectance per year; the
"3-year step" at year Y = mean(Y..Y+2) − mean(Y−3..Y−1); the step at
2000 compared against the spread (MAD) of the same step at every
other year.

Result (stored units ×10000): step at 2000 vs typical wobble —
blue −13.8 vs 29.2 (score 0.1); green −2.6 vs 29.4 (0.1); red −46.5
vs 37.7 (0.5); nir +31.4 vs 50.9 (0.3); swir1 −27.2 vs 64.8 (0.1);
swir2 −60.6 vs 81.1 (0.1). The 2000 step is indistinguishable from
ordinary year-to-year wobble in every band.

ATBD text: §10 discloses the MERRA-2 era change and cites this
negative result; one sentence, per the disclosure-size rule.

## Count anchor — DONE (2026-09-01; owner to approve the advice text)

usable_count + quarters_present sampled at the 700 stable points
across all 38 sandbox years of NC-43-X-D (sample file held in the
private archive, not part of this release). Percentiles of
usable_count by era — 1987–1999: p10 1, p25 1, MEDIAN 1, p75 2,
max 6; 2000–2012: 3/4/6/9/20; 2013–2025: 10/12/15/20/63. Median
quarters_present: 1 / 3 / 4 by era. So pre-2000 in this wet-Ghats
cell a typical pixel's year rests on ONE observation in ONE quarter.

Drafted advice (for §6/§10, pending owner approval): "usable_count
is the how-many-photographs-went-into-this-answer band. In the
verified wet-Ghats cell, a typical pixel rests on about 15 usable
observations a year after 2013, about 6 in 2000–2012, and only 1–2
before 2000. Treat any pixel-year with usable_count below about 3 as
a sketch rather than a measurement — and check quarters_present
beside it: below 3, the seasonal bands describe part of a year, not
a year. These anchors come from one very cloudy cell; drier regions
run higher, and national numbers follow the national build."
Caveat recorded: single-cell calibration; the anchor sentence must
say so until the national run replaces it.

## Area and archive-depth numbers — DONE (2026-09-01)

- Land above 5,500 m (the correction tables' elevation ceiling):
  32,406 km² of 3,270,257 km² = 0.99% of India — glacier and rock.
  §10 gets its one sentence, per the disclosure-size rule.
- Single-TRACK cells (≤1 distinct L5 WRS path with any Tier-1 scene,
  pheno-1990–1999): 5 of 283, all islands (NC-43-Y-C, NC-46-Y-D,
  ND-43-V-A, ND-46-Y-B, ND-46-Y-D).
- The truer measure is archive DEPTH: median cell = 395 Tier-1 L5
  scenes across the 1990s decade; ELEVEN cells under 20 for the whole
  decade: NC-43-Y-C 3 (Lakshadweep), NC-43-Z-D 4, NC-46-Y-B 4,
  NC-46-Y-D 9 (the new Nicobar cell), NB-46-X-C 10, NB-46-X-A 12,
  NC-46-Z-C 12, NC-46-X-A 13, NC-46-V-B 14, NC-46-V-D 14,
  ND-46-Y-B 15. These are the cells whose pre-2000 mosaics rest on
  almost nothing; §10 names them with the numbers.

## Sunlight-angle (BRDF-after-topo) check — DONE (2026-09-01)

Question: applied after the terrain correction, does the flat-ground
BRDF adjustment repaint hill patterns?

Method: finished NC-43-X-D 2019 mosaics, dense forest only
(decoded ndvi > 0.6), nir_median. (a) Slope-bin drift; (b) the
sharper test — same steepness (15–40°), sun-facing (south) vs shady
(north) faces, v2 against the uncorrected legacy as the yardstick.

Results (stored units):
- Slope bins, v2: 0–5° 2872; 5–15° 2872; 15–25° 2800; 25–40° 2735
  (−4.8% flat→steepest). Legacy drifts more (−5.7%). No sign of
  reintroduced terrain from the BRDF step.
- Asymmetry, steep forest: legacy sunlit 2800 vs shady 2543 = +256
  (the raw terrain signature). v2 sunlit 2672 vs shady 2895 = −224 —
  the correction removes the signature and OVERSHOOTS, flipping the
  sign at similar magnitude (~2% absolute reflectance, ~8% relative).

Verdict: the BRDF order is fine; the overshoot is the KNOWN, RULED
nir over-correction in steep wet terrain (owner ruling 2026-08-29:
correction closed, no damping, accepted residual; per-band fixes
belong in future C tables). ATBD: the terrain section's residual
disclosure now carries these numbers; §10 one line; future-work line
(per-band table refinement) noted.

## Residual-cloud bound + the score's definition — DONE (2026-09-01)

Definition (the "cloudy-median" score, stated operationally at last):
the share of a product's VALID land pixels whose stored blue_median
exceeds 1000 (reflectance 0.10) — a brightness proxy for cloud
surviving into the annual composite. Circularity admitted in one
sentence: the score detects cloud by brightness, as the masks partly
do, so cloud that fools both is invisible to it; the human-checked
stratified sample (owner-ordered) is the independent grade.

Result, NC-43-X-D, all 38 years, v2 vs legacy: v2 median 0.06%;
from 1999 onward v2 ≤ 0.5% every year (mostly ≤ 0.1%). Thin early
years are the honest worst cases: 1991 v2 9.5% (legacy 23.5%),
1987 3.5%, 1995 3.4%, 1994 2.3% — with 1–2 observations per pixel a
cloudy one can BE the median. Caveat: shares are over each product's
own valid pixels, flattering whichever masks more away in thin
years. ATBD: §9/§10 carry the number and both caveats.

## Landsat-7 stripe check — DONE (2026-09-01)

Method: NC-43-X-D 2012 (L7-only year). Stripe zones reconstructed
from the year's least-cloudy real scene (inside its footprint, the
pixels its own scanner missed); the annual mosaic filled those from
other passes. Median mosaic statistics over dense forest, inside vs
outside the stripes.

Result: usable_count 7 vs 8 (exactly the expected one-look loss);
blue −17.9, nir −66.5, ndvi +33 stored units (0.2–0.7% reflectance);
ndvi_mad −80 (slightly smoother inside, fewer looks). The fill
leaves FAINT marks, quantified — not invisible, not disfiguring.
Caveats: one reference scene, one year, one cover class. ATBD:
§5.3's evidence sentence + §10 with the numbers.

## Cloud-mask spot check, eye-marked — DONE pending owner audit
(2026-09-01)

Frame: ten climate anchors (Punjab, Thar, Rann, Central, Deccan,
Odisha, Assam, Tamil, Kerala, Himalaya) × two eras (L5 1995, L8
2019), one deliberately partly-cloudy scene each (catalogue cloud
20–70%), 20 km windows; per scene a raw picture and a picture of
what the production mask (QA-bit ∧ thermal witness) kept. 17 pairs
produced (3 anchor-eras had no qualifying scene); 16 gradeable
(kerala 2019 window was open ocean, unusable). Chips and a
manifest of scene ids were kept locally (not part of this release).

Verdict by eye (mine; owner audit of ~6 pairs pending):
- THICK CLOUD: removed in every pair, with generous halos. No case
  of surviving thick cloud in 16 pairs, either era.
- CONTROL: the fully-clear Odisha 2019 window shows ZERO removals —
  no commission on clean scenes; clear-land Central 2019 shows only
  scattered speck removals (slight).
- Recurring SLIGHT OMISSION, two kinds: (a) bright cloud RIMS
  survive as specks at removal edges (Rann/Tamil/Punjab 2019);
  (b) THIN TRANSLUCENT VEILS — dust and smoke, aerosol rather than
  cloud — partly survive (the Punjab 1995 smoke-plume tail, the Rann
  1995 dust wash). Matches the 1990s haze spikes already seen in the
  stable-point series; the masks are not designed for aerosol.
- SHADOW: caught where ground is dark (Deccan/Thar 2019); sometimes
  kept over brighter desert ground where the darkness test fails
  (Thar 1995) and in some Tamil 2019 smudges — slight-to-moderate.
- MOUNTAIN SNOW: Himalaya 2019 — cloud removed cleanly but much
  high-altitude summer snow removed with it (the recorded
  2026-08-10 rescue-tightening trade; snow_count discloses it).
OWNER AUDIT (2026-09-01, six pairs): five gradings CONFIRMED
(Punjab, Tamil, Himalaya, Deccan, Odisha control). One CORRECTED —
Rann 1995: the removals across the northern third and the central
patch are FALSE POSITIVES (clear arid ground removed as
cloud/shadow); only the bottom-right quadrant's removal is genuine.
So the audited commission story is: over bright arid/saline ground
in the L5 era the mask can remove usable clear pixels. Practical
cost is modest — deserts are observation-rich, so usable_count stays
high — but it is a REAL commission mode and the ATBD states it.
SPOT CHECK CLOSED. ATBD: §9 carries this as the independent,
non-brightness grade of the masks (16 pairs, owner-audited), with
the omission stories (cloud rims, aerosol veils, bright-ground
shadows) and the audited Rann commission mode; §10 cross-refs.

## Witness fail-closed share by era — DONE (2026-09-01)

The thermal witness fails closed where a pixel's year holds under 8
clear thermal readings (no flag can be overruled → near-strict
masking there). Share of India's land in that state, read from the
40 national temperature records: MEDIAN by era — 1986–1999: 56.6%
(peaks: 1997 59.2%, 1999 44.3%); 2000–2012: 10.1%; 2013–2025: 0.6%.
Direction of the induced bias, as ruled acceptable: early composites
are CLEANER but THINNER over most of the country. Compounds the
count-anchor finding. ATBD: §5.2 states the fail-closed rule with
these shares; §10 carries the era-dependent-strictness limitation.

## Era flatness at the three sensor joins — DONE (2026-09-01)

Same step-vs-wobble test as the year-2000 check (cached 700-point
series, class-pooled medians, 3-year windows). Verdict: PASS at every
join, every band. Largest excursion anywhere: nir at 2003, step
-96.2 stored units vs typical wobble 49.8 = 1.5 wobbles (inside
ordinary variation; ndvi 1.3 there). At 2013 no band exceeds 1.2
wobbles (ndvi step +290.3 vs wobble 154.5 = 0.8); at 2017 none
exceeds 0.7. ATBD §9.3 carries the numbers.

## Trim-knob shake — INTERIM (first arm, 2026-09-01; rest overnight)

Sharpest arm: CLOUD_TRIM_DELTA halved 0.03→0.015 (trim twice as
aggressive), full builds, NC-43-X-D 2019 (cloudiest-cell worst case),
vs the full baseline: usable_count identical everywhere (max diff 0 —
counts are pre-trim, confirmed); blue_median mean |Δ| 6.8 stored
units (0.0007 refl), max 749; ndvi_median changes on 15.0% of pixels,
mean |Δ| 84 stored units over all pixels (≈0.056 NDVI over changed
pixels), isolated max 5663; ndvi_mad mean |Δ| 35. Reading: not
knife-edge — 85% of pixels unmoved under a 50% aggressive shove; the
moved sixth are the borderline stacks the trim exists to re-decide.
Remaining arms (delta up, spread up/down, both cells) run overnight
as lite builds; the ATBD §5.8 slot fills from the complete set.

## Seasonal rebuild-stability finding (2026-09-01, from the cleanup
proof hunt — PRE-EXISTING, not caused by the excision)

Rebuilding NC-43-X-D 1990 and comparing against the stored asset:
masks agree on every pixel; annual medians, counts and thresholds
reproduce exactly; but 54 seasonal bands (median_wet/median_dry/
swing families) differ on some pixels, worst ≈ 2,600–3,100 stored
units — and the PRE-cleanup code shows the same behaviour (same 54
bands), so it predates the excision. Best-fitting explanation:
observations lying exactly on a pixel's own season-threshold
(p25/p75 of its NDVI record — in a five-image year the quarter-mark
IS one of the observations) can flip in or out between runs on
last-decimal arithmetic differences; a thin season's median then
swings. Exact mechanism not yet pinned (small probe noted, not
queued).

ATBD consequence (§11 Reproduction): the recipe reproduces the
product; bit-for-bit reproduction holds for annual medians, counts
and masks but NOT for the seasonal picks of thin years. Sits beside
the catalogue-pinning honesty statement.
