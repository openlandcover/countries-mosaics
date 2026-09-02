"""
ONE-OFF builder for the terrain half of the illumination term.

WHY THIS ASSET EXISTS
---------------------
SCS+C needs cos(i), the local illumination angle:

    cos(i) = cos(zen)*cos(slope) + sin(zen)*sin(slope)*cos(azi - aspect)

cos(i) itself CANNOT be precomputed -- it depends on the sun position, which
changes every scene. But it expands into a form that is LINEAR in three
terrain-only quantities, with scene-constant scalar weights:

    cos(i) = cos(zen) * cos(slope)
           + sin(zen) * [ cos(azi) * (sin(slope)*cos(aspect))
                        + sin(azi) * (sin(slope)*sin(aspect)) ]

That matters because Earth Engine evaluates expressions at the REQUESTED
scale. Fitting reduces at 300 m (per cell) and 600 m (national). Under the
old code the aspect band -- plain compass bearings in degrees -- was averaged
across the box BEFORE the cosine was taken, and bearings do not average:
north at 350 deg and north at 10 deg average to due south. Measured on
NI-43-Z-A hillside pixels (sun az 150, zen 40): at 30 m the old route equals
the truth exactly (0.6527); at 300 m it read 0.7209 against a truth of
0.6533; at 600 m 0.7629 against 0.6542. Median gap 0.066 and 0.105, with the
worst tenth of pixels over 0.31 and 0.42 out.

Stored as the products below, every term is a plain weighted SUM, and sums
survive averaging. Aggregation becomes exact at any scale. This does not fix
the fault -- it makes it impossible to write.

The existing asset already carries `aspect_sin`/`aspect_cos` in exactly this
damped form, but derived from the RAW slope/aspect. The correction geometry
uses the SMOOTHED pair (register C19: raw DEM noise becomes per-pixel
correction speckle). These two bands are the smoothed equivalents.

BANDS (int16, scale 1e-4, so read them with .multiply(1e-4))
    cos_slope_smooth          = cos(slope_smooth)                      * 1e4
    sinslope_sinaspect_smooth = sin(slope_smooth) * sin(aspect_smooth) * 1e4
    sinslope_cosaspect_smooth = sin(slope_smooth) * cos(aspect_smooth) * 1e4

ALL THREE must be stored. v1 stored only the two aspect products and left
cos(slope) to be computed live from `slope_smooth` -- so at 300 m Earth
Engine averaged the slope in DEGREES and then took the cosine, which is the
same non-linear mistake as the original bearing fault, just on the other
term. The verification step caught it: gap against truth grew 0.0041 at
240 m, 0.0056 at 480 m, 0.0090 at 960 m, while the fully-pinned route was
exact at every scale.

Both lie in [-1, 1] before scaling, so [-10000, 10000] fits int16 with room.

Run:  python scripts/export_terrain_illum_asset.py
"""

import os
import sys

import ee

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# project + output path routed through config (fold-in hardening
# 2026-08-30: producers must honour the single config point)
from pipeline import config as _C0  # noqa: E402
ee.Initialize(project=_C0.EE_PROJECT)

from pipeline import config as C                      # noqa: E402

OUT = _C0.TERRAIN_ILLUM_ASSET
D2R = 3.141592653589793 / 180.0


def build():
    src = ee.Image(C.TERRAIN_ASSET)
    # stored scales, verified by sampling 2026-08-20:
    #   slope_smooth  int, degrees x100
    #   aspect_smooth int, degrees x10
    slope = src.select('slope_smooth').multiply(0.01).multiply(D2R)
    aspect = src.select('aspect_smooth').multiply(0.1).multiply(D2R)
    sin_s = slope.sin()
    out = (slope.cos().rename('cos_slope_smooth')
           .addBands(sin_s.multiply(aspect.sin())
                     .rename('sinslope_sinaspect_smooth'))
           .addBands(sin_s.multiply(aspect.cos())
                     .rename('sinslope_cosaspect_smooth'))
           .multiply(1e4).round().toInt16())
    return out.copyProperties(src, ['system:time_start'])


def main():
    src = ee.Image(C.TERRAIN_ASSET)
    proj = src.select('slope_smooth').projection().getInfo()
    img = ee.Image(build())
    task = ee.batch.Export.image.toAsset(
        image=img,
        description='glo30_india_terrain_illum_v2',
        assetId=OUT,
        region=src.geometry(),
        crs=proj['crs'],
        crsTransform=proj['transform'],
        maxPixels=1e13,
        pyramidingPolicy={'.default': 'mean'},
    )
    task.start()
    print('queued:', task.id)
    print('asset :', OUT)
    print('grid  :', proj['crs'], proj['transform'])
    print('bands : cos_slope_smooth, sinslope_sinaspect_smooth, '
          'sinslope_cosaspect_smooth  (int16, x1e4)')
    print('pyramid policy MEAN -- required: coarse reads must be the average '
          'of the 30 m products, which is exactly what makes aggregation exact')


if __name__ == '__main__':
    main()
