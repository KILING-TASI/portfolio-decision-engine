# SPDX-License-Identifier: MIT
"""Preserved dated exit cash accounting; no workbench dependency."""
from .cash_scenario_validation import context,value,date_value
from .scheduled_cash import xirr

def field(row,key,s):
 x=row.get(key)
 if x is None:return None
 if x.get('unit',s['unit'])!=s['unit']:raise ValueError('数量或金额单位不同')
 return value(x,s['asOf'])

def exit_cash(s):
 asof=context(s);cases=s['scenarios']
 if not 1<=len(cases)<=20 or len({c['name'] for c in cases})!=len(cases):raise ValueError('需1至20个不同名称情景')
 out=[]
 for case in cases:
  if case.get('costCoverage') not in ['declared-complete','partial'] or case.get('cashFlowCoverage') not in ['declared-complete','partial']:raise ValueError('需分别声明现金流与费用税收覆盖')
  if case.get('currency',s['currency'])!=s['currency'] or case.get('unit',s['unit'])!=s['unit']:raise ValueError('现金流币种或单位不一致')
  ledger=[];bydate={};totals={k:0. for k in ['investment','proceeds','distribution','fee','tax']}
  for row in case['flows']:
   day=date_value(row['date']);kind=row['kind']
   if kind not in totals:raise ValueError('未知现金流类别')
   if day>asof and row['amount']['basis']!='assumption':raise ValueError('未来现金流须明确假设')
   amount=field(row,'amount',s)
   if amount is None or amount<0:raise ValueError('现金流金额需非负，方向由类别定义')
   signed=amount if kind in ['proceeds','distribution'] else -amount;bydate[day]=bydate.get(day,0)+signed;totals[kind]+=amount;ledger.append(dict(date=day,kind=kind,amount=amount,signed=signed,basis=row['amount']['basis']))
  if totals['investment']<=0:raise ValueError('需正投入')
  kinds={r['kind'] for r in ledger}
  if case['costCoverage']=='declared-complete' and not {'fee','tax'}<=kinds:raise ValueError('完整费用声明需显式费用和税收，包括明确零假设')
  chronological=sorted(bydate.items());nonzero=[(d,v) for d,v in chronological if abs(v)>1e-12];signs=[1 if v>0 else -1 for d,v in nonzero];changes=sum(a!=b for a,b in zip(signs,signs[1:]));conventional=bool(signs and signs[0]<0 and signs[-1]>0 and changes==1)
  receipts=totals['proceeds']+totals['distribution'];costs=totals['fee']+totals['tax'];complete=case['costCoverage']=='declared-complete' and case['cashFlowCoverage']=='declared-complete';rate=xirr(nonzero) if conventional and complete else None
  out.append(dict(name=case['name'],route=case.get('route','未指定'),ledger=sorted(ledger,key=lambda r:r['date']),aggregatedFlows=chronological,totals=totals,knownCashChange=receipts-totals['investment']-costs,grossRecoveryMultiple=receipts/totals['investment'],netRecoveryMultiple=(receipts-costs)/totals['investment'] if complete else None,xirrPct=rate,annualizationStatus='calculated' if rate is not None else ('cashflow-or-costs-incomplete' if not complete else 'same-day-or-nonconventional-or-root-outside-range'),costCoverage=case['costCoverage'],cashFlowCoverage=case['cashFlowCoverage'],firstDate=chronological[0][0],lastDate=chronological[-1][0]))
 return dict(type='dated-exit-cash-scenarios',scenarios=out,formulas=['已知现金变化=回收及分配-投入-已知费用税收','扣费用回收倍数=(回收及分配-费用税收)/投入','XIRR用实际日期及365.25日年长，同日现金流先合并'],limitations=['费用完整性是输入声明，未独立核验实际税负或交易渠道','现金流或费用税收缺项不填零，不输出净回收倍数或年化','非传统多次正负切换可能多根，年化留空；总现金变化不因此丢弃','退出时间和回收额为情景假设，不承诺IPO、并购或转让能实现','未自动计入借款、外汇、资金占用、流动性限制或监管窗口，不生成退出指令'])
