# SPDX-License-Identifier: MIT
"""Explicit tabular observations for macro and micro series, not the rule handoff envelope."""
from datetime import datetime,date
from decimal import Decimal,InvalidOperation
import json,hashlib
SCHEMA='cn-research-observations/1.0'
FIELDS={'id','entity','metric','value','unit','currency','basis','periodStart','periodEnd','observedAt','publishedAt','availableAt','retrievedAt','sourceUrl','sourceVersion','locator','verification'}

def stamp(x):
    if x is None:return None
    d=datetime.fromisoformat(x.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('资料时点须含时区，未知用null')
    return d

def validate(spec):
    if not isinstance(spec,dict) or set(spec)!={'schemaVersion','asOf','rows','rawSourceSha256','origin'} or spec['schemaVersion']!=SCHEMA:raise ValueError('不支持的显式观察表格式')
    cutoff=stamp(spec['asOf'])
    if cutoff is None:raise ValueError('截止时点不可未知')
    sha=spec['rawSourceSha256']
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('需原始观察表字节摘要')
    if spec['origin'] not in {'provided-tabular-bytes','teaching-tabular-bytes'}:raise ValueError('仅本地观察表或教学，不冒充实时采集')
    if not isinstance(spec['rows'],list) or not 1<=len(spec['rows'])<=100000:raise ValueError('观察表需1至100000行')
    seen=set();unknown=[];excluded=[]
    for row in spec['rows']:
        if not isinstance(row,dict) or set(row)!=FIELDS:raise ValueError('观察字段不完整，不能默认日期、单位、口径和来源')
        for k in ('id','entity','metric','unit','basis','sourceUrl','sourceVersion','locator'):
            if not isinstance(row[k],str) or not row[k].strip():raise ValueError('字段不能为空：'+k)
        if row['id'] in seen:raise ValueError('观察ID重复，版本变化须新ID')
        seen.add(row['id'])
        if not row['sourceUrl'].startswith('https://') or row['verification']!='declared-not-original-verified':raise ValueError('本地声明资料不能冒充原文已核')
        if row['currency'] not in (None,'CNY','USD','HKD'):raise ValueError('币种需明确支持币种或非货币null')
        if isinstance(row['value'],bool) or not isinstance(row['value'],str):raise ValueError('数值统一十进制文本，不用浮点隐式改精度')
        try:value=Decimal(row['value'])
        except InvalidOperation as e:raise ValueError('观察数值无效') from e
        if not value.is_finite():raise ValueError('观察数值非有限')
        for key in ('periodStart','periodEnd'):
            if row[key] is not None:
                if not isinstance(row[key],str) or len(row[key])!=10:raise ValueError('期间日期须YYYY-MM-DD或null')
                date.fromisoformat(row[key])
        if row['periodStart'] and row['periodEnd'] and row['periodStart']>row['periodEnd']:raise ValueError('期间倒置')
        times={key:stamp(row[key]) for key in ('observedAt','publishedAt','availableAt','retrievedAt')}
        if times['retrievedAt'] is None:raise ValueError('原取得时点必须提供，不猜可得时点')
        if times['publishedAt'] and times['publishedAt']>times['retrievedAt']:raise ValueError('取得早于声明发布时间')
        if times['availableAt'] and times['publishedAt'] and times['availableAt']<times['publishedAt']:raise ValueError('可得早于发布时间')
        if times['retrievedAt']>cutoff or times['availableAt'] and times['availableAt']>cutoff:excluded.append(row['id'])
        if times['availableAt'] is None:unknown.append(row['id'])
    return {'status':'declared-table-contract-valid','schemaVersion':SCHEMA,'count':len(seen),'excludedAfterCutoffIds':excluded,'historicalAvailabilityUnknownIds':unknown,'sourceVerified':False,'unitConverted':False,'calendarVerified':False}
