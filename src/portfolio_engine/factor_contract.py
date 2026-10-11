# SPDX-License-Identifier: MIT
"""Versioned declared factor inputs; never upgrade frozen legacy records."""
from .review_io import digest, instant, number

SCHEMA = 'factor-review/2'


def percent(value):
    return '未知' if value is None else format(value * 100, '.6g') + '%'


def status_label(value):
    return {'descriptive_only': '仅描述样本', 'partial_coverage': '覆盖不完整',
            'conditional_on_declared_inputs': '按声明条件计算', 'unknown_cost': '费用未知',
            'blocked_or_unknown': '不可执行或条件未知', 'unknown': '资料不足',
            'missing': '缺少资料', 'insufficient_data': '样本不足'}.get(value, value)


def finite(value, label, minimum=None, maximum=None):
    result = float(number(value))
    import math
    if not math.isfinite(result) or (minimum is not None and result < minimum) or (maximum is not None and result > maximum):
        raise ValueError(label + ' 超出支持范围')
    return result


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('须声明 ' + label)
    return value


def identity(spec, strict=True):
    if not isinstance(spec, dict):
        raise ValueError('因子底稿须为对象')
    schema = spec.get('schemaVersion')
    if schema not in (None, SCHEMA):
        raise ValueError('不支持的因子 schemaVersion')
    if strict and schema != SCHEMA:
        raise ValueError('新动作须声明 schemaVersion=' + SCHEMA)
    fields = ('factorId', 'factorVersion', 'factorDefinition', 'factorSource')
    gaps = [field for field in fields if not isinstance(spec.get(field), str) or not spec[field].strip()]
    if schema == SCHEMA and gaps:
        raise ValueError('因子定义缺少：' + '、'.join(gaps))
    return {**{field: spec.get(field) for field in fields}, 'schemaVersion': schema or 'legacy', 'definitionGaps': gaps}


def stamp(spec, result, action):
    instant(spec['asOf'])
    return {**result, 'methodVersion': 'factor-investability/' + action + '/1.0',
            'factorIdentity': identity(spec), 'inputSha256': digest(spec),
            'asOf': text(spec.get('asOf'), 'asOf'), 'parameters': spec.get('parameters', {}),
            'status': result.get('status', 'descriptive_only'),
            'limitations': result.get('limitations', []) + [
                '资料与交易条件来自声明底稿；程序通过不认证来源完整或实际可成交',
                '不自动联网、下单或覆盖冻结结果；本结果不证明未来盈利']}


def available(row, cutoff, signal=None):
    if not isinstance(row, dict):
        raise ValueError('证据记录须为对象')
    acquired = instant(row['availableAt'])
    if acquired > cutoff or (signal is not None and acquired > signal):
        raise ValueError('资料可得时点晚于使用时点')
    text(row.get('source'), 'source')


def unique_rows(rows, key='security'):
    if not isinstance(rows, list):
        raise ValueError('记录须为列表')
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('每条记录须为对象')
        identifier = text(row.get(key), key)
        if identifier in result:
            raise ValueError('记录重复：' + identifier)
        result[identifier] = row
    return result
