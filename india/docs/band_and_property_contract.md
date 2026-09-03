# Asset property schema v2 — SETTLED (owner interview, 2026-08-30)

Replaces an earlier internal draft (not part of this release). Every decision
below was made by the owner in the 2026-08-30 interview; deviations need
a fresh ruling.

> [!note] Identity
> - `product` — `'IOLN annual Landsat mosaic, India'`
> - `product_version` — `'2'` (the legacy asset on disk is version 1)
> - `grid_name` — e.g. `'NC-43-Z-D'` (KEPT from legacy, not renamed:
>   downstream classification code filters on it)
> - `region` — `'India'` (retained)

> [!note] Time (phenological year: 1 April – 31 March)
> - `year` — `2005` (pheno start year; KEPT: every legacy-style filter
>   says eq('year', N))
> - `window_start` / `window_end` — `'2005-04-01'` / `'2006-03-31'`
> - `system:time_start` / `system:time_end` — same instants,
>   machine-readable (fixes the confirmed missing-end bug)
> - **No `epoch_label`, no `n_years`, no end-year machinery** — owner
>   ruling 2026-08-30: the product is ANNUALS ONLY; pre-2000 multi-year
>   epoch composites are out of the plan. (Pipeline simplification filed
>   for the fold-in work.)

> [!note] Input
> - `input_collection` — `'Landsat Collection 2 Level 2'` (all HLS
>   references gone — this is entirely a C2 stack)
> - `sensors` — compact list, e.g. `'L5,L7'`
> - `n_scenes` — count of distinct passes used
> - `processing_track` — DEAD (owner ruling 2026-08-30: BOTH masks
>   everywhere, one rule for all years; there is no mask era to name).

> [!note] Corrections — one bookkeeping property (owner: nothing ships
> uncorrected, so per-correction state flags describe nothing)
> - `corrections` — `'terrain (SCS+C, physics C from 6S tables, factor
>   bounded 0.25-4); BRDF (c-factor); sensor harmonisation (TM->ETM+
>   ->OLI bandpass, no offset)'`

> [!note] Use
> - `crs` — `'EPSG:4326'` · `pixel_size_m` — `30`
> - Scaling as GROUP properties (owner choice), one rule per band family.
>   LEVEL vs SPREAD (owner ruling 2026-08-30): the -1 offset applies to
>   index LEVEL bands only (median / _dry / _wet / ndvi quarters and
>   percentiles). SPREAD bands (_mad and the seasonal swing) sit at the
>   parent scale with NO offset — a spread has none to carry.
>   EXCEPTION: the tasselled-cap bands (tcb/tcg/tcw) are level bands but
>   are NEVER shifted — signed values stored x 10000 plain.
>   - `refl_scale` — `0.0001` (the six `*_median` reflectance bands)
>   - `index_scale` / `index_offset` — `0.0001` / `-1` (index LEVEL
>     bands only: true = stored x 0.0001 - 1). EXCEPTION: `bci`/`ibi`
>     use the ndfi convention instead — 0-200, (true + 1) x 100
>     (config BCI_SCALE; band finalisation sheet 2026-08-13)
>   - `tir_scale` — `0.1` (thermal stored as Kelvin x 10, Int16;
>     pipeline/build.py:922)
>   - `fraction_scale` — `100` (SMA fractions gv/npv/soil/shade stored
>     0-100 whole percent; config.py SMA_PCT_SCALE)
>   - `ndfi_scale` / `ndfi_offset` — `100` / `+100` (ndfi ships 0-200,
>     the legacy scale: stored = (true + 1) x 100; refusal codes sit
>     OUTSIDE that range: snow -20, water -10; pipeline/sma.py:220)
>   - slope — degrees x 100; aspect_sin/aspect_cos — sin/cos damped by
>     sin(slope), x 10000 (NOT unit vectors, by design; config.py:51);
>     lon/lat — degrees x 10000
>   - CONSUMER RULE (owner-agreed 2026-08-30): classifiers use
>     aspect_sin/aspect_cos directly and never reconstruct an aspect
>     angle from them — on flat ground that is atan2(0, 0), garbage
>   - counts (`usable_count`, `tir_count`, `snow_count`, `q*_count`,
>     `quarters_present`) and `elevation` (m) — plain integers, no
>     scaling; `hand` — metres x 10 (terrain.py static_bands; CORRECTED
>     2026-08-30, an earlier note here wrongly said plain metres)
>   - all of the above verified 2026-08-30 against both the code and the
>     live v9 asset (NH-46-Z-D_2022_c2_only_v9, proof pixel)
> - `contact` — `'mdmadhu@gmail.com'`
> - `citation` — `'India Open LandCover Network'`

