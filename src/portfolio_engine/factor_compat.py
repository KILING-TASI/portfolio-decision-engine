# SPDX-License-Identifier: MIT
"""Explicit standalone-provider selection, with frozen v0.12 fallback."""
import importlib,re,sys

def provider():
    try:package=importlib.import_module('cn_factor_research')
    except ModuleNotFoundError as error:
        if error.name!='cn_factor_research':raise
        return dict(provider='frozen-pde-v0.12',version='0.12.0',reason='独立因子仓未安装')
    version=getattr(package,'__version__',None)
    if not isinstance(version,str) or not re.fullmatch(r'0\.1\.\d+',version):
        return dict(provider='frozen-pde-v0.12',version='0.12.0',reason='已安装因子仓版本尚未通过本兼容入口验证')
    return dict(provider='cn-factor-research',version=version,reason='使用已安装的独立发行包')

def dispatch(kind,args):
    if kind not in ('cnn','pattern'):raise ValueError('此兼容入口只接受cnn/pattern')
    selected=provider()
    if selected['provider']=='cn-factor-research':
        print('研究入口已转交独立量化因子仓 '+selected['version']+'；PDE继续负责组合条件审查。',file=sys.stderr)
        path='cn_factor_research.'+('cnn_cli' if kind=='cnn' else 'candle_patterns')
    else:
        print(selected['reason']+'；本次使用PDE冻结的v0.12研究兼容实现，不自动安装或读取其他仓库。',file=sys.stderr)
        path='portfolio_engine.'+('cnn_cli' if kind=='cnn' else 'candle_patterns')
    return importlib.import_module(path).main(args)
