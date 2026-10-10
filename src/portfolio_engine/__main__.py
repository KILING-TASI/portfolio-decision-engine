"""Native CLI with actionable missing-dependency guidance."""
import sys

def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    args=list(sys.argv[1:] if argv is None else argv)
    if args and args[0]=='doctor':
        from ._entry import doctor
        return doctor(args[1:])
    if not args or args[0] in ('--help','-h'):
        print('轻量入口：account-exposure、cash-demand、convert-lookthrough、verify、light-demo、doctor。')
        print('输出用 --out-dir 新目录，可加 --auto-name 保留旧结果。子命令 --help 查看字段。')
        print('完整历史分析：demo、run、m2-evaluate 等，需安装 .[analysis]；不会自动安装。')
        return 0
    from .light_cli import COMMANDS
    if args and args[0] in COMMANDS:
        from .light_cli import main as light
        return light(args)
    try:
        from .cli import main as run
    except ModuleNotFoundError as error:
        if (error.name or '').split('.')[0] not in {'numpy','pandas','scipy','sklearn','statsmodels','joblib','dateutil','patsy'}:
            raise
        print('缺少完整分析组件。下一步：在源码目录执行 python -m pip install ".[analysis]"，或安装 wheel 的 [analysis] 扩展。金额敞口可用 account-exposure，现金需求可用 cash-demand，教学可用 light-demo；不会自动安装。', file=sys.stderr)
        return 2
    return run(argv)

if __name__ == '__main__':
    raise SystemExit(main())