> [!warning] Classifier gotchas (owner rulings 2026-08-30; ATBD must
> carry all three prominently)
> - `_range` bands are SIGNED SEASONAL SWING (wet median minus dry
>   median), not max-minus-min — negatives are correct behaviour.
>   RULING: rename `_range` -> `_swing` at the fold-in pass, across
>   BAND_ORDER and every consumer.
> - `ndfi` level bands span -20..200 with NAMED refusal codes embedded
>   in the numeric band (-10 refused water, -20 refused snow; where
>   both, water wins). `ndfi_range` spans -200..200 and uses a -999
>   sentinel instead (the codes would collide with real values). Safe
>   for tree classifiers, which learn the codes as facts; POISON for
>   means, normalisation, linear models, or neural networks. Prominent
>   ATBD warning required. RULING (owner 2026-08-30): the in-band codes
>   STAY (no separate flag band, no neutral filler) — the warning is the
>   remedy.
> - Slightly negative stored reflectance is REAL and KEPT (~2.6% of
>   blue_median pixels in the verified cell, all in deep shadow, almost
>   none below -0.05; inherited from the Collection 2 surface
>   reflectance input, deliberately not clamped). Indices are computed
>   from a zero-floored copy and are unaffected.

> [!note] Descriptions (owner ruling 2026-08-30)
> - The COLLECTION asset carries the one human-readable `description`:
>   a compact decode cheat sheet — band families, scales, offsets, the
>   level-vs-spread rule, the ndfi sentinels, the swing sign, the
>   consumer rules — plus a pointer to the ATBD.
> - Individual images carry NO description property. One cheat sheet
>   maintained once beats ~11,000 copies drifting out of sync.

> [!note] Provenance
> - `built_utc`, `git_commit`, `builder_script` — kept as-is
> - **No `dbg_` ledger on production assets** (owner 2026-08-30): the
>   development ledger stays on lab exports only; git_commit +
>   builder_script carry reproducibility.
> - `variant` — DROPPED (one public recipe; defined once in the ATBD)

## Band contract v2 — 117 bands (owner rulings 2026-08-30)

This list IS the ATBD Section 4 backbone and the fold-in target. It
supersedes the 116-band v1 contract in config BAND_ORDER. Changes vs
v1, all owner-ruled 2026-08-30: `_range` -> `_swing`; `ndvi_q1..q4` ->
`ndvi_q1_median..q4_median`; `ndfi_mad` ADDED (116 -> 117; more
outlier-robust than the swing; carries the SAME named codes -10 water /
-20 snow — legal because a real mad is >= 0); position moved BEFORE
bookkeeping and is a legitimate classifier input (REVERSES the C29
"export only" note in the band finalisation sheet, which the owner
calls a misunderstanding); bookkeeping dead last and NEVER a classifier
feature (ATBD must warn prominently).

> [!note] A. Annual Medians (21)
> `red_median, green_median, blue_median, nir_median, swir1_median,
> swir2_median, tir_median, gv_median, npv_median, soil_median,
> shade_median, ndfi_median, ndvi_median, evi2_median, ndmi_median,
> mndwi_median, tcb_median, tcg_median, tcw_median, bci_median,
> ibi_median`
> Reflectance x1e-4 · tir K x10 · fractions 0-100 % · ndfi 0-200
> (codes -10/-20) · ndvi/evi2/ndmi/mndwi (true+1) x 1e4 ·
> tcb/tcg/tcw x 1e4 unshifted · bci/ibi 0-200 ((true+1) x 100)

