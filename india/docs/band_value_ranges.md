# Band finalisation — three-agent review synthesis and decision sheet

2026-08-13. Three independent reviewers (classification-evidence / India-domain /
temporal-consistency adversary) answered the owner's eight keep/drop questions plus
the urban question. Full reports in session transcripts. This sheet is the synthesis;
owner decisions pending are marked ▢.

## Unanimous (all three)

- **Raw light: keep all 7.** Blue and tir keep their medians but their spread stats
  are era/atmosphere channels — prune in the stat matrix.
- **SMA family: keep all 5.** India note: npv is the workhorse (stubble/dry grass —
  the grassland and post-harvest contrasts NDVI is blind to). Vertisol + Rann
  caveat: fractions there are classifier features, not interpretable fractions;
  training samples must cover both surfaces.
- **Season anatomy: keep all 6.** The quarterly bands are the only sequence
  information (double-crop vs single-crop) AND half the urban signature (urban =
  the phenology-free class). Thin-quarter gating needed (see bookkeeping).
- **Terrain: keep all 5.** hand = floodplain wetlands; aspect = Himalayan forest
  types.
- **ndmi: keep.** Dry-season canopy moisture (evergreen vs deciduous, tea vs wet
  forest); ratio survives the era join where tcw (magnitude) does not. Bonus fact:
  NDBI, the standard urban index, is exactly −ndmi — already owned.
- **ndti: keep.** Only swir1↔swir2 contrast in the set: IGP residue/tillage/burn
  cycle + built-vs-soil swir shape. Protect the `ndti_median_dry` cell.
- **bgi: DROP.** Over the IGP it would encode the 40-year aerosol trend as fake
  land change; its legend value (turbid vs clear water; laterite) is unrewarded.
  Two reviewers drop outright, one allows median-only. ▢ drop all 8 cells
- **Bookkeeping: keep in the product, NEVER as classifier features** (a tree
  splitting on usable_count learns the sensor eras in one cut). India addition:
  **add per-quarter usable counts** (minimum: q2_count) — the monsoon quarter is
  structurally thin exactly in the Ghats/NE belt where the plantation triad must
  be decided; the classifier must be able to tell "cloudy" from "anomalous".
  ▢ add 4 per-quarter count bands (or q2_count only)
- **lon/lat: never in the default feature list** (place-memorisation suppresses
  change). 2-of-3: keep in the mosaic (costless; forecloses nothing); coarsened
  position (agro-climatic zone) if a spatial feature is ever needed.
- **Urban: NO new spectral band exists** — the six-band ratio space is full.
  The urban recipe is already in the stack: high tcb + low ndvi + FLAT
  ndvi_q1..q4 + near-zero ndvi_range + entropy_swir1 + tir_range as the
  built-vs-bare tie-breaker (impervious LST swings less than bare soil between
  seasons — daytime SUHI is sign-unstable in India, so a dedicated thermal-urban
  band is a trap; nightlights fail pre-1992; WSF/GHSL are Landsat-derived and
  circular). ▢ name built-vs-bare as tir_range's protected class pair;
  WSF Evolution (annual 1985–2015) + forest_plantations asset used for
  TRAINING-SAMPLE MINING only, never as features.

## The one split: texture — and the reconciliation

- Consistency: drop both from the archive (kernel bands are era-watermark magnets;
  and entropy is computed FROM the exported median bands, so it is recomputable at
  classification time — dropping costs nothing, ever).
- Evidence + India: keep (min. entropy_swir1) — the owner's by-eye "nothing there"
  predates the requantisation fix (the fixed band has never been evaluated);
  project docs name texture the ONLY discriminator for the plantation triad and
  built-vs-bare; ~9-pt producer's-accuracy gains published for rubber-vs-forest;
  entropy_swir1 is effectively the village-detection band.
- **Reconciliation all three accept: take texture OUT of the mosaic export,
  compute it at classification time from green_median/swir1_median (identical
  values by construction, C15 reproject included), and let a stratified
  separability test — not the eye — decide whether the classifier uses it.**
  ▢ adopt reconciliation | keep in mosaic | drop forever

## The two reframings (adopt both)

1. **Mosaic ≠ feature list ≠ side-car.** The archive errs generous (re-export is
   the expensive mistake); the classifier's feature list is a versioned SUBSET,
   free to change; ancillary statics (WSF, distance-to-coast, climate zone) join
   at classification time. Half the keep/drop anxiety dissolves: a band can ship
   and not be fed to the forest. lon/lat, bookkeeping, and (if kept) bgi_median
   are export-only by default.
