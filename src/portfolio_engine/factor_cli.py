# SPDX-License-Identifier: MIT
"""Light dispatch, preserving the historical factor module entry."""
from .review_io import cli


def handlers():
    from .factor_research import panel, trials
    from .factor_series import series, cost
    from .factor_exposure import exposure
    from .factor_cash import cashfit
    from .factor_diagnostics import decay, stability
    from .factor_advanced import budget, multi
    return {'panel': panel, 'trials': trials, 'series': series, 'exposure': exposure,
            'cost': cost, 'cashfit': cashfit, 'decay': decay, 'stability': stability,
            'budget': budget, 'multi': multi}


def main(argv=None):
    import sys
    old = sys.argv[:]
    try:
        if argv is not None:
            sys.argv = ['portfolio-decision-engine factor', *argv]
        try:
            return cli(handlers(), '因子进入组合前的条件审查')
        except ModuleNotFoundError as error:
            if (error.name or '').split('.')[0] not in {'numpy', 'pandas', 'scipy', 'sklearn', 'statsmodels'}:
                raise
            print('未完成：此计算需要 analysis 可选组件。请安装 portfolio-decision-engine[analysis]；基础因子动作和 budget 的 compute=false 导出只需标准库。不会自动安装。', file=sys.stderr)
            return 2
    finally:
        sys.argv[:] = old