> [!note] B. Dry-season medians (18)
> `red_median_dry, green_median_dry, blue_median_dry, nir_median_dry,
> swir1_median_dry, swir2_median_dry, gv_median_dry, npv_median_dry,
> soil_median_dry, shade_median_dry, ndfi_median_dry, ndvi_median_dry,
> evi2_median_dry, ndmi_median_dry, mndwi_median_dry, tcb_median_dry,
> tcg_median_dry, tcw_median_dry`
> Same scaling as A. No tir (median+mad only, C30), no bci/ibi (no
> seasons for built classes, C24).

> [!note] C. Wet-season medians (18)
> `red_median_wet, green_median_wet, blue_median_wet, nir_median_wet,
> swir1_median_wet, swir2_median_wet, gv_median_wet, npv_median_wet,
> soil_median_wet, shade_median_wet, ndfi_median_wet, ndvi_median_wet,
> evi2_median_wet, ndmi_median_wet, mndwi_median_wet, tcb_median_wet,
> tcg_median_wet, tcw_median_wet`
> Same scaling and exclusions as B.

> [!note] D. Seasonal Swing — wet minus dry, SIGNED (18)
> `red_swing, green_swing, blue_swing, nir_swing, swir1_swing,
> swir2_swing, gv_swing, npv_swing, soil_swing, shade_swing,
> ndfi_swing, ndvi_swing, evi2_swing, ndmi_swing, mndwi_swing,
> tcb_swing, tcg_swing, tcw_swing`
> Parent scale, NO offset. `ndfi_swing` -200..200 with -999 sentinel
> (no real pair).

> [!note] E. Spread — Median Absolute Deviation, MAD (21)
> `red_mad, green_mad, blue_mad, nir_mad, swir1_mad, swir2_mad,
> tir_mad, gv_mad, npv_mad, soil_mad, shade_mad, ndfi_mad, ndvi_mad,
> evi2_mad, ndmi_mad, mndwi_mad, tcb_mad, tcg_mad, tcw_mad, bci_mad,
> ibi_mad`
> Parent scale, NO offset, real values >= 0. `ndfi_mad` is NEW
> (2026-08-30) and carries the named refusal codes -10 water / -20 snow.

> [!note] F. Seasonal Greenness Levels (6)
> `ndvi_q1_median, ndvi_q2_median, ndvi_q3_median, ndvi_q4_median,
> ndvi_p25, ndvi_p75`
> ndvi level rule, (true+1) x 1e4. Quarters with no usable looks are
> MASKED, not coded (finalisation sheet) — flag at classification time.

> [!note] G. Terrain (5)
> `elevation, slope, aspect_sin, aspect_cos, hand`
> Metres · degrees x100 · damped sin/cos x1e4 (consume directly, never
> reconstruct the angle) · metres x10.

> [!note] H. Position (2) — CLASSIFIER INPUT (owner reversal 2026-08-30)
> `lon, lat`
> Degrees x 1e4, Int32, planar-safe across India.

> [!note] I. Bookkeeping (8) — dead last, QA ONLY, never classifier
> features (ATBD warning mandatory)
> `usable_count, tir_count, snow_count, quarters_present, q1_count,
> q2_count, q3_count, q4_count`
> Plain integers. The user-facing trust signals.

Group total: 21+18+18+18+21+6+5+2+8 = 117.

## Property contract v2 — FINAL (owner sign-off 2026-08-30)

This section is the ATBD property chapter's backbone and the fold-in
target. It SUPERSEDES the interview blocks above wherever they differ:
`window_start`/`window_end` -> `start_date`/`end_date`; `sensors` ->
`sensors_used`; the scaling group properties are replaced by decode
FORMULAS (owner idea — formulas carry the exception families too);
`contact`/`citation` move into Identity; `corrections` shrinks to the
processing sequence, its detail moving to the collection description;
`builder_script` dropped. 27 properties per image, nothing else.
Category titles below are the ATBD section headings.

