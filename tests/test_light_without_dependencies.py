import subprocess,sys,json
from pathlib import Path

def test_no_scientific_imports_and_identical_account_result(tmp_path):
    root=Path(__file__).resolve().parents[1]
    source=root/'examples/account-exposure-demo.json'
    code='''import sys,json,pathlib
sys.path.insert(0,sys.argv[1])
from portfolio_engine.__main__ import main
assert main(['account-exposure','--input',sys.argv[2],'--out-dir',sys.argv[3]])==0
assert not any(n in sys.modules for n in ['numpy','pandas','scipy','sklearn','statsmodels'])
'''
    result=subprocess.run([sys.executable,'-I','-S','-c',code,str(root/'src'),str(source),str(tmp_path/'light')],capture_output=True)
    assert result.returncode==0,result.stderr
    from portfolio_engine.account_exposure import account_exposure
    actual=json.loads((tmp_path/'light/account-exposure.json').read_text(encoding='utf-8'))
    assert actual==account_exposure(json.loads(source.read_text(encoding='utf-8')))

def test_cash_command_and_conversion_need_no_site_packages(tmp_path):
    root=Path(__file__).resolve().parents[1]
    code='''import sys
sys.path.insert(0,sys.argv[1])
from portfolio_engine.__main__ import main
assert main(['cash-demand','--input',sys.argv[2],'--out-dir',sys.argv[3]])==0
assert main(['convert-lookthrough','--input',sys.argv[4],'--out-dir',sys.argv[5]])==0
assert not any(n in sys.modules for n in ['numpy','pandas','scipy','sklearn','statsmodels'])
'''
    result=subprocess.run([sys.executable,'-I','-S','-c',code,str(root/'src'),str(root/'examples/cash-demand-demo.json'),str(tmp_path/'cash'),str(root/'examples/cn-lookthrough-demo.json'),str(tmp_path/'conversion')],capture_output=True)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'cash/cash-demand-report.html').is_file()
    assert (tmp_path/'conversion/conversion-result.json').is_file()
