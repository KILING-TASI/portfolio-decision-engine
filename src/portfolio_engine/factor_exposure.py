# SPDX-License-Identifier: MIT
"""Partial factor coverage is not a complete account exposure."""
import statistics
from .factor_contract import available, finite, identity, stamp, text, unique_rows, percent
from .review_io import instant


def exposure(spec):
    identity(spec)
    snapshot = instant(spec['snapshotAt'])
    cutoff = instant(spec['asOf'])
    if snapshot > cutoff:
        raise ValueError('持仓时点晚于截至日')
    if spec.get('weightBasis') != 'long-only-account-equity':
        raise ValueError('当前暴露仅支持只多账户资金权重，现金须明确标识；空头/杠杆另走完整分析')
    text(spec.get('factorScale'), 'factorScale')
    values = unique_rows(spec['factorValues'])
    for row in values.values():
        available(row, cutoff, snapshot)
        if row.get('factorId') != spec['factorId'] or row.get('factorVersion') != spec['factorVersion'] or row.get('factorScale') != spec['factorScale']:
            raise ValueError('因子数值定义、版本或尺度不匹配')
        if instant(row['valueAt']) > snapshot or instant(row['valueAt']) > instant(row['availableAt']):
            raise ValueError('因子观察时点晚于持仓时点')
        if row.get('factor') is not None:
            finite(row['factor'], 'factor')

    def aggregate(rows):
        positions = unique_rows(rows)
        weights = {k: finite(r['weight'], 'weight', 0, 1) for k, r in positions.items()}
        if abs(sum(weights.values()) - 1) > 1e-8:
            raise ValueError('只多账户权重含现金须合计为1，不能静默归一')
        known = unknown = cash = contribution = 0.0
        unknown_securities = []
        for security, row in positions.items():
            weight = weights[security]
            if row.get('kind') == 'cash':
                cash += weight
                continue
            if row.get('kind') != 'security':
                raise ValueError('持仓kind须明确为cash或security')
            factor = values.get(security, {}).get('factor')
            if factor is None:
                unknown += weight
                unknown_securities.append(security)
            else:
                known += weight
                contribution += weight * finite(factor, 'factor')
                finite(contribution, '已知贡献')
        return {'knownWeightedContribution': contribution if known else None, 'knownWeight': known,
                'knownNormalizedExposure': contribution / known if known else None, 'unknownWeight': unknown,
                'unknownSecurities': unknown_securities, 'cashWeight': cash,
                'completeSecurityExposure': contribution if unknown <= 1e-12 else None}

    result = aggregate(spec['holdings'])
    benchmark = spec.get('benchmark')
    comparison = None
    if benchmark is not None:
        if any(benchmark.get(k) != spec.get(k) for k in ('snapshotAt', 'weightBasis', 'factorId', 'factorVersion', 'factorScale')):
            raise ValueError('基准与账户时点、权重或因子口径不一致')
        comparison = aggregate(benchmark['holdings'])
    percentile = None
    reference = spec.get('referenceUniverse')
    if reference is not None:
        if any(reference.get(k) != spec.get(k) for k in ('snapshotAt', 'factorId', 'factorVersion', 'factorScale')):
            raise ValueError('参考池时点或因子口径不一致')
        text(reference.get('definition'), '参考池 definition')
        text(reference.get('version'), '参考池 version')
        members = reference['securities']
        if not isinstance(members, list) or not members or len(set(members)) != len(members):
            raise ValueError('参考池成员为空或重复')
        reference_values = [values.get(k, {}).get('factor') for k in members]
        if None not in reference_values and result['unknownWeight'] <= 1e-12 and result['knownNormalizedExposure'] is not None:
            reference_values = [finite(v, '参考池factor') for v in reference_values]
            target = result['knownNormalizedExposure']
            percentile = 100 * (sum(v < target for v in reference_values) + .5 * sum(v == target for v in reference_values)) / len(reference_values)
    result.update(benchmarkExposure=comparison, percentile=percentile,
                  percentileBasis='账户已知证券部分均值相对声明参考池的中秩百分位；仅完整证券覆盖时计算',
                  status='partial_coverage' if result['unknownWeight'] > 1e-12 else 'descriptive_only',
                  conclusion='已知贡献、已知部分均值和未知权重分开列示；暴露大小不能直接判断是否应减仓。',
                  humanRows=[['已知证券权重', percent(result['knownWeight'])], ['未知证券权重', percent(result['unknownWeight'])],
                             ['现金权重', percent(result['cashWeight'])], ['已知贡献（未归一）', result['knownWeightedContribution'] if result['knownWeightedContribution'] is not None else '未知'],
                             ['已知部分均值', result['knownNormalizedExposure'] if result['knownNormalizedExposure'] is not None else '未知']],
                  limitations=['现金不默认为因子值0，另列现金权重；缺值证券不参与已知均值',
                               '参考池或覆盖不足时百分位未知；历史股票池完整性仍需另核',
                               '账户与基准的覆盖不同会影响比较，不能将部分均值冒充完整暴露'])
    return stamp(spec, result, 'exposure')
