# SPDX-License-Identifier: MIT
"""A single declared NAV format, accepting raw responses or existing native archives."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import json
import re
from urllib.request import Request, urlopen
from ._contract import request, record, unique, reject_constant, digest, canonical

MAX_BYTES = 16 * 1024 * 1024

def embedded(text, name):
    match = re.search(r'var\s+' + re.escape(name) + r'\s*=\s*', text)
    if not match: raise ValueError('渠道字段缺失：' + name)
    return json.JSONDecoder(object_pairs_hook=unique, parse_constant=reject_constant, parse_float=Decimal).raw_decode(text[match.end():])[0]

def url_for(req):
    req = request(req)
    return 'https://fund.eastmoney.com/pingzhongdata/' + req['fundCode'] + '.js'

def parse(raw, req, *, retrieved_at, origin='provided-response', replayed_at=None):
    req = request(req)
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES: raise ValueError('原始响应无效或超过16MiB')
    text = raw.decode('utf-8-sig')
    if embedded(text, 'fS_code') != req['fundCode']: raise ValueError('渠道基金代码不一致')
    name = embedded(text, 'fS_name')
    values = embedded(text, 'Data_netWorthTrend')
    if not isinstance(values, list) or not values: raise ValueError('渠道净值表缺失或为空')
    rows = []
    for row in values:
        if not isinstance(row, dict): raise ValueError('渠道净值行无效')
        stamp = row.get('x')
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float, Decimal)) or not Decimal(str(stamp)).is_finite() or stamp < 0:
            raise ValueError('渠道净值时间戳无效')
        observed = datetime.fromtimestamp(float(stamp / 1000), timezone(timedelta(hours=8))).date().isoformat()
        rows.append({'date': observed, 'nav': row.get('y'), 'distribution_text': row.get('unitMoney', '')})
    return record(req, rows, name=name, retrieved_at=retrieved_at, raw=raw,
                  source_url=url_for(req), origin=origin, replayed_at=replayed_at)

def fetch(req, *, online=False, fetcher=None):
    req = request(req)
    if online is not True: raise ValueError('采集需明确--online；默认不联网')
    url = url_for(req)
    raw = None; acquired = None
    try:
        if fetcher is None:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/'}), timeout=25) as response:
                raw = response.read(MAX_BYTES + 1)
        else: raw = fetcher(url)
        acquired = datetime.now(timezone.utc).isoformat()
        result = parse(raw, req, retrieved_at=acquired, origin='online-response')
        return result, raw
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        retained = raw if isinstance(raw, bytes) and len(raw) <= MAX_BYTES else None
        return record(req, [], source_url=url, origin='online-response', failure=str(exc),
                      raw=retained, retrieved_at=acquired), retained

def from_native(native, req, *, raw_directory=None):
    req = request(req)
    if not isinstance(native, dict): raise ValueError('原生档案须为对象')
    if native.get('type') == 'research-bundle':
        if not isinstance(native.get('rows'),list) or any(not isinstance(r,dict) for r in native['rows']):raise ValueError('工作台rows须对象列表')
        matches = [r for r in native.get('rows', []) if r.get('kind') == 'fund' and r.get('code') == req['fundCode']]
        if len(matches) != 1: raise ValueError('工作台档案须唯一匹配基金；不支持股票行情冒充净值')
        row = matches[0]
        if native.get('asOf') != req['asOf']: raise ValueError('工作台截止日与标准请求不同')
        if row.get('history') and row.get('historyBasis') != 'nav-with-distributions': raise ValueError('工作台净值口径未知或不支持')
        return record(req, row.get('history', []), name=(row.get('identity') or {}).get('name'),
                      retrieved_at=row.get('retrievedAt'), source_url=row.get('source'),
                      snapshot_sha=digest(canonical(row)), origin='workbench-native',
                      failure=row.get('errors') if not row.get('history') else None,
                      refresh_error=row.get('errors') if row.get('history') else None)
    if native.get('type') == 'portfolio-source-archive':
        if not isinstance(native.get('results'),list) or any(not isinstance(r,dict) or not isinstance(r.get('request',{}),dict) for r in native['results']):raise ValueError('组合results及请求须对象列表')
        matches = [r for r in native.get('results', []) if r.get('code', r.get('request', {}).get('code')) == req['fundCode']]
        if len(matches) != 1: raise ValueError('组合档案须唯一匹配基金')
        row = matches[0]
        if row.get('status') == 'failed':
            return record(req, [], failure=row.get('reason', '原生采集失败'), origin='portfolio-native')
        if row.get('provider') != 'eastmoney_fund_nav' or row.get('basis') != 'nav_with_unverified_events':
            raise ValueError('组合档案不是首版支持的单位净值渠道')
        if (row.get('requested_start'), row.get('requested_end')) != (req['start'], req['end']):
            raise ValueError('组合原请求区间与标准请求不同')
        raw = None
        if raw_directory is not None:
            root = Path(raw_directory).resolve()
            path = root / row.get('response_file', '')
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > MAX_BYTES:
                raise ValueError('原始响应路径越界、缺失或过大')
            raw = path.read_bytes()
        return record(req, row['history'], name=row.get('name'), retrieved_at=row.get('retrieved_at'),
                      raw=raw, raw_sha=row.get('response_sha256'), source_url=row.get('source_url'),
                      snapshot_sha=digest(canonical(row)), origin='portfolio-native')
    raise ValueError('仅接受工作台research-bundle或组合portfolio-source-archive；不自动推断格式')

def replay(snapshot, raw):
    from ._contract import validate
    validate(snapshot)
    if digest(raw) != snapshot['provenance']['rawResponseSha256']:
        raise ValueError('重放响应与原快照不一致，不刷新或覆盖原记录')
    result = parse(raw, snapshot['request'], retrieved_at=snapshot['dates']['retrievedAt'],
                   origin='frozen-response-replay', replayed_at=datetime.now(timezone.utc).isoformat())
    if result['data'] != snapshot['data']: raise ValueError('重放数据不一致，需核对转换版本')
    return result
