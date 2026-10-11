import json,unittest
from pathlib import Path
from portfolio_engine.scheduled_cash import calculate
from portfolio_engine.exit_cash import exit_cash

class Tests(unittest.TestCase):
    def test_old_full_objects_and_failures(self):
        data=json.loads((Path(__file__).parent/'fixtures/cash-migration-vectors.json').read_text('utf-8'))
        for index,vector in enumerate(data['vectors']):
            with self.subTest(index=index,kind=vector['kind']):
                method=calculate if vector['kind']=='scheduled' else exit_cash
                try:out={'result':method(vector['input'])}
                except (ValueError,KeyError,TypeError) as exc:out={'errorType':type(exc).__name__,'error':str(exc)}
                self.assertEqual(json.loads(json.dumps(out)),vector['expected'])
