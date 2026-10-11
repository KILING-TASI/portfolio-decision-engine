# SPDX-License-Identifier: MIT
"""Optional analysis is imported only for requested model computations."""
from .factor_contract import available, finite, identity, stamp, text, unique_rows
from .factor_series import ledger
from .review_io import instant


def budget(spec):
    identity(spec)
    result = ledger(spec)
    bridge = {'rows': [{'date': r['endAt'], 'declaredAccountNetReturn': r['netReturn']} for r in result['periods']],
              'scope': '只多声明账户的非重叠净收益，不是多空分层价差',
              'simulationCosts': 0, 'costScope': '账本收益已扣声明费用，不再扣第二次；不模拟重新选股或改变成交计划'}
    if result['accountNetSeries'] is None:
        return stamp(spec, {'status': 'unknown', 'bridge': bridge, 'budgetResult': None,
                           'conclusion': '净收益路径不完整，不能计算回撤预算。', 'unknowns': result['unknowns'],
                           'limitations': ['费用、成交条件或收益缺失时停止桥接，不用毛价差替代']}, 'budget')
    compute = spec.get('compute', False)
    if type(compute) is not bool:
        raise ValueError('compute 须为布尔值')
    simulation = None
    if compute:
        import pandas as pd
        from .bootstrap import drawdown_budget
        options = spec['budgetParameters']
        allowed = {'budget', 'horizon', 'paths', 'block_lengths', 'seed', 'mc_tolerance', 'max_paths', 'strict', 'periods'}
        if set(options) != allowed:
            raise ValueError('budgetParameters 须明确声明全部模拟参数，不能静默忽略未知字段')
        for key in ('horizon', 'paths', 'max_paths', 'periods'):
            if type(options[key]) is not int or options[key] <= 0:
                raise ValueError('模拟步数与路径数须为正整数')
        if options['paths'] > 20000 or options['max_paths'] > 20000 or options['horizon'] > 3660:
            raise ValueError('本入口模拟上限为20000路径、3660步；更大任务须单独评估资源')
        if type(options['seed']) is not int or type(options['strict']) is not bool:
            raise ValueError('seed/strict 类型无效')
        blocks = options['block_lengths']
        if not isinstance(blocks, list) or not blocks or len(blocks) > 10 or any(finite(b, 'block_length', 1) > len(bridge['rows']) for b in blocks):
            raise ValueError('块长度须不超过样本记录数，最多10档')
        frame = pd.DataFrame({'declared_account': result['accountNetSeries']},
                             index=pd.to_datetime([r['date'] for r in bridge['rows']], utc=True))
        simulation = drawdown_budget(frame, {'declared_path': [1.0]}, costs=0, rebalance_every=0,
                                     initial_weights=[1.0], **options)
        simulation = _plain(simulation)
    return stamp(spec, {'status': 'conditional_model_result' if compute else 'bridge_only', 'bridge': bridge,
                       'budgetResult': simulation, 'conclusion': '回撤预算按声明净收益路径处理；桥接导出与模型计算分别标明状态。',
                       'humanRows': [['净收益记录', len(bridge['rows'])], ['预算计算', '已计算条件模型' if compute else '尚未计算']],
                       'limitations': ['预算模型需要analysis；标准库只导出已核对账本的桥接资料',
                                       '模拟区间只反映条件重采样与蒙特卡洛精度，不能解释为真实未来概率',
                                       '不同记录可能对应不同时间长度，periods和horizon是声明步数口径，不自动认定交易日年化',
                                       '只评估声明路径，不重新生成因子订单；独立测试与选型污染仍需另核']}, 'budget')


