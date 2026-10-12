"""Installed user entry. Native computations and frozen outputs stay unchanged."""
import argparse
import runpy
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

REPO = 'portfolio-decision-engine'
PACKAGE = 'portfolio_engine'
SOURCE_DEPTH = 2
MODE = 'module'
SCRIPT = 'portfolio_engine'
OUTPUT_FLAG = '--out'
REPORT_FILE = 'report.html'

def resources():
    bundled = Path(__file__).resolve().parent / '_skill'
    if bundled.is_dir():
        return bundled
    source = Path(__file__).resolve().parents[SOURCE_DEPTH]
    if (source / 'README.md').is_file():
        return source
    shared = Path(sys.prefix) / 'share' / REPO
    if shared.is_dir():
        return shared
    raise ValueError('缺少教学资源；请重新安装完整 wheel，或在完整源码目录安装。')

def fresh_name(path):
    """Select a new sibling; the native atomic/no-overwrite writer still owns it."""
    path = Path(path)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    for _ in range(20):
        suffix = '-' + stamp + '-' + uuid4().hex[:8]
        candidate = path.with_name(path.stem + suffix + path.suffix)
        if not candidate.exists():
            return candidate
    raise FileExistsError('无法选择新输出名，请换一个目录后重试。')

def native(root, args, selected=None):
    old_argv, old_path, old_bytecode = sys.argv[:], sys.path[:], sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.argv = [REPO, *args]
    try:
        if MODE == 'script':
            sys.path[:0] = [str(root / 'scripts'), str(root)]
            runpy.run_path(str(root / (selected or SCRIPT)), run_name='__main__')
        else:
            runpy.run_module(SCRIPT, run_name='__main__')
        return 0
    except SystemExit as error:
        if isinstance(error.code, int) or error.code is None:
            return error.code or 0
        print(str(error.code), file=sys.stderr)
        return 2
    finally:
        sys.argv[:] = old_argv
        sys.path[:] = old_path
        sys.dont_write_bytecode = old_bytecode

