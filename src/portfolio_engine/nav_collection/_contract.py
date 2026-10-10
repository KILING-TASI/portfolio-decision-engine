# SPDX-License-Identifier: MIT
"""Fund NAV collection format v1. Frozen bytes, observation dates and provenance differ."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

SCHEMA = 'cn-research-collection/1.0'
METHOD = 'fund-nav-normalization/1.0'

def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out: raise ValueError('重复JSON字段：' + key)
        out[key] = value
    return out

def reject_constant(value):
    raise ValueError('不接受非有限JSON数值：' + value)

def loads(text):
    return json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def day(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期须为YYYY-MM-DD')
    return date.fromisoformat(value)

def instant(value):
    if value is None: return None
    if not isinstance(value, str): raise ValueError('取得时间须为含时区的文本或null')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None: raise ValueError('时间戳必须声明时区')
    return value

def amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('净值须为明确的有限数值')
    try: result = Decimal(str(value))
    except InvalidOperation as exc: raise ValueError('净值数值无效') from exc
    if not result.is_finite() or result <= 0: raise ValueError('净值须大于0且有限')
    text = format(result, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text

def request(value):
    allowed = {'id', 'source', 'fundCode', 'start', 'end', 'asOf', 'currency', 'frequency', 'fields'}
    if not isinstance(value, dict) or set(value) != allowed:
        raise ValueError('请求须完整声明id/source/fundCode/start/end/asOf/currency/frequency/fields')
    if not isinstance(value['id'], str) or not value['id'].strip(): raise ValueError('请求id不能为空')
    if value['source'] != 'eastmoney-fund-nav': raise ValueError('首版只接受eastmoney-fund-nav')
    if not isinstance(value['fundCode'], str) or not re.fullmatch(r'[0-9]{6}', value['fundCode']):
        raise ValueError('基金代码须为六位字符串，不接受数值代码')
    if not day(value['start']) <= day(value['end']) <= day(value['asOf']):
        raise ValueError('区间须满足start <= end <= asOf')
    if value['currency'] != 'CNY' or value['frequency'] != 'daily':
        raise ValueError('首版只接受声明的CNY日度单位净值，币种声明不是原文核验')
    if value['fields'] != ['unit_nav', 'distribution_text']:
        raise ValueError('首版字段为unit_nav和distribution_text；不接受未实现字段')
    return dict(value)

def normalized_rows(rows, req):
    output = []
    for row in rows:
        if not isinstance(row, dict): raise ValueError('净值行须为对象')
        observed = day(row.get('date'))
        value = amount(row.get('nav'))
        text = row.get('distribution_text', row.get('distribution', ''))
        if not isinstance(text, str): raise ValueError('分红拆分原始描述须为文本，不能默认为已核事件')
        if day(req['start']) <= observed <= day(req['end']):
            output.append({'date': row['date'], 'unit_nav': value, 'distribution_text': text})
    days = [row['date'] for row in output]
    if days != sorted(set(days)): raise ValueError('净值日期重复或乱序，不能静默排序去重')
    if not output: raise ValueError('请求区间无有效净值；不能判定没有交易或基金不存在')
    return output

def record(req, rows, *, name=None, retrieved_at=None, raw=None, raw_sha=None,
           source_url=None, snapshot_sha=None, origin='provided-native-archive', failure=None,
           refresh_error=None, replayed_at=None):
    req = request(req)
    if name is not None and (not isinstance(name, str) or not name.strip()): raise ValueError('基金名称无效')
    instant(retrieved_at);instant(replayed_at)
    if raw is not None:
        if not isinstance(raw, bytes): raise ValueError('原始响应必须是字节')
        actual = digest(raw)
        if raw_sha is not None and raw_sha != actual: raise ValueError('原始响应摘要不一致')
        raw_sha = actual
    elif raw_sha is not None and not re.fullmatch(r'[a-f0-9]{64}', raw_sha):
        raise ValueError('原始摘要格式无效')
    data = [] if failure else normalized_rows(rows, req)
    missing = []
    if retrieved_at is None: missing.append('原取得时间未提供')
    if raw is None: missing.append('原始响应字节未提供，不能复查转换')
    if name is None: missing.append('基金名称未提供')
    if failure: missing.append(str(failure))
    if refresh_error: missing.append('刷新失败，仍使用原快照：' + str(refresh_error))
    result = {
        'schemaVersion': SCHEMA, 'normalizationVersion': METHOD, 'request': req,
        'status': 'failed' if failure else 'partial' if refresh_error else 'success',
        'data': data,
        'identity': {'kind': 'fund', 'code': req['fundCode'], 'name': name,
                     'market': None, 'marketMeaning': '基金代码不推断上市交易所', 'verification': 'declared-or-channel-code-matched'},
        'units': {'unit_nav': {'unit': 'CNY-per-unit', 'basis': 'unit-net-asset-value',
                              'currencyVerification': 'declared-not-original-verified'},
                  'distribution_text': {'basis': 'unverified-provider-description'}},
        'dates': {'asOf': req['asOf'], 'retrievedAt': retrieved_at, 'replayedAt': replayed_at,
                  'publishedAt': None, 'availableAt': None, 'verifiedAt': None,
                  'observationTimezone': 'Asia/Shanghai'},
        'provenance': {'channel': 'eastmoney', 'publisher': None, 'sourceUrl': source_url,
                       'rawResponseSha256': raw_sha, 'rawBytesAvailable': raw is not None,
                       'nativeSnapshotSha256': snapshot_sha, 'origin': origin,
                       'authorization': 'not-assessed', 'redistribution': 'not-assessed'},
        'verification': {'fetchStatus': 'failed' if failure else 'not-reexecuted' if origin != 'online-response' else 'received',
                         'sourceVerified': False, 'calendarVerified': False, 'eventsVerified': False,
                         'historicalAvailabilityVerified': False},
        'coverage': {'requestedStart': req['start'], 'requestedEnd': req['end'],
                     'observedStart': data[0]['date'] if data else None,
                     'observedEnd': data[-1]['date'] if data else None,
                     'count': len(data), 'completeness': 'unknown'},
        'unknown': missing + ['当前修订序列不是历史时点冻结资料', '单位净值和渠道分红文本不是完整总回报'],
        'alerts': [{'code': 'COLLECTION_FAILED' if failure else 'COVERAGE_UNVERIFIED',
                    'message': str(failure) if failure else '资料已标准化，来源、日历和事件完整性仍未认证',
                    'nextStep': '复查原始响应和请求，补官方身份、分红拆分与交易日历；失败不填零',
                    'evidence': raw_sha}]
    }
    result['standardizedSha256'] = digest(canonical(result))
    return result

def validate(value):
    if not isinstance(value, dict) or value.get('schemaVersion') != SCHEMA:
        raise ValueError('不支持的采集契约版本')
    expected = value.get('standardizedSha256')
    if expected != digest(canonical({k: v for k, v in value.items() if k != 'standardizedSha256'})):
        raise ValueError('标准化结果摘要不一致')
    req = request(value['request'])
    required={'schemaVersion','normalizationVersion','request','status','data','identity','units','dates','provenance','verification','coverage','unknown','alerts','standardizedSha256'}
    if set(value)!=required or value['normalizationVersion']!=METHOD:raise ValueError('契约字段或转换方法不支持')
    if value['identity'].get('kind')!='fund' or value['identity'].get('market') is not None:raise ValueError('基金身份/交易所口径不支持')
    if value['units']!={'unit_nav':{'unit':'CNY-per-unit','basis':'unit-net-asset-value','currencyVerification':'declared-not-original-verified'},'distribution_text':{'basis':'unverified-provider-description'}}:raise ValueError('净值单位或事件核验口径不支持')
    if value['dates'].get('asOf')!=req['asOf'] or value['dates'].get('observationTimezone')!='Asia/Shanghai':raise ValueError('截止日或观察时区不一致')
    if any(value['dates'].get(k) is not None for k in ('publishedAt','availableAt','verifiedAt')):raise ValueError('首版不接受未实现的历史可得或认证时间')
    if any(value['verification'].get(k) is not False for k in ('sourceVerified','calendarVerified','eventsVerified','historicalAvailabilityVerified')):raise ValueError('首版不认证来源、日历、事件或历史可得性')
    provenance=value['provenance']
    if provenance.get('channel')!='eastmoney' or not isinstance(provenance.get('rawBytesAvailable'),bool):raise ValueError('渠道或原始字节状态无效')
    for key in ('rawResponseSha256','nativeSnapshotSha256'):
        if provenance.get(key) is not None and (not isinstance(provenance[key],str) or not re.fullmatch(r'[a-f0-9]{64}',provenance[key])):raise ValueError('来源摘要格式无效')
    if provenance['rawBytesAvailable'] and provenance.get('rawResponseSha256') is None:raise ValueError('有原始字节须有摘要')
    if value['identity']['code'] != req['fundCode']: raise ValueError('身份与请求不一致')
    if value['status'] not in {'success', 'partial', 'failed'}: raise ValueError('状态无效')
    rows = value['data']
    if value['status'] == 'failed':
        if rows or not value['alerts']: raise ValueError('失败不能带成功数据')
    else:
        check = normalized_rows([{'date': r['date'], 'nav': r['unit_nav'], 'distribution_text': r['distribution_text']} for r in rows], req)
        if check != rows: raise ValueError('标准化数据类型或口径不一致')
    instant(value['dates']['retrievedAt']);instant(value['dates']['replayedAt'])
    if value['coverage']['count'] != len(rows): raise ValueError('覆盖数量与实际数据不符')
    coverage=value['coverage']
    if coverage!={'requestedStart':req['start'],'requestedEnd':req['end'],'observedStart':rows[0]['date'] if rows else None,'observedEnd':rows[-1]['date'] if rows else None,'count':len(rows),'completeness':'unknown'}:raise ValueError('覆盖区间或完整性声明不符')
    return {'status': 'declared-contract-valid', 'sourceVerified': False, 'dataCount': len(rows)}
