# SPDX-License-Identifier: MIT
import copy
import importlib.util
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from portfolio_engine import cnn_contract as c
from portfolio_engine.cnn_cli import bridge,frozen,main
from portfolio_engine.review_io import digest,publish,read

ROOT=Path(__file__).resolve().parents[1]


def sample():return json.loads((ROOT/'examples/cnn-teaching/train.json').read_text(encoding='utf-8'))


class ContractTests(unittest.TestCase):
    def test_valid(self):
        rows,excluded=c.validate(sample());self.assertEqual(len(rows),64);self.assertEqual(excluded,[])

    def test_bad_inputs(self):
        changes=[('volumeBasis','provider-unspecified'),('lookbackRecords',True),('dataKind','real-certified'),
                 ('returnUnit','percent'),('horizonRecords',False),('asOf','2020-01-01T00:00:00+08:00')]
        for key,value in changes:
            with self.subTest(key=key):
                s=sample();s[key]=value
                with self.assertRaises(ValueError):c.validate(s)

    def test_row_attacks(self):
        attacks=[lambda r:r.update(universeAvailableAt='2030-01-01T00:00:00+08:00'),
                 lambda r:r['adjustmentEvidence'].update(availableAt='2030-01-01T00:00:00+08:00'),
                 lambda r:r['history'][0].update(availableAt='2030-01-01T00:00:00+08:00'),
                 lambda r:r['history'][0].update(close=float('nan')),
                 lambda r:r['history'][0].update(volumeShares=-1),
                 lambda r:r['history'][0].update(low=1000),
                 lambda r:r['history'][0].update(open=True),
                 lambda r:r['history'].reverse(),
                 lambda r:r['history'].pop(),
                 lambda r:r['label'].update(returnEndAt=r['signalAt']),
                 lambda r:r['label'].update(horizonRecords=99),
                 lambda r:r['label'].update(forwardReturn=-1.1),
                 lambda r:r.update(signalAt='2024-01-11T16:00:00')]
        for index,attack in enumerate(attacks):
            with self.subTest(attack=index):
                s=sample();attack(s['samples'][0])
                with self.assertRaises(ValueError):c.validate(s)

    def test_duplicate(self):
        s=sample();s['samples'].append(copy.deepcopy(s['samples'][0]))
        with self.assertRaises(ValueError):c.validate(s)

    def test_nonmember_explicit(self):
        s=sample();s['samples'][0]['membershipAtSignal']=None
        rows,excluded=c.validate(s);self.assertEqual(len(rows),63);self.assertEqual(len(excluded),1)

    def test_overlap_and_purge(self):
        s=sample();rows,_=c.validate(s)
        for row in rows[:4]:row['label']['availableAt']=s['split']['validationStart']
        groups,purged=c.splits(s,rows,s['split']);self.assertEqual(len(purged),4)
        self.assertFalse(set(r['id'] for r in groups['train']) & {r['id'] for r in rows[:4]})
        fold=dict(s['split'],validationStart=s['split']['trainEnd'])
        with self.assertRaises(ValueError):c.splits(s,rows,fold)

    def test_parameters_bounds(self):
        for key,value in [('epochs',201),('seed',-1),('learningRate',.2),('epochs',True)]:
            with self.subTest(key=key):
                s=sample();s['parameters'][key]=value
                with self.assertRaises(ValueError):c.parameters(s)

    def test_no_torch_validation(self):
        code="import sys;sys.modules['torch']=None;from portfolio_engine.cnn_contract import validate;import json;validate(json.load(open(sys.argv[1])));from portfolio_engine.cnn_engine import runtime;\ntry: runtime()\nexcept ValueError as e: assert '[cnn]' in str(e)\nelse: raise AssertionError('missing dependency')"
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'examples/cnn-teaching/train.json')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_frozen_integrity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'report';publish(sample(),{'conclusion':'teaching'},out,'test')
            receipt=digest(read(out/'receipt.json'));frozen(out,receipt)
            with self.assertRaises(ValueError):publish(sample(),{},out,'test')
            with self.assertRaises(ValueError):frozen(out,'0'*64)
            (out/'report.html').write_text('modified',encoding='utf-8')
            with self.assertRaises(ValueError):frozen(out,receipt)

    def test_simulation_cannot_bridge(self):
        with self.assertRaises(ValueError):bridge({},dict(availabilityMode='retrospective-simulation'))

    def test_cli_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            args=['validate','--input',str(ROOT/'examples/cnn-teaching/train.json'),'--out-dir',str(Path(temp)/'result')]
            self.assertEqual(main(args),0);self.assertEqual(main(args),2)


