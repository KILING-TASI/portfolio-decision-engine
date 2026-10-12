# SPDX-License-Identifier: MIT
"""Original explicit candle rules and descriptive event study, standard library only."""
import statistics
from . import cnn_contract as c
from .review_io import instant,digest,cli

RULE_VERSION='original-candle-rules/1'
DEFAULTS=dict(dojiBodyMax=.1,smallBodyMax=.3,longBodyMin=.5,shadowBodyMin=2.,oppositeShadowMax=.1,
              trendRecords=3,trendReturnMin=.01,starPenetration=.5)
NAMES={'doji':'十字线','hammer':'锤头','hanging_man':'上吊线','inverted_hammer':'倒锤头',
       'shooting_star':'流星线','bullish_engulfing':'看涨吞没','bearish_engulfing':'看跌吞没',
       'morning_star':'晨星','evening_star':'暮星','three_white_soldiers':'三白兵','three_black_crows':'三只乌鸦'}
DIRECTION={'doji':0,'hammer':1,'hanging_man':-1,'inverted_hammer':1,'shooting_star':-1,
           'bullish_engulfing':1,'bearish_engulfing':-1,'morning_star':1,'evening_star':-1,
           'three_white_soldiers':1,'three_black_crows':-1}


def rules(spec):
    supplied=spec.get('patternParameters',{})
    if not isinstance(supplied,dict) or set(supplied)-set(DEFAULTS):raise ValueError('形态参数字段无效')
    p=dict(DEFAULTS,**supplied)
    c.integer(p['trendRecords'],3,64)
    for k in ('dojiBodyMax','smallBodyMax','longBodyMin','oppositeShadowMax','starPenetration'):
        if not 0<c.finite(p[k])<1:raise ValueError('比例参数须大于0且小于1')
    if not p['dojiBodyMax']<p['smallBodyMax']<p['longBodyMin']:raise ValueError('实体阈值顺序无效')
    if not 1<=c.finite(p['shadowBodyMin'])<=10 or not 0<c.finite(p['trendReturnMin'])<=.5:
        raise ValueError('影线或趋势阈值无效')
    return p


def candle(bar):
    o,h,l,close=[c.finite(bar[k]) for k in ('open','high','low','close')]
    span=h-l
    if span==0:return dict(body=0,upper=0,lower=0,span=0,bodyRatio=None,sign=0,o=o,close=close)
    body=abs(close-o)
    return dict(body=body,upper=h-max(o,close),lower=min(o,close)-l,span=span,
                bodyRatio=body/span,sign=1 if close>o else -1 if close<o else 0,o=o,close=close)


def inspect(row,p):
    bars=row['history'];cs=[candle(b) for b in bars];last=cs[-1]
    def trend(length):
        previous=bars[:-length]
        if len(previous)<p['trendRecords']:return None,None
        rs=previous[-p['trendRecords']:];value=rs[-1]['close']/rs[0]['close']-1
        return ('up' if value>=p['trendReturnMin'] else 'down' if value<=-p['trendReturnMin'] else 'flat'),value
    candidates=[]
    def add(code,geometry,length,expected):
        actual,value=trend(length)
        state='matched' if geometry and (expected is None or actual==expected) else (
            'context-unknown' if geometry and actual is None else 'context-not-matched' if geometry else 'not-matched')
        candidates.append(dict(pattern=code,name=NAMES[code],direction=DIRECTION[code],status=state,
                               geometryMatched=bool(geometry),patternRecords=length,requiredTrend=expected,
                               observedTrend=actual,precedingTrendReturn=value))
    nonzero=last['span']>0
    small=nonzero and p['dojiBodyMax']<last['bodyRatio']<=p['smallBodyMax']
    lower=small and last['lower']>=p['shadowBodyMin']*last['body'] and last['upper']/last['span']<=p['oppositeShadowMax']
    upper=small and last['upper']>=p['shadowBodyMin']*last['body'] and last['lower']/last['span']<=p['oppositeShadowMax']
    add('doji',nonzero and last['bodyRatio']<=p['dojiBodyMax'],1,None)
    for code,geometry,expected in [('hammer',lower,'down'),('hanging_man',lower,'up'),
                                  ('inverted_hammer',upper,'down'),('shooting_star',upper,'up')]:add(code,geometry,1,expected)
    a,b=cs[-2:]
    for code,sign,expected in [('bullish_engulfing',1,'down'),('bearish_engulfing',-1,'up')]:
        geometry=a['sign']==-sign and b['sign']==sign and b['body']>a['body'] and min(b['o'],b['close'])<=min(a['o'],a['close']) and max(b['o'],b['close'])>=max(a['o'],a['close'])
        add(code,geometry,2,expected)
    a,b,d=cs[-3:]
    for code,sign,expected in [('morning_star',1,'down'),('evening_star',-1,'up')]:
        # Strict body gap: do not silently substitute a no-gap mainland-market variant.
        gap=max(b['o'],b['close'])<min(a['o'],a['close']) if sign==1 else min(b['o'],b['close'])>max(a['o'],a['close'])
        penetration=d['close']>=a['close']+p['starPenetration']*a['body'] if sign==1 else d['close']<=a['close']-p['starPenetration']*a['body']
        geometry=a['sign']==-sign and d['sign']==sign and a['bodyRatio'] is not None and a['bodyRatio']>=p['longBodyMin'] and b['bodyRatio'] is not None and b['bodyRatio']<=p['smallBodyMax'] and gap and penetration
        add(code,geometry,3,expected)
    for code,sign,expected in [('three_white_soldiers',1,'down'),('three_black_crows',-1,'up')]:
        trio=cs[-3:]
        geometry=all(x['sign']==sign and x['bodyRatio'] is not None and x['bodyRatio']>=p['longBodyMin'] and (x['upper'] if sign==1 else x['lower'])/x['span']<=p['oppositeShadowMax'] for x in trio)
        geometry=geometry and all(sign*(trio[i]['close']-trio[i-1]['close'])>0 and min(trio[i-1]['o'],trio[i-1]['close'])<=trio[i]['o']<=max(trio[i-1]['o'],trio[i-1]['close']) for i in (1,2))
        add(code,geometry,3,expected)
    matched=[x['pattern'] for x in candidates if x['status']=='matched']
    signal=sum(DIRECTION[k] for k in matched)
    return dict(id=row['id'],security=row['security'],signalAt=row['signalAt'],lastCandle=last,
                matchedPatterns=matched,ruleSignal=1 if signal>0 else -1 if signal<0 else 0,
                checks=candidates,execution=row.get('cnExecution'),
                executionStatus=execution_status(row.get('cnExecution')))


