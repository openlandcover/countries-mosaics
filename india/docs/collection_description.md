# Collection description — structure (owner ruling 2026-08-30)

The ONE human-readable `description` lives on the collection asset;
images carry none. Structure below follows the conventions of Earth
Engine Data Catalog entries (Landsat C2, HLS, JRC GSW, MapBiomas pages
all share the shape: what-it-is prose -> band decode -> properties ->
caveats -> terms/citation). A user asset shows this as one plain-text
property, so the final text must be compact (~1 printed page); every
section below maps to schema/ATBD material that already exists — the
text itself is written at the ATBD stage.

## Section order and content

1. **What this is** (3-4 sentences). Product name + version; annual
   Landsat surface-reflectance mosaics for India, 1986-2025, 30 m
   (nominal — the grid is EPSG:4326 degrees); one image per 1:250k grid
   cell per PHENOLOGICAL year (1 April - 31 March); built by the India
   Open LandCover Network.

2. **How it was made** (the telegraphic pipeline, one line per stage).
   Landsat Collection 2 Level 2 (every usable sensor incl. gap-filler
   L7) -> cloud/shadow masking (QA bit AND thermal witness, one rule
   all years) -> blue-anchored stack trim for unflagged cloud ->
   physics-based terrain correction (SCS+C, 6S tables, all cells) ->
   BRDF -> sensor harmonisation (global bandpass, no local offset) ->
   per-pixel seasonal statistics (median / dry / wet / swing / MAD).

3. **Reading the numbers** (decode, one line per band family — mirrors
   the decode_* image properties verbatim, plus the two facts that live
   only here: the level-vs-spread offset rule stated in words, and the
   nominal-30 m/degree-grid note).

4. **Sentinels and consumer rules** (the classifier gotchas):
   ndfi codes -10/-20 in levels and mad, -999 in swing — safe for
   trees, poison for means/linear models; aspect_sin/cos consumed
   directly, never rebuilt into an angle; bookkeeping counts are
   QA-only, NEVER classifier features; counts are pre-trim ("looks
   entering the compositor"); lat/long ARE legitimate features.

5. **Known limits** (honest, short): witness reference is same-year
   clear-sky history and fails closed in thin years; zero-scene
   cell-years are skipped (archive holes, mostly pre-2000); 2013 rests
   on ~9 months of L8 + gap-filler L7; persistent-monsoon pixels can
   defeat all three cloud layers (disclosed by counts); ndfi_mad over
   un-refused water is solver noise, read such pixels as land context;
   the trim clips the brightest looks of all-snow stacks.

6. **Terms, citation, contact, links**: product licence (CC-BY 4.0,
   pending owner confirmation at publication); 'India Open LandCover
   Network' citation + DOI when minted; contact; pointers to the ATBD
   and the GitHub repo.

## Mechanics

- Written once, at ATBD time, from the schema doc; updated only when
  the recipe version bumps. THE FINAL TEXT NEEDS EXPLICIT OWNER
  CLEARANCE before it is set on the asset (owner instruction
  2026-08-30). The words are now drafted, in
  docs/collection_description.txt, and await that clearance.
- Set on the collection asset by scripts/set_collection_description.py,
  which reads the wording from docs/collection_description.txt. It shows
  the text by default and writes only with --set, reads the result back
  to confirm, and does nothing when the text is already in place. Only
  the owner of the collection can run it, which is whoever ran the
  export; the script says so plainly when it cannot write.
- The collection asset also carries system:description-compatible
  fields where the Code Editor shows them.
