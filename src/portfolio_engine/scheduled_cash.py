# SPDX-License-Identifier: MIT
"""Preserved scheduled contribution accounting; no workbench dependency."""
import bisect,calendar,math
from datetime import date,timedelta
from .cash_scenario_validation import day,num,source,NOTICE

def schedule(start,end,frequency):
    start=date.fromisoformat(day(start));end=date.fromisoformat(day(end))
    if start>end:raise ValueError('起止日期倒置')
    if frequency not in ('weekly','monthly'):raise ValueError('周期须weekly或monthly')
    out=[];n=0
    while True:
        if frequency=='weekly':d=start+timedelta(days=7*n)
        else:
            m=start.year*12+start.month-1+n;y,m=divmod(m,12);m+=1
            d=date(y,m,min(start.day,calendar.monthrange(y,m)[1]))
        if d>end:break
        out.append(d.isoformat());n+=1
    return out

def xirr(flows):
    origin=date.fromisoformat(flows[0][0]);ts=[((date.fromisoformat(d)-origin).days/365.25,v) for d,v in flows]
    if ts[-1][0]<=0:return None
    def npv(r):
        exps=[-t*math.log1p(r) for t,v in ts];scale=max(exps)
        return sum(v*math.exp(e-scale) for (t,v),e in zip(ts,exps))
    lo=-.999999999;hi=1.
    while npv(hi)>0 and hi<1e8:hi=hi*2+1
    if npv(lo)<0 or npv(hi)>0:return None
    for _ in range(150):
        mid=(lo+hi)/2
        if npv(mid)>0:lo=mid
        else:hi=mid
    return (lo+hi)/2*100

