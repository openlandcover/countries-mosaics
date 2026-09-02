# Asset inventory v3 — post-fold-in truth (2026-08-30)

Replaces an earlier internal version (not part of this release). This
version reflects the folded-in pipeline (physics topo native, both
masks, cloud-trim, band/property contracts v2, annuals only, L7
1999-2021, gate removed) and reviewer 2's dependency audit, all claims
re-verified 2026-08-30.

## 1. What a mosaic build actually reads (complete)

> [!note] Repo-bundled files (ship with the repo, load-bearing)
> - `data/lut/lut_oli.csv`, `lut_etm.csv`, `lut_tm.csv` (+ manifests) —
>   the 6S tables the physics correction reads client-side. PURE
>   ATMOSPHERE TABLES (axes: aot 0.05-1.0, wv 1-5, elev 0-5500 m,
>   sunzen 10-80 deg) — nothing cell-specific; one per sensor family
>   serves all 282 cells (verified 2026-08-30, answering the owner's
>   gate question: the topo-gate never entered their construction).
> - `data/lut/lut_v1_spare.csv` — coarser spare; loud fallback.

> [!note] Owner EE assets read at build time (all to be public-read at
> publication)
> - `mosaic_v2_inputs/terrain` (was shared_assets/
>   glo30_india_terrain_v1) — terrain sheet (DEM bands +
>   slope x100, damped aspect sin/cos x1e4, slope_smooth x100,
>   aspect_smooth x10, hand x10). Carries its own description. Producer:
>   scripts/export_terrain_asset.py (guarded; live asset authoritative).
> - `mosaic_v2_inputs/terrain_illum` (was .../glo30_india_terrain_
>   illum_v2) — linear illumination
>   terms; PRODUCTION (TOPO_ILLUM_LINEAR on). Producer tracked.
> - `mosaic_v2_inputs/witness_stats/INDIA_1986..2025` (was
>   shared_assets/witness_stats_v1) — per-year
>   clear-sky temperature records; feeds BOTH the witness mask and the
>   tir output bands. 1984-85 not needed: ZERO scenes those years
>   (verified; zero-scene skip covers them). Producer:
>   build.export_witness_stats.
> - `mosaic_v2_inputs/regions_mask` (was shared_assets/
>   regions_mask_v1) — painted extent raster (preferred
>   read). Producer: build.export_region_mask.
> - `mosaic_v2_inputs/regions` (was ioln_classification_regions_v2)
>   — the AUTHORITATIVE regions vector
>   (owner ruling 2026-08-30; the _v3 config used to name never
>   existed). Fallback for the raster; snapshot in data/vectors/.
> - `mosaic_v2_inputs/boundary` (was shared_assets/
>   india_boundary_official) — cell enumeration + the
>   witness-stats producer's extent. Snapshot in data/vectors/.
> - `mosaic_v2_inputs/lut_oli`/`lut_etm`/`lut_tm`/`lut_v1_spare`
>   (were shared_assets/c_phys_lut_*) — EE
>   copies of the LUTs, row-identical to the repo CSVs (26680 each,
>   verified 2026-08-30). Convenience only: the pipeline reads the
>   CSVs. Producer: scripts/build_6s_correction_tables.py (--upload).
> - PLANNED: `mosaic_v2_inputs/overpass_conditions/INDIA_<year>` —
>   the D1 precompute (build-after-migration APPROVED; the ~40 table
>   exports await their own go).

> [!note] Public third-party (no producer needed; reachable by anyone)
> - `LANDSAT/{LT05,LE07,LC08,LC09}/C02/T1_L2` + `T1` (angles)
> - `NASA/GSFC/MERRA/aer/2` + `slv/2` (until the pass-facts precompute
>   makes these a producer-time dependency only; per-pass climatology
>   fallback exists: PHYS_AOT_CLIM/PHYS_WV_CLIM)
> - `JRC/GSW1_4/MonthlyHistory` + `projects/JRC/GSW1_5/...2022_2024`
> - `COPERNICUS/DEM/GLO30_2024_1`, `users/gena/global-hand/hand-100`
>   (both FALLBACK-only: the terrain sheet carries elevation and hand)
> - `projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000` (grid;
>   verify stranger read access at publication — mitigation DONE
>   2026-08-30: data/vectors/grid_cells_india.geojson, 282 cells)

