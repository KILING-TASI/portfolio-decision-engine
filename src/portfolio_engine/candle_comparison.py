# SPDX-License-Identifier: MIT
"""Predeclared paired CNN/geometry/rule comparison, never selects by test performance."""
import statistics
from . import cnn_contract as c
from . import candle_patterns as patterns
from .review_io import instant


def compare(spec):
    from .cnn_engine import fit,metrics
    rows,excluded=c.validate(spec);p=patterns.rules(spec)
    if spec.get('comparisonPlan')!='ohlcv-vs-rules-vs-geometry/1':raise ValueError('须预声明三路线对照计划版本')
    folds=spec.get('folds',[spec['split']] if 'split' in spec else [])
    if not isinstance(folds,list) or not 1<=len(folds)<=12:raise ValueError('对照窗口须1至12个')
    if len(rows)*c.parameters(spec)['epochs']*len(folds)*2>1000000:raise ValueError('对照计算超过小范围上限')
    previous=None
    for fold in folds:
        c.splits(spec,rows,fold)
        if previous is not None and instant(fold['testStart'])<=previous:raise ValueError('对照测试区间重叠或无序')
        previous=instant(fold['testEnd'])
    events={r['id']:patterns.inspect(r,p) for r in rows};results=[]
    for fold in folds:
        groups,purged=c.splits(spec,rows,fold)
        original=fit(spec,rows,fold)
        augmented=fit(spec,rows,fold,feature_mode='ohlcv-geometry')
        targets=[r['label']['forwardReturn'] for r in groups['train']]
        fallback=statistics.mean(targets);mapping={}
        for signal in (-1,0,1):
            ys=[r['label']['forwardReturn'] for r in groups['train'] if events[r['id']]['ruleSignal']==signal]
            mapping[str(signal)]=dict(count=len(ys),predictedReturn=statistics.mean(ys) if ys else fallback,fallbackUsed=not bool(ys))
        rule_scores=[mapping[str(events[r['id']]['ruleSignal'])]['predictedReturn'] for r in groups['test']]
        rule_metrics=metrics(groups['test'],rule_scores)
        results.append(dict(split=fold,sampleIds={k:[r['id'] for r in rs] for k,rs in groups.items()},purged=purged,
                            ohlcvCNN=original,geometryCNN=augmented,
                            rules=dict(ruleVersion=patterns.RULE_VERSION,parameters=p,trainingOnlyReturnMapping=mapping,
                                       testMetrics=rule_metrics,scores=[dict(id=r['id'],security=r['security'],signalAt=r['signalAt'],score=v,ruleSignal=events[r['id']]['ruleSignal']) for r,v in zip(groups['test'],rule_scores)]),
                            pairedTestMSE=dict(ohlcv=original['testMetrics']['MSE'],geometry=augmented['testMetrics']['MSE'],rules=rule_metrics['MSE']),
                            geometryMSEImprovement=original['testMetrics']['MSE']-augmented['testMetrics']['MSE']))
    result=c.base(spec,excluded)
    result.update(methodVersion='paired-candle-cnn-review/1',comparisonPlan=spec['comparisonPlan'],ruleVersion=patterns.RULE_VERSION,patternParameters=p,
                  availabilityMode='retrospective-paired-comparison',folds=results,selectedWinner=None,
                  conclusion='三路线使用同一时间窗口和测试样本；改善可为负，不按测试结果自动选择赢家。',
                  humanRows=[['资料性质','原创合成教学' if spec['dataKind']=='synthetic-teaching' else '声明历史底稿，未认证'],
                             ['对照窗口',len(results)],['测试样本',sum(len(f['sampleIds']['test']) for f in results)],
                             ['对照路线','OHLCV CNN / 显式规则训练均值 / OHLCV加五个几何通道'],['自动选型','未执行']])
    result['limitations']+=['规则预测仅用训练集按方向分组的标签均值，缺组回退训练均值，不使用测试标签拟合',
                           '增强网络输入通道更多，参数量也增加；结果不能证明增益只来自形态信息',
                           '几何通道是实体、影线、跳空和短期变化，不是神经网络已识别命名形态的证明',
                           '增强模型仅用于此冻结对照；不能交给旧五通道predict入口',
                           '参数、规则和两条CNN路线预声明；无法认证研究者此前是否查看过测试集']
    for i,f in enumerate(results,1):
        m=f['pairedTestMSE']
        result['humanRows'].append([f'窗口{i}测试均方误差',f"OHLCV {m['ohlcv']:.6g}；规则 {m['rules']:.6g}；几何增强 {m['geometry']:.6g}"])
        result['humanRows'].append([f'窗口{i}几何增强误差改善',f"{f['geometryMSEImprovement']:.6g}（可以为负，不是收益改善）"])
    return result
