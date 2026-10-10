# SPDX-License-Identifier: MIT
import argparse
import sys
import json
from pathlib import Path
import tempfile
import os
import shutil
from html import escape
from ._contract import loads, canonical, digest, validate
from .nav import fetch, parse, from_native, replay, MAX_BYTES

def read(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError('输入缺失、为符号链接或超过16MiB')
    return path.read_bytes()

def publish(result, output, *, raw=None, native=None):
    validate(result)
    out = Path(output).absolute()
    if out.exists() or out.is_symlink(): raise ValueError('输出必须为新目录，旧资料不覆盖')
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.nav-stage-', dir=out.parent))
    try:
        (stage/'snapshot.json').write_bytes(canonical(result))
        (stage/'request.json').write_bytes(canonical(result['request']))
        if raw is not None: (stage/'response.txt').write_bytes(raw)
        if native is not None: (stage/'native-input.json').write_bytes(native)
        rows = ''.join('<tr><td>'+escape(r['date'])+'</td><td>'+escape(r['unit_nav'])+'</td><td>'+escape(r['distribution_text'])+'</td></tr>' for r in result['data'])
        gaps = ''.join('<li>'+escape(gap)+'</li>' for gap in result['unknown'])
        html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>基金净值资料</title><style>body{max-width:1000px;margin:32px auto;padding:0 20px;font:17px/1.7 system-ui}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}.table{overflow-x:auto}</style><h1>基金净值资料</h1><p>代码 '+escape(result['request']['fundCode'])+'；状态 '+escape(result['status'])+'。标准化成功不代表来源、分红或完整收益已核验。</p><h2>需要补齐的资料</h2><ul>'+gaps+'</ul><p>来源取得时间：'+escape(str(result['dates']['retrievedAt']))+'；重放时间：'+escape(str(result['dates']['replayedAt']))+'</p><div class="table"><table><tr><th>观察日期</th><th>单位净值（声明CNY/份）</th><th>渠道事件文本（未核）</th></tr>'+rows+'</table></div><p>基金名称与币种仅按本次声明或渠道记录；没有交易、审批或来源鉴真。</p></html>'
        (stage/'report.html').write_text(html, encoding='utf-8')
        manifest = {p.name: digest(p.read_bytes()) for p in stage.iterdir() if p.is_file()}
        (stage/'receipt.json').write_bytes(canonical({'files':manifest,'schemaVersion':result['schemaVersion'],'scope':'字节完整性，不是来源认证'}))
        os.rename(stage, out)
        return out
    finally:
        if stage.exists():
            if not stage.resolve().is_relative_to(out.parent.resolve()):
                raise ValueError('临时目录不在声明输出父目录内，拒绝清理')
            shutil.rmtree(stage)

def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='基金净值标准化采集、原生档案转换与冻结响应重放；默认离线')
    parser.add_argument('command',choices=['collect','normalize','replay','validate','demo'])
    parser.add_argument('--request',type=Path);parser.add_argument('--input',type=Path)
    parser.add_argument('--raw',type=Path);parser.add_argument('--raw-directory',type=Path)
    parser.add_argument('--out-dir',type=Path);parser.add_argument('--online',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.command=='validate':
            if args.input is None: raise ValueError('validate需要--input')
            print(json.dumps(validate(loads(read(args.input).decode('utf-8-sig'))),ensure_ascii=False));return 0
        if args.out_dir is None: raise ValueError('需要--out-dir指定新目录')
        if args.out_dir.exists(): raise ValueError('输出目录已存在，未执行取数或覆盖')
        native_bytes=None;raw=None
        if args.command=='demo':
            from .teaching import build
            result,raw=build()
            print('原创合成教学响应，不是真实基金、行情或收益。')
        elif args.command=='collect':
            if args.request is None: raise ValueError('collect需要--request')
            result,raw=fetch(loads(read(args.request).decode('utf-8-sig')),online=args.online)
        elif args.command=='normalize':
            if args.request is None or args.input is None: raise ValueError('normalize需要--request和--input')
            native_bytes=read(args.input)
            result=from_native(loads(native_bytes.decode('utf-8-sig')),loads(read(args.request).decode('utf-8-sig')),raw_directory=args.raw_directory)
            if result['provenance']['rawBytesAvailable']:
                doc=loads(native_bytes.decode('utf-8-sig'));row=next(r for r in doc['results'] if r.get('code')==result['request']['fundCode'])
                raw=read(args.raw_directory/row['response_file'])
        else:
            if args.input is None or args.raw is None: raise ValueError('replay需要--input和--raw')
            raw=read(args.raw);result=replay(loads(read(args.input).decode('utf-8-sig')),raw)
        out=publish(result,args.out_dir,raw=raw,native=native_bytes)
        print('已保存标准资料与报告：'+str(out/'report.html'))
        print('下一步：核对来源、日历和分红拆分；净值不能直接当完整账户收益。')
        return 2 if result['status']=='failed' else 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('未完成：'+str(exc)+'。下一步：按README核对输入及新输出目录。');return 2

if __name__=='__main__': raise SystemExit(main())
