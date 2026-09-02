#!/usr/bin/env python
"""
Re-upload the provenance vector snapshots in data/vectors/ as EE table
assets — DISASTER RECOVERY ONLY (owner ruling 2026-08-30): the live
assets are authoritative and the pipeline reads them from record; the
GeoJSON files exist so the vectors cannot be lost with the assets.
Refuses to overwrite a live asset: give --dest a fresh id.

Snapshots taken 2026-08-30 (held in the private archive; of the vector
snapshots, only grid_cells_india.geojson is part of this release):
  india_boundary_official.geojson          (253 features)
  ioln_classification_regions.geojson      (8 regions)
  ioln_classification_regions_v2.geojson   (8 regions)
NOTE (open item, 2026-08-30): config.REGIONS_ASSET points at a _v3
vector that does NOT exist in the project; production is unaffected
because the painted regions_mask_v1 raster is read instead. Owner to
rule which vector is authoritative before the fallback path is fixed.

Usage:
  python scripts/upload_vectors.py --file data/vectors/<name>.geojson \
         --dest projects/<project>/assets/<new asset id>
"""
import argparse
import json
import os
import sys

import ee

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pipeline import config as C            # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--dest', required=True)
    a = ap.parse_args()
    ee.Initialize(project=C.EE_PROJECT)
    try:
        ee.data.getAsset(a.dest)
        sys.exit('refusing: {} already exists (live assets are '
                 'authoritative; pick a fresh id)'.format(a.dest))
    except ee.ee_exception.EEException:
        pass
    except Exception:
        pass
    with open(a.file) as fh:
        gj = json.load(fh)
    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry(f['geometry']), f.get('properties', {}))
        for f in gj['features']])
    task = ee.batch.Export.table.toAsset(
        collection=fc,
        description=os.path.splitext(os.path.basename(a.file))[0],
        assetId=a.dest)
    task.start()
    print('queued', a.dest, getattr(task, 'id', None))


if __name__ == '__main__':
    main()
