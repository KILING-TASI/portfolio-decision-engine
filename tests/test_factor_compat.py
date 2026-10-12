# SPDX-License-Identifier: MIT
import sys,types,unittest
from unittest.mock import patch
from portfolio_engine.factor_compat import provider,dispatch

class CompatibilityTests(unittest.TestCase):
    def test_missing_standalone_falls_back(self):
        with patch.dict(sys.modules,{'cn_factor_research':None}):self.assertEqual(provider()['provider'],'frozen-pde-v0.12')

    def test_unvalidated_version_falls_back(self):
        package=types.ModuleType('cn_factor_research');package.__version__='0.2.0'
        with patch.dict(sys.modules,{'cn_factor_research':package}):self.assertEqual(provider()['provider'],'frozen-pde-v0.12')

    def test_supported_version_delegates(self):
        package=types.ModuleType('cn_factor_research');package.__version__='0.1.0'
        module=types.ModuleType('cn_factor_research.cnn_cli');called=[]
        module.main=lambda args:called.append(args) or 17
        with patch.dict(sys.modules,{'cn_factor_research':package,'cn_factor_research.cnn_cli':module}):
            self.assertEqual(dispatch('cnn',['--help']),17);self.assertEqual(called,[['--help']])

    def test_no_other_command_rerouted(self):
        with self.assertRaises(ValueError):dispatch('account-exposure',[])

if __name__=='__main__':unittest.main()
