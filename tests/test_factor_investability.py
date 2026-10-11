# SPDX-License-Identifier: MIT
"""Accounting counterexamples, unknown coverage and independent light entry."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from portfolio_engine.factor_research import panel, trials
from portfolio_engine.factor_series import series, cost
from portfolio_engine.factor_exposure import exposure
from portfolio_engine.factor_cash import cashfit
from portfolio_engine.factor_diagnostics import decay, stability
from portfolio_engine.factor_advanced import budget
from portfolio_engine.review_io import digest, publish, read


def draft(action):
    return json.loads((ROOT / 'examples/factor-review' / (action + '.json')).read_text(encoding='utf-8'))


class DefinitionTests(unittest.TestCase):
    def test_legacy_results_exactly_unchanged(self):
        hashes = read(ROOT / 'tests/fixtures/factor-legacy-digests.json')
        for action, handler in [('panel', panel), ('trials', trials)]:
            spec = read(ROOT / 'examples/expansion-teaching' / (action + '.json'))
            self.assertEqual(digest(handler(spec)), hashes[action])

    def test_new_schema_missing_definition_rejected(self):
        for field in ('factorId', 'factorVersion', 'factorDefinition', 'factorSource'):
            with self.subTest(field=field):
                spec = draft('series'); del spec[field]
                with self.assertRaises(ValueError): series(spec)

    def test_unknown_schema_rejected(self):
        spec = draft('series'); spec['schemaVersion'] = 'future/99'
        with self.assertRaises(ValueError): series(spec)

    def test_new_identity_retained_without_input_mutation(self):
        spec = draft('series'); before = digest(spec)
        result = series(spec)
        self.assertEqual(result['factorIdentity']['factorVersion'], '1')
        self.assertEqual(before, digest(spec))
        self.assertEqual(result['inputSha256'], before)

    def test_malformed_asof_and_nonfinite_rejected(self):
        for value in ('NaN', True, float('inf')):
            spec = draft('series'); spec['rows'][0]['factor'] = value
            with self.assertRaises(ValueError): series(spec)

    def test_frozen_directory_and_receipt(self):
        spec = draft('exposure')
        with tempfile.TemporaryDirectory() as tmp:
            path = publish(spec, exposure(spec), Path(tmp) / 'result', '教学')
            before = (path / 'result.json').read_bytes()
            with self.assertRaises(ValueError): publish(spec, exposure(spec), path, '再次')
            self.assertEqual(before, (path / 'result.json').read_bytes())
            self.assertIn('result.json', read(path / 'receipt.json')['files'])


class SeriesTests(unittest.TestCase):
    def test_existing_spreads_preserved_with_windows(self):
        result = series(draft('series'))
        self.assertEqual([r['topMinusBottomGrossReturn'] for r in result['series']], [.015, .015])
        self.assertTrue(result['overlappingWindows'])
        self.assertIsNone(result['cumulative'])
        self.assertIsNone(result['maxDrawdown'])

    def test_constant_factor_does_not_create_spread(self):
        spec = draft('series')
        for row in spec['rows']: row['factor'] = 0
        result = series(spec)
        self.assertTrue(all(r['topMinusBottomGrossReturn'] is None for r in result['series']))
        self.assertTrue(all(r['emptyGroups'] for r in result['series']))

    def test_declared_plan_preserves_tied_group(self):
        spec = draft('series')
        for row in spec['rows']:
            if row['security'] == 'teaching:1': row['factor'] = 0
        result = series(spec)
        self.assertEqual(result['researchGroupPlans'][0]['groups']['1'], {'teaching:0': .5, 'teaching:1': .5})

    def test_future_returns_excluded_without_zero_filling(self):
        spec = draft('series'); spec['asOf'] = '2026-01-07T16:00:00+08:00'
        result = series(spec)
        self.assertEqual(result['series'], [])
        self.assertEqual(len(result['excluded']), 6)

    def test_signal_lookahead_rejected(self):
        for field in ('factorAvailableAt', 'universeAvailableAt'):
            spec = draft('series'); spec['rows'][0][field] = '2026-01-05T11:00:00+08:00'
            with self.assertRaises(ValueError): series(spec)


class ExposureTests(unittest.TestCase):
    def test_partial_contribution_not_normalized_mean(self):
        result = exposure(draft('exposure'))
        self.assertAlmostEqual(result['knownWeightedContribution'], 1.4)
        self.assertAlmostEqual(result['knownNormalizedExposure'], 2)
        self.assertAlmostEqual(result['unknownWeight'], .3)
        self.assertIsNone(result['completeSecurityExposure'])
        self.assertIsNone(result['percentile'])

    def test_all_unknown_is_not_zero(self):
        spec = draft('exposure'); spec['factorValues'] = []
        result = exposure(spec)
        self.assertIsNone(result['knownWeightedContribution'])
        self.assertIsNone(result['knownNormalizedExposure'])
        self.assertEqual(result['unknownWeight'], 1)

    def test_cash_not_imputed_as_factor_zero(self):
        spec = draft('exposure'); spec['holdings'][1]['kind'] = 'cash'
        result = exposure(spec)
        self.assertEqual(result['cashWeight'], .3)
        self.assertEqual(result['unknownWeight'], 0)
        self.assertEqual(result['knownNormalizedExposure'], 2)

    def test_universe_percentile_requires_coverage(self):
        spec = draft('exposure')
        spec['referenceUniverse'] = {k: spec[k] for k in ('snapshotAt', 'factorId', 'factorVersion', 'factorScale')}
        spec['referenceUniverse'].update(definition='教学', version='1', securities=['teaching:A', 'teaching:C'])
        self.assertIsNone(exposure(spec)['percentile'])
        spec['holdings'][1]['kind'] = 'cash'
        self.assertEqual(exposure(spec)['percentile'], 25)

    def test_nonunit_leverage_or_negative_weights_rejected(self):
        for weight in (1.5, -.1, True, 'NaN'):
            spec = draft('exposure'); spec['holdings'][0]['weight'] = weight
            with self.assertRaises(ValueError): exposure(spec)

    def test_duplicate_security_rejected(self):
        spec = draft('exposure'); spec['holdings'].append(copy.deepcopy(spec['holdings'][0]))
        with self.assertRaises(ValueError): exposure(spec)

    def test_time_and_scale_mismatch_rejected(self):
        for field, value in [('availableAt', '2026-01-06T10:00:00+08:00'), ('factorScale', 'other'),
                             ('valueAt', '2026-01-06T10:00:00+08:00'), ('factorVersion', '2')]:
            spec = draft('exposure'); spec['factorValues'][0][field] = value
            with self.assertRaises(ValueError): exposure(spec)

    def test_benchmark_mismatch_rejected(self):
        spec = draft('exposure')
        spec['benchmark'] = {k: spec[k] for k in ('snapshotAt', 'weightBasis', 'factorId', 'factorVersion', 'factorScale')}
        spec['benchmark'].update(holdings=spec['holdings'], factorScale='other')
        with self.assertRaises(ValueError): exposure(spec)


class LedgerTests(unittest.TestCase):
    def test_signed_trades_fees_and_drift_match_hand_ledger(self):
        # Start: A50 + cash50. Sell A20, buy B20, fee .04.
        # End1: A33+B24+cash49.96=106.96. End2: A29.7+B24+49.96=103.66.
        result = cost(draft('cost'))
        first = result['periods'][0]
        self.assertAlmostEqual(first['absoluteTradedAmount'], 40)
        self.assertAlmostEqual(first['costAmount'], .04)
        self.assertAlmostEqual(first['netEquity'], 106.96)
        self.assertAlmostEqual(result['periods'][1]['netEquity'], 103.66)
        self.assertAlmostEqual(result['netCumulative'], .0366)
        self.assertAlmostEqual(result['maxDrawdown'], 3.3 / 106.96)
        self.assertAlmostEqual(result['grossCumulative'], .037)

    def test_zero_cost_gross_equals_net(self):
        spec = draft('cost'); spec['account']['costBps'] = 0
        result = cost(spec)
        self.assertEqual(result['netCumulative'], result['grossCumulative'])
        for row in result['periods']: self.assertEqual(row['grossReturn'], row['netReturn'])

    def test_missing_cost_leaves_net_unknown(self):
        spec = draft('cost'); del spec['account']['costBps']
        result = cost(spec)
        self.assertIsNone(result['accountNetSeries'])
        self.assertIsNone(result['netCumulative'])
        self.assertIsNone(result['maxDrawdown'])

    def test_initial_entry_and_final_exit_cost_once_each(self):
        spec = draft('cost'); spec.pop('costBpsRange')
        a = spec['account']; a['initialHoldings'] = {}; a['initialCash'] = 100
        p, q = a['periods']
        p['assetReturns'] = {'teaching:A': 0}
        p['trades'] = [{**p['trades'][0], 'notional': 50}]
        q['assetReturns'] = {}
        q['trades'] = [{**p['trades'][0], 'notional': -50, 'tradeAt': q['startAt'], 'availableAt': q['startAt']}]
        result = cost(spec)
        self.assertAlmostEqual(sum(r['costAmount'] for r in result['periods']), .1)
        self.assertAlmostEqual(result['netCumulative'], -.001)

    def test_stopped_limit_up_or_unknown_trade_is_not_account_return(self):
        for can_trade in (False, None):
            spec = draft('cost'); spec['account']['periods'][0]['trades'][0]['canTrade'] = can_trade
            result = cost(spec)
            self.assertIsNone(result['accountNetSeries'])
            self.assertIsNone(result['grossCumulative'])

    def test_cantrade_integer_is_not_true(self):
        spec = draft('cost'); spec['account']['periods'][0]['trades'][0]['canTrade'] = 1
        with self.assertRaises(ValueError): cost(spec)

    def test_short_unavailable_not_silently_supported(self):
        spec = draft('cost'); spec['account']['periods'][0]['trades'][0]['notional'] = -60
        with self.assertRaisesRegex(ValueError, '空头'): cost(spec)

    def test_cash_shortage_no_automatic_borrowing(self):
        spec = draft('cost'); spec.pop('costBpsRange'); spec['account']['initialCash'] = 0
        with self.assertRaisesRegex(ValueError, '现金不足'): cost(spec)

    def test_missing_return_not_filled_zero(self):
        spec = draft('cost'); spec.pop('costBpsRange'); del spec['account']['periods'][0]['assetReturns']['teaching:B']
        self.assertIsNone(cost(spec)['accountNetSeries'])

    def test_overlaps_gaps_future_and_intraperiod_trades_rejected(self):
        for field, value in [('startAt', '2026-01-05T11:00:00+08:00'), ('startAt', '2026-01-07T09:00:00+08:00'),
                             ('availableAt', '2026-03-01T09:00:00+08:00')]:
            spec = draft('cost'); spec['account']['periods'][1][field] = value
            with self.assertRaises(ValueError): cost(spec)
        spec = draft('cost'); spec['account']['periods'][0]['trades'][0]['tradeAt'] = '2026-01-05T11:00:00+08:00'
        with self.assertRaises(ValueError): cost(spec)

    def test_cashflows_and_cash_yield_not_ignored(self):
        for field, value in [('externalFlows', [{'amount': 1}]), ('cashReturn', .01)]:
            spec = draft('cost'); spec['account'][field] = value
            with self.assertRaises(ValueError): cost(spec)

    def test_unknown_settlement_not_available_cash(self):
        spec = draft('cost'); del spec['account']['settlementMode']
        with self.assertRaisesRegex(ValueError, '未知到账'): cost(spec)

    def test_new_panel_identity_and_legacy_schema_separate(self):
        spec = draft('series')
        self.assertEqual(panel(spec)['factorIdentity']['schemaVersion'], 'factor-review/2')

    def test_sensitivity_is_monotone_for_identical_fixed_trades(self):
        result = cost(draft('cost'))
        values = [r['netCumulative'] for r in result['sensitivity']]
        self.assertGreater(values[0], values[1]); self.assertGreater(values[1], values[2])


class CashTests(unittest.TestCase):
    def known(self):
        spec = draft('cashfit')
        spec['cashDemand']['cashflows'] = []
        spec['cashDemand']['planned_liquidations'] = []
        spec['cashDemand']['frozen_releases'] = []
        spec['cashDemand']['scenarios'] = [spec['cashDemand']['scenarios'][0]]
        return spec

    def test_known_no_conflict_empty_array(self):
        spec = self.known(); spec['rebalanceCashNeeds'][0]['amount'] = 0
        result = cashfit(spec)
        self.assertEqual(result['scenarios'][0]['conflictDates'], [])

    def test_unknown_amount_not_no_conflict(self):
        spec = self.known(); spec['rebalanceCashNeeds'][0]['amount'] = None
        result = cashfit(spec)
        self.assertIsNone(result['scenarios'][0]['conflictDates'])
        self.assertIsNone(result['scenarios'][0]['conflictAmount'])

    def test_cash_shortfall_and_options_no_fabricated_cost(self):
        spec = self.known(); spec['rebalanceCashNeeds'][0]['amount'] = 1000000
        result = cashfit(spec)['scenarios'][0]
        self.assertGreater(result['conflictAmount'], 0)
        self.assertEqual(len(result['options']), 3)
        self.assertTrue(all(r['cost'] is None and r['executionDate'] is None for r in result['options']))

    def test_untradeable_does_not_certify_cashfit(self):
        spec = self.known(); spec['rebalanceCashNeeds'][0]['canTrade'] = False
        self.assertIsNone(cashfit(spec)['scenarios'][0]['conflictDates'])

    def test_duplicate_economic_event_rejected(self):
        spec = draft('cashfit')
        spec['rebalanceCashNeeds'][0]['economicEventId'] = spec['cashDemand']['cashflows'][0]['economic_event_id']
        with self.assertRaises(ValueError): cashfit(spec)

    def test_future_plan_and_duplicate_cash_scope_rejected(self):
        for field, value in [('availableAt', '2026-10-13T10:00:00+08:00'), ('scope', 'already-in-baseline')]:
            spec = draft('cashfit'); spec['rebalanceCashNeeds'][0][field] = value
            with self.assertRaises(ValueError): cashfit(spec)


class DiagnosticTests(unittest.TestCase):
    def test_missing_horizon_no_interpolation(self):
        result = decay(draft('decay'))
        self.assertEqual(len(result['decayCurve']), 3)
        self.assertIsNone(result['decayCurve'][-1]['meanGrossSpread'])

    def test_nonpositive_is_sample_observation_not_expiry(self):
        spec = draft('decay')
        for draft_ in spec['panels'].values():
            for row in draft_['rows']: row['forwardReturn'] = -row['factor'] / 100
        result = decay(spec)
        self.assertEqual(result['nonPositiveSpreadHorizonsInSample'], [1, 5])
        self.assertNotIn('expiry', result)

    def test_wrong_horizon_and_definition_rejected(self):
        spec = draft('decay'); spec['panels']['1']['rows'][0]['returnEndAt'] = '2026-01-10T15:00:00+08:00'
        with self.assertRaises(ValueError): decay(spec)
        spec = draft('decay'); spec['panels']['1']['factorVersion'] = '2'
        with self.assertRaises(ValueError): decay(spec)

    def test_ic_stability_missing_and_zero_breaks(self):
        result = stability(draft('stability'))['groups'][0]
        self.assertEqual(result['observations'], 5)
        self.assertEqual(result['positiveShare'], .4)
        self.assertEqual(result['signFlips'], 1)
        self.assertEqual(result['longestNonPositiveRunRecords'], 2)
        self.assertAlmostEqual(result['cumulativeICPathFall'], .3)

    def test_sample_threshold_and_out_of_range(self):
        spec = draft('stability'); spec['records'] = spec['records'][:2]
        self.assertIsNone(stability(spec)['groups'][0]['positiveShare'])
        spec['records'][0]['IC'] = 1.1
        with self.assertRaises(ValueError): stability(spec)

    def test_unsorted_duplicate_or_future_records_rejected(self):
        for action in ('reverse', 'duplicate', 'future'):
            spec = draft('stability')
            if action == 'reverse': spec['records'].reverse()
            elif action == 'duplicate': spec['records'].append(spec['records'][0])
            else: spec['records'][0]['availableAt'] = '2026-04-01T10:00:00+08:00'
            with self.assertRaises(ValueError): stability(spec)


class BudgetTests(unittest.TestCase):
    def test_bridge_not_model_completed(self):
        result = budget(draft('budget'))
        self.assertEqual(result['status'], 'bridge_only')
        self.assertIsNone(result['budgetResult'])
        self.assertEqual(result['bridge']['simulationCosts'], 0)

    def test_unknown_cost_stops_budget(self):
        spec = draft('budget'); del spec['account']['costBps']
        result = budget(spec)
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['budgetResult'])


class LightEntryTests(unittest.TestCase):
    def run_light(self, code, directory):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'CODEX', 'RESEARCH_WORKBENCH', 'PORTFOLIO'))}
        env.update(PYTHONPATH=str(ROOT / 'src'), HOME=directory, USERPROFILE=directory, PYTHONIOENCODING='utf-8')
        return subprocess.run([sys.executable, '-S', '-c', code], cwd=directory, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)

    def test_all_base_commands_without_dependencies_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            for action in ('series', 'exposure', 'cost', 'cashfit', 'decay', 'stability', 'budget'):
                with self.subTest(action=action):
                    args = ['factor', action, '--input', str(ROOT / 'examples/factor-review' / (action + '.json')), '--out-dir', str(Path(tmp) / action)]
                    code = 'import socket; socket.socket.connect=lambda *a: (_ for _ in ()).throw(AssertionError("network")); from portfolio_engine.__main__ import main; raise SystemExit(main(' + repr(args) + '))'
                    result = self.run_light(code, tmp)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue((Path(tmp) / action / 'report.html').is_file())

    def test_missing_analysis_friendly_consistent_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = ['factor', 'multi', '--input', str(ROOT / 'examples/factor-review/multi.json'), '--out-dir', str(Path(tmp) / 'multi')]
            result = self.run_light('from portfolio_engine.__main__ import main; raise SystemExit(main(' + repr(args) + '))', tmp)
            self.assertEqual(result.returncode, 2)
            self.assertIn('analysis', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse((Path(tmp) / 'multi').exists())


if __name__ == '__main__': unittest.main()
