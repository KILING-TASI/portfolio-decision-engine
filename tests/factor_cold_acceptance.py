# SPDX-License-Identifier: MIT
"""Install one wheel offline, away from source and user caches, and exercise it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheel', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    wheel = root / args.wheel.name
    shutil.copyfile(args.wheel, wheel)
    home = root / 'empty-user'; home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'CODEX', 'RESEARCH_WORKBENCH', 'PORTFOLIO', 'AUTHOR', 'SPECIALIST')) and k not in ('PIP_TARGET', 'PIP_PREFIX', 'PIP_USER')}
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / 'appdata'), LOCALAPPDATA=str(home / 'local'),
               PIP_CONFIG_FILE=os.devnull, PIP_CACHE_DIR=str(home / 'pip-cache'), PYTHONIOENCODING='utf-8')
    records = []

    def run(argv, expected=0):
        started = time.perf_counter()
        result = subprocess.run([str(a) for a in argv], cwd=root, env=env, capture_output=True, timeout=90)
        index = len(records)
        (root / f'command-{index}.stdout').write_bytes(result.stdout)
        (root / f'command-{index}.stderr').write_bytes(result.stderr)
        records.append({'argv': [str(a) for a in argv], 'elapsedSeconds': time.perf_counter() - started,
                        'returncode': result.returncode, 'expected': expected})
        if result.returncode != expected:
            raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
        return result

    run([sys.executable, '-m', 'venv', root / 'venv'])
    scripts = root / 'venv' / ('Scripts' if os.name == 'nt' else 'bin')
    python = scripts / ('python.exe' if os.name == 'nt' else 'python')
    binary = scripts / ('portfolio-decision-engine.exe' if os.name == 'nt' else 'portfolio-decision-engine')
    run([python, '-m', 'pip', 'install', '--no-index', '--no-deps', '--no-cache-dir', wheel])
    probe = """
import importlib.util,json,sys,pathlib,importlib.metadata
import portfolio_engine
from portfolio_engine._entry import resources
missing=['numpy','pandas','scipy','sklearn','statsmodels','research_workbench','pytest']
assert all(importlib.util.find_spec(name) is None for name in missing)
assert pathlib.Path(portfolio_engine.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix))
assert resources().joinpath('FACTOR_REVIEW.md').is_file()
print(json.dumps({'version':importlib.metadata.version('portfolio-decision-engine'),'resources':str(resources()),'optionalAndOtherRepositoriesAbsent':True}))
"""
    installation = json.loads(run([python, '-I', '-c', probe]).stdout)
    resources = Path(installation['resources'])
    guard = """
import socket,sys
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected network'))
socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected network'))
from portfolio_engine._entry import main
raise SystemExit(main(sys.argv[1:]))
"""
    for action in ('series', 'exposure', 'cost', 'cashfit', 'decay', 'stability', 'budget'):
        input_path = resources / 'examples/factor-review' / (action + '.json')
        run([python, '-I', '-c', guard, 'factor', action, '--input', input_path, '--out-dir', root / action])
        result = json.loads((root / action / 'result.json').read_text(encoding='utf-8'))
        assert result['limitations'] and result['inputSha256']
    run([binary, 'factor', '--help'])
    run([binary, 'factor', 'multi', '--input', resources / 'examples/factor-review/multi.json', '--out-dir', root / 'multi'], 2)
    assert not (root / 'multi').exists()
    frozen = hashlib.sha256((root / 'exposure/result.json').read_bytes()).hexdigest()
    run([binary, 'factor', 'exposure', '--input', resources / 'examples/factor-review/exposure.json', '--out-dir', root / 'exposure'], 2)
    assert hashlib.sha256((root / 'exposure/result.json').read_bytes()).hexdigest() == frozen
    run([python, '-I', '-m', 'portfolio_engine.factor_research', 'panel', '--input', resources / 'examples/expansion-teaching/panel.json', '--out-dir', root / 'legacy-panel'])
    receipt = {'installation': installation, 'commands': records, 'baseActionsPassed': 7,
               'offlineWheelInstall': True, 'networkBlockedDuringBaseActions': True,
               'frozenOutputPreserved': True, 'legacyModulePassed': True,
               'wheelSha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
               'scope': '单仓进程、目录和依赖隔离验收；不是全新操作系统或市场数据认证'}
    (root / 'acceptance.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'baseActionsPassed': 7, 'version': installation['version'], 'coldAcceptance': str(root / 'acceptance.json')}))


if __name__ == '__main__': main()
