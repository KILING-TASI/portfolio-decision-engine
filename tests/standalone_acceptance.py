"""Single-wheel process/directory acceptance; does not claim a fresh OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    wheel = root / Path(args.wheel).name
    shutil.copyfile(args.wheel, wheel)
    home = root / "empty-user"
    home.mkdir()
    (root / "temp").mkdir()
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("PYTHON", "RESEARCH_WORKBENCH_")) or any(
            token in key for token in ("CODEX", "WORKBUDDY", "PORTFOLIO", "LOOKTHROUGH", "FINANCIAL")
        ) or key in {"PIP_TARGET", "PIP_PREFIX", "PIP_USER"}:
            env.pop(key, None)
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "appdata"),
               LOCALAPPDATA=str(home / "localappdata"), XDG_CACHE_HOME=str(home / "cache"),
               PIP_CACHE_DIR=str(home / "pip-cache"), PIP_CONFIG_FILE=os.devnull,
               TEMP=str(root / "temp"), TMP=str(root / "temp"), TMPDIR=str(root / "temp"))
    commands = []
    def run(arguments, expected=0):
        completed = subprocess.run(arguments, cwd=root, env=env, capture_output=True)
        index = len(commands)
        (root / f"command-{index}.stdout").write_bytes(completed.stdout)
        (root / f"command-{index}.stderr").write_bytes(completed.stderr)
        commands.append({"argv": arguments, "returncode": completed.returncode,
                         "expected": expected})
        assert completed.returncode == expected, completed.stderr[-2000:]
        return completed.stdout
    run([sys.executable, "-m", "venv", str(root / "venv")])
    py = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(py), "-m", "pip", "install", "--no-cache-dir", str(wheel)])
    probe = r'''
import sys,json,pathlib,importlib.util,importlib.metadata
import portfolio_engine.cli
root=pathlib.Path(sys.argv[1]).resolve();base=pathlib.Path(sys.base_prefix).resolve()
origins={n:str(pathlib.Path(m.__file__).resolve()) for n,m in sys.modules.items() if getattr(m,'__file__',None) and not str(m.__file__).startswith('<')}
def allowed(value):
 p=pathlib.Path(value).resolve()
 return p.is_relative_to(root) or (p.is_relative_to(base) and 'site-packages' not in p.parts)
assert all(allowed(p) for p in sys.path if p)
assert all(allowed(p) for p in origins.values())
assert pathlib.Path(portfolio_engine.cli.__file__).resolve().is_relative_to(root/'venv')
assert all(importlib.util.find_spec(n) is None for n in ['cnlookthrough','cnreconcile','research_workbench','pytest','build'])
print(json.dumps({'sys_path':sys.path,'module_origins':origins,'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'self_repositories_and_dev_dependencies_absent':True}))
'''
    origin = json.loads(run([str(py), "-I", "-c", probe, str(root)]))
    demo = root / "demo"
    # Run the unchanged -m entry via runpy to inspect origins after computation,
    # not just at import time. argv and CLI workflow are identical to README.
    launch = r'''
import runpy,sys,json,pathlib
root=pathlib.Path(sys.argv.pop(1)).resolve()
sys.argv=['portfolio_engine',*sys.argv[1:]]
try:runpy.run_module('portfolio_engine',run_name='__main__')
except SystemExit as e:assert e.code==0,e.code
base=pathlib.Path(sys.base_prefix).resolve()
origins={n:str(pathlib.Path(m.__file__).resolve()) for n,m in sys.modules.items() if getattr(m,'__file__',None) and not str(m.__file__).startswith('<')}
def allowed(value):
 p=pathlib.Path(value).resolve()
 return p.is_relative_to(root) or (p.is_relative_to(base) and 'site-packages' not in p.parts)
assert all(allowed(p) for p in origins.values())
assert all(allowed(p) for p in sys.path if p)
(root/'post-demo-origins.json').write_text(json.dumps({'sys_path':sys.path,'module_origins':origins},indent=2),encoding='utf8')
'''
    run([str(py), "-I", "-c", launch, str(root), "demo", "--fast", "--out", str(demo)])
    verified = json.loads(run([str(py), "-I", "-m", "portfolio_engine", "verify", str(demo)]))
    assert verified["status"] == "stored_content_verified"
    report = json.loads((demo / "report.json").read_text("utf8"))
    assert report["inputs"]["data"]["return_type"] == "synthetic_total_return"
    assert report["provenance"]["seed"] == 42 and report["engine_version"] == "0.7.0"
    exposure = report["supplemental"]["lookthrough"]
    assert abs(exposure["unknown_weight"] - .14) < 1e-12
    assert abs(exposure["known_weight"] + exposure["unknown_weight"] - 1) < 1e-12
    html = (demo / "report.html").read_text("utf8")
    for link in re.findall(r'href="([^"]+)"', html):
        if not link.startswith(("http:", "https:", "#")):
            assert (demo / link).is_file(), link
    previous = hashlib.sha256((demo / "report.json").read_bytes()).hexdigest()
    run([str(py), "-I", "-m", "portfolio_engine", "demo", "--fast", "--out", str(demo)], 2)
    assert hashlib.sha256((demo / "report.json").read_bytes()).hexdigest() == previous
    config = json.loads((demo / "source-config.json").read_text("utf8"))
    for field in ["factor_csv", "orders_csv", "premium_file"]:
        config[field] = str(demo / "inputs" / config[field])
    config["lookthrough_file"] = "missing-optional-disclosure.json"
    bad = root / "missing-input-config.json"
    bad.write_text(json.dumps(config), encoding="utf8")
    run([str(py), "-I", "-m", "portfolio_engine", "run", "--returns", str(demo / "source-input.csv"),
         "--config", str(bad), "--out", str(root / "failed")], 2)
    assert json.loads((root / "failed/failure.json").read_text("utf8"))["status"] == "blocked"
    result = {"status": "independent_passed_for_synthetic_minimum", "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
              "environment": "isolated directory, new venv and child HOME/cache; host still contains other repos",
              "commands": commands, "origin_probe": origin,
              "post_workflow_origins": json.loads((root / "post-demo-origins.json").read_text("utf8")),
              "expected_unknown_weight": .14,
              "report_integrity": verified, "report_links": "passed", "teaching_not_market_coverage": True,
              "failures": ["existing output refused without overwrite", "missing requested optional input blocked"],
              "optional_dependencies": "dev pytest/build absent; no other self-repository required",
              "release_scope": "pending wheel tested; old Release runtime not tested this batch",
              "visual_and_natural_language_discovery": "not verified"}
    (root / "acceptance.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps({"status": result["status"], "output": str(root)}))


if __name__ == "__main__":
    main()