def execution_status(value):
    if value is None:return 'unknown'
    if not isinstance(value,dict):raise ValueError('成交条件须明确对象')
    fields=('entryTradable','exitTradable','tPlusOneSatisfied','settlementAvailable','feesKnown')
    for key in fields:
        if value.get(key) is not None and type(value[key]) is not bool:raise ValueError('成交条件须布尔或未知')
    if any(value.get(k) is False for k in fields):return 'blocked-or-incomplete'
    if any(value.get(k) is None for k in fields):return 'unknown'
    c.text(value.get('source'),'成交条件依据')
    return 'declared-only-not-simulated'


def inputs(spec):
    # Outcomes cannot enter geometry or trend; identification permits unobserved labels.
    copy=dict(spec,samples=[{k:v for k,v in r.items() if k!='label'} for r in spec['samples']])
    rows,excluded=c.validate(copy,labels=False)
    if len(rows)>1000:raise ValueError('形态报告本轮最多1000个合格样本，请明确拆批并保留批次身份')
    original={r['id']:r for r in spec['samples']}
    return [original[r['id']] for r in rows],excluded,rules(spec)


def identify(spec):
    rows,excluded,p=inputs(spec);events=[inspect(row,p) for row in rows]
    return dict(methodVersion=RULE_VERSION,ruleVersion=RULE_VERSION,parameters=p,inputSha256=digest(spec),
                dataKind=spec['dataKind'],events=events,excluded=excluded,
                conclusion='按明确实体、影线、跳空和前置趋势规则识别；形态命中不代表上涨或可成交。',
                humanRows=[['资料性质','原创合成教学' if spec['dataKind']=='synthetic-teaching' else '声明历史底稿，未认证'],
                           ['检查样本',len(events)],['有命中样本',sum(bool(e['matchedPatterns']) for e in events)],['规则版本',RULE_VERSION],
                           ['成交条件未知',sum(e['executionStatus']=='unknown' for e in events)],
                           ['成交受限或资料不全',sum(e['executionStatus']=='blocked-or-incomplete' for e in events)],
                           ['全部条件仅人工声明',sum(e['executionStatus']=='declared-only-not-simulated' for e in events)]],
                limitations=['自定义原创阈值，不冒称复刻TA-Lib或第三方网站算法','形态可重叠，多个命中不是独立证据',
                             '趋势只使用形态发生前的记录；缺前置窗口保留未知','一字板零振幅不作为十字线；严格晨暮星保留跳空条件',
                             '成交声明不认证涨跌停、停牌、T+1、费用或到账，不输出交易建议'])


