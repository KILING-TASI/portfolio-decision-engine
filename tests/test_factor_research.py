import unittest,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from portfolio_engine.factor_research import panel,trials,ranks
class FactorTests(unittest.TestCase):
 def spec(self,n):return json.loads((ROOT/'examples/expansion-teaching'/(n+'.json')).read_text(encoding='utf-8'))
 def test_known_rank_ic(self):
  r=panel(self.spec('panel'));self.assertAlmostEqual(r['meanRankIC'],1);self.assertIsNone(r['nonAnnualizedICIR'])
 def test_average_ties(self):self.assertEqual(ranks([1,1,3]),[1.5,1.5,3])
 def test_lookahead_rejected(self):
  s=self.spec('panel');s['rows'][0]['factorAvailableAt']='2026-01-06T10:00:00+08:00'
  with self.assertRaises(ValueError):panel(s)
 def test_duplicate_rejected(self):
  s=self.spec('panel');s['rows'].append(s['rows'][0])
  with self.assertRaises(ValueError):panel(s)
 def test_constant_factor_unknown(self):
  s=self.spec('panel')
  for r in s['rows']:r['factor']=0
  r=panel(s);self.assertIsNone(r['meanRankIC']);self.assertTrue(r['daily'][0]['emptyGroups'])
 def test_trials_not_probability(self):self.assertIsNone(trials(self.spec('trials'))['DSR'])
 def test_test_selection_leak(self):
  s=self.spec('trials');s['trials'][0]['testTouchedDuringSelection']=True
  with self.assertRaises(ValueError):trials(s)
 def test_label_overlaps_test(self):
  s=self.spec('trials');s['trials'][0]['labelEnd']='2025-08-01'
  with self.assertRaises(ValueError):trials(s)
