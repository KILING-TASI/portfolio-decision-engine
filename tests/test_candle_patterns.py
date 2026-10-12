# SPDX-License-Identifier: MIT
import copy,importlib.util,json
from pathlib import Path
import unittest
from portfolio_engine import candle_patterns as p
from portfolio_engine.candle_comparison import compare

ROOT=Path(__file__).resolve().parents[1]
def sample():return json.loads((ROOT/'examples/cnn-teaching/train.json').read_text(encoding='utf-8'))
def bar(o,c,hi=None,lo=None):return dict(open=o,close=c,high=max(o,c)+.05 if hi is None else hi,low=min(o,c)-.05 if lo is None else lo)
def row_with(trio,direction='down'):
    row=copy.deepcopy(sample()['samples'][0]);history=row['history'];length=len(trio)
    prior=[12,11,10] if direction=='down' else [10,11,12] if direction=='up' else [10,10,10]
    for target,value in zip(history[-length-3:-length],prior):target.update(bar(value,value))
    for target,values in zip(history[-length:],trio):target.update(values)
    return row
def codes(row):return p.inspect(row,p.DEFAULTS)['matchedPatterns']

class PatternTests(unittest.TestCase):
    def test_hammer_and_hanging_man(self):
        shape=bar(10,10.5,10.55,8.5)
        self.assertIn('hammer',codes(row_with([shape])))
        self.assertNotIn('hanging_man',codes(row_with([shape])))
        self.assertIn('hanging_man',codes(row_with([shape],'up')))
        self.assertNotIn('hammer',codes(row_with([shape],'flat')))

    def test_upper_shadow(self):
        shape=bar(10,10.5,12,9.95)
        self.assertIn('inverted_hammer',codes(row_with([shape])))
        self.assertIn('shooting_star',codes(row_with([shape],'up')))

    def test_engulfing(self):
        self.assertIn('bullish_engulfing',codes(row_with([bar(11,10),bar(9.9,11.1)])))
        self.assertIn('bearish_engulfing',codes(row_with([bar(10,11),bar(11.1,9.9)],'up')))
        self.assertNotIn('bullish_engulfing',codes(row_with([bar(11,10),bar(10.2,10.8)])))

    def test_stars_require_gap_and_trend(self):
        shapes=[bar(11,10),bar(9.7,9.75,9.9,9.5),bar(9.8,10.7)]
        self.assertIn('morning_star',codes(row_with(shapes)))
        shapes[1]=bar(10.1,10.15,10.3,9.95)
        self.assertNotIn('morning_star',codes(row_with(shapes)))
        shapes=[bar(10,11),bar(11.3,11.35,11.5,11.1),bar(11.2,10.3)]
        self.assertIn('evening_star',codes(row_with(shapes,'up')))

    def test_three_candles(self):
        self.assertIn('three_white_soldiers',codes(row_with([bar(10,11),bar(10.8,11.8),bar(11.5,12.5)])))
        self.assertIn('three_black_crows',codes(row_with([bar(12,11),bar(11.2,10.2),bar(10.5,9.5)],'up')))

    def test_doji_and_cn_one_price_limit(self):
        self.assertIn('doji',codes(row_with([bar(10,10,11,9)])))
        self.assertEqual(codes(row_with([bar(10,10,10,10)])),[])

    def test_unknown_context(self):
        row=row_with([bar(10,10.5,10.55,8.5)]);row['history']=row['history'][-3:]
        result=p.inspect(row,p.DEFAULTS)
        check=next(x for x in result['checks'] if x['pattern']=='hammer')
        self.assertEqual(check['status'],'context-unknown');self.assertEqual(result['matchedPatterns'],[])

    def test_thresholds(self):
        for params in ({'new':1},{'dojiBodyMax':True},{'smallBodyMax':.05},{'trendRecords':2},{'trendReturnMin':0}):
            with self.subTest(params=params):
                with self.assertRaises(ValueError):p.rules(dict(patternParameters=params))

    def test_threshold_boundary_and_report_bound(self):
        self.assertIn('doji',codes(row_with([bar(14,15,20,10)])))
        self.assertNotIn('doji',codes(row_with([bar(14,15.1,20,10)])))
        s=sample();r=s['samples'][0];s['samples']=[]
        for i in range(1001):
            cloned=copy.deepcopy(r);cloned.update(id=f'bound-{i}',security=f'TEACHING-{i}');s['samples'].append(cloned)
        with self.assertRaises(ValueError):p.identify(s)

    def test_future_and_bad_prices(self):
        for key,value in [('availableAt','2030-01-01T00:00:00+08:00'),('low',1000),('volumeShares',None)]:
            with self.subTest(key=key):
                s=sample();s['samples'][0]['history'][0][key]=value
                with self.assertRaises((ValueError,TypeError)):p.identify(s)

    def test_outcomes_do_not_change_identification(self):
        s=sample();baseline=p.identify(s)['events']
        for row in s['samples']:row['label']['forwardReturn']=999999
        self.assertEqual(baseline,p.identify(s)['events'])

    def test_causal_features(self):
        row=sample()['samples'][0];base=p.feature_channels(row)
        for k in ('open','high','low','close'):row['history'][-1][k]*=2
        changed=p.feature_channels(row)
        self.assertEqual([x[:-1] for x in base],[x[:-1] for x in changed])
        self.assertNotEqual([x[-1] for x in base],[x[-1] for x in changed])

    def study_input(self):
        s=sample();row=row_with([bar(10,10.5,10.55,8.5)]);s['samples']=[row];s['studyHorizons']=[1,5];return s

    def test_statistics_and_missing(self):
        s=self.study_input();s['samples'][0]['label']['forwardReturn']=.02
        result=p.study(s);entry=next(r for r in result['summary'] if r['pattern']=='hammer' and r['horizonRecords']==1)
        self.assertEqual(entry['sampleCount'],1);self.assertEqual(entry['medianGrossReturn'],.02)
        self.assertEqual(entry['positiveReturnFraction'],1);self.assertIsNone(entry['meanBenchmarkExcess'])
        self.assertEqual(entry['executionCounts']['unknown'],1)
        self.assertTrue(any(x['horizonRecords']==5 for x in result['omittedOutcomes']))

    def test_bearish_win_definition(self):
        s=self.study_input();s['samples'][0]=row_with([bar(10,10.5,12,9.95)],'up');s['samples'][0]['label']['forwardReturn']=-.02
        result=p.study(s);entry=next(r for r in result['summary'] if r['pattern']=='shooting_star' and r['horizonRecords']==1)
        self.assertEqual(entry['positiveReturnFraction'],0);self.assertEqual(entry['signalAlignedFraction'],1)

    def test_benchmark_scope(self):
        s=self.study_input();label=s['samples'][0]['label']
        label.update(benchmarkReturn=.01,benchmarkSource='synthetic-benchmark',benchmarkStartAt=label['returnStartAt'],benchmarkEndAt=label['returnEndAt'],benchmarkAvailableAt=label['availableAt'])
        result=p.study(s);entry=next(r for r in result['summary'] if r['pattern']=='hammer' and r['horizonRecords']==1)
        self.assertAlmostEqual(entry['meanBenchmarkExcess'],label['forwardReturn']-.01)
        label['benchmarkEndAt']='2023-01-01T00:00:00+08:00'
        with self.assertRaises(ValueError):p.study(s)

    def test_future_outcome_excluded(self):
        s=self.study_input();s['samples'][0]['label']['availableAt']='2030-01-01T00:00:00+08:00'
        result=p.study(s)
        self.assertEqual(sum(r['sampleCount'] for r in result['summary']),0)
        self.assertTrue(any('截止' in x['reason'] for x in result['omittedOutcomes']))

    def test_duplicate_horizon_and_bad_labels(self):
        s=self.study_input();label=s['samples'][0]['label'];s['samples'][0]['outcomes']=[label,label]
        with self.assertRaises(ValueError):p.study(s)
        s=self.study_input();s['samples'][0]['label']['forwardReturn']=-2
        with self.assertRaises(ValueError):p.study(s)

    def test_cn_execution_does_not_filter_bad_events(self):
        s=self.study_input();s['samples'][0]['cnExecution']=dict(entryTradable=False,exitTradable=None,tPlusOneSatisfied=False,settlementAvailable=None,feesKnown=False)
        result=p.study(s);entry=next(r for r in result['summary'] if r['pattern']=='hammer' and r['horizonRecords']==1)
        self.assertEqual(entry['sampleCount'],1);self.assertEqual(entry['executionCounts']['blocked-or-incomplete'],1)
        s['samples'][0]['cnExecution']['entryTradable']='yes'
        with self.assertRaises(ValueError):p.identify(s)


