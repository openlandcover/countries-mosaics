#!/usr/bin/env python
"""
Physical C look-up table for SCS+C, built offline with 6S (via Py6S).

C_phys = diffuse / direct downwelling irradiance at the ground, per OLI band,
on a grid of (sun zenith, elevation, AOT at 550 nm, water vapour). Earth
Engine cannot run a radiative-transfer model, so this is computed here once,
written to CSV with a manifest, and ingested as a FeatureCollection that the
pipeline reads (config.PHYS_LUT_ASSETS, via pipeline/topo_physics.py). An
internal code-editor inspector script first read it (not part of this release).

Two sweeps:
  reduced  sunzen 10-80 by 2.5; elev 0-5500 by 500 m; AOT {0.1,0.3,0.7};
           WV {2,4}                             -> 2,088 nodes, 12,528 runs
  full     sunzen 10-80 by 2.5; elev 0-5500 by 250 m; AOT {0.05,0.1,0.15,
           0.2,0.3,0.45,0.7,1.0}; WV {1..5}     -> 26,680 nodes, 160,080 runs

Fixed settings (recorded in the manifest): continental aerosol, US62
profile with user water vapour and ozone 0.3 cm-atm, nadir view, uniform
Lambertian ground 0.3 (only affects the environmental term, stored
separately), 15 June (the ratio does not depend on earth-sun distance).

Usage (from the py6s-lut conda env):
  PATH=$CONDA_PREFIX/bin:$PATH python scripts/build_6s_correction_tables.py --sweep reduced
  python scripts/build_6s_correction_tables.py --upload data/lut/lut_oli.csv \
      --asset projects/mapbiomas-india/assets/mosaic_v2_inputs/lut_oli
The upload step uses the Earth Engine API and needs the project's normal
Python environment (any env with `earthengine-api`).
"""
import argparse
import csv
import datetime as dt
import itertools
import json
import multiprocessing as mp
import os
import platform
import sys
import time

BANDS = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7']
SWEEPS = {
    'reduced': dict(sunzen=[10 + 2.5 * i for i in range(29)],
                    elev=[500 * i for i in range(12)],
                    aot=[0.1, 0.3, 0.7], wv=[2.0, 4.0]),
    'full': dict(sunzen=[10 + 2.5 * i for i in range(29)],
                 elev=[250 * i for i in range(23)],
                 aot=[0.05, 0.1, 0.15, 0.2, 0.3, 0.45, 0.7, 1.0],
                 wv=[1.0, 2.0, 3.0, 4.0, 5.0]),
    'smoke': dict(sunzen=[30.0, 60.0], elev=[0, 2000], aot=[0.2], wv=[2.0]),
}
OZONE = 0.3
GROUND = 0.3
# Band shapes per sensor. Output columns are ALWAYS named by colour slot
# using the OLI numbers (C_B2 blue, C_B3 green, C_B4 red, C_B5 nir, C_B6
# swir1, C_B7 swir2) so every reader works unchanged; the manifest and the
# file name say which sensor's filters were used.
SENSOR_WL = {
    'oli': ['LANDSAT_OLI_B2', 'LANDSAT_OLI_B3', 'LANDSAT_OLI_B4',
            'LANDSAT_OLI_B5', 'LANDSAT_OLI_B6', 'LANDSAT_OLI_B7'],
    'etm': ['LANDSAT_ETM_B1', 'LANDSAT_ETM_B2', 'LANDSAT_ETM_B3',
            'LANDSAT_ETM_B4', 'LANDSAT_ETM_B5', 'LANDSAT_ETM_B7'],
    'tm':  ['LANDSAT_TM_B1', 'LANDSAT_TM_B2', 'LANDSAT_TM_B3',
            'LANDSAT_TM_B4', 'LANDSAT_TM_B5', 'LANDSAT_TM_B7'],
}
_SENSOR = 'oli'


def _init_worker(sensor):
    global _SENSOR
    _SENSOR = sensor


def _sixs_path():
    p = os.environ.get('SIXS_PATH')
    if p:
        return p
    cand = os.path.join(os.path.dirname(sys.executable), 'sixs')
    return cand if os.path.exists(cand) else None


