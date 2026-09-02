# Witness vs plain mask — measurement results (2026-08-30)

Owner ruling "measure first" executed. Script: an internal measurement
script, not part of this release (predictions pre-registered in its
header).
Both arms built from the identical C2-only stack; the mask is the only
difference. A third arm, **both** (a look survives only if BOTH masks
keep it), was added mid-measurement when the data showed the two masks
catch different clouds.

## Part A — NH-46-Z-D pheno-2022 (the proven-leak cell)

- Proof look 2022-07-29 (blue 8181, nir 7904): **plain keeps, witness
  removes** — prediction confirmed at the pixel.
- Cell-wide, per pixel: kept looks / cloud-like kept / snow-like kept
  - plain 21.69 / 0.792 / 0.264
  - witness 22.34 / **1.454** / 0.208
  - **both 21.00 / 0.551 / 0.202**
- Mechanism: the plain BIT catches firmly-flagged warm cloud but ignores
  medium-confidence flags; the witness upholds medium-confidence flags
  only where COLD, so warm cloud is rescued. Two half-nets.
- The 2023-03-18 monster (blue 6671) passes ALL masks — warm, unflagged.
  That residue is the cloud-trim arm's territory, not any mask's.

## Part B — pheno-2015 both ways (the comparison config.py asked for)

- ND-43-V-D (Ghats): the three arms are indistinguishable (blue median
  173–180, cloudy-median fraction 0.0000 everywhere); both costs 0.8
  looks/pixel (~6 %) vs plain.
- NH-46-Z-D: cloudy-median fraction — plain 0.0242, witness 0.0302,
  **both 0.0235**; blue median — plain 300, witness 328, **both 297**.
  Both costs 0.5 looks/pixel (~3 %) vs plain.

## Honest scoreboard on the pre-registered predictions

- "Witness catches the July leak" — **right**.
- "Witness collateral small" — wrong in an interesting way: witness
  keeps MORE warm cloud, not less.
- "Witness arm shows lower cloudy-median fraction in 2015" — **wrong**:
  the current era-A production mask is the LEAKIEST of the three tested.

## What the numbers say

**Both-masks-everywhere wins or ties every metric measured**, at a cost
of 3–6 % of looks (most of them cloud anyway). It would also:
- delete the 2015/16 mask discontinuity from the archive,
- kill the `processing_track` property (schema simplification),
- and is a two-line implementation (chain the two keep-masks).

**RULING (owner, 2026-08-30): BOTH MASKS, EVERYWHERE.** One rule for all
years; the 2015/16 mask discontinuity is abolished; `processing_track`
leaves the property schema. Implementation rides with the pipeline
fold-in pass, verified by a trial export before any wide re-export.

## For the ATBD (owner instruction 2026-08-30: describe this clearly)

Cloud handling is a three-layer defence; each layer reads evidence the
others cannot, and each covers a failure mode the others cannot.

> Cloud contamination is controlled in three complementary layers.
> (1) The **QA-bit mask** removes observations that Collection 2's
> CFMask firmly labels cloud or shadow (shadow flags upheld only where
> the observation is actually dark; saturated and fill pixels removed;
> snow retained by design). (2) The **thermal witness** additionally
> removes observations carrying a medium-confidence cloud flag whenever
> the observation is anomalously cold against that pixel's own
> multi-year clear-sky surface-temperature history (precomputed
> national 30 m statistics, one per year, 1986–2025). The two masks are
> applied in conjunction — an observation survives only if both retain
> it — because measurement showed their blind spots are disjoint: the
> bit misses hesitantly-flagged cold cloud, the witness misses
> firmly-flagged warm cloud. One conjunctive rule is applied uniformly
> across the entire archive; there is no era split. (3) The
> **stack trim** addresses cloud that carries no flag at all: within
> each pixel's annual stack, observations whose blue reflectance
> exceeds the stack's 25th percentile by more than 0.03 are excluded
> before compositing, but only where the stack shows evidence of
> contamination (blue inter-quartile spread > 0.03) and enough
> observations survive (five, or half the stack rounded up, whichever
> is smaller, and never fewer than two — otherwise the trim abstains
> and the untrimmed median stands). The per-observation masks judge
> each observation on external evidence and therefore operate at any
> contamination fraction, protecting the trim's assumption that the
> darkest quarter of the stack is clean; the trim catches unflagged
> bright cloud the masks cannot see; cloud-shadow (dark) contamination
> is handled exclusively by the masks, as a one-sided bright trim
> cannot address it. Residual limitation: warm, unflagged cloud in
> stacks with no clean core (persistently overcast monsoon pixels)
> survives all three layers and is disclosed by the per-pixel
> observation counts.