def doctor(args):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream, "reconfigure"):stream.reconfigure(encoding="utf-8")
    import json,importlib.util,importlib.metadata,platform
    parser=argparse.ArgumentParser(description='仅检查本仓软件环境；不联网、不检查数据或安装组件')
    parser.add_argument('--json',action='store_true');options=parser.parse_args(args)
    try:version=importlib.metadata.version(REPO)
    except importlib.metadata.PackageNotFoundError:version='source-checkout; see pyproject.toml'
    analysis={name:importlib.util.find_spec(name) is not None for name in ('numpy','pandas','scipy','sklearn','statsmodels')} if REPO=='portfolio-decision-engine' else {}
    minimum=(3,11) if REPO=='research-workbench' else (3,10)
    ready=sys.version_info>=minimum
    try:root=str(resources())
    except ValueError:root=None;ready=False
    result=dict(status='environment-ready' if ready else 'environment-blocked',repo=REPO,version=version,python=platform.python_version(),teachingReady=ready,analysisComponents=analysis,resourceDirectory=root,dataChecked=False,sourceVerified=False,filesWritten=False,networkAccess=False,nextSteps=['运行 demo --out-dir 新目录 --auto-name 查看教学结果；教学不是实际研究。'])
    if analysis and not all(analysis.values()):result['nextSteps'].append('轻量金额与现金路径可用；完整历史分析请安装 .[analysis]，不会自动安装。')
    if not ready:result['nextSteps']=['核对Python版本与完整源码或wheel资源，按README处理。']
    if options.json:print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print('软件环境可运行教学' if ready else '软件环境尚未就绪')
        for step in result['nextSteps']:print('下一步：'+step)
        print('本检查不代表取得或核验了研究数据。')
    return 0 if ready else 2

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "doctor":return doctor(args[1:])
    if not args or args in [['--help'], ['-h']]:
        print(REPO + '：独立研究工具。')
        print('教学试用：' + REPO + ' demo --out-dir reports/demo --auto-name')
        print('原生入口：' + REPO + ' run --help（原有参数与计算口径保留）')
        print('因子审查：' + REPO + ' factor --help；基础动作只需标准库。')
        print('CNN研究：' + REPO + ' cnn --help；训练、预测需 [cnn]，输入校验只需标准库。')
        print('K线形态：' + REPO + ' pattern --help；识别/统计只需标准库，cnn compare 用可选组件对照。')
        print('因子研究以独立 cn-factor-research 为维护入口；本仓保留冻结兼容实现，不自动安装。')
        if MODE == 'script':
            print('其他专题：' + REPO + ' script --help 查看已安装的脚本入口。')
        print('--auto-name 另选新输出名，保留旧文件；不会安装依赖或联网取数。')
        return 0
    try:
        if args[0] == 'demo':
            parser = argparse.ArgumentParser(prog=REPO + ' demo', description='教学输入；不是实际行情或账户。')
            parser.add_argument('--out-dir', default='reports/demo', type=Path)
            parser.add_argument('--auto-name', action='store_true')
            options = parser.parse_args(args[1:])
            output = fresh_name(options.out_dir) if options.auto_name else options.out_dir
            if output.exists():
                raise FileExistsError('输出目录已存在。请换一个新名字，或加 --auto-name；旧结果未覆盖。')
            root = resources()
            if REPO == 'marketlens':
                forwarded = ['demo', '--db', str(output / 'teaching.sqlite3'), '--out-dir', str(output), '--human']
            elif REPO == 'cn-fund-lookthrough' or REPO == 'cn-financial-reconcile':
                forwarded = [str(root / 'examples/demo.json'), '--format', 'html', '--out', str(output / 'report.html')]
            elif REPO == 'convertible-bond-engine':
                forwarded = [str(root / 'examples/demo.json'), '--out-dir', str(output)]
            elif REPO == 'bjx-ipo-engine':
                forwarded = ['scenarios', str(root / 'examples/scenarios.json'), '--out-dir', str(output)]
            elif REPO == 'portfolio-decision-engine':
                from importlib.util import find_spec
                complete=all(find_spec(name) is not None for name in ('numpy','pandas','scipy','sklearn','statsmodels'))
                forwarded = ['demo', '--fast', '--out', str(output)] if complete else ['light-demo', '--out-dir', str(output)]
                if not complete:
                    print('使用轻量教学：仅金额敞口，不运行历史风险或优化；完整分析可安装 .[analysis]。',file=sys.stderr)
            elif REPO == 'research-workbench':
                forwarded = ['demo', '--out-dir', str(output)]
            else:
                forwarded = [OUTPUT_FLAG, str(output)]
            result = native(root, forwarded)
            if result == 0 and REPORT_FILE and (output / REPORT_FILE).is_file():
                print('请打开：' + str((output / REPORT_FILE).resolve()) + '；本次使用教学输入。', file=sys.stderr)
            return result
        selected = None
        if args[0] == 'script':
            if MODE != 'script':
                raise ValueError('本仓用 run 调用原生模块参数；请运行 ' + REPO + ' run --help。')
            root = resources()
            scripts = {p.stem: 'scripts/' + p.name for p in (root / 'scripts').glob('*.py')
                       if not p.name.startswith(('_','test_','build_','check_','verify_','audit_'))}
            if len(args) == 1 or args[1] in {'--help','-h'}:
                print('用法：' + REPO + ' script 脚本名 原参数\n可用入口：' + '、'.join(sorted(scripts)))
                return 0
            if args[1] not in scripts:
                raise ValueError('未知脚本名；用 script --help 查看入口，不接受文件路径。')
            selected = scripts[args[1]]
            args = args[2:]
        elif args[0] == 'run':
            args.pop(0)
        if '--auto-name' in args:
            args.remove('--auto-name')
            choices = list(dict.fromkeys([OUTPUT_FLAG, '--out-dir', '--output-dir', '--out', '--output']))
            positions = [(i, flag) for i, value in enumerate(args) for flag in choices if value == flag or value.startswith(flag + '=')]
            if len(positions) != 1:
                raise ValueError('--auto-name 需要一个明确的输出参数；不改输入、数据库或历史记录。')
            index, flag = positions[0]
            if args[index].startswith(flag + '='):
                output = args[index].split('=', 1)[1]
                if not output: raise ValueError('输出路径不能为空。')
                target = fresh_name(output)
                args[index] = flag + '=' + str(target)
            else:
                if index + 1 >= len(args) or args[index + 1].startswith('--'):
                    raise ValueError('输出参数缺少路径。')
                target = fresh_name(args[index + 1])
                args[index + 1] = str(target)
            print('本次新输出：' + str(target.resolve()), file=sys.stderr)
        return native(resources() if MODE == 'script' else None, args, selected)
    except ModuleNotFoundError as error:
        if (error.name or '').split('.')[0] not in {'numpy','pandas','scipy','sklearn','statsmodels','joblib','dateutil','patsy','pdfplumber','pypdf'}:
            raise
        print('缺少运行依赖。请在完整源码目录执行 python -m pip install .，或安装对应 wheel。组合完整分析用 .[analysis]；PDF 功能按 README 的可选依赖步骤安装。', file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(str(error)+'\n下一步：核对本仓 run --help 与输入示例，使用新输出路径；可用 doctor 检查软件环境。', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
