"""Offline guards on the v2 band + property contracts (owner-approved
2026-08-30). These run without an Earth Engine server (the NamingTests
need the ee package importable, but nothing here initialises or touches
the network): they pin the config-side contract so a rename or an
accidental duplicate fails HERE, not in a shipped asset. The live end-to-end check (real band names from a built
graph, the no-shadowed-names probe) lives in the trial-export
verification — a graph evaluation cannot run offline.
"""
import io
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


class ProductionRunTests(unittest.TestCase):
    """The national run is expensive and writes into a published
    collection. These pin the two things that stop it starting by
    accident, and the span it covers."""

    def test_span_matches_the_legacy_product(self):
        self.assertEqual(C.PRODUCTION_FIRST_YEAR, 1986)
        self.assertEqual(C.PRODUCTION_LAST_YEAR, 2025)

    def test_run_refuses_without_the_confirmation_phrase(self):
        from pipeline import run_production as rp
        for wrong in (None, '', 'yes', rp.CONFIRM_PHRASE.lower()):
            with self.assertRaises(ValueError):
                rp.run(confirm=wrong)

    def test_plan_covers_every_cell_and_year(self):
        from pipeline import run_production as rp
        # offline: cell_names falls back to the shipped grid snapshot
        work = rp.plan()
        cells = {c for c, _ in work}
        years = {y for _, y in work}
        self.assertEqual(len(cells), 283)
        self.assertEqual(sorted(years)[0], C.PRODUCTION_FIRST_YEAR)
        self.assertEqual(sorted(years)[-1], C.PRODUCTION_LAST_YEAR)
        self.assertEqual(len(work), len(cells) * len(years))

    def test_plan_rejects_a_backwards_year_span(self):
        from pipeline import run_production as rp
        with self.assertRaises(ValueError):
            rp.plan(cells=['NC-43-X-D'], first_year=2020, last_year=2019)


if __name__ == '__main__':
    unittest.main()

class ProductionRunSafetyTests(unittest.TestCase):
    """The guards that stop a run of 11,320 doing harm when the set-up is
    wrong rather than the cell."""

    def test_a_run_refuses_the_offline_grid_snapshot(self):
        # A real run must build the cell list from the grid asset. Falling
        # back to the shipped snapshot would let it run against a list that
        # is not the asset's.
        from pipeline import run_production as rp
        with self.assertRaises(RuntimeError):
            rp.cell_names(strict=True)

    def test_planning_still_works_offline(self):
        from pipeline import run_production as rp
        self.assertEqual(len(rp.cell_names()), 283)

    def test_a_run_stops_after_repeated_failures(self):
        # Wrong credentials, or no write access, would otherwise grind
        # through every one of 11,320 cell-years failing each time.
        from unittest import mock
        from pipeline import run_production as rp
        cells = ['C{}'.format(i) for i in range(rp.CONSECUTIVE_FAILURE_LIMIT + 30)]
        with mock.patch.object(rp.build, 'export',
                               side_effect=RuntimeError('no write access')):
            out = rp.run(confirm=rp.CONFIRM_PHRASE, cells=cells,
                         first_year=2019, last_year=2019,
                         collection_path='projects/x/assets/y', verbose=False)
        self.assertEqual(len(out['failed']), rp.CONSECUTIVE_FAILURE_LIMIT)
        self.assertEqual(len(out['queued']), 0)

    def test_one_bad_cell_year_does_not_end_the_run(self):
        from unittest import mock
        from pipeline import run_production as rp

        def flaky(cell, year, **kw):
            if cell == 'BAD':
                raise RuntimeError('this one is broken')
            return object()

        with mock.patch.object(rp.build, 'export', side_effect=flaky):
            out = rp.run(confirm=rp.CONFIRM_PHRASE,
                         cells=['A', 'BAD', 'B'], first_year=2019,
                         last_year=2019, collection_path='projects/x/assets/y',
                         verbose=False)
        self.assertEqual(len(out['queued']), 2)
        self.assertEqual(len(out['failed']), 1)


