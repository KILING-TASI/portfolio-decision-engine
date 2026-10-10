"""Native CLI with actionable missing-dependency guidance."""
import sys

def main(argv=None):
    try:
        from .cli import main as run
    except ModuleNotFoundError as error:
        if (error.name or '').split('.')[0] not in {'numpy','pandas','scipy','sklearn','statsmodels','joblib','dateutil','patsy'}:
            raise
        print('缺少组合计算依赖。请在源码目录执行 python -m pip install .，或安装完整 wheel 并保留依赖安装。首次安装需要下载五个科学计算包；不会自动安装。', file=sys.stderr)
        return 2
    return run(argv)

if __name__ == '__main__':
    raise SystemExit(main())