def _plain(value):
    import numpy as np
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def multi(spec):
    identity(spec)
    import numpy as np
    rows = unique_rows(spec['observations'])
    definitions = unique_rows(spec['factors'], 'id')
    if not definitions:
        raise ValueError('多因子定义不能为空')
    names = list(definitions)
    for definition in definitions.values():
        for key in ('version', 'definition', 'source'):
            text(definition.get(key), key)
    snapshot = instant(spec['snapshotAt'])
    cutoff = instant(spec['asOf'])
    if snapshot > cutoff:
        raise ValueError('多因子快照晚于截至日')
    weights = spec['combinationWeights']
    if set(weights) != set(names) or abs(sum(abs(finite(v, '合成权重')) for v in weights.values()) - 1) > 1e-8:
        raise ValueError('合成权重须逐因子声明且绝对值合计为1，不自动挑选权重')
    neutralize = spec['neutralize']
    if neutralize not in ('none', 'industry-log-market-cap'):
        raise ValueError('中性化仅支持none或industry-log-market-cap')
    if type(spec.get('orthogonalize')) is not bool:
        raise ValueError('须声明 orthogonalize 布尔值')
    selected, excluded = [], []
    for security, row in rows.items():
        available(row, cutoff, snapshot)
        if instant(row['valueAt']) > snapshot or instant(row['valueAt']) > instant(row['availableAt']):
            raise ValueError('多因子观察时点晚于快照')
        if set(row['factors']) != set(names):
            raise ValueError('逐证券因子字段不对应声明定义')
        if any(value is None for value in row['factors'].values()):
            excluded.append({'security': security, 'reason': '因子缺值，整行排除并列出覆盖缺口'})
            continue
        if neutralize != 'none':
            if row.get('industry') is None or row.get('marketCap') is None:
                excluded.append({'security': security, 'reason': '行业或市值缺失'})
                continue
            available(row['controlsEvidence'], cutoff, snapshot)
            if instant(row['controlsEvidence']['valueAt']) > instant(row['controlsEvidence']['availableAt']):
                raise ValueError('行业市值观察时点晚于可得时点')
            text(row['industry'], '行业分类')
            if finite(row['marketCap'], '市值', 0) == 0:
                raise ValueError('市值须大于0')
        selected.append(row)
    limitations = ['使用声明的因子、行业和市值资料，不维护或认证主数据',
                   '标准化使用当前快照样本均值与总体标准差，不证明跨期可比或未来收益',
                   'VIF>10是诊断阈值，不是可投判定；合成权重由底稿给定，不做自动选型',
                   '缺值采用完整行排除并展示覆盖；正交顺序按因子定义列表，会影响结果']
    def blocked(reason):
        return stamp(spec, {'status': 'invalid_or_insufficient_data', 'reason': reason, 'scores': None,
                           'excluded': excluded, 'conclusion': '资料或矩阵条件不足，未生成多因子分数。',
                           'limitations': limitations}, 'multi')
    if len(selected) <= len(names) + 5:
        return blocked('有效样本须大于因子数+5，这是本动作计算门槛')
    x = np.array([[finite(r['factors'][name], '因子数值') for name in names] for r in selected])
    scales = x.std(axis=0)
    if np.any(scales <= 1e-12):
        return blocked('常数因子无法标准化')
    z = (x - x.mean(axis=0)) / scales
    if not np.isfinite(z).all():
        return blocked('数值尺度溢出，不能生成分数')
    controls = np.ones((len(selected), 1))
    if neutralize != 'none':
        industries = sorted({r['industry'] for r in selected})
        controls = np.column_stack([controls, np.log([r['marketCap'] for r in selected]),
                                    *[[float(r['industry'] == name) for r in selected] for name in industries[1:]]])
        if np.linalg.matrix_rank(controls) < controls.shape[1] or len(selected) <= controls.shape[1] + 1:
            return blocked('行业市值控制矩阵秩或样本不足')
        z -= controls @ np.linalg.lstsq(controls, z, rcond=None)[0]
        residual_scale = z.std(axis=0)
        if np.any(residual_scale <= 1e-12):
            return blocked('中性化后因子无有效变动')
        z /= residual_scale
    design = np.column_stack([np.ones(len(z)), z])
    if np.linalg.matrix_rank(design) < len(names) + 1:
        return blocked('因子矩阵秩不足，不继续合成')
    vifs = {}
    for index, name in enumerate(names):
        target = z[:, index]
        others = np.delete(design, index + 1, axis=1)
        residual = target - others @ np.linalg.lstsq(others, target, rcond=None)[0]
        denominator = float(np.sum(residual ** 2))
        vifs[name] = float(np.sum((target - target.mean()) ** 2)) / denominator
    correlations = np.atleast_2d(np.corrcoef(z, rowvar=False)).tolist() if len(names) > 1 else [[1.0]]
    transformed = z.copy()
    if spec['orthogonalize']:
        for index in range(len(names)):
            for previous in range(index):
                axis = transformed[:, previous]
                transformed[:, index] -= (axis @ transformed[:, index]) / (axis @ axis) * axis
            scale = transformed[:, index].std()
            if scale <= 1e-12:
                return blocked('正交后因子无有效变动')
            transformed[:, index] /= scale
    scores = transformed @ np.array([weights[name] for name in names], float)
    return stamp(spec, {'status': 'degraded' if any(v > 10 for v in vifs.values()) else 'descriptive_only',
                       'scores': [{'security': r['security'], 'score': float(score)} for r, score in zip(selected, scores)],
                       'factorOrder': names, 'vif': vifs, 'factorCorrelations': correlations,
                       'neutralize': neutralize, 'orthogonalize': spec['orthogonalize'], 'excluded': excluded,
                       'observations': len(selected), 'conclusion': '按声明权重和处理顺序生成描述性因子分数；不代表策略已验证。',
                       'humanRows': [['有效证券数', len(selected)], ['排除证券数', len(excluded)]],
                       'limitations': limitations}, 'multi')
