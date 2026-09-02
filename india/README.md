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
here are new. See `docs/` for the full method record.

## Run one cell-year

Open `notebooks/run_one_cell_year.ipynb`. Set the grid cell, the
year(s), and the destination in the first cell, run the preview cell to
see the mosaic, then run the export cell to queue the full asset. The
default destination is the development sandbox, which is safe to write
to.

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
