# SPDX-License-Identifier: MIT
"""Original standalone research report I/O, no mandatory shared installation."""
import argparse,json,hashlib,os,tempfile,shutil,sys
from pathlib import Path
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
from html import escape

def day(value):
    if not isinstance(value,str) or len(value)!=10:raise ValueError('日期须YYYY-MM-DD')
    return date.fromisoformat(value)

def instant(value):
    if not isinstance(value,str):raise ValueError('取得/截止时间须含时区')
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('时间须含时区')
    return d

def number(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float)):raise ValueError('金额须明确有限数值')
    try:n=Decimal(str(value))
    except InvalidOperation as e:raise ValueError('金额无效') from e
    if not n.is_finite():raise ValueError('金额非有限')
    return n

def evidence(row,cutoff):
    if not isinstance(row,dict) or not isinstance(row.get('source'),str) or not row['source'].startswith('https://') or not row.get('locator') or not row.get('sourceVersion'):raise ValueError('资料须明确HTTPS来源、定位及版本')
    published=day(row['publishedDate']);acquired=instant(row['acquiredAt'])
    if published>acquired.astimezone(timezone(timedelta(hours=8))).date():raise ValueError('取得早于发布日期')
    sha=row.get('rawSourceSha256')
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('需原始来源摘要，摘要不认证原文')
    return acquired<=instant(cutoff) and published<=instant(cutoff).astimezone(timezone(timedelta(hours=8))).date()

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()

def pairs(items):
    out={}
    for k,v in items:
        if k in out:raise ValueError('JSON字段重复：'+k)
        out[k]=v
    return out

def read(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>16*1024*1024:raise ValueError('输入不存在、链接或超过16MiB')
    return json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('非有限JSON')))

def render(result,title):
    summary=result.get('conclusion','结果按所填资料范围生成；先核对下方依据与缺口。')
    lines=result.get('humanRows',[])
    table='<table><tr><th>核对项</th><th>本次结果</th></tr>'+''.join('<tr><td>'+escape(str(a))+'</td><td>'+escape(str(b))+'</td></tr>' for a,b in lines)+'</table>' if lines else ''
    gaps='<ul>'+''.join('<li>'+escape(str(s))+'</li>' for s in result.get('limitations',[]))+'</ul>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{max-width:960px;margin:32px auto;padding:0 20px;font:17px/1.7 system-ui;color:#203047}td,th{padding:10px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}table{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin-top:24px}</style><h1>'+escape(title)+'</h1><p>'+escape(summary)+'</p>'+table+'<h2>范围与缺口</h2>'+gaps+'<details><summary>完整输入绑定、结果及依据</summary><pre>'+escape(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))+'</pre></details></html>'

def publish(spec,result,out,title):
    out=Path(out).absolute()
    if out.exists() or out.is_symlink():raise ValueError('输出必须是新目录，历史结果不覆盖')
    out.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.research-',dir=out.parent))
    try:
        result=dict(result,inputSha256=digest(spec),methodVersion=result.get('methodVersion','explicit-research-review/1.0'))
        for name,data in [('input.json',spec),('result.json',result)]: (stage/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (stage/'report.html').write_text(render(result,title),encoding='utf-8')
        (stage/'receipt.json').write_text(json.dumps({'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()},'scope':'文件摘要不是来源认证或审计意见'},ensure_ascii=False,indent=2),encoding='utf-8')
        os.rename(stage,out)
    finally:
        if stage.exists():
            if not stage.resolve().is_relative_to(out.parent.resolve()):raise ValueError('临时目录越界')
            shutil.rmtree(stage)
    return out

def cli(handlers,title):
    for s in (sys.stdout,sys.stderr):
        if hasattr(s,'reconfigure'):s.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=title);p.add_argument('command',choices=list(handlers));p.add_argument('--input',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
    try:
        if a.out_dir.exists():raise ValueError('输出已存在，旧结果保留')
        spec=read(a.input);result=handlers[a.command](spec);out=publish(spec,result,a.out_dir,title)
        print('报告已生成：'+str(out/'report.html'));print('下一步：复查口径、来源和缺口，不能把程序通过当成原文已验证。');return 0
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as e:print('未完成：'+str(e)+'。请补齐资料并使用新目录。',file=sys.stderr);return 2
