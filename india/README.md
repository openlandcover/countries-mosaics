# India annual Landsat mosaics — v2 pipeline

Builds annual Landsat surface-reflectance mosaics for India on Google
Earth Engine: 30 m resolution, one image per 1:250,000 grid cell per
phenological year (April to March), 117 bands per image, years 1986
onwards. Product of the India Open LandCover Network (IOLN).

This pipeline builds annual Landsat mosaics for India using Google
Earth Engine. Its processing approach — cloud/shadow masking, spectral
mixture analysis, and grid-tiled compositing — follows the method
established by the MapBiomas
[countries-mosaics](https://github.com/mapbiomas/countries-mosaics)
collection, which produced the original India mosaic script this
project supersedes. The codebase itself is an independent, ground-up
implementation: no code was copied from that repository, and the
architecture, module structure, and masking/terrain-correction logic
here are new.

The full method record is the ATBD, `docs/IOLN Landsat Mosaics ATBD.pdf`:
what the product is, how every step works, what was measured, and what
its limits are. For a shorter read, `docs/IOLN Landsat Mosaics
V1-vs-V2.pdf` sets the two versions side by side, row by row.
`docs/README.md` says what everything else in that folder is.

## Run it

Open `notebooks/run_mosaics.ipynb`. It has two modes.

**development** builds one grid cell for one or a few years, into a
collection you own. This is the mode to use first, to check that the
pipeline works after you clone it. Set your own Earth Engine project in
`EE_PROJECT` and your own destination in `DEV_COLLECTION`; the
collection is created for you if it is not there. A development run
cannot write to the published collection.

**production** builds every grid cell for every year, 1986 to 2025, into
the published collection: 11,320 export tasks, days of compute, and it
needs write access you must already hold. Nothing is queued until you
paste a confirmation phrase.

Either mode can be tracked at any time from the notebook's tracking
cell, or from a terminal with
`python -m pipeline.run_production --progress`. It reads the state from
Earth Engine, so it works after you close the notebook, and from a
different machine than the one that started the run.

You need Python with the packages in `requirements.txt` installed
(`pip install -r requirements.txt`) and a Google Earth Engine account
whose project you name in `pipeline/config.py` (`EE_PROJECT`).

## Run at scale

The batch driver is `pipeline/run.py`:

```bash
python -m pipeline.run --smoke     # quick check that the build works
python -m pipeline.run --list      # what would be exported
python -m pipeline.run --export    # queue the export tasks
python -m pipeline.run --export --cell NH-43-X-C --year 2023
```

It resumes cleanly: years already exported are skipped, so re-running
is safe.

## Where the assets live

Every input the pipeline reads is a published cloud asset under
`projects/mapbiomas-india/assets/mosaic_v2_inputs` — the grid, the
boundary, the terrain sheets, the atmospheric lookup tables. A forker
reads them where they live and never rebuilds them; do not repoint
`ASSET_ROOT` in `pipeline/config.py`. The copies in `data/` are loud
fallbacks and provenance snapshots only.

Finished mosaics land in the collection named by `OUTPUT_COLLECTION` in
`pipeline/config.py` (the published production collection in this
version; a development sandbox is also defined there). The scripts in
`scripts/` rebuild the supporting assets and verify exported mosaics;
`docs/input_assets_and_run_order.md` lists every asset and the order to
build them in.