> [!note] Identity (6)
> - `product` — `'IOLN annual Landsat mosaic, India'`
> - `product_version` — `'2'`
> - `grid_name` — e.g. `'NH-46-Z-D'`
> - `region` — `'India'`
> - `contact` — `'mdmadhu@gmail.com'`
> - `citation` — `'India Open LandCover Network'`

> [!note] Time Window (5) — phenological year, 1 April to 31 March
> - `year` — e.g. `2022` (start year; legacy filters use it)
> - `start_date` / `end_date` — `'2022-04-01'` / `'2023-03-31'`
> - `system:time_start` / `system:time_end` — machine-readable window.
>   PRECISION (review correction 2026-08-30): `end_date` is the
>   INCLUSIVE last calendar day; `system:time_end` is the EXCLUSIVE end
>   instant (00:00 on 1 April of the next year, the EE convention) —
>   deliberately NOT the same instant as `end_date`.

> [!note] Inputs (3)
> - `input_collection` — `'Landsat Collection 2 Level 2'`
> - `sensors_used` — e.g. `'L5,L7'`
> - `n_scenes` — count of distinct passes used

> [!note] Processing (1)
> - `corrections` — `'Topographic Correction + BRDF + Sensor
>   Harmonisation'` (the sequence only; the full plain-English story —
>   including GLOBAL bandpass, no LOCAL offset, and the three-layer
>   cloud defence — lives in the collection description)

> [!note] Decoding Formulas (10) — one per band family, exceptions
> included; true value = apply the formula to the stored integer
> - `decode_reflectance` — `'reflectance = stored x 0.0001
>   (red/green/blue/nir/swir1/swir2, every statistic)'`
> - `decode_temperature` — `'kelvin = stored x 0.1 (tir bands)'`
> - `decode_fractions` — `'percent = stored; fraction = stored / 100
>   (gv/npv/soil/shade, every statistic)'`
> - `decode_indices` — `'index = stored x 0.0001 - 1 (level bands);
>   index = stored x 0.0001 (swing and mad) — ndvi, evi2, ndmi, mndwi'`
> - `decode_tasseled_cap` — `'value = stored x 0.0001, every
>   statistic, never shifted (tcb, tcg, tcw)'`
> - `decode_ndfi` — `'ndfi = stored / 100 - 1 (levels); ndfi units =
>   stored / 100 (swing, mad). Codes: -10 refused water, -20 refused
>   snow (levels, mad); -999 no real pair (swing)'`
> - `decode_bci_ibi` — `'index = stored / 100 - 1 (median); spread =
>   stored / 100 (mad)'`
> - `decode_terrain` — `'elevation: metres. slope: degrees = stored /
>   100. aspect_sin/cos = stored / 10000, slope-damped — use directly,
>   never rebuild the angle. hand: metres = stored / 10'`
> - `decode_position` — `'degrees = stored / 10000 (lon, lat)'`
> - `decode_counts` — `'plain integers, no conversion. Quality signals
>   only — never classifier features'`

> [!note] Build Record (2)
> - `built_utc` — build timestamp (distinguishes pre-fix from post-fix
>   rebuilds inside the weeks-long national run)
> - `git_commit` — exactly which code built this image

> [!note] Collection Description (collection asset only, no per-image
> description)
> - `description` — plain-English front page: what the product is, the
>   telegraphic pipeline (cloud defence included), the corrections
>   story (global bandpass, no local offset), the consumer warnings
>   (aspect rule, ndfi codes, bookkeeping never features), ATBD pointer.

## Open items — ALL CLOSED (2026-08-30)

- `processing_track` — CLOSED: the mask measurement ran, the owner ruled
  BOTH masks everywhere, the property dies.
- Temperature/count/fraction scaling — CLOSED: confirmed against the
  code and the live v9 asset; rules recorded in the Use block above.
