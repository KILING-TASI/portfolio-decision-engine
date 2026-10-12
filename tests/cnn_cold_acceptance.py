# SPDX-License-Identifier: MIT
"""Install one wheel in an empty environment; runtime network is disabled."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib,json,os,platform,subprocess,sys,time,venv
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--out',required=True,type=Path);p.add_argument('--cnn',action='store_true');p.add_argument('--dependency-wheelhouse',type=Path);args=p.parse_args()
    wheels=list(Path().glob(args.wheel)) if '*' in args.wheel else [Path(args.wheel)]
    if len(wheels)!=1:raise ValueError('须明确唯一wheel')
    wheel=wheels[0].resolve();out=args.out.resolve()
    if out.exists():raise ValueError('验收目录已存在')
    out.mkdir(parents=True);venv.create(out/'venv',with_pip=True)
    py=out/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    home=out/'empty-user';home.mkdir();work=out/'empty-cwd';work.mkdir()
    env=dict(os.environ,PYTHONUTF8='1',PYTHONNOUSERSITE='1',HOME=str(home),USERPROFILE=str(home))
    env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    records=[]
    def run(arguments,expected=0,network_blocked=True):
        start=time.perf_counter()
        result=subprocess.run([str(py),*arguments],cwd=work,env=env,capture_output=True,text=True,encoding='utf-8',timeout=600)
        row=dict(arguments=arguments,returncode=result.returncode,expected=expected,elapsedSeconds=time.perf_counter()-start,networkBlocked=network_blocked)
        records.append(row);index=len(records)
        (out/f'command-{index}.stdout').write_text(result.stdout,encoding='utf-8');(out/f'command-{index}.stderr').write_text(result.stderr,encoding='utf-8')
        (out/'acceptance.json').write_text(json.dumps(dict(status='running',python=platform.python_version(),platform=platform.platform(),wheelSha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),cnn=args.cnn,commands=records),indent=2),encoding='utf-8')
        if result.returncode!=expected:
            failed=json.loads((out/'acceptance.json').read_text(encoding='utf-8'));failed['status']='failed'
            (out/'acceptance.json').write_text(json.dumps(failed,indent=2),encoding='utf-8')
            raise AssertionError(result.stderr+result.stdout)
        return result.stdout
    if args.cnn:
        install=['-I','-m','pip','install','torch']
        if args.dependency_wheelhouse:install+=['--no-index','--find-links',str(args.dependency_wheelhouse.resolve())]
        else:install+=['--index-url','https://download.pytorch.org/whl/cpu']
        run(install,network_blocked=False)
    run(['-I','-m','pip','install','--no-deps','--no-index',str(wheel)],network_blocked=False)
    prefix="import socket;def_block=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('network disabled'));socket.socket.connect=def_block;socket.socket.connect_ex=def_block;socket.socket.sendto=def_block;socket.create_connection=def_block;"
    def code(statement):return run(['-I','-c',prefix+statement])
    def command(action,input_file,target,expected=0,extra=()):
        argv=['cnn',action,'--input',str(input_file),'--out-dir',str(target),*extra]
        return run(['-I','-c',prefix+'from portfolio_engine._entry import main;raise SystemExit(main())',*argv],expected)
    resources=Path(code("from portfolio_engine._entry import resources;print(resources())").strip())
    source=resources/'examples/cnn-teaching/train.json'
    assert source.is_file() and (resources/'CNN_RESEARCH.md').is_file()
    code("import importlib.util;assert importlib.util.find_spec('pandas') is None;assert importlib.util.find_spec('scipy') is None;assert importlib.util.find_spec('sklearn') is None;assert importlib.util.find_spec('statsmodels') is None")
    command('validate',source,out/'validate')
    command('validate',source,out/'validate',2)
    if not args.cnn:
        command('train',source,out/'missing',2)
        assert not (out/'missing').exists()
    else:
        command('train',source,out/'train');command('walk-forward',source,out/'rolling')
        trained=json.loads((out/'train/result.json').read_text(encoding='utf-8'))
        receipt=code(f"from portfolio_engine.review_io import read,digest;print(digest(read({str(out/'train/receipt.json')!r})))").strip()
        spec=json.loads(source.read_text(encoding='utf-8'));spec['mode']='prediction';spec['samples']=spec['samples'][-4:]
        at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat();spec['asOf']=at
        for row in spec['samples']:row.pop('label');row['signalAt']=at
        prediction=out/'prediction.json';prediction.write_text(json.dumps(spec),encoding='utf-8')
        command('predict',prediction,out/'predict',extra=['--artifact-dir',str(out/'train'),'--receipt-sha256',receipt,'--model-fingerprint',trained['model']['fingerprint']])
        predicted=json.loads((out/'predict/result.json').read_text(encoding='utf-8'))
        end=(datetime.fromisoformat(at)+timedelta(days=1)).isoformat()
        labels=[dict(id=r['id'],security=r['security'],signalAt=at,returnStartAt=at,returnEndAt=end,availableAt=end,forwardReturn=.01*i,horizonRecords=1,source='original-synthetic-teaching') for i,r in enumerate(predicted['scores'])]
        measured=dict(asOf=end,groups=2,labels=labels,**{k:spec[k] for k in ('labelDefinition','returnUnit','horizonRecords','priceBasis')})
        label_file=out/'labels.json';label_file.write_text(json.dumps(measured),encoding='utf-8')
        pred_receipt=code(f"from portfolio_engine.review_io import read,digest;print(digest(read({str(out/'predict/receipt.json')!r})))").strip()
        command('bridge',label_file,out/'bridge',extra=['--artifact-dir',str(out/'predict'),'--receipt-sha256',pred_receipt])
        panel=json.loads((out/'bridge/result.json').read_text(encoding='utf-8'))['panelInput']
        panel_file=out/'panel.json';panel_file.write_text(json.dumps(panel),encoding='utf-8')
        run(['-I','-c',prefix+'from portfolio_engine._entry import main;raise SystemExit(main())','factor','panel','--input',str(panel_file),'--out-dir',str(out/'panel')])
        command('bridge',label_file,out/'blocked-simulation',2,['--artifact-dir',str(out/'train'),'--receipt-sha256',receipt])
        (out/'train/report.html').write_text('tampered',encoding='utf-8')
        command('predict',prediction,out/'blocked-tamper',2,['--artifact-dir',str(out/'train'),'--receipt-sha256',receipt,'--model-fingerprint',trained['model']['fingerprint']])
    record=json.loads((out/'acceptance.json').read_text(encoding='utf-8'));record['status']='passed';record['scope']='single wheel; empty working/user directories; no sibling repositories; runtime socket blocked; synthetic teaching only'
    (out/'acceptance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('独立安装验收通过：'+str(out/'acceptance.json'))


if __name__=='__main__':main()
