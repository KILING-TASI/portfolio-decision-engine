# SPDX-License-Identifier: MIT
"""Small original CPU CNN; no imported paper code or unsafe model pickle."""
from contextlib import contextmanager
from datetime import datetime, timezone
import math
import statistics
import warnings
from . import cnn_contract as contract
from .review_io import digest, instant


def runtime():
    try:
        with warnings.catch_warnings():
            # This module never uses Tensor.numpy(); missing NumPy is supported.
            warnings.filterwarnings('ignore', message='Failed to initialize NumPy: No module named.*', category=UserWarning)
            import torch
    except ModuleNotFoundError as error:
        raise ValueError('缺少CNN可选组件：请安装 portfolio-decision-engine[cnn]，不会自动安装') from error
    return torch


@contextmanager
def deterministic(torch, seed):
    threads = torch.get_num_threads()
    enabled = torch.are_deterministic_algorithms_enabled()
    warn = torch.is_deterministic_algorithms_warn_only_enabled()
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            yield
    finally:
        torch.set_num_threads(threads)
        torch.use_deterministic_algorithms(enabled, warn_only=warn)


def network(torch, channels=5):
    nn = torch.nn
    return nn.Sequential(nn.Conv1d(channels, 8, 3, padding=1), nn.ReLU(),
                         nn.Conv1d(8, 8, 3, padding=1), nn.ReLU(),
                         nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(8, 1))


def feature_values(row,mode='ohlcv'):
    values=contract.features(row)
    if mode=='ohlcv':return values
    if mode!='ohlcv-geometry':raise ValueError('不支持此特征模式')
    from .candle_patterns import feature_channels
    return values+feature_channels(row)


def scaling(rows,mode='ohlcv'):
    data = [feature_values(r,mode) for r in rows]
    means, scales = [], []
    for channel in range(len(data[0])):
        values = [v for sample in data for v in sample[channel]]
        means.append(statistics.mean(values))
        scales.append(statistics.pstdev(values) or 1.0)
    ys = [contract.finite(r['label']['forwardReturn']) for r in rows]
    yscale = statistics.pstdev(ys)
    if yscale <= 1e-12:
        raise ValueError('训练标签无有效变化，不能训练CNN')
    result=dict(means=means, scales=scales, targetMean=statistics.mean(ys), targetScale=yscale)
    if mode!='ohlcv':result['featureMode']=mode
    return result


def tensor(torch, rows, scaler):
    values = [[[ (v - scaler['means'][c]) / scaler['scales'][c] for v in channel]
               for c, channel in enumerate(feature_values(r,scaler.get('featureMode','ohlcv')))] for r in rows]
    x = torch.tensor(values, dtype=torch.float32)
    if not torch.isfinite(x).all():
        raise ValueError('标准化后超出浮点计算范围')
    return x


def scores(torch, model, rows, scaler):
    model.eval()
    with torch.no_grad():
        predicted = model(tensor(torch, rows, scaler)).flatten().tolist()
    return [contract.finite(v * scaler['targetScale'] + scaler['targetMean']) for v in predicted]


def metrics(rows, values):
    from .factor_research import ranks, corr
    actual = [r['label']['forwardReturn'] for r in rows]
    daily = {}
    for row, value in zip(rows, values):
        daily.setdefault(instant(row['signalAt']).isoformat(), []).append((value, row['label']['forwardReturn']))
    per_day = []
    for at, pairs in sorted(daily.items()):
        ic = corr(ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])) if len(pairs) >= 3 else None
        per_day.append(dict(signalAt=at, count=len(pairs), rankIC=ic))
    valid = [d['rankIC'] for d in per_day if d['rankIC'] is not None]
    return dict(MSE=statistics.mean((a-b)**2 for a,b in zip(actual,values)),
                daily=per_day, meanRankIC=statistics.mean(valid) if valid else None)