class CollectionDescriptionTests(unittest.TestCase):
    """The collection has to describe itself. Nothing in an export writes
    that, so the run does it once, before it queues anything."""

    def test_the_shipped_text_exists_and_says_what_it_should(self):
        from pipeline import run_production as rp
        with io.open(rp.DESCRIPTION_FILE, encoding='utf-8') as handle:
            text = handle.read()
        self.assertGreater(len(text), 500)
        for phrase in ('IOLN ANNUAL LANDSAT MOSAICS OF INDIA',
                       'READING THE NUMBERS', 'BEFORE YOU USE IT'):
            self.assertIn(phrase, text)

    def test_the_description_is_written_before_any_export(self):
        from unittest import mock
        from pipeline import run_production as rp
        order = []
        with mock.patch.object(rp, 'describe_destination',
                               side_effect=lambda p: order.append('describe')), \
             mock.patch.object(rp.build, 'export',
                               side_effect=lambda *a, **k: order.append('export')):
            rp.run(confirm=rp.CONFIRM_PHRASE, cells=['A', 'B'],
                   first_year=2019, last_year=2019,
                   collection_path='projects/x/assets/y', verbose=False)
        self.assertEqual(order[0], 'describe')
        self.assertEqual(order.count('describe'), 1)

    def test_a_failed_description_does_not_stop_the_run(self):
        # The product matters more than its label: the description can be
        # set afterwards, so this must never be fatal.
        from unittest import mock
        from pipeline import run_production as rp
        with mock.patch.object(rp, 'describe_destination',
                               side_effect=RuntimeError('no permission')), \
             mock.patch.object(rp.build, 'export', return_value=object()):
            out = rp.run(confirm=rp.CONFIRM_PHRASE, cells=['A'],
                         first_year=2019, last_year=2019,
                         collection_path='projects/x/assets/y', verbose=False)
        self.assertEqual(len(out['queued']), 1)

    def test_describing_can_be_switched_off(self):
        from unittest import mock
        from pipeline import run_production as rp
        with mock.patch.object(rp, 'describe_destination') as described, \
             mock.patch.object(rp.build, 'export', return_value=None):
            rp.run(confirm=rp.CONFIRM_PHRASE, cells=['A'], first_year=2019,
                   last_year=2019, collection_path='projects/x/assets/y',
                   verbose=False, describe=False)
        described.assert_not_called()


class QueueFullTests(unittest.TestCase):
    """Earth Engine's ceiling on pending tasks depends on the account, so the
    run must recognise the refusal rather than rely on a guessed number."""

    def test_it_knows_a_refusal_from_a_breakage(self):
        from pipeline import run_production as rp
        for message in ('Too many pending tasks',
                        'Quota exceeded for tasks',
                        'RESOURCE_EXHAUSTED: rate limit',
                        'too many concurrent operations'):
            self.assertTrue(rp.looks_like_a_full_queue(message), message)
        for message in ('no write access to the collection',
                        'Asset not found',
                        'invalid band name'):
            self.assertFalse(rp.looks_like_a_full_queue(message), message)

    def test_a_full_queue_stops_the_sitting_without_counting_failures(self):
        from unittest import mock
        from pipeline import run_production as rp

        calls = {'n': 0}

        def refuse_after_three(cell, year, **kw):
            calls['n'] += 1
            if calls['n'] > 3:
                raise RuntimeError('Too many pending tasks in the queue')
            return object()

        with mock.patch.object(rp, 'describe_destination'), \
             mock.patch.object(rp.build, 'export',
                               side_effect=refuse_after_three):
            out = rp.run(confirm=rp.CONFIRM_PHRASE,
                         cells=['A', 'B', 'C', 'D', 'E', 'F'],
                         first_year=2019, last_year=2019,
                         collection_path='projects/x/assets/y', verbose=False)
        self.assertEqual(len(out['queued']), 3)
        # a full queue is not a failure; nothing should be recorded as one
        self.assertEqual(len(out['failed']), 0)