def calculate(s):
    if not isinstance(s,dict):raise ValueError('定投输入须为对象')
    if not isinstance(s.get('history'),list) or any(not isinstance(row,dict) for row in s['history']):raise ValueError('净值历史须为观测对象列表')
    if not isinstance(s.get('plans'),list) or any(not isinstance(p,dict) or not isinstance(p.get('name'),str) or not p['name'].strip() for p in s['plans']):raise ValueError('定投方案须为具有名称的对象列表')
    day(s['asOf']);day(s['start']);day(s['end']);source(s['sourceUrl'])
    if s['end']>s['asOf']:raise ValueError('区间超过截止日')
    if s.get('eventCoverage') not in ('verified-complete','assumed-complete'):raise ValueError('须声明事件完整核验或完整性假设，未知不可计算')
    if not isinstance(s.get('eventEvidence'),str) or not s['eventEvidence'].strip():raise ValueError('须给出文字事件依据或假设说明')
    if not isinstance(s.get('events'),list):raise ValueError('须显式列出事件清单；无事件用空数组，不将缺失当作无分红')
    hs=s['history'];days=[];nav={}
    for row in hs:
        d=day(row['date']);num(row['nav'],True)
        if days and d<=days[-1] or d>s['asOf']:raise ValueError('净值乱序重复或晚于截止日')
        days.append(d);nav[d]=row['nav']
    if not days or days[0]>s['start'] or days[-1]<s['end']:raise ValueError('净值须覆盖起止日；不能默默缩短区间')
    endpos=bisect.bisect_right(days,s['end'])-1;valuation=days[endpos]
    def elapsed(a,b):return (date.fromisoformat(b)-date.fromisoformat(a)).days
    limits={}
    for key in ('maxScheduleDelayDays','maxValuationAgeDays'):
        v=s.get(key)
        if v is not None and (isinstance(v,bool) or not isinstance(v,int) or v<0):raise ValueError(key+'须为非负整数日数')
        limits[key]=v
    valuationAge=elapsed(valuation,s['end'])
    if limits['maxValuationAgeDays'] is not None and valuationAge>limits['maxValuationAgeDays']:raise ValueError('期末净值距截止日过久，超过估值门槛')
    events={}
    for e in s['events']:
        if not isinstance(e,dict):raise ValueError('事件须为结构化条目')
        if not any(key in e for key in ('cashPerOldUnit','newUnitsPerOldUnit')):raise ValueError('事件未披露分红或拆分数量，不默认无变化')
        d=day(e['date']);source(e['sourceUrl'])
        if d not in nav:raise ValueError('事件日无净值，不能猜测再投资价格')
        cash=num(e.get('cashPerOldUnit',0));split=num(e.get('newUnitsPerOldUnit',1),True)
        if cash<0 or d in events:raise ValueError('负分红或重复事件须先合并核对')
        reinvest=day(e.get('reinvestDate',d))
        if reinvest<d:raise ValueError('再投日期不得早于权益事件日')
        if reinvest<=valuation and reinvest not in nav:raise ValueError('再投日无净值，不能猜测成交价格')
        policy=e.get('distributionPolicy','unspecified')
        if policy not in ('cash-only','cash-or-reinvest','unspecified'):raise ValueError('分红方式须为cash-only/cash-or-reinvest/unspecified')
        if policy!='unspecified' and (not isinstance(e.get('policyEvidence'),str) or not e['policyEvidence'].strip()):raise ValueError('已声明分红方式须附原文依据说明')
        events[d]=(cash,split,reinvest,e['sourceUrl'],policy,e.get('policyEvidence'))
    plans=s['plans']
    if not plans or len(plans)>30 or len({p['name'] for p in plans})!=len(plans):raise ValueError('方案需唯一，最多30个')
    results=[]
    for p in plans:
        mode=p['mode'];distribution=p['distribution']
        if mode not in ('amount','units') or distribution not in ('reinvest','cash'):raise ValueError('金额/份额或分红方式无效')
        if distribution=='reinvest' and any(x[0]>0 and x[4]=='cash-only' and s['start']<=d<=valuation for d,x in events.items()):raise ValueError('公告声明仅现金分红，不支持作为红利再投方案；现金到账后再买入须另作交易模拟')
        amount=num(p['value'],True);fee=num(p.get('subscriptionFeePct',0))
        if not 0<=fee<=100:raise ValueError('申购费率无效')
        pending={};skipped=[];delays=[]
        for planned in schedule(s['start'],s['end'],p['frequency']):
            j=bisect.bisect_left(days,planned)
            if j> endpos:skipped.append(planned);continue
            delay=elapsed(planned,days[j])
            if limits['maxScheduleDelayDays'] is not None and delay>limits['maxScheduleDelayDays']:raise ValueError('计划投入顺延超过门槛，不能默认为正常成交')
            if delay:delays.append(dict(plannedDate=planned,executionDate=days[j],calendarDays=delay,reason='顺延至已有净值日；未认证为交易日历正常休市'))
            pending.setdefault(days[j],[]).append(planned)
        units=0.;cashbalance=0.;invested=0.;ledger=[];flows=[];path=[];fees=0.;reinvestPending={}
        for d in days:
            if d<s['start'] or d>valuation:continue
            if d in events:
                dividend,split,reinvest,eventSource,policy,policyEvidence=events[d];oldUnits=units;distributioncash=units*dividend;units*=split
                cashbalance+=distributioncash
                if distribution=='reinvest':reinvestPending[reinvest]=reinvestPending.get(reinvest,0)+distributioncash
                ledger.append(dict(kind='distribution-or-split',date=d,eligibleOldUnits=oldUnits,cashEntitlement=distributioncash,splitFactor=split,reinvestDate=reinvest if distribution=='reinvest' else None,sourceUrl=eventSource,distributionPolicy=policy,policyEvidence=policyEvidence,unitsAfter=units,cashAfter=cashbalance))
            reinvestcash=reinvestPending.pop(d,0)
            if reinvestcash:
                bought=reinvestcash/nav[d];units+=bought;cashbalance-=reinvestcash
                ledger.append(dict(kind='dividend-reinvestment',date=d,nav=nav[d],cashUsed=reinvestcash,purchasedUnits=bought,unitsAfter=units,cashAfter=cashbalance))
            for planned in pending.get(d,[]):
                if mode=='amount':gross=amount;net=gross/(1+fee/100);purchased=net/nav[d]
                else:purchased=amount;net=purchased*nav[d];gross=net*(1+fee/100)
                units+=purchased;invested+=gross;fees+=gross-net;flows.append((d,-gross))
                ledger.append(dict(kind='contribution',plannedDate=planned,date=d,scheduleDelayDays=elapsed(planned,d),nav=nav[d],grossContribution=gross,subscriptionFee=gross-net,purchasedUnits=purchased,totalUnits=units))
            path.append(dict(date=d,fundValue=units*nav[d],cashEntitlement=cashbalance,totalAssets=units*nav[d]+cashbalance,cumulativeContribution=invested))
        if not flows:raise ValueError('区间内没有可执行投入')
        final=units*nav[valuation]+cashbalance;flows.append((valuation,final))
        if not all(math.isfinite(value) for value in (final,invested,fees,units,cashbalance)):raise ValueError('定投数量或金额溢出')
        results.append(dict(name=p['name'],parameters=p,totalContribution=invested,endingFundValue=units*nav[valuation],endingCashEntitlement=cashbalance,endingTotalAssets=final,profit=final-invested,cumulativeReturnPct=(final/invested-1)*100,xirrPct=xirr(flows),periods=sum(x['kind']=='contribution' for x in ledger),subscriptionFees=fees,pendingReinvestment=[dict(date=k,cashEntitlement=v) for k,v in sorted(reinvestPending.items()) if v],skippedPlannedDates=skipped,scheduleDelays=delays,ledger=ledger,path=path))
    return dict(type='fund-dca-comparison',code=s['code'],asOf=s['asOf'],start=s['start'],requestedEnd=s['end'],valuationDate=valuation,valuationAgeDays=valuationAge,dateQualityLimits=limits,eventCoverage=s['eventCoverage'],eventEvidence=s['eventEvidence'],distributionPolicyStatus='all-input-declared' if events and all(x[4]!='unspecified' for x in events.values()) else 'not-fully-declared',eventVerificationStatus='input-declared-not-independently-verified' if s['eventCoverage']=='verified-complete' else 'explicit-completeness-assumption',sourceUrl=s['sourceUrl'],plans=results,riskNotice=NOTICE,limitations=['非交易日顺延至下个已取得净值日；无官方交易日历时不能证明净值无缺日','按当日净值成交，不模拟确认延迟、额度、最小金额、份额舍入及渠道限制','分红按输入事件日及当日投入前的份额确认权益；未提供再投日期时为当日理论再投，非真实登记确认。显式再投日期前保留无息权益，日期到达后按已有净值增加份额','现金分红及未完成再投保留为无息应收权益，不代表可用现金；拆分先处理再投入','净值已扣运作费用，不重复扣；期末按市值计量，未扣赎回费和税费，不是到手收益','XIRR采用实际日期及期末资产假设变现；同日或超求解范围留空','累计资产受追加资金影响，不用于直接计算账户最大回撤','方案投入总额可能不同，终值高不能直接判为更优；历史结果不代表未来'])