> [!note] Lab-only (not read under production defaults)
> - topo_fits_v2/v1 (+parts), align_offsets_v1, cell_hillside_v2,
>   cell_topo_gate_v1 (gate REMOVED under physics), the pilot
>   collections, landsat_usable_pixels, mosaic_c2phys_v1 (v3/v8/v9
>   evidence builds), mosaic_c2phys_trial_v1, w_cal_ne_2022 tables,
>   mask_measurement.

## 2. Input-asset directory structure — APPROVED AND EXECUTED
## (owner interview 2026-08-30; all renames done same day, config
## repointed via INPUTS_ROOT, full build re-verified on new paths)

Everything the v2 mosaics read, in ONE folder, clear names, so the
publication ACL is a single public-read grant and a stranger can see
the whole input surface at a glance:

    projects/mapbiomas-india/assets/mosaic_v2_inputs/
      boundary                      (table;  now india_boundary_official)
      regions                       (table;  now ioln_classification_regions_v2)
      regions_mask                  (image;  now regions_mask_v1)
      terrain                       (image;  now glo30_india_terrain_v1)
      terrain_illum                 (image;  now glo30_india_terrain_illum_v2)
      lut_oli / lut_etm / lut_tm / lut_v1_spare   (tables; local fallback copies in data/lut/)
      witness_stats/INDIA_<year>    (image collection; now witness_stats_v1)
      overpass_conditions/INDIA_<year>  (tables; NEW — the D1
                          precompute; owner-named: one row per
                          satellite overpass — date, sun angle,
                          haze, moisture)

Rules: lowercase snake names; the folder name carries the product
version (a v3 recipe gets mosaic_v3_inputs, so old products never lose
their inputs); versions of an ASSET stay as _vN suffixes only while
two coexist; lab/evidence assets stay in shared_assets and are never
mixed in.

Migration mechanics (when approved): server-side rename
(ee.data.renameAsset / earthengine mv) — instant, no re-export; one
config commit repoints all paths; old paths in lab scripts/docs go
stale (acceptable, docs are history); nothing re-uploads. Witness
stats: 40 renames, scriptable in one loop.

Outputs stay separate from inputs by design:
sandbox `shared_assets/ioln_mosaics_v2_sandbox` now, final
`projects/mapbiomas-mosaics/assets/LANDSAT/LULC/INDIA/mosaics-2`
(the committed PR version flips OUTPUT_COLLECTION; owner ruling).

## 3. D1 — overpass-conditions precompute (approved 2026-08-30;
## build on go)

One small table per year at
`mosaic_v2_inputs/overpass_conditions/INDIA_<year>`:
one row per pass over India (sensor, pass_key, date, sun zenith,
MERRA-2 aot, wv). Producer script derives rows exactly as
topo_physics.pass_table does today, nationally. apply_physics then
reads the year's table in ONE small query and computes C profiles from
the repo LUTs as now; live fallback with a LOUD warning when a year's
table is absent. MERRA-2 becomes a producer-time dependency only.
Queueing the ~40 table exports is an export batch — own go required.

## 4. Run order for a fresh project (shrunken, post-fold-in)

1. boundary + regions vectors (manual upload or scripts/upload_vectors)
2. terrain sheet (scripts/export_terrain_asset.py) -> illum asset ->
   (gate table now lab-only)
3. witness stats per year (build.export_witness_stats, 1986-2025)
4. region mask (build.export_region_mask)
5. pass facts per year (D1 producer, once built)
6. mosaics (build.export) — destination collection auto-created

A forker READING the published inputs skips 1-5 entirely.

## 5. Publication checklist (ACLs and access)

- Public-read on the whole input folder (one grant under the proposed
  structure).
- Verify anonymous read on the mapbiomas-workspace grid asset.
- OUTPUT_COLLECTION -> PRODUCTION_COLLECTION flip in the PR version.
- The collection description text set on the output collection (owner
  clears the words first).

## 6. Corrections vs the v2 inventory (why this doc exists)

Physics native, one builder ('two parallel builders' framing dead);
topo_fits/cell_hillside/gate demoted to lab; illum asset is production;
LUT CSVs tracked in git (old warning stale) and EE copies verified
in-sync; witness stats every-year AND hard-required (thermal record);
water rule is the 3-pheno-year moving window; epochs retired (annuals
only); L7 1999-2021; regions vector corrected to _v2; 1984-85 zero
scenes; requirements.txt + README now exist.