- The annuals-only ruling lets the fold-in delete the epoch machinery
  (implementation note, not a schema question).

**This schema is complete. Nothing here awaits a decision; the fold-in
pass implements it as written.**

## AMENDMENT 1 — index storage shift removed (owner ruling 2026-09-01)

Fresh ruling amending the sealed contract above, given after the
signed-vs-unsigned storage review (an internal decision memo, not part
of this release), BEFORE the national run (no archive rebuild):

- The +1 storage shift is REMOVED from the four ratio indices — ndvi,
  evi2, ndmi, mndwi — on every LEVEL band (annual/dry/wet medians,
  ndvi_q1..q4_median, ndvi_p25/p75). One rule now covers the whole
  x0.0001 family, tasselled cap included: true = stored x 0.0001,
  every band, every statistic, never shifted. Swing and MAD bands are
  numerically unchanged (the shift always cancelled in differences
  and deviations).
- decode_indices and decode_tasseled_cap become identical and are
  MERGED into one property, decode_indices, covering ndvi, evi2,
  ndmi, mndwi, tcb, tcg, tcw. The image property count becomes 26
  (was 27); the decode-property count becomes 9 (was 10).
- evi2 returns to Int16 (unshifted ceiling 25,000 fits); the Int32
  special case for the evi2 group is deleted. lon/lat remain Int32.
- NDFI, BCI and IBI are UNTOUCHED: their 0-200 shift is load-bearing
  (it vacates the space where the refusal codes live).
- Classifier output is provably unchanged (tree splits are invariant
  to a constant shift); the change removes the documented
  level-vs-spread decoding trap for this family.
- Gate: this ruling approves code, documents, tests and the sandbox
  re-check only. The national run needs its own go. Owner will
  rework external readers that expected the old shift.

## AMENDMENT 2 — narrow storage for 32 small-ranged bands (owner ruling 2026-09-03)

Fresh ruling amending the sealed contract above, given BEFORE the
national run (no archive rebuild):

- 32 bands whose legal range never needed 16 bits now ship in 8:
  UInt8 (0-255) for 28 bands — the gv/npv/soil/shade medians (annual,
  dry, wet) and MADs, bci/ibi median and mad, quarters_present, and
  the six count bands (usable, tir, snow, q1..q4) — and Int8
  (-128 to 127) for 4 bands: gv_swing, npv_swing, soil_swing,
  shade_swing. Everything else is unchanged: Int16 for the rest,
  Int32 for lon/lat.
- Nothing else moves. Band names, band order, band count (117),
  legal ranges, decoding rules, reserved codes and image properties
  are all untouched. This is a container change only — the stored
  integer in each of these bands is bit-for-bit what it was.
- ndfi_mad, ndfi_swing and the rest of the NDFI family keep Int16:
  the -999 sentinel and the -10/-20 refusal codes cannot coexist
  with a 0-200 range in any 8-bit type.
- Evidence: legal ranges from the band contract, a 92-image sample
  survey over 8 cells, and for the count bands a full national sweep
  of all 283 grid cells (highest usable_count in India in any year:
  108; q1..q4_count: 31-32). snow_count is bounded by usable_count
  by construction. tir_count rests on the sample evidence (highest
  seen 112) plus the owner's ruling: it is drawn from the national
  temperature record's looser clear-sky test, so it has no analytic
  bound against usable_count.
- Verified by sandbox re-export (NC-43-X-D 2019): all 117 bands carry
  the intended type, and all 32 narrowed bands are pixel-for-pixel
  identical to the pre-change asset. No value was clipped — the
  closest approach to a ceiling is bci_median at 200 of 255.
- Measured effect on stored size: about 3% smaller per image (a
  cell-year fell from 3,589 MB to 3,477 MB, a figure that also
  includes Amendment 1's evi2 narrowing). Far less than the raw byte
  arithmetic suggests, because compression was already absorbing most
  of the unused space.
- Gate: this ruling approves code, documents and the sandbox
  re-check only. The national run needs its own go.