@unittest.skipUnless(importlib.util.find_spec('torch'),'CNN optional component not installed')
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from portfolio_engine.cnn_engine import train
        cls.spec=sample();cls.result=train(cls.spec)

    def test_training_and_repeat(self):
        from portfolio_engine.cnn_engine import train
        repeated=train(sample())
        self.assertEqual(self.result['model']['weights'],repeated['model']['weights'])
        self.assertEqual(self.result['scores'],repeated['scores'])
        self.assertFalse(self.result['model']['historicalAvailabilityCertified'])
        self.assertEqual(self.result['baseline']['method'],'training-label-mean-only')
        self.assertIsNone(self.result['baseline']['testMetrics']['meanRankIC'])

    def test_test_labels_do_not_choose_model(self):
        from portfolio_engine.cnn_engine import train
        changed=sample()
        ids=set(self.result['model']['sampleIds']['test'])
        for row in changed['samples']:
            if row['id'] in ids:row['label']['forwardReturn']+=.5
        result=train(changed)
        self.assertEqual(result['model']['weights'],self.result['model']['weights'])
        self.assertEqual(result['model']['selectedEpoch'],self.result['model']['selectedEpoch'])
        self.assertNotEqual(result['testMetrics'],self.result['testMetrics'])

    def test_train_only_scaler(self):
        from portfolio_engine.cnn_engine import train
        changed=sample();ids=set(self.result['model']['sampleIds']['test'])
        for row in changed['samples']:
            if row['id'] in ids:
                for bar in row['history']:bar['volumeShares']*=10000
        result=train(changed)
        self.assertEqual(result['model']['scaler'],self.result['model']['scaler'])
        self.assertEqual(result['model']['weights'],self.result['model']['weights'])

    def test_walk_forward_and_overlap(self):
        from portfolio_engine.cnn_engine import walk_forward
        result=walk_forward(sample());self.assertEqual(len(result['folds']),2)
        self.assertEqual(len(result['scores']),28)
        changed=sample();changed['folds'][1]=changed['folds'][0]
        with self.assertRaises(ValueError):walk_forward(changed)

    def test_model_attacks(self):
        from portfolio_engine.cnn_engine import load_model
        original=self.result['model']
        with self.assertRaises(ValueError):load_model(original,'0'*64)
        for attack in (lambda m:m['weights'].update({'unknown':[1]}),lambda m:m['scaler'].update(targetScale=0),
                       lambda m:m['weights'].update({'0.weight':[1,2]}),lambda m:m.update(architecture='evil')):
            model=copy.deepcopy(original);attack(model)
            model['fingerprint']=digest({k:v for k,v in model.items() if k!='fingerprint'})
            with self.assertRaises(ValueError):load_model(model,model['fingerprint'])

    def prediction_input(self):
        s=sample();s['mode']='prediction';s['samples']=s['samples'][-4:]
        future=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat();s['asOf']=future
        for row in s['samples']:row.pop('label');row['signalAt']=future
        return s

    def test_predict_and_bridge(self):
        from portfolio_engine.cnn_engine import predict
        s=self.prediction_input();model=self.result['model'];result=predict(s,model,model['fingerprint'])
        self.assertEqual(len(result['scores']),4)
        start=s['asOf'];end=(datetime.fromisoformat(start)+timedelta(days=1)).isoformat()
        labels=[dict(id=r['id'],security=r['security'],signalAt=start,forwardReturn=.01*i,
                     returnStartAt=start,returnEndAt=end,availableAt=end,source='synthetic-teaching',
                     horizonRecords=1)
                for i,r in enumerate(result['scores'])]
        bridge_input=dict(asOf=end,groups=2,labels=labels,**{k:s[k] for k in ('labelDefinition','returnUnit','horizonRecords','priceBasis')})
        bridged=bridge(bridge_input,result)
        self.assertEqual(bridged['panelReview']['daily'][0]['count'],4)
        self.assertEqual(bridged['panelInput']['rows'][0]['factorAvailableAt'],result['scoreComputedAt'])
        bridge_input['horizonRecords']=2
        with self.assertRaises(ValueError):bridge(bridge_input,result)

    def test_predict_past_and_labels_and_signature(self):
        from portfolio_engine.cnn_engine import predict
        model=self.result['model']
        s=sample()
        with self.assertRaises(ValueError):predict(s,model,model['fingerprint'])
        for row in s['samples']:row.pop('label')
        with self.assertRaises(ValueError):predict(s,model,model['fingerprint'])
        s=self.prediction_input();s['volumeBasis']='lots'
        with self.assertRaises(ValueError):predict(s,model,model['fingerprint'])

    def test_constant_label(self):
        from portfolio_engine.cnn_engine import train
        s=sample()
        for row in s['samples']:row['label']['forwardReturn']=.01
        with self.assertRaises(ValueError):train(s)

    def test_runtime_state_restored(self):
        import torch
        from portfolio_engine.cnn_engine import train
        threads=torch.get_num_threads();state=torch.random.get_rng_state().clone()
        enabled=torch.are_deterministic_algorithms_enabled();train(sample())
        self.assertEqual(threads,torch.get_num_threads());self.assertTrue(torch.equal(state,torch.random.get_rng_state()))
        self.assertEqual(enabled,torch.are_deterministic_algorithms_enabled())

    def test_embargo_and_sample_bound(self):
        from portfolio_engine.cnn_engine import train,walk_forward
        s=sample();s['parameters']['embargoSeconds']=86400
        result=train(s)
        self.assertGreater(len(result['model']['purged']),0)
        s['parameters']['embargoSeconds']=366*86400
        with self.assertRaises(ValueError):train(s)
        s=sample();s['folds']=s['folds']*7
        with self.assertRaises(ValueError):walk_forward(s)


if __name__=='__main__':unittest.main()
