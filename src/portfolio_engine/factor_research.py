# SPDX-License-Identifier: MIT
"""Standalone factor panel research and declared trial history, no trading engine."""
import math,statistics
from datetime import date
from .review_io import number,instant,digest,cli

def ranks(values):
    order=sorted(range(len(values)),key=lambda i:values[i]);result=[0.0]*len(values);start=0
    while start<len(order):
        end=start+1
        while end<len(order) and values[order[end]]==values[order[start]]:end+=1
        mean=(start+1+end)/2
        for i in order[start:end]:result[i]=mean
        start=end
    return result

def corr(a,b):
    am,bm=statistics.mean(a),statistics.mean(b);aa=sum((x-am)**2 for x in a);bb=sum((x-bm)**2 for x in b)
    return sum((x-am)*(y-bm) for x,y in zip(a,b))/math.sqrt(aa*bb) if aa>0 and bb>0 else None

def panel(spec):
    if 'schemaVersion' in spec:
        from .factor_contract import identity
        identity(spec)
    cutoff=instant(spec['asOf']);groups=spec['groups']
    if isinstance(groups,bool) or not isinstance(groups,int) or not 2<=groups<=10:raise ValueError('分层数须2至10')
    if not spec.get('universeDefinition') or spec.get('universeVersion') is None:raise ValueError('须声明股票池定义及版本，避免无股票池依据')
    rows=spec['rows'];seen=set();dates={};excluded=[]
    for r in rows:
        key=(r['signalDate'],r['security'])
        if not isinstance(r['security'],str) or not r['security'] or key in seen:raise ValueError('同日证券重复或身份缺失')
        seen.add(key);signal=instant(r['signalAt']);factor_available=instant(r['factorAvailableAt']);universe_available=instant(r['universeAvailableAt']);realized=instant(r['returnAvailableAt'])
        if signal.date().isoformat()!=r['signalDate']:raise ValueError('信号日和时点不一致')
        if factor_available>signal or universe_available>signal:raise ValueError('因子/股票池晚于信号时点，存在前视')
        if instant(r['returnStartAt'])<signal or instant(r['returnEndAt'])<=instant(r['returnStartAt']) or realized<instant(r['returnEndAt']):raise ValueError('未来收益区间或可得时点无效')
        if r.get('membershipAtSignal') is not True:raise ValueError('须明确当期股票池成员，不用当前存活列表补历史')
        f,y=float(number(r['factor'])),float(number(r['forwardReturn']))
        if not math.isfinite(f) or not math.isfinite(y) or y<-1:raise ValueError('因子/简单收益不在支持范围')
        if realized>cutoff:excluded.append({'security':r['security'],'signalDate':r['signalDate'],'reason':'收益截止后才可得'});continue
        dates.setdefault(r['signalDate'],[]).append((r,f,y))
    stats=[]
    for day,rs in sorted(dates.items()):
        if len(rs)<max(3,groups):raise ValueError('每日样本不足，不能用少量股票伪造分层')
        if len({(r['returnStartAt'],r['returnEndAt']) for r,_,_ in rs})!=1:raise ValueError('同日收益窗口不同')
        f=[x for _,x,_ in rs];y=[x for _,_,x in rs];rank=ranks(f)
        # Equal factor values always remain in the same group, without security-code tie breaks.
        buckets={i:[] for i in range(1,groups+1)}
        for rk,(_,_,value) in zip(rank,rs):buckets[min(groups,int((rk-1)*groups/len(rs))+1)].append(value)
        means={str(k):statistics.mean(v) if v else None for k,v in buckets.items()}
        ic=corr(f,y);rank_ic=corr(rank,ranks(y));spread=None if means['1'] is None or means[str(groups)] is None else means[str(groups)]-means['1']
        stats.append({'signalDate':day,'count':len(rs),'IC':ic,'rankIC':rank_ic,'equalWeightGroupMeanReturns':means,'topMinusBottomGrossReturn':spread,'emptyGroups':[k for k,v in buckets.items() if not v]})
    valid=[r['rankIC'] for r in stats if r['rankIC'] is not None]
    sd=statistics.stdev(valid) if len(valid)>1 else None
    mean=statistics.mean(valid) if valid else None
    result = {'methodVersion':'point-in-time-panel-review/1.0','conclusion':'先核对因子和股票池在信号时点是否可得，再计算逐日横截面相关和分层；这些结果尚不是可执行策略。','daily':stats,'excluded':excluded,'meanRankIC':mean,'rankICSampleStd':sd,'nonAnnualizedICIR':mean/sd if sd and mean is not None else None,'humanRows':[['可计算日期',len(stats)],['平均秩相关（rank IC）',mean],['未年化ICIR',mean/sd if sd and mean is not None else '未知：日期不足或波动为零']],'limitations':['IC是因子与随后收益的横截面相关，不是预测准确率','ICIR未年化，重叠收益与时间相关未校正，不输出置信概率','分层采用平均秩保持并列值同组，可能空组；价差未扣费且不是实际组合净收益','股票池及可得时点均由底稿声明，不能证明退市、停牌及复权数据完整','当前模块不包含自动取数、订单、行业市值中性化或完整因子生产平台']}

    if 'schemaVersion' in spec:
        result['factorIdentity'] = identity(spec)
    return result

def trials(spec):
    rows=spec['trials'];cutoff=instant(spec['asOf']);ids=set();selected=[];failed=[]
    for r in rows:
        if not r.get('id') or r['id'] in ids:raise ValueError('试验ID须唯一，失败也保留')
        ids.add(r['id'])
        if instant(r['recordedAt'])>cutoff:raise ValueError('试验记录晚于复查截止')
        if r.get('status') not in {'completed','failed','blocked'} or not r.get('dataVersion') or not r.get('parameters') or not r.get('selectionRule'):raise ValueError('试验需状态、数据版本、参数和选择规则')
        if r.get('selected') is True:
            if r['status']!='completed':raise ValueError('不能选失败试验')
            selected.append(r['id'])
        if r['status']!='completed':failed.append(r['id'])
        if r.get('testTouchedDuringSelection') is not False:raise ValueError('需明确选型期间未查看测试集，未知不能标独立测试')
        train_end=date.fromisoformat(r['trainEnd']);test_start=date.fromisoformat(r['testStart'])
        if train_end>=test_start:raise ValueError('训练结束不早于测试开始')
        if date.fromisoformat(r['labelEnd'])>=test_start:raise ValueError('训练标签跨入测试区间，需清洗/隔离')
    return {'conclusion':'成功、失败和选型记录并列留存；试验次数只表示声明留档量，不能自动变成独立试验数或可信概率。','trialCount':len(rows),'selectedIds':selected,'failedOrBlockedIds':failed,'trials':rows,'humanRows':[['声明试验数',len(rows)],['失败或阻断数',len(failed)],['选择记录',', '.join(selected)]],'DSR':None,'realityCheck':None,'limitations':['不是完整回测框架或DSR/Reality Check实现','需试验相关性、收益矩及真正独立测试资料，不能只填尝试次数得到可信度','交易成本、幸存偏差和复权事件需要另核']}

if __name__=='__main__':
    from .factor_cli import main
    raise SystemExit(main())
