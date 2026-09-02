"""Offline guards on the v2 band + property contracts (owner-approved
2026-08-30). These run without an Earth Engine server (the NamingTests
need the ee package importable, but nothing here initialises or touches
the network): they pin the config-side contract so a rename or an
accidental duplicate fails HERE, not in a shipped asset. The live end-to-end check (real band names from a built
graph, the no-shadowed-names probe) lives in the trial-export
verification — a graph evaluation cannot run offline.
"""
import unittest

from pipeline import config as C


class BandContractTests(unittest.TestCase):

    def test_117_bands(self):
        self.assertEqual(len(C.BAND_ORDER), 117)

    def test_no_duplicates(self):
        self.assertEqual(len(C.BAND_ORDER), len(set(C.BAND_ORDER)))

    def test_no_shadow_suffix(self):
        # an EE band collision renames the loser to <name>_1; the
        # contract must never legitimise such a name
        self.assertFalse([b for b in C.BAND_ORDER if b.endswith('_1')])

    def test_v2_renames_present(self):
        for b in ('red_swing', 'ndfi_mad', 'ndvi_q1_median',
                  'ndvi_q4_median'):
            self.assertIn(b, C.BAND_ORDER)
        for gone in ('red_range', 'ndvi_q1', 'processing_track'):
            self.assertNotIn(gone, C.BAND_ORDER)

    def test_block_order(self):
        # position before bookkeeping, bookkeeping dead last
        self.assertLess(C.BAND_ORDER.index('lon'),
                        C.BAND_ORDER.index('usable_count'))
        self.assertEqual(C.BAND_ORDER[-1], 'q4_count')
        # opens as true colour: bands 1-3 are red/green/blue medians
        self.assertEqual(C.BAND_ORDER[:3],
                         ['red_median', 'green_median', 'blue_median'])


class PropertyContractTests(unittest.TestCase):

    def test_nine_decode_props(self):
        # AMENDMENT 1 (2026-09-01): decode_tasseled_cap merged into
        # decode_indices — one rule for the whole x0.0001 family
        self.assertEqual(len(C.DECODE_PROPS), 9)
        self.assertNotIn('decode_tasseled_cap', C.DECODE_PROPS)
        self.assertIn('never shifted', C.DECODE_PROPS['decode_indices'])
        for k in C.DECODE_PROPS:
            self.assertTrue(k.startswith('decode_'), k)

    def test_identity_constants(self):
        self.assertEqual(C.PRODUCT_VERSION, '2')
        self.assertTrue(C.PRODUCT.startswith('IOLN'))
        self.assertIn('Topographic Correction', C.CORRECTIONS)


class RulingsTests(unittest.TestCase):

    def test_mask_and_trim_rules(self):
        self.assertEqual(C.MASK_RULE, 'both')
        self.assertTrue(C.CLOUD_TRIM)
        self.assertEqual((C.CLOUD_TRIM_DELTA, C.CLOUD_TRIM_SPREAD,
                          C.CLOUD_TRIM_MAX_FLOOR), (0.03, 0.03, 5))

    def test_topo_rules(self):
        self.assertEqual(C.TOPO_C_ESTIMATOR, 'physics')
        self.assertEqual(C.TOPO_UNCORRECTED_BANDS, ())
        self.assertTrue(C.TOPO_ILLUM_LINEAR)

    def test_l7_span(self):
        # owner ruling 2026-08-30: L7 through pheno-2021 (last mostly
        # single-clean-satellite year), withdrawn from pheno-2022
        self.assertEqual(C.SENSOR_YEARS['l7'], (1999, 2021))

    def test_input_root_is_pinned(self):
        # the fork model: inputs are published assets, never repointed
        self.assertEqual(C.ASSET_ROOT, 'projects/mapbiomas-india/assets')
        self.assertIn('mosaics-2', C.PRODUCTION_COLLECTION)

    def test_luts_read_from_inputs_folder(self):
        # owner rule 2026-08-30/31: EVERY pipeline input lives in
        # mosaic_v2_inputs; the 6S tables are cloud-first, CSV fallback
        for kind in ('oli', 'etm', 'tm'):
            self.assertTrue(
                C.PHYS_LUT_ASSETS[kind].startswith(C.INPUTS_ROOT))


class NamingTests(unittest.TestCase):
    """Asset naming (owner ruling 2026-09-01): sandbox names keep the
    variant/version tail; production names are CELL_YEAR only, and
    export() refuses lab tails on a production destination BEFORE any
    network call."""

    def test_sandbox_name(self):
        from pipeline import build
        self.assertEqual(
            build.asset_name('NC-43-X-D', 2019, 'c2_only'),
            'NC-43-X-D_2019_c2_only_v{}'.format(C.VERSION))

    def test_sandbox_label_replaces_year(self):
        from pipeline import build
        self.assertEqual(
            build.asset_name('NC-43-X-D', 2019, 'c2_only',
                             label='2019trimshi'),
            'NC-43-X-D_2019trimshi_c2_only_v{}'.format(C.VERSION))

    def test_production_name_is_cell_year_only(self):
        from pipeline import build
        self.assertEqual(build.production_asset_name('NC-43-X-D', 2019),
                         'NC-43-X-D_2019')

    def test_export_refuses_label_on_production(self):
        from pipeline import build
        with self.assertRaises(ValueError):
            build.export('NC-43-X-D', 2019, label='2019trimshi',
                         collection_path=C.PRODUCTION_COLLECTION)

    def test_export_refuses_variant_tail_on_production(self):
        from pipeline import build
        with self.assertRaises(ValueError):
            build.export('NC-43-X-D', 2019, variant='lab',
                         collection_path=C.PRODUCTION_COLLECTION)

    def test_export_refuses_lite_on_production(self):
        # a lite build claiming the full CELL_YEAR name would make
        # skip_existing silently block the real export forever
        from pipeline import build
        with self.assertRaises(ValueError):
            build.export('NC-43-X-D', 2019, lite=True,
                         collection_path=C.PRODUCTION_COLLECTION)

    def test_guard_survives_default_destination_flip(self):
        # the pre-publication flip sets OUTPUT_COLLECTION to the
        # production collection; the guard must still fire on the
        # collection_path=None default
        from unittest import mock
        from pipeline import build
        with mock.patch.object(C, 'OUTPUT_COLLECTION',
                               C.PRODUCTION_COLLECTION):
            with self.assertRaises(ValueError):
                build.export('NC-43-X-D', 2019, label='2019trimshi')


if __name__ == '__main__':
    unittest.main()
