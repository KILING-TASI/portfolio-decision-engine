# SPDX-License-Identifier: MIT
"""Local CSV format normalization with an explicit column mapping; no guessed source metadata."""
import csv,io,json,hashlib
from ._observations import FIELDS,SCHEMA,validate
from .review_io import cli

def normalize(spec):
    if set(spec)!={'csvText','mapping','constants','asOf','origin'}:raise ValueError('CSV转换需完整原文、列映射、固定元数据、截止和来源类别')
    raw=spec['csvText']
    if not isinstance(raw,str) or len(raw.encode('utf-8'))>16*1024*1024:raise ValueError('CSV输入无效或过大')
    mapping,constants=spec['mapping'],spec['constants']
    if not isinstance(mapping,dict) or not isinstance(constants,dict) or set(mapping)&set(constants) or set(mapping)|set(constants)!=FIELDS:raise ValueError('每个标准字段须由唯一列或明确固定值提供，不能猜缺项')
    reader=csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):raise ValueError('CSV表头缺失或重复')
    if any(not isinstance(v,str) or v not in reader.fieldnames for v in mapping.values()):raise ValueError('映射列不存在')
    rows=[]
    for original in reader:
        if None in original or any(v is None for v in original.values()):raise ValueError('CSV列数与表头不匹配')
        row=dict(constants)
        for key,column in mapping.items():row[key]=original[column]
        rows.append(row)
    result={'schemaVersion':SCHEMA,'asOf':spec['asOf'],'rows':rows,'rawSourceSha256':hashlib.sha256(raw.encode('utf-8')).hexdigest(),'origin':spec['origin']}
    checks=validate(result)
    return {'conclusion':'宏观和微观表按显式映射统一身份、指标、单位、期间与来源；不混同观察、发布、可得和取得时点。','snapshot':result,'validation':checks,'humanRows':[['标准行数',checks['count']],['历史可得时点未知行数',len(checks['historicalAvailabilityUnknownIds'])],['截止后排除行数',len(checks['excludedAfterCutoffIds'])]],'limitations':['本入口只转换提供的CSV，不联网抓全部宏观/行情/财报源','标准单位为明确原单位，未隐式换算、复权、补零或调整季频','原文及元数据依赖声明，摘要不证明源站真实性','统一观察表与净值采集、规则证据信封分别有版本，不覆盖原业务契约']}

if __name__=='__main__':raise SystemExit(cli({'normalize':normalize},'宏观与微观观察表标准化'))
