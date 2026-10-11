import json,unittest,math
from pathlib import Path
from portfolio_engine.scheduled_cash import calculate
from portfolio_engine.exit_cash import exit_cash

class Tests(unittest.TestCase):
    def compare(self,actual,expected,path=()):
        # Only the libm-dependent root solver may differ at floating-point tails.
        # Cash amounts, dates, schemas, missing values and errors remain exact.
        if path and path[-1]=='xirrPct' and type(actual) in (int,float) and type(expected) in (int,float):
            self.assertTrue(math.isclose(actual,expected,rel_tol=1e-13,abs_tol=1e-10),(path,actual,expected))
        elif isinstance(expected,dict):
            self.assertIsInstance(actual,dict);self.assertEqual(set(actual),set(expected))
            for key in expected:self.compare(actual[key],expected[key],path+(key,))
        elif isinstance(expected,list):
            self.assertIsInstance(actual,list);self.assertEqual(len(actual),len(expected))
            for index,(left,right) in enumerate(zip(actual,expected)):self.compare(left,right,path+(index,))
        else:self.assertEqual(actual,expected,path)

    def test_tolerance_does_not_relax_cash_missing_or_material_rates(self):
        for actual,expected in [({'cash':1.000000000001},{'cash':1}),({'xirrPct':0},{'xirrPct':None}),({'xirrPct':10.000001},{'xirrPct':10})]:
            with self.assertRaises(AssertionError):self.compare(actual,expected)
    def test_old_full_objects_and_failures(self):
        data=json.loads((Path(__file__).parent/'fixtures/cash-migration-vectors.json').read_text('utf-8'))
        for index,vector in enumerate(data['vectors']):
            with self.subTest(index=index,kind=vector['kind']):
                method=calculate if vector['kind']=='scheduled' else exit_cash
                try:out={'result':method(vector['input'])}
                except (ValueError,KeyError,TypeError) as exc:out={'errorType':type(exc).__name__,'error':str(exc)}
                self.compare(json.loads(json.dumps(out)),vector['expected'])
