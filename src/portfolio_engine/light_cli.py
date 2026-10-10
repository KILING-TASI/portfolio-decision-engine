"""Amounts, disclosed exposures and dated cash needs; standard library only."""
import argparse
from pathlib import Path
import shutil
from .archive import atomic_output,manifest,verify,read_json
from .io import write_json
from .validation import InputError

COMMANDS={'account-exposure','cash-demand','convert-lookthrough','verify','light-demo'}

def main(argv):
    parser=argparse.ArgumentParser(description='轻量组合研究：金额、披露敞口与日期现金需求；不计算历史风险或优化')
    parser.add_argument('command',choices=sorted(COMMANDS))
    parser.add_argument('directory',nargs='?')
    parser.add_argument('--input',type=Path)
    parser.add_argument('--out-dir','--out',dest='out',type=Path)
    parser.add_argument('--auto-name',action='store_true')
    parser.add_argument('--as-of');parser.add_argument('--historical',action='store_true')
    outputs=[v for v in argv if v in ('--out','--out-dir') or v.startswith(('--out=','--out-dir='))]
    if len(outputs)>1:parser.error('只能指定一个输出目录参数：--out-dir 或兼容别名 --out')
    a=parser.parse_args(argv)
    try:
        if a.command=='verify':
            if not a.directory or a.out or a.input or a.auto_name:raise InputError('verify 只接受已有结果目录；不会改写报告')
            r=verify(a.directory);import json;print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if r['status']=='stored_content_verified' else 2
        if not a.out or a.directory:raise InputError('请用 --out-dir 指定新输出目录')
        if a.command!='convert-lookthrough' and (a.as_of or a.historical):raise InputError('--as-of 和 --historical 仅用于 convert-lookthrough')
        if a.auto_name:
            from ._entry import fresh_name
            a.out=fresh_name(a.out)
        if a.command=='light-demo':
            if a.input:raise InputError('light-demo 使用教学输入，真实资料请用 account-exposure 或 cash-demand')
            from ._entry import resources
            a.input=resources()/'examples/account-exposure-demo.json'
        if not a.input:raise InputError('需要 --input 指定已整理资料；格式及示例见 README')
        spec=read_json(a.input)
        with atomic_output(a.out) as stage:
            (stage/'source-input.json').write_bytes(a.input.read_bytes())
            if a.command in ('account-exposure','light-demo'):
                from .account_exposure import account_exposure
                from .exposure_report import save_exposure_report
                result=account_exposure(spec);save_exposure_report(spec,result,stage)
                report='exposure-report.html'
                if a.command=='light-demo':
                    shutil.copyfile(stage/report,stage/'report.html');write_json(stage/'report.json',dict(type='light-teaching-demo',result=result,scope='仅披露金额敞口，不运行M1-M7历史风险、统计或优化'))
                    report='report.html'
            elif a.command=='cash-demand':
                from .cash_demand import cash_demand
                from .cash_demand_report import save_cash_demand
                result=cash_demand(spec);save_cash_demand(spec,result,stage);report='cash-demand-report.html'
            else:
                from .lookthrough_adapter import cn_lookthrough_input
                value=cn_lookthrough_input(spec)
                if a.as_of:value['evaluation_as_of']=a.as_of
                value['historical_mode']=a.historical
                from .disclosed_structure import lookthrough
                result=lookthrough(value,research_as_of=a.as_of,historical=a.historical)
                write_json(stage/'lookthrough.json',value);write_json(stage/'conversion-result.json',result);report=None
            manifest(stage)
        print('轻量研究已保存：'+str(a.out.resolve())+'；资料来源和完整性仍需核对。')
        if a.command=='light-demo':print('本次是教学金额敞口；完整收益与优化教学需安装 analysis 组件。')
        if report:print('请打开：'+str((a.out/report).resolve()))
        return 0
    except (InputError,ValueError,KeyError,TypeError,OSError) as e:
        print('未完成轻量研究：'+str(e)+'\n下一步：核对输入口径与示例，使用新输出目录；原报告未覆盖。',file=__import__('sys').stderr)
        if a.out and not a.out.exists():
            with atomic_output(a.out) as stage:
                write_json(stage/'failure.json',dict(status='blocked',reason=str(e),next_step='correct input and choose a new output directory'))
        return 2
