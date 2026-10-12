# SPDX-License-Identifier: MIT
"""Point-in-time OHLCV contract; validation needs only the standard library."""
import math
from datetime import timedelta
from .review_io import instant, digest

SCHEMA = 'cnn-factor/1'
ARCHITECTURE = 'ohlcv-conv1d-8x8-average/1'


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + '须明确非空文字')
    return value


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('CNN数值须为有限数字，不能用未知或布尔值补齐')
    return float(value)


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('CNN整数参数超出支持范围')
    return value


def validate(spec, labels=True):
    if spec.get('schemaVersion') != SCHEMA:
        raise ValueError('需cnn-factor/1输入')
    for key in ('researchId', 'dataVersion', 'universeDefinition', 'universeVersion', 'priceBasis', 'labelDefinition'):
        text(spec.get(key), key)
    if spec.get('dataKind') not in ('synthetic-teaching', 'declared-history'):
        raise ValueError('须声明教学或历史数据')
    if spec.get('volumeBasis') != 'shares' or spec.get('returnUnit') != 'decimal-simple-total-return':
        raise ValueError('成交量须明确股数，收益须小数简单总收益')
    cutoff = instant(spec['asOf'])
    lookback = integer(spec['lookbackRecords'], 4, 256)
    horizon = integer(spec['horizonRecords'], 1, 256)
    samples = spec['samples']
    if not isinstance(samples, list) or not 1 <= len(samples) <= 5000:
        raise ValueError('样本数须1至5000')
    seen, keys, eligible, excluded = set(), set(), [], []
    for row in samples:
        sid = text(row.get('id'), '样本ID')
        security = text(row.get('security'), '证券')
        signal = instant(row['signalAt'])
        key = (security, signal)
        if sid in seen or key in keys:
            raise ValueError('样本ID或证券信号重复')
        seen.add(sid); keys.add(key)
        if signal > cutoff or instant(row['universeAvailableAt']) > signal:
            raise ValueError('信号或股票池时点存在前视')
        if row.get('membershipAtSignal') is not True:
            excluded.append({'id': sid, 'reason': '非已确认当期成员'}); continue
        adjustment = row['adjustmentEvidence']
        text(adjustment.get('source'), '复权证据')
        if instant(adjustment['availableAt']) > signal:
            raise ValueError('复权证据晚于信号，不能使用事后复权系数')
        history = row['history']
        if not isinstance(history, list) or len(history) != lookback:
            raise ValueError('历史窗口须恰为声明的记录数；不自动补停牌或缺失日')
        previous = None
        for bar in history:
            at, available = instant(bar['at']), instant(bar['availableAt'])
            if (previous is not None and at <= previous) or not at <= available <= signal:
                raise ValueError('行情顺序或可得时点无效')
            previous = at
            o, h, l, c, v = [finite(bar[k]) for k in ('open', 'high', 'low', 'close', 'volumeShares')]
            if min(o, h, l, c) <= 0 or v < 0 or not l <= min(o, c) <= max(o, c) <= h:
                raise ValueError('OHLC或成交量不符合价格边界')
            text(bar.get('source'), '行情来源')
        if labels:
            label = row['label']
            start, end, available = [instant(label[k]) for k in ('returnStartAt', 'returnEndAt', 'availableAt')]
            if not signal <= start < end <= available <= cutoff:
                raise ValueError('标签窗口、可得时点或截止无效')
            if label.get('horizonRecords') != horizon or finite(label['forwardReturn']) < -1:
                raise ValueError('标签期限或总收益无效')
            text(label.get('source'), '标签来源')
        elif 'label' in row:
            raise ValueError('预测输入不能夹带未来标签')
        eligible.append(row)
    if not eligible:
        raise ValueError('没有合格当期样本')
    return eligible, excluded


def features(row):
    anchor = finite(row['history'][0]['close'])
    return [[finite(b[k]) / anchor - 1 for b in row['history']] for k in ('open', 'high', 'low', 'close')] + [
        [math.log1p(finite(b['volumeShares'])) for b in row['history']]]


def splits(spec, rows, fold):
    times = {k: instant(fold[k]) for k in ('trainStart', 'trainEnd', 'validationStart', 'validationEnd', 'testStart', 'testEnd')}
    if not times['trainStart'] <= times['trainEnd'] < times['validationStart'] <= times['validationEnd'] < times['testStart'] <= times['testEnd'] <= instant(spec['asOf']):
        raise ValueError('训练、验证和测试区间须按时间严格分开')
    embargo=integer(spec['parameters'].get('embargoSeconds',0),0,366*86400)
    groups, purged = {}, []
    for name, next_start in (('train', times['validationStart']), ('validation', times['testStart']), ('test', instant(spec['asOf']))):
        selected = [r for r in rows if times[name+'Start'] <= instant(r['signalAt']) <= times[name+'End']]
        if name != 'test':
            kept = []
            for row in selected:
                if instant(row['label']['availableAt']) >= next_start-timedelta(seconds=embargo):
                    purged.append({'id': row['id'], 'stage': name, 'reason': '标签可得时点触及下一阶段或声明隔离缓冲'})
                else:
                    kept.append(row)
            selected = kept
        if len(selected) < 3:
            raise ValueError(name + '清洗后不足三个样本')
        groups[name] = selected
    return groups, purged


def parameters(spec):
    p = spec['parameters']
    epochs = integer(p['epochs'], 1, 200)
    seed = integer(p['seed'], 0, 2147483647)
    rate = finite(p['learningRate'])
    if not 0 < rate <= .1:
        raise ValueError('学习率须大于0且不超过0.1')
    return dict(epochs=epochs, seed=seed, learningRate=rate,
                embargoSeconds=integer(p.get('embargoSeconds',0),0,366*86400))


def signature(spec):
    return {k: spec[k] for k in ('schemaVersion', 'dataKind', 'lookbackRecords', 'horizonRecords', 'priceBasis', 'volumeBasis', 'labelDefinition', 'returnUnit', 'universeDefinition', 'universeVersion')}


def base(spec, excluded):
    return dict(methodVersion='original-ohlcv-cnn/1', inputSha256=digest(spec), excluded=excluded,
                architecture=ARCHITECTURE, dataKind=spec['dataKind'],
                limitations=['得分是回归估计，不是上涨概率或盈利保证',
                             '只审查声明样本；来源真实性、退市覆盖、复权与交易日历仍需核验',
                             '标签和股票池依据由输入声明；格式通过不代表原文已验证',
                             '没有订单、成本、涨跌停、停牌、T+1或账户净收益模拟',
                             '不同PyTorch版本和平台不保证逐位一致；未认证真实A股预测效果'])