def fit(spec, rows, fold,feature_mode='ohlcv'):
    torch = runtime()
    groups, purged = contract.splits(spec, rows, fold)
    p = contract.parameters(spec)
    scaler = scaling(groups['train'],feature_mode)
    with deterministic(torch, p['seed']):
        model = network(torch,len(scaler['means']))
        optimizer = torch.optim.Adam(model.parameters(), lr=p['learningRate'])
        x = tensor(torch, groups['train'], scaler)
        y = torch.tensor([(r['label']['forwardReturn']-scaler['targetMean'])/scaler['targetScale'] for r in groups['train']], dtype=torch.float32)
        vx = tensor(torch, groups['validation'], scaler)
        vy = torch.tensor([(r['label']['forwardReturn']-scaler['targetMean'])/scaler['targetScale'] for r in groups['validation']], dtype=torch.float32)
        best, state, selected_epoch, history = math.inf, None, None, []
        for epoch in range(1, p['epochs']+1):
            model.train(); optimizer.zero_grad()
            loss = torch.nn.functional.mse_loss(model(x).flatten(), y)
            if not torch.isfinite(loss):
                raise ValueError('训练损失非有限；请检查输入与参数')
            loss.backward(); optimizer.step(); model.eval()
            with torch.no_grad():
                validation_loss = float(torch.nn.functional.mse_loss(model(vx).flatten(), vy))
            contract.finite(validation_loss)
            history.append(dict(epoch=epoch, trainingLoss=float(loss.detach()), validationLoss=validation_loss))
            if validation_loss < best:
                best, selected_epoch = validation_loss, epoch
                state = {k: v.detach().clone() for k,v in model.state_dict().items()}
        model.load_state_dict(state)
        # Test labels are accessed only after validation has frozen the checkpoint.
        test_values = scores(torch, model, groups['test'], scaler)
    architecture=contract.ARCHITECTURE if feature_mode=='ohlcv' else 'ohlcv-geometry-conv1d-8x8-average/1'
    artifact = dict(architecture=architecture, signature=contract.signature(spec),
                    scaler=scaler, weights={k:v.tolist() for k,v in state.items()},
                    torchVersion=torch.__version__, createdAt=datetime.now(timezone.utc).isoformat(),
                    simulatedAvailableAt=fold['testStart'], historicalAvailabilityCertified=False,
                    parameters=p, selectedEpoch=selected_epoch, inputSha256=digest(spec),
                    split=fold, sampleIds={k:[r['id'] for r in rs] for k,rs in groups.items()},
                    history=history, purged=purged)
    artifact['fingerprint'] = digest(artifact)
    scored = [dict(id=r['id'],security=r['security'],signalAt=r['signalAt'],score=v,
                   forwardReturn=r['label']['forwardReturn'],label=r['label'],
                   universeAvailableAt=r['universeAvailableAt']) for r,v in zip(groups['test'],test_values)]
    test_metrics=metrics(groups['test'],test_values)
    baseline=metrics(groups['test'],[scaler['targetMean']]*len(groups['test']))
    validation_baseline=statistics.mean((r['label']['forwardReturn']-scaler['targetMean'])**2 for r in groups['validation'])
    return dict(model=artifact, scores=scored, testMetrics=test_metrics,
                baseline=dict(method='training-label-mean-only',testMetrics=baseline,
                              validationMSE=validation_baseline,modelValidationMSE=best*scaler['targetScale']**2,
                              testMSEImprovement=baseline['MSE']-test_metrics['MSE'],
                              scope='同一冻结测试样本；改善可为负，不用于重新选型或证明盈利'))


def train(spec):
    rows, excluded = contract.validate(spec)
    result = contract.base(spec, excluded)
    result.update(fit(spec, rows, spec['split']))
    result.update(availabilityMode='retrospective-simulation',
                  conclusion='已按时间分开训练、验证和测试；这是事后复查，不能证明模型在历史信号日已存在。',
                  humanRows=[['测试样本',len(result['scores'])],['选中轮数',result['model']['selectedEpoch']],
                             ['测试均方误差',result['testMetrics']['MSE']],
                             ['相对训练均值基线的误差改善',result['baseline']['testMSEImprovement']],
                             ['实际历史模型可得性','未认证']])
    return result