def study(spec):
    result=identify(spec);rows,_,_=inputs(spec)
    horizons=spec.get('studyHorizons',[spec['horizonRecords']])
    if not isinstance(horizons,list) or not 1<=len(horizons)<=8 or len(set(horizons))!=len(horizons):raise ValueError('统计期限须唯一列表')
    for h in horizons:c.integer(h,1,256)
    event_by_id={e['id']:e for e in result['events']};buckets={};omitted=[]
    for row in rows:
        outcomes=row.get('outcomes',[row['label']] if 'label' in row else [])
        if not isinstance(outcomes,list):raise ValueError('收益观察须列表')
        seen=set()
        for label in outcomes:
            h=c.integer(label['horizonRecords'],1,256)
            if h in seen:raise ValueError('同样本统计期限重复')
            seen.add(h)
            if not instant(row['signalAt'])<=instant(label['returnStartAt'])<instant(label['returnEndAt'])<=instant(label['availableAt']):raise ValueError('事件收益时点无效')
            y=c.finite(label['forwardReturn']);c.text(label.get('source'),'收益依据')
            if y<-1:raise ValueError('简单总收益不能小于-100%')
            if h not in horizons:continue
            if instant(label['availableAt'])>instant(spec['asOf']):
                omitted.append(dict(id=row['id'],horizonRecords=h,reason='截止后才可得'));continue
            benchmark=label.get('benchmarkReturn');excess=None
            if benchmark is not None:
                benchmark=c.finite(benchmark)
                if benchmark<-1:raise ValueError('基准总收益无效')
                c.text(label.get('benchmarkSource'),'基准依据')
                if label.get('benchmarkStartAt')!=label['returnStartAt'] or label.get('benchmarkEndAt')!=label['returnEndAt']:raise ValueError('基准收益窗口不一致')
                if not instant(label['returnEndAt'])<=instant(label['benchmarkAvailableAt'])<=instant(spec['asOf']):raise ValueError('基准可得时点无效')
                excess=y-benchmark
            for pattern in event_by_id[row['id']]['matchedPatterns']:
                buckets.setdefault((pattern,h),[]).append((row,y,excess,label,event_by_id[row['id']]['executionStatus']))
        for h in set(horizons)-seen:omitted.append(dict(id=row['id'],horizonRecords=h,reason='收益未知，未补零'))
    summary=[]
    for pattern in NAMES:
        for h in horizons:
            rs=buckets.get((pattern,h),[]);ys=[r[1] for r in rs];xs=[r[2] for r in rs if r[2] is not None]
            summary.append(dict(pattern=pattern,name=NAMES[pattern],horizonRecords=h,sampleCount=len(rs),
                                meanGrossReturn=statistics.mean(ys) if ys else None,medianGrossReturn=statistics.median(ys) if ys else None,
                                positiveReturnFraction=sum(v>0 for v in ys)/len(ys) if ys else None,
                                signalAlignedFraction=sum(DIRECTION[pattern]*v>0 for v in ys)/len(ys) if ys and DIRECTION[pattern] else None,
                                worstObservedGrossReturn=min(ys) if ys else None,bestObservedGrossReturn=max(ys) if ys else None,
                                meanBenchmarkExcess=statistics.mean(xs) if xs else None,benchmarkKnownCount=len(xs),
                                missingBenchmarkCount=len(rs)-len(xs),sampleIds=[r[0]['id'] for r in rs],
                                executionCounts={k:sum(r[4]==k for r in rs) for k in ('unknown','blocked-or-incomplete','declared-only-not-simulated')}))
    result.update(methodVersion='pattern-gross-event-study/1',summary=summary,omittedOutcomes=omitted,
                  conclusion='按形态及声明期限描述毛收益；正收益比例与方向符合比例分开，尚非扣费后胜率或策略表现。')
    populated=[r for r in summary if r['sampleCount']]
    result['humanRows']+=[['有收益观察的形态期限组',len(populated)],['排除或缺失收益记录',len(omitted)]]
    for r in populated[:12]:
        aligned='未知' if r['signalAlignedFraction'] is None else f"{r['signalAlignedFraction']:.1%}"
        result['humanRows'].append([f"{r['name']} · {r['horizonRecords']}条记录",
            f"样本{r['sampleCount']}；毛收益中位数{r['medianGrossReturn']:.2%}；正收益{r['positiveReturnFraction']:.1%}；方向符合{aligned}；已知基准{r['benchmarkKnownCount']}"])
    if len(populated)>12:result['humanRows'].append(['其余统计组','展开完整结果查看，未按收益排序筛选'])
    result['limitations']+=['所有命中事件均保留，不按事后涨跌停或收益筛选；重复和重叠事件未作独立性认证',
                           '期限是声明记录数，不自动等同交易日；缺收益、基准或成交条件保留未知',
                           '极值是事件观察收益，不是路径最大回撤；无显著性、概率校准或净收益认证']
    return result


def feature_channels(row):
    """Five causal geometry channels, each computed without future bars."""
    bars=row['history'];channels=[[] for _ in range(5)]
    for i,bar in enumerate(bars):
        x=candle(bar);span=x['span']
        values=[(bar['close']-bar['open'])/span if span else 0,x['upper']/span if span else 0,
                x['lower']/span if span else 0,bar['open']/bars[i-1]['close']-1 if i else 0,
                bar['close']/bars[max(0,i-2)]['close']-1]
        for channel,v in zip(channels,values):channel.append(c.finite(v))
    return channels


def main(argv=None):
    import sys
    old=sys.argv[:]
    try:
        if argv is not None:sys.argv=['portfolio-decision-engine pattern',*argv]
        return cli({'identify':identify,'study':study},'K线形态与事件复查')
    finally:sys.argv[:]=old


if __name__=='__main__':raise SystemExit(main())
