#!/usr/bin/env python
"""
Producer for the prepared terrain sheet glo30_india_terrain_v1 —
PROVENANCE AND DISASTER RECOVERY ONLY (owner ruling 2026-08-30): the
live asset is authoritative and the pipeline reads it from record; this
script exists so the asset is REPRODUCIBLE, and it REFUSES to overwrite
the original. To rebuild after a disaster, export to a new path and
verify against the recorded band scales before repointing config.

Construction (matches the live asset's own description property,
verified 2026-08-30; register C19-addendum-2):
  bands 0-4  DEM/EDM/FLM/HEM/WBM copied unchanged from
             COPERNICUS/DEM/GLO30_2024_1, flattened to one image on the
             native 1 arc-second grid
  slope         ee.Terrain slope on the raw DEM, degrees x100, int16
  aspect_sin    sin(aspect) x sin(slope), x10000, int16 (slope-damped)
  aspect_cos    cos(aspect) x sin(slope), x10000, int16 (slope-damped)
  slope_smooth  slope after DEM_SMOOTH_PX focal mean, degrees x100
  aspect_smooth aspect from the same smoothed DEM, degrees x10 (never
                resample bilinear — wraps at north)
  hand          metres x10, int16, from users/gena/global-hand/hand-100
                (threshold-100), masked to [0, 10000) m

Usage:
  python scripts/export_terrain_asset.py                # print the plan
  python scripts/export_terrain_asset.py --run \
         --dest projects/.../shared_assets/glo30_india_terrain_v2_rebuild
"""
import argparse
import math
import os
import sys

import ee

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pipeline import config as C            # noqa: E402

D2R = math.pi / 180.0


def build_image():
    dem_coll = ee.ImageCollection(C.DEM_ASSET)
    proj = dem_coll.first().select('DEM').projection()
    raw = dem_coll.select(['DEM', 'EDM', 'FLM', 'HEM', 'WBM']) \
        .mosaic().setDefaultProjection(proj)
    d = raw.select('DEM')

    slope = ee.Terrain.slope(d)
    aspect = ee.Terrain.aspect(d).multiply(D2R)
    damp = slope.multiply(D2R).sin()
    a_sin = aspect.sin().multiply(damp).multiply(10000).toInt16()
    a_cos = aspect.cos().multiply(damp).multiply(10000).toInt16()

    d_sm = (d.focalMean(C.DEM_SMOOTH_PX, 'square', 'pixels')
            .setDefaultProjection(proj))
    slope_sm = ee.Terrain.slope(d_sm)
    aspect_sm = ee.Terrain.aspect(d_sm)

    hand = ee.ImageCollection(C.HAND_ASSET).mosaic()
    hand = hand.updateMask(hand.gte(0).And(hand.lt(10000)))

    return ee.Image.cat([
        raw,
        slope.multiply(100).toInt16().rename('slope'),
        a_sin.rename('aspect_sin'),
        a_cos.rename('aspect_cos'),
        slope_sm.multiply(100).toInt16().rename('slope_smooth'),
        aspect_sm.multiply(10).toInt16().rename('aspect_smooth'),
        hand.multiply(10).toInt16().rename('hand'),
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true',
                    help='actually queue the export (default: plan only)')
    ap.add_argument('--dest', default=None,
                    help='destination asset id (REQUIRED with --run; '
                         'must NOT be the live asset)')
    a = ap.parse_args()
    ee.Initialize(project=C.EE_PROJECT)

    live = C.TERRAIN_ASSET
    print('live (authoritative) asset:', live)
    print('this script rebuilds the same construction; it will not '
          'overwrite the live asset.')
    if not a.run:
        print('plan only — pass --run --dest <new asset id> to export.')
        return
    if not a.dest or a.dest == live:
        sys.exit('refusing: --dest is required and must differ from the '
                 'live asset ({})'.format(live))

    img = build_image()
    india = ee.FeatureCollection(C.INDIA_ASSET).geometry().buffer(20000)
    task = ee.batch.Export.image.toAsset(
        image=img.clip(india),
        description='glo30_india_terrain_rebuild',
        assetId=a.dest,
        region=india.bounds(),
        crs='EPSG:4326',
        crsTransform=[1.0 / 3600, 0, -180, 0, -1.0 / 3600, 90],
        maxPixels=1e12)
    task.start()
    print('queued', a.dest, getattr(task, 'id', None))


if __name__ == '__main__':
    main()