def walk_forward(spec):
    rows, excluded = contract.validate(spec)
    folds = spec['folds']
    if not isinstance(folds,list) or not 1 <= len(folds) <= 12:
        raise ValueError('滚动窗口须1至12个')
    if len(rows)*contract.parameters(spec)['epochs']*len(folds)>1000000:
        raise ValueError('滚动计算超出小范围研究上限')
    previous, seen = None, set()
    for fold in folds:
        contract.splits(spec, rows, fold)
        if previous is not None and instant(fold['testStart']) <= previous:
            raise ValueError('滚动测试区间须有序且不重叠')
        previous = instant(fold['testEnd'])
    results = []
    for fold in folds:
        current = fit(spec, rows, fold)
        for row in current['scores']:
            if row['id'] in seen:
                raise ValueError('测试样本重复')
            seen.add(row['id'])
        results.append(current)
    result = contract.base(spec, excluded)
    result.update(folds=results, scores=[r for f in results for r in f['scores']],
                  availabilityMode='retrospective-walk-forward-simulation',
                  conclusion='滚动窗口分别拟合并冻结，再评估各自测试集；未认证历史实盘可得性。',
                  humanRows=[['滚动窗口',len(results)],['测试样本',len(seen)],['历史实盘验证','未认证']])
    return result


def load_model(model, expected):
    torch = runtime()
    unsigned = {k:v for k,v in model.items() if k!='fingerprint'}
    if digest(unsigned) != expected or model.get('fingerprint') != expected:
        raise ValueError('模型摘要不一致；须使用冻结结果中的明确摘要')
    if model['architecture'] != contract.ARCHITECTURE:
        raise ValueError('不支持此模型结构')
    scaler = model['scaler']
    for key in ('means','scales'):
        if not isinstance(scaler[key],list) or len(scaler[key])!=5:
            raise ValueError('标准化参数维数无效')
        for v in scaler[key]: contract.finite(v)
    if any(v<=0 for v in scaler['scales']) or contract.finite(scaler['targetScale'])<=0:
        raise ValueError('标准化尺度须正数')
    contract.finite(scaler['targetMean'])
    with deterministic(torch,0): model_net=network(torch)
    template=model_net.state_dict()
    if set(template)!=set(model['weights']): raise ValueError('模型权重字段无效')
    weights={}
    for key,value in model['weights'].items():
        # The reader caps JSON size; shape checking prevents alternate architectures.
        try: weight=torch.tensor(value,dtype=torch.float32)
        except (ValueError,TypeError,RuntimeError) as error: raise ValueError('模型权重无效') from error
        if weight.shape!=template[key].shape or not torch.isfinite(weight).all():
            raise ValueError('模型权重维数或数值无效')
        weights[key]=weight
    model_net.load_state_dict(weights)
    return torch,model_net,scaler


def predict(spec, model, expected):
    rows, excluded = contract.validate(spec,labels=False)
    if contract.signature(spec)!=model['signature']:
        raise ValueError('预测数据口径与模型不一致')
    if model['signature']['dataKind']=='synthetic-teaching' and spec['dataKind']!='synthetic-teaching':
        raise ValueError('教学模型不能冒充历史研究模型')
    torch,net,scaler=load_model(model,expected)
    with deterministic(torch,0): values=scores(torch,net,rows,scaler)
    computed_at=datetime.now(timezone.utc).isoformat()
    for row in rows:
        if instant(row['signalAt']) < max(instant(model['createdAt']),instant(computed_at)):
            raise ValueError('模型或本次计算晚于信号；历史复查请用滚动模拟')
    result=contract.base(spec,excluded)
    result.update(modelFingerprint=expected,modelCreatedAt=model['createdAt'],scoreComputedAt=computed_at,dataSignature=contract.signature(spec),availabilityMode='created-before-declared-signal',
                  scores=[dict(id=r['id'],security=r['security'],signalAt=r['signalAt'],score=v,
                               universeAvailableAt=r['universeAvailableAt'],membershipAtSignal=True) for r,v in zip(rows,values)],
                  conclusion='已生成声明信号时点的回归得分；来源、成交条件及模型效果仍需复查。',
                  humanRows=[['得分样本',len(rows)],['得分含义','未来总收益回归估计，不是上涨概率']])
    return result