Verification anchors for the document: the 2022-07-29 leak look
(witness catch), the 2023-03-18 unflagged monster (trim territory), and
the measured arm comparison in this file.

### Edge-case catalogue (owner instruction 2026-08-30: the ATBD must
### describe the concrete failure stories each layer exists to catch)

Every case below was observed in this build, not hypothesised.

- **Hesitantly-flagged cold cloud enters the median.** NH-46-Z-D
  (Aalo), look of 2022-07-29: bright monsoon cloud (blue 0.82, NIR
  0.79) carried only a medium-confidence flag; the QA bit ignores
  hesitant flags, so the look survived and brightened the annual
  median. *Caught by the thermal witness* — the look is far colder than
  the pixel's own clear-day temperature history.
- **Warm cloud rescued by the witness.** The witness upholds a cloud
  flag only where cold; low warm cloud is "acquitted" and kept.
  Measured on the same cell: witness-only masking retained nearly twice
  the cloud-like looks of the bit alone (1.45 vs 0.79 per pixel).
  *Caught by the QA bit* — hence the conjunctive rule: the two blind
  spots are disjoint.
- **The median strays onto cloud in persistently cloudy country.** In
  monsoon Aalo, the Western Ghats and the NE hills, more than half of a
  pixel's surviving looks can be cloud even after both masks; the
  median — the middle value — then IS a cloudy look. No per-look mask
  can fix this, because each cloudy look individually passed its
  checks. *Caught by the stack trim*, which anchors on the darkest
  quarter of the pixel's own blue values and so still finds the clean
  core when up to ~three-quarters of the stack is contaminated.
- **Unflagged warm bright cloud.** Look of 2023-03-18 (blue 0.67):
  no flag of any confidence, warm top — invisible to both masks.
  *Caught by the trim* (far brighter than the stack's clean core).
- **Cloud shadow darkens the record.** Shadow contamination is DARK; a
  bright-side trim cannot see it. *Caught by the masks' shadow test*
  (shadow flag upheld only where the observation is actually dark).
- **Winter snow mistaken for cloud.** Himalayan winter scenes: bright,
  cold surface snow is routinely cloud-flagged; naive masking deletes
  entire snow seasons. *Handled by the witness's snow rescue* — surface
  snow shares the ground's clear-day climate, while a cloud top is far
  colder than the same pixel's usual clear reading; measured 2026-08-30,
  the witness kept fewer false "snow" looks than the bit while retaining
  genuine snow.
- **Stacks with no clean core.** Where essentially every look is cloudy
  (worst monsoon pixels), the trim's anchor would itself be cloud; the
  adaptive survivor floor (min(5, half the stack), never below 2) makes
  the trim ABSTAIN rather than calibrate against cloud, and the
  contamination is disclosed honestly by the per-pixel observation
  count rather than hidden. This is the accepted residual limitation.

### Corrections to the ATBD paragraph above (review find, 2026-08-30 —
### verified in code before filing; the ATBD must use these facts)

- The witness's reference is the pixel's clear-sky temperature history
  from the SAME phenological year (one national record per year,
  build.export_witness_stats_national reduces exactly one pheno year),
  NOT "multi-year" as the paragraph says. Consequence worth disclosing:
  where a year's clear history holds fewer than 8 looks
  (WITNESS_MIN_OBS) the witness FAILS CLOSED — every medium-confidence
  cloud flag is upheld, so thin early years are masked near-strictly.
- RESOLVED (owner ruling 2026-08-30, second sitting): the trim moved
  UPSTREAM of the quarterly computation, so the seasonal-anatomy block
  (quarterly ndvi medians and quarter counts) is now protected by layer
  3 like every other statistic. A thin quarter whose only look is cloud
  reads as an honest masked gap. The snow caveat extends with it: the
  trim can clip the brightest looks of all-snow winter quarters.
- The ANNUAL observation counts (usable_count, snow_count, tir_count)
  stay PRE-trim by design — the disclosure channel: they mean "looks
  entering the compositor". The QUARTERLY counts are POST-trim and
  count the looks their own medians actually used. The ATBD carries
  both definitions.
- Thermal (tir_median/mad/count) bypasses all three layers: it is read
  from the national temperature record (plain-QA-clear population),
  neither witnessed nor trimmed. The three-layer text governs the
  optical stack only.
