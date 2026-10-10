"""Check the installed command away from its source tree and user cache."""
import hashlib,json,os,subprocess,sys,tempfile,sysconfig
from pathlib import Path

REPO='portfolio-decision-engine'

def check():
    binary=Path(sysconfig.get_path('scripts'))/(REPO+'.exe' if os.name=='nt' else REPO)
    with tempfile.TemporaryDirectory(prefix='installed-entry-') as tmp:
        root=Path(tmp);home=root/'empty-home';home.mkdir()
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','RESEARCH_WORKBENCH_','CODEX','PORTFOLIO_'))}
        env.update(HOME=str(home),USERPROFILE=str(home),PYTHONIOENCODING='utf-8')
        def run(args,expected=0):
            result=subprocess.run([str(binary),*args],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=300)
            assert result.returncode==expected,(args,result.stdout,result.stderr)
            return result
        assert '--auto-name' in run(['--help']).stdout
        first=run(['demo','--out-dir','reports/demo'])
        def hashes():
            return {str(p.relative_to(root/'reports/demo')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'reports/demo').rglob('*') if p.is_file()}
        frozen=hashes();assert frozen
        assert '--auto-name' in run(['demo','--out-dir','reports/demo'],2).stderr
        assert hashes()==frozen
        run(['demo','--out-dir','reports/demo','--auto-name'])
        assert len(list((root/'reports').iterdir()))==2 and hashes()==frozen
        if REPO=='portfolio-decision-engine':
            assert '请打开' in first.stderr and '教学' in first.stderr
        print(json.dumps(dict(repo=REPO,installed_demo=True,automatic_new_name=True,old_outputs_unchanged=True,source_working_directory=False)))

if __name__=='__main__':check()