2. **The stat axis is the big lever, and era-flatness is the arbiter.**
   p5/p95/stdDev step at every era join BY CONSTRUCTION (order statistics grow
   with n): ~60 bands of structural fake change. Prune to
   median + dry + wet + range + MAD, with named exceptions only where an extreme
   names a class pair (mndwi p95 = transient flood; ndvi, tir, gv candidates;
   evi2 keeps 8 for mosaics-1 continuity). And the selection test for every
   surviving cell is the INVARIANT-SITE ERA-FLATNESS test (task #3 machinery):
   any band whose stable-site year-over-year delta steps at 2003/2013/2017 is
   disqualified as a feature regardless of importance — RF importance is the
   wrong arbiter (usable_count would top it by learning eras).
   ▢ global stat prune with exceptions list

## Net effect if all adopted

Roughly 171 → ~105–115 exported bands (drop bgi −8, texture −2, stat prune −50±,
add +4 quarter counts), with every physical quantity still present at
median/dry/wet/range/MAD, and a separate, versioned classifier feature list
(~90) that excludes bookkeeping, position, and anything failing era-flatness.

## Standing risk to carry forward (India reviewer's top find)

The wet-season statistics are thinnest exactly where India's hardest class
triad (natural forest / timber plantation / tea-coffee-rubber) must be decided
— monsoon-quarter clear looks are near-absent in the Ghats/NE in single-satellite
years. Mitigations: per-quarter counts (above), condition wet/range cells on
them, lean on epoch mosaics pre-2000 there.

---

## BCI — adopted as a mosaic band (owner ruling, second sitting 2026-08-13)

**What it is.** Deng & Wu 2012 (RSE 127, 247–259): BCI = ((H+L)/2 − V)/((H+L)/2 + V)
on tasseled-cap brightness (H), greenness (V) and wetness (L), each normalised to
[0,1]. Value story from the paper: **built = clearly positive, bare soil = near
zero, vegetation = negative** — built-vs-bare is the *designed* margin (built
fabric keeps some low-albedo/darkness signal; bone-dry soil is uniformly bright).

**Our deliberate deviation, documented in full.** The paper normalises H/V/L by
each image's own min and max. For a 40-year, 282-cell change product that is
temporally inconsistent *by construction*: the normalisation constants would
change with cell-year content (a new reservoir shifts every other pixel's BCI
that year), printing fake change. We therefore normalise with **frozen national
constants** (config.BCI_NORM). Literature status, stated honestly: a targeted
search (2026-08-13) found **no published BCI time-series application with fixed
normalisation** — the deviation rests on the general change-detection principle
that transformations must use time-invariant parameters, and on this product's
own precedent (texture quantisation bounds "fixed and global so the same
landscape reads the same in every cell and year", register C13).

**Constants — FROZEN 2026-08-13:** tcb (0, 14000), tcg (−500, 2500),
tcw (−5000, 1500), ×10000 working space. Derived as p2/p98 of annual TC
medians over 9 cell-year samples (5 contrasting cells × both eras; 2023 rows
strict-masked as a documented dodge around the Era B interactive memory wall —
mask choice is invisible at whole-cell p2/p98; one 2023 cell OOMed, dropped),
rounded outward. Measured envelope: tcb (59, 13647), tcg (−308, 2200), tcw
(−4665, 1429). Verified after freezing: forest cell bci_median p5–p95 = 60–91
(below neutral = vegetation negative, matching the paper — the provisional
seed's tcg max of 6000 was ~3× too wide and had squashed the vegetation term).
NEVER change these: they renumber every BCI value in the archive.

**Bands.** `bci_median`, `bci_median_dry` (0–200, (x+1)×100, int16). The DRY
variant carries the built-vs-bare margin — monsoon-wet dark soils (vertisols)
creep toward "built" in the wet season. India caveats on record: Rann salt
crust will read extreme-bright; check both surfaces in training data.

**Related documentation notes (same sitting):** NDBI ≡ −NDMI (identical to any
tree classifier — the product already carries the standard built-up index under
ndmi's name). IBI is a recombination of −ndmi, a SAVI-like greenness and mndwi,
all derivable from exported medians — classification-time trial feature, never
a mosaic band.

## Transient water — closed by prediction (owner + assistant, same sitting)

mndwi extremes are NOT carried. Mechanism: the dry/wet split ranks by NDVI, and
flooded looks have the LOWEST NDVI a pixel shows — so floods route into the
small "dry" stack (bottom quartile of looks), whose median 2–3 flood scenes can
dominate. **Pre-registered signature of transient water: mndwi_median_dry HIGH
(watery), mndwi_median_wet lower, mndwi_range strongly NEGATIVE** — inverse of
permanent water (both high, range ≈ 0) and dry land (both low). Known residual
blind spot, accepted: a flood captured in a single look of a thin year can be
out-median'd (a p90 band would be equally unstable at that depth). Verify the
signature in the lab on a tank/floodplain cell before campaign export.

---

## Scaling audit vs the legacy mosaicing script (2026-08-13, third sitting)

Legacy conventions, read from `countries-mosaics` (SpectralIndexes.py,
SmaAndNdfi.py, DataType.py, country scripts):
reflectance ×10000 uint16 · ratio indices (value+1)×10000 uint16 (0–20000) ·
SMA fractions ×100 byte (0–100) · shade ×100 byte · NDFI (value+1)×100 byte
(0–200) · stdDev int32 · no thermal exported.

**Verdict: every quantity with a legacy counterpart already matches legacy
numerically.** Reflectance ×10000 ✓ · ndvi/evi2/ndmi(-as-ndwi) (x+1)×10000 ✓ ·
gv/npv/soil 0–100 ✓ · shade 0–100 ✓ (maths differs: floored deficit, not abs —
documented defect fix, same scale) · ndfi 0–200 ✓. New quantities follow the
nearest convention: tc* signed ×10000 (reflectance-space rotations),
bci/ibi 0–200 (the ndfi convention), mad in parent units, ranges signed in
parent units, tir Kelvin ×10.

**One deliberate typing divergence, kept:** int16 everywhere legacy used
uint16/byte — required to carry negative reflectance retrievals, signed
ranges, and the −999 sentinel; values are unchanged, only the container.
No rescaling action needed.

## Legacy vs new — the band diff (quantity level)

**Common (same numbers, sometimes better maths):** blue, green, red, nir,
swir1, swir2 (median/dry/wet) · ndvi, evi2 (+ amp→range) · ndwi→**ndmi**
(renamed; same pair, same scale) · gv, npv, soil, shade, ndfi · slope ·
texture-as-concept (legacy green_median_texture ↔ our classification-time
entropy).

**Removed from legacy, each with cause:** cloud fraction (witness mask owns
cloud) · gvs, sefi, wefi, fns (exact functions of exported fractions; wefi≡veg)
· savi (superseded by tcg) · gcvi (function of ndmi+mndwi) · cai (reformed to
ndti, then dropped by owner) · pri (both PRI wavelengths sit inside one
Landsat band — never computable) · hallcover/hallheigth (N-American conifer
calibration; worst blow-up offenders) · min/max/amp (extremes grow with stack
depth — fake change at era joins) · stdDev (→mad) · biomes (regions asset
lives separately) · red_edge_* (S2-only variant, not applicable).

**Added by us:** tir family (legacy exported NO thermal) · mndwi (legacy had
no water index at all) · tcb/tcg/tcw · bci, ibi · ndvi_q1..q4 + ndvi_p25/p75 ·
_range and _mad statistic families · elevation, aspect_sin/cos, hand ·
usable/tir/snow counts, quarters_present, q1..q4_count · lon/lat · the −999
refusal semantics on the ndfi family.

## Addendum (2026-08-16, register C29 + addenda): ndfi refusal recode

The ndfi LEVEL bands (median, median_dry, median_wet) now span exactly
−20..200: real readings 0..200, plus two NAMED refusal codes the
classifier learns as separate facts —

- **−10 = refused WATER**: that year's JRC record shows water more than
  half the year (>50% of months, i.e. ≥6 of 12), from the assembled
  1984–2024 yearly series (2025+ repeats 2024).
- **−20 = refused SNOW**: snow index ≥ 0.2 AND year temperature ≤ 280 K,
  OR elevation ≥ 5000 m (above every Indian treeline).

Water wins where both apply (glacial lakes). ndfi_range keeps the −999
sentinel — its signed −200..200 span would collide with the codes — and
its both-parents rule now tests "both parents ≥ 0". The C24 shade>0.8
darkness refusal is retired (measured refusing shaded Himalayan forest).

## Value ranges, band by band (added 2026-08-16, C29 addenda)

> [!note] How to read this
> Every band's LEGAL range, its special values, and the basis, plainly.
> Rule of the product: a special value must be IMPOSSIBLE as a real
> reading in that band's own range. That is why the ndfi level bands can
> use −10/−20 (their real range starts at 0) while the signed ndfi_range
> cannot (−10/−20 are real swings there) and keeps −999 — owner-approved
> reasoning, 2026-08-16.

**Raw light (red, green, blue, nir, swir1, swir2 × 5 stats)**
- Scale: reflectance × 10000. Medians ≈ 0..10000 (small negatives can
  survive correction and ship honestly); ranges signed; mad ≥ 0.
- No special values. Basis: the sensor's own units, untouched.

**Temperature (tir_median, tir_mad only — owner ruling 2026-08-16, C30)**
- Scale: Kelvin × 10. Median ≈ 2400..3400; mad ≥ 0.
- No special values. Basis: one thermal quantity across all 41 years.
- tir_median_dry / tir_median_wet / tir_range DROPPED (C30): temperature
  receives no corrections and the seasonal split earns no place; median,
  mad and tir_count suffice. Band total 119 → 116. Recipes that leaned
  on tir_range (urban, C24-addendum) must adapt at classification time.

**Ground-mix fractions (gv, npv, soil, shade × median/dry/wet)**
- Whole percent, 0..100. No special values (fractions are always real;
  refusal lives in ndfi only, by C24 ruling).

**Fraction ranges (gv, npv, soil, shade `_range`)**
- Signed percent, −100..100 (wet minus dry). No special values.

**Fraction wobbles (gv, npv, soil, shade `_mad`)**
- Percent points, 0..100. No special values.

**Forest score levels (ndfi_median, ndfi_median_dry, ndfi_median_wet)**
- Real readings 0..200 ((value+1) × 100), clamped — impossible values
  cannot ship. Special values: **−10 = refused WATER** (that year's JRC
  record: water >50% of months, ≥6 of 12), **−20 = refused SNOW** (snow
  index ≥ 0.2 AND year ≤ 280 K, OR elevation ≥ 5000 m); water wins
  where both. Total span: exactly −20..200.

**Forest score swing (ndfi_range)**
- Signed, −200..200 (wet minus dry, both parents real). Special value:
  **−999 = no real pair** (either parent refused). The −10/−20 codes are
  NOT used here — they are legitimate swing values in this band, and a
  special value must be impossible as a real reading.

**Indices (ndvi, evi2, ndmi, mndwi × their stats)**
- Stored (value+1) × 10000: levels 0..20000 (evi2 to 35000, hence its
  32-bit type); ranges signed; mad ≥ 0. No special values.

**Tasseled cap (tcb, tcg, tcw × their stats)**
- Signed × 10000 working space, no +1 shift (tcb ≥ 0 in practice; tcg,
  tcw signed). No special values.

**Built indices (bci, ibi — median and mad only)**
- 0..200 ((value+1) × 100, frozen national normalisation for bci). No
  special values.

**Season anatomy (ndvi_q1..q4, ndvi_p25, ndvi_p75)**
- Same ndvi storage, 0..20000. Quarters with no usable looks are MASKED,
  not coded. No special values.

**Terrain (elevation, slope, aspect_sin, aspect_cos, hand)**
- Metres; degrees × 100; damped sin/cos × 10000 (−10000..10000);
  metres × 10. No special values.

**Bookkeeping (usable_count, tir_count, snow_count, quarters_present,
q1..q4_count)**
- Plain counts ≥ 0 (quarters_present 0..4). QA only, never classifier
  features. No special values.

**Position (lon, lat)**
- Degrees × 10000, 32-bit. Export only, never classifier features.

**Masked (no data) everywhere**: a pixel with no usable observations at
all is MASKED in every band — absence of data is the mask, never a code.

## Addendum (2026-08-30): superseded by band contract v2

Owner rulings 2026-08-30 — the live authority is now
[[band_and_property_contract]] ("Band contract v2 — 117 bands"):

- `_range` statistic family renamed `_swing` (it is signed wet-minus-dry).
- `ndvi_q1..q4` renamed `ndvi_q1_median..q4_median`.
- `ndfi_mad` ADDED (116 -> 117 bands), carrying the same -10/-20 codes
  (legal: a real mad is >= 0).
- Position (lon/lat): the "Export only, never classifier features" line
  above is REVERSED — lat/long is a legitimate classifier input; the
  original note was a misunderstanding. Position now sits before the
  bookkeeping block, which is dead last.
- Bookkeeping "never classifier features" stands, and becomes a
  prominent ATBD warning.
