# SPDX-License-Identifier: MIT
"""Preserved validation for workbench scheduled/exit cash migration, stdlib only."""
import datetime as dt, hashlib, json, math
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
def unique_pairs(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('JSON出现重复字段：'+key)
  result[key]=value
 return result

def reject_constant(value):raise ValueError('JSON包含非有限数值：'+value)

def finite_json_float(token):
 value=float(token)
 if not math.isfinite(value):raise ValueError('JSON浮点数超出有限范围：'+token)
 return value

def load_json(text):
 return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def date_value(x):
 if not isinstance(x,str):raise ValueError("日期须为YYYY-MM-DD文字")
 try:parsed=dt.date.fromisoformat(x)
 except ValueError as exc:raise ValueError("日期须为YYYY-MM-DD文字") from exc
 if parsed.isoformat()!=x:raise ValueError("日期须为YYYY-MM-DD文字")
 return x

def number(x):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('需有限数值')
 return float(x)

def value(x,asof):
 if not isinstance(x,dict) or x.get('basis') not in ['source-statement','calculation','assumption']:raise ValueError('输入需明确来源陈述或假设')
 v=number(x['value'])
 if not isinstance(x.get('note'),str) or not x['note'].strip():raise ValueError('需说明参数含义或假设依据')
 if x['basis']!='assumption':
  source=x.get('sourceUrl');locator=x.get('locator')
  if not isinstance(source,str) or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in source) or not isinstance(locator,str) or not locator.strip():raise ValueError('来源值需URL和原文定位')
  try:
   u=urlsplit(source);port=u.port
  except ValueError as exc:raise ValueError('来源URL无效') from exc
  if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or port not in (None,443):raise ValueError('来源URL无效')
  published=date_value(x.get('publishedAt'))
  if published>asof:raise ValueError('来源发布日期晚于截止日')
 return v

def numeric_bindings(s):
 """Check declared numeric JSON anchors; this is not PDF original verification."""
 results=[]
 def visit(obj,path):
  if isinstance(obj,dict):
   binding=obj.get('numericBinding')
   if binding is not None:
    if obj.get('basis')=='assumption':raise ValueError('假设不能冒充历史数值绑定')
    candidates=[b for b in s.get('sourceFiles',[]) if b['path']==binding.get('path')]
    if len(candidates)!=1:raise ValueError('字段绑定需唯一已登记来源文件')
    source=Path(binding['path'])
    if source.suffix.lower()!='.json':raise ValueError('数值绑定仅支持JSON底稿；PDF需原文核验流程')
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=candidates[0]['sha256']:raise ValueError('字段来源文件哈希已变化')
    pointer=binding.get('pointer')
    if not isinstance(pointer,str) or not pointer.startswith('/'):raise ValueError('需明确JSON字段路径')
    target=load_json(raw.decode('utf-8-sig'));row_metadata=None
    try:
     for token in pointer[1:].split('/'):
      token=token.replace('~1','/').replace('~0','~')
      target=target[int(token)] if isinstance(target,list) else target[token]
      if isinstance(target,dict) and 'period' in target and 'publishedAt' in target:row_metadata=target
    except (KeyError,IndexError,ValueError,TypeError) as e:raise ValueError('来源数值字段不存在') from e
    if row_metadata is not None:
     for key in ['period','publishedAt']:
      observed=row_metadata[key]
      if not isinstance(observed,str):raise ValueError('绑定底稿行的日期格式无效')
      date_value(observed)
      if observed>s['asOf']:raise ValueError('绑定底稿行的报告期或发布日期晚于研究截止日')
     if obj.get('publishedAt')!=row_metadata['publishedAt']:raise ValueError('输入发布日期与绑定底稿行不一致')
     if obj.get('observationPeriod') is not None and obj['observationPeriod']!=row_metadata['period']:raise ValueError('输入报告期与绑定底稿行不一致')
    scale=number(binding.get('scale',1))
    if scale<=0:raise ValueError('金额缩放系数需为正')
    expected=number(target)*scale;actual=number(obj['value'])
    if not math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-8):raise ValueError('输入数值与来源字段不一致：'+path)
    results.append(dict(inputPath=path,sourcePath=str(source),pointer=pointer,scale=scale,status='numeric-json-anchor-matched',originalVerified=False,boundPeriod=row_metadata.get('period') if row_metadata else None,boundPublishedAt=row_metadata.get('publishedAt') if row_metadata else None))
   for k,v in obj.items():
    if k!='numericBinding':visit(v,path+'/'+k)
  elif isinstance(obj,list):
   for i,v in enumerate(obj):visit(v,path+'/'+str(i))
 visit(s,'')
 return results

def context(s):
 if not isinstance(s,dict):raise ValueError('情景输入须为对象')
 date_value(s['asOf'])
 if not s.get('currency') or not s.get('unit') or not s.get('identity',{}).get('name'):raise ValueError('需公司名称、币种和金额单位')
 for binding in s.get('sourceFiles',[]):
  raw=Path(binding['path']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('输入来源文件哈希已变化')
  if Path(binding['path']).suffix.lower()=='.json':
   data=load_json(raw.decode('utf-8-sig'));code=data.get('code') if isinstance(data,dict) else None
   expected={r['code'] for r in s['companies']} if s.get('companies') else {s['identity'].get('code')}
   if code is not None and len(str(code))==6 and str(code).isdigit() and None not in expected and str(code) not in expected:raise ValueError('来源公司代码与本次对象不一致')
 numeric_bindings(s)
 return s['asOf']

def day(v):
    if not isinstance(v, str) or date.fromisoformat(v).isoformat() != v:
        raise ValueError('日期须为YYYY-MM-DD')
    return v

def num(v, positive=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (positive and v <= 0):
        raise ValueError('数值无效')
    return v

def source(v):
    try:u=urlsplit(v) if isinstance(v,str) else None
    except ValueError:u=None
    if u is None or u.scheme not in ['https','http'] or not u.hostname or u.username is not None or u.password is not None:
        raise ValueError('缺来源URL')

NOTICE = '客观历史研究，不构成投资建议；本金可能亏损，历史结果不代表未来。'
