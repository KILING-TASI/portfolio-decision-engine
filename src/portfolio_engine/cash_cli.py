# SPDX-License-Identifier: MIT
"""Independent stdlib CLI for migrated cash scenarios."""
import argparse, hashlib, json, sys
from pathlib import Path
from .cash_scenario_validation import load_json
def main(argv=None):
    p=argparse.ArgumentParser(description='定投与退出现金流研究；不联网、不交易')
    p.add_argument('command',choices=['scheduled-cash','exit-cash'])
    p.add_argument('--input',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        if a.out_dir.exists():raise ValueError('输出目录已存在，历史结果不覆盖')
        if not a.input.is_file() or a.input.is_symlink() or a.input.stat().st_size>16*1024*1024:raise ValueError('需要不超过16MiB的普通JSON输入')
        spec=load_json(a.input.read_text('utf-8-sig'))
        if a.command=='scheduled-cash':
            from .scheduled_cash import calculate
        else:
            from .exit_cash import exit_cash as calculate
        result=calculate(spec)
        result_bytes=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
        input_bytes=json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
        a.out_dir.mkdir(parents=True)
        (a.out_dir/'input.json').write_bytes(input_bytes);(a.out_dir/'result.json').write_bytes(result_bytes)
        (a.out_dir/'receipt.json').write_text(json.dumps({'methodVersion':'workbench-preserved-cash/1','files':{'input.json':hashlib.sha256(input_bytes).hexdigest(),'result.json':hashlib.sha256(result_bytes).hexdigest()},'scope':'原计算兼容；输入完整性声明不等于原文或实际成交核验'},ensure_ascii=False,indent=2),'utf-8')
        print('已完成现金流研究：'+str(a.out_dir/'result.json'));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('未完成：'+str(exc)+'。请核对日期、费用及输入完整性。',file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