def run_node(node):
    """One (sunzen, elev, aot, wv) node -> dict with all six bands."""
    from Py6S import (SixS, AtmosProfile, AeroProfile, Geometry,
                      GroundReflectance, Wavelength, PredefinedWavelengths)
    sunzen, elev, aot, wv = node
    s = SixS(_sixs_path())
    s.atmos_profile = AtmosProfile.UserWaterAndOzone(wv, OZONE)
    s.aero_profile = AeroProfile.PredefinedType(AeroProfile.Continental)
    s.aot550 = aot
    s.altitudes.set_target_custom_altitude(elev / 1000.0)
    s.altitudes.set_sensor_satellite_level()
    s.geometry = Geometry.User()
    s.geometry.solar_z = sunzen
    s.geometry.solar_a = 0
    s.geometry.view_z = 0
    s.geometry.view_a = 0
    s.geometry.month = 6
    s.geometry.day = 15
    s.ground_reflectance = GroundReflectance.HomogeneousLambertian(GROUND)
    row = {'sunzen': sunzen, 'elev': elev, 'aot': aot, 'wv': wv}
    t0 = time.time()
    for b, wl in zip(BANDS, SENSOR_WL[_SENSOR]):
        s.wavelength = Wavelength(getattr(PredefinedWavelengths, wl))
        s.run()
        o = s.outputs
        edir = o.direct_solar_irradiance
        edif = o.diffuse_solar_irradiance
        eenv = o.environmental_irradiance
        row['Edir_' + b] = round(edir, 3)
        row['Edif_' + b] = round(edif, 3)
        row['Eenv_' + b] = round(eenv, 3)
        row['C_' + b] = round(edif / edir, 5) if edir > 0 else None
        row['Ce_' + b] = round((edif + eenv) / edir, 5) if edir > 0 else None
    row['sec'] = round(time.time() - t0, 3)
    return row


