#!/usr/bin/env python
"""
Producer for mosaic_v2_inputs/overpass_conditions/INDIA_<year> (owner
approved 2026-08-30): ONE national table per year, one row per Landsat
FRAME with the conditions the physics terrain correction needs — date,
sun zenith, MERRA-2 aerosol (aot) and water vapour at the pass hour —
plus the frame's bounds so a cell build can read just its own passes.

Rows are derived EXACTLY as pipeline/topo_physics.pass_table does live
(same sources.build query, same _sun_angles_deg, same +/-1 h MERRA
scene-wide mean), just server-side into a table instead of per-export
client queries. After these exist, MERRA-2 is a producer-time
dependency only.

  python scripts/export_overpass_conditions.py --years 1986 2025
  python scripts/export_overpass_conditions.py --years 2022 2022
"""
import argparse
import os
import sys

import ee

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pipeline import config as C, sources, terrain    # noqa: E402


def year_table(india, year):
    coll, _era = sources.build(india, year, mode='c2')
    aer = ee.ImageCollection('NASA/GSFC/MERRA/aer/2')
    slv = ee.ImageCollection('NASA/GSFC/MERRA/slv/2')

    def f(im):
        im = ee.Image(im)
        t = ee.Date(im.get('system:time_start'))
        _az, zen = terrain._sun_angles_deg(im)
        geom = im.geometry()
        # NULL-SAFE (found on pheno-2025: MERRA-2 lags months, an empty
        # hour made mean() a zero-band image and killed the export; a
        # missing value must become the climatology fallback instead)
        aer_h = (aer.filterDate(t.advance(-1, 'hour'), t.advance(1, 'hour'))
                 .select('TOTEXTTAU'))
        slv_h = (slv.filterDate(t.advance(-1, 'hour'), t.advance(1, 'hour'))
                 .select('TQV'))
        a = ee.Algorithms.If(
            aer_h.size().gt(0),
            aer_h.mean().reduceRegion(ee.Reducer.mean(), geom, 5000,
                                      bestEffort=True).get('TOTEXTTAU'),
            None)
        w = ee.Algorithms.If(
            slv_h.size().gt(0),
            slv_h.mean().reduceRegion(ee.Reducer.mean(), geom, 5000,
                                      bestEffort=True).get('TQV'),
            None)
        return ee.Feature(geom.bounds(), {
            'sensor': im.get('sensor'), 'pass_key': im.get('pass_key'),
            'idx': im.get('system:index'), 'zen': zen,
            't': im.get('system:time_start'), 'aot': a, 'tqv': w})

    return ee.FeatureCollection(coll.map(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--years', nargs=2, type=int, required=True,
                    metavar=('FIRST', 'LAST'))
    a = ap.parse_args()
    ee.Initialize(project=C.EE_PROJECT)
    folder = C.INPUTS_ROOT + '/overpass_conditions'
    try:
        ee.data.createAsset({'type': 'FOLDER'}, folder)
        print('created folder', folder)
    except Exception:
        pass
    india = ee.FeatureCollection(C.INDIA_ASSET).geometry()
    queued = skipped = 0
    for year in range(a.years[0], a.years[1] + 1):
        asset_id = '{}/INDIA_{}'.format(folder, year)
        try:
            ee.data.getAsset(asset_id)
            skipped += 1
            continue
        except Exception:
            pass
        task = ee.batch.Export.table.toAsset(
            collection=year_table(india, year),
            description='overpass_conditions_{}'.format(year),
            assetId=asset_id)
        task.start()
        queued += 1
        print('queued INDIA_{} ({})'.format(year, task.id))
    print('{} queued, {} already existed'.format(queued, skipped))


if __name__ == '__main__':
    main()