@unittest.skipUnless(importlib.util.find_spec('torch'),'CNN optional component unavailable')
class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=sample();cls.s['comparisonPlan']='ohlcv-vs-rules-vs-geometry/1';cls.s.pop('folds')
        cls.result=compare(cls.s)

    def test_same_samples_and_no_selected_winner(self):
        f=self.result['folds'][0]
        self.assertIsNone(self.result['selectedWinner'])
        self.assertEqual(f['ohlcvCNN']['model']['sampleIds'],f['geometryCNN']['model']['sampleIds'])
        self.assertEqual([r['id'] for r in f['rules']['scores']],f['sampleIds']['test'])
        self.assertEqual(len(f['geometryCNN']['model']['scaler']['means']),10)

    def test_test_labels_never_fit(self):
        s=copy.deepcopy(self.s);ids=set(self.result['folds'][0]['sampleIds']['test'])
        for row in s['samples']:
            if row['id'] in ids:row['label']['forwardReturn']+=.2
        changed=compare(s)['folds'][0];original=self.result['folds'][0]
        for route in ('ohlcvCNN','geometryCNN'):
            self.assertEqual(original[route]['model']['weights'],changed[route]['model']['weights'])
            self.assertEqual(original[route]['model']['scaler'],changed[route]['model']['scaler'])
        self.assertEqual(original['rules']['trainingOnlyReturnMapping'],changed['rules']['trainingOnlyReturnMapping'])

    def test_plan_and_overlap(self):
        s=copy.deepcopy(self.s);s.pop('comparisonPlan')
        with self.assertRaises(ValueError):compare(s)
        s=copy.deepcopy(self.s);s['folds']=[s['split'],s['split']]
        with self.assertRaises(ValueError):compare(s)

    def test_augmented_model_rejected_by_legacy_predict(self):
        from portfolio_engine.cnn_engine import load_model
        model=self.result['folds'][0]['geometryCNN']['model']
        with self.assertRaises(ValueError):load_model(model,model['fingerprint'])


if __name__=='__main__':unittest.main()