def build(sweep, out_csv, workers, sensor='oli'):
    sw = SWEEPS[sweep]
    nodes = list(itertools.product(sw['sunzen'], sw['elev'], sw['aot'],
                                   sw['wv']))
    n_runs = len(nodes) * len(BANDS)
    print('sweep {}: {} nodes, {} 6S runs, {} workers'.format(
        sweep, len(nodes), n_runs, workers))
    t0 = time.time()
    rows = []
    with mp.Pool(workers, initializer=_init_worker, initargs=(sensor,)) as pool:
        for i, row in enumerate(pool.imap_unordered(run_node, nodes,
                                                    chunksize=4), 1):
            rows.append(row)
            if i % 100 == 0 or i == len(nodes):
                el = time.time() - t0
                print('  {}/{} nodes  {:.0f}s elapsed  eta {:.0f}s'.format(
                    i, len(nodes), el, el / i * (len(nodes) - i)))
    wall = time.time() - t0
    rows.sort(key=lambda r: (r['aot'], r['wv'], r['elev'], r['sunzen']))
    cols = (['sunzen', 'elev', 'aot', 'wv']
            + ['C_' + b for b in BANDS] + ['Ce_' + b for b in BANDS]
            + ['Edir_' + b for b in BANDS] + ['Edif_' + b for b in BANDS]
            + ['Eenv_' + b for b in BANDS] + ['sec'])
    os.makedirs(os.path.dirname(out_csv) or '.', exist_ok=True)
    with open(out_csv, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    sec_per_run_cpu = sum(r['sec'] for r in rows) / n_runs
    full = SWEEPS['full']
    n_full = (len(full['sunzen']) * len(full['elev']) * len(full['aot'])
              * len(full['wv']) * len(BANDS))
    try:
        import Py6S
        py6s_ver = Py6S.__version__
    except Exception:
        py6s_ver = 'unknown'
    manifest = {
        'built': dt.datetime.now().isoformat(timespec='seconds'),
        'sweep': sweep, 'grid': sw, 'bands': BANDS,
        'n_nodes': len(nodes), 'n_runs': n_runs,
        'engine': '6S v1.1 via Py6S {} (conda-forge sixs)'.format(py6s_ver),
        'sensor': sensor,
        'band_responses': 'Py6S PredefinedWavelengths ' + ', '.join(SENSOR_WL[sensor]) + ' (columns named by colour slot with OLI numbers)',
        'settings': {'aerosol': 'Continental', 'atmosphere':
                     'US62 with user water vapour', 'ozone_cm_atm': OZONE,
                     'ground_reflectance': GROUND, 'view': 'nadir',
                     'date': '15 June (ratio is distance-independent)'},
        'columns': {'C_Bn': 'diffuse/direct downwelling irradiance',
                    'Ce_Bn': '(diffuse+environment)/direct',
                    'Edir/Edif/Eenv_Bn': 'W m-2 um-1 as 6S reports'},
        'timing': {
            'wall_seconds': round(wall, 1), 'workers': workers,
            'cpu_seconds_per_run': round(sec_per_run_cpu, 4),
            'wall_seconds_per_run': round(wall / n_runs, 4),
            'projected_full_sweep_runs': n_full,
            'projected_full_sweep_wall_seconds_same_workers':
                round(wall / n_runs * n_full),
            'projected_full_sweep_cpu_seconds_single_core':
                round(sec_per_run_cpu * n_full)},
        'machine': '{} {}'.format(platform.machine(), platform.platform()),
    }
    mpath = out_csv.replace('.csv', '_manifest.json')
    with open(mpath, 'w') as fh:
        json.dump(manifest, fh, indent=2)
    print('wrote', out_csv, 'and', mpath)
    print('wall {:.0f}s; {:.3f} s/run wall, {:.3f} s/run cpu; full sweep '
          '~{:.0f} min at {} workers'.format(
              wall, wall / n_runs, sec_per_run_cpu,
              manifest['timing']['projected_full_sweep_wall_seconds_same_workers']
              / 60.0, workers))
    # The physics check, for free: C must fall B2 > B3 > ... > B7 at every node.
    bad = [r for r in rows if any(r['C_' + BANDS[i]] <= r['C_' + BANDS[i + 1]]
                                  for i in range(5))]
    print('physics check (blue largest .. swir2 smallest): {} of {} nodes '
          'violate'.format(len(bad), len(rows)))


def upload(csv_path, asset_id, columns='all'):
    """columns='minimal' sends only the axes and the C_Bn columns (the full
    sweep with every column is too large for one request)."""
    import ee
    ee.Initialize(project='mapbiomas-india')
    keep = None if columns == 'all' else \
        set(['sunzen', 'elev', 'aot', 'wv'] + ['C_' + b for b in BANDS])
    feats = []
    with open(csv_path) as fh:
        for r in csv.DictReader(fh):
            props = {k: (float(v) if v not in ('', None) else None)
                     for k, v in r.items() if keep is None or k in keep}
            feats.append(ee.Feature(ee.Geometry.Point([0, 0]), props))  # EE refuses null-geometry exports
    fc = ee.FeatureCollection(feats)
    task = ee.batch.Export.table.toAsset(
        collection=fc, description='lut_table_upload', assetId=asset_id)
    task.start()
    print('started', task.id, '->', asset_id, '({} rows)'.format(len(feats)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sweep', choices=sorted(SWEEPS), default='reduced')
    ap.add_argument('--out', default='data/lut/lut_v1_spare.csv')
    ap.add_argument('--workers', type=int, default=10)
    ap.add_argument('--sensor', choices=sorted(SENSOR_WL), default='oli',
                    help='band shapes: oli (L8/9), etm (L7), tm (L5)')
    ap.add_argument('--upload', metavar='CSV')
    ap.add_argument('--upload-columns', choices=['all', 'minimal'], default='all')
    ap.add_argument('--asset',
                    default='projects/mapbiomas-india/assets/'
                            'mosaic_v2_inputs/lut_oli')
    a = ap.parse_args()
    if a.upload:
        upload(a.upload, a.asset, a.upload_columns)
    else:
        build(a.sweep, a.out, a.workers, a.sensor)
