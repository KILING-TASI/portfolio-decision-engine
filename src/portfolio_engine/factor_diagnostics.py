# SPDX-License-Identifier: MIT
"""Descriptive horizons and IC records, without profitability probabilities."""
import statistics
from .factor_contract import finite, identity, stamp, text, status_label
from .factor_research import panel
from .review_io import instant


def decay(spec):
    identity(spec)
    basis = spec.get('horizonBasis')
    if basis not in ('declared-trading-days', 'calendar-days'):
        raise ValueError('须声明持有期按交易日还是自然日')
    horizons = spec['horizons']
    if not isinstance(horizons, list) or not horizons or any(type(h) is not int or h <= 0 for h in horizons) or len(set(horizons)) != len(horizons):
        raise ValueError('持有期须为不重复正整数')
    panels = spec['panels']
    if not isinstance(panels, dict) or set(panels) - {str(h) for h in horizons}:
        raise ValueError('持期底稿须对应声明持期')
    curve = []
    for horizon in horizons:
        draft = panels.get(str(horizon))
        if draft is None:
            curve.append({'horizon': horizon, 'status': 'missing', 'meanRankIC': None, 'meanGrossSpread': None})
            continue
        identity(draft)
        if any(draft[k] != spec[k] for k in ('factorId', 'factorVersion', 'factorDefinition', 'factorSource', 'asOf')):
            raise ValueError('各持期因子定义和截至日须一致')
        if draft.get('horizon') != horizon or draft.get('horizonBasis') != basis:
            raise ValueError('底稿持期声明与外层不一致')
        if basis == 'declared-trading-days':
            text(draft.get('calendarSource'), '交易日历依据')
        else:
            for row in draft['rows']:
                if (instant(row['returnEndAt']).date() - instant(row['returnStartAt']).date()).days != horizon:
                    raise ValueError('自然日窗口与声明持期不一致')
        result = panel(draft)
        spreads = [r['topMinusBottomGrossReturn'] for r in result['daily'] if r['topMinusBottomGrossReturn'] is not None]
        curve.append({'horizon': horizon, 'status': 'descriptive_only', 'meanRankIC': result['meanRankIC'],
                      'meanGrossSpread': statistics.mean(spreads) if spreads else None,
                      'periodCount': len(result['daily']), 'excluded': result['excluded'],
                      'signalDates': [r['signalDate'] for r in result['daily']]})
    return stamp(spec, {'decayCurve': curve, 'nonPositiveSpreadHorizonsInSample': [r['horizon'] for r in curve if r['meanGrossSpread'] is not None and r['meanGrossSpread'] <= 0],
                       'conclusion': '按声明持期描述样本表现；毛价差非正不证明因子永久失效。',
                       'humanRows': [[r['horizon'], status_label(r['status'])] for r in curve],
                       'limitations': ['缺持期不插值或外推；未提供推断方法，不判断与0是否不可辨',
                                       '不同持期可能覆盖不同信号日，应先比较覆盖；交易日历为声明依据，未认证完整性',
                                       'IC与毛价差属于横截面研究，未扣费且不是实际账户净收益']}, 'decay')


def stability(spec):
    identity(spec)
    rows = spec['records']
    if not isinstance(rows, list) or not rows:
        raise ValueError('稳定性记录不能为空')
    threshold = spec.get('minimumObservations', 3)
    if type(threshold) is not int or threshold < 3:
        raise ValueError('展示门槛须为至少3条记录的整数')
    cutoff = instant(spec['asOf'])
    previous = None
    groups = {}
    excluded = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError('IC记录须为对象')
        at = instant(row['at'])
        if previous is not None and at <= previous:
            raise ValueError('稳定性记录须严格按时点排序且不重复')
        previous = at
        if instant(row['availableAt']) < at or instant(row['availableAt']) > cutoff:
            raise ValueError('IC记录可得时点无效')
        group = text(row.get('group'), '分组')
        if row.get('IC') is None:
            excluded.append({'at': row['at'], 'reason': 'IC缺失，打断连续段'})
        else:
            finite(row['IC'], 'IC', -1, 1)
        groups.setdefault(group, []).append((index, row))
    summaries = []
    for name, records in groups.items():
        valid = [finite(r['IC'], 'IC', -1, 1) for _, r in records if r.get('IC') is not None]
        flips = run = longest = 0
        last_sign = None
        path = high = fall = 0.0
        last_at = None
        for index, row in records:
            # Interleaved group records are a gap, not adjacent observations.
            interrupted = last_at is not None and index != last_at + 1
            last_at = index
            if row.get('IC') is None or interrupted:
                run = 0
                last_sign = None
            if row.get('IC') is None:
                continue
            value = finite(row['IC'], 'IC', -1, 1)
            sign = 1 if value > 0 else -1 if value < 0 else 0
            if last_sign is not None and sign != 0 and last_sign != sign:
                flips += 1
            last_sign = sign if sign else None
            run = run + 1 if value <= 0 else 0
            longest = max(longest, run)
            path += value
            high = max(high, path)
            fall = max(fall, high - path)
        sufficient = len(valid) >= threshold
        summaries.append({'group': name, 'observations': len(valid), 'status': 'descriptive_only' if sufficient else 'insufficient_data',
                          'positiveShare': sum(v > 0 for v in valid) / len(valid) if sufficient else None,
                          'signFlips': flips if sufficient else None, 'longestNonPositiveRunRecords': longest if sufficient else None,
                          'cumulativeICPathFall': fall if sufficient else None})
    return stamp(spec, {'groups': summaries, 'excludedPeriods': excluded,
                       'conclusion': '正值占比和连续非正记录只描述样本，不是胜率或账户回撤。',
                       'humanRows': [[r['group'], status_label(r['status'])] for r in summaries],
                       'limitations': ['记录数不是交易天数；缺值和分组间断会打断连续段，零值打断符号翻转但计入非正记录',
                                       '累计IC路径回落单位为IC累计点，与资产净值回撤不同；门槛是展示政策，不证明统计有效性']}, 'stability')
