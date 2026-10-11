# SPDX-License-Identifier: MIT
"""Factor rebalance cash demands reuse the existing conditional cash ledger."""
import copy
from .cash_demand import cash_demand
from .disclosure_time import observation_day
from .factor_contract import finite, identity, stamp, text, unique_rows, status_label
from .review_io import digest, instant


def cashfit(spec):
    identity(spec)
    declared = copy.deepcopy(spec['cashDemand'])
    if observation_day(declared['account']['as_of']) > observation_day(spec['asOf']):
        raise ValueError('现金底稿截至日晚于因子审查截至日')
    baseline = cash_demand(declared)
    plans = unique_rows(spec['rebalanceCashNeeds'], 'id')
    execution_unknowns = []
    for identifier, plan in plans.items():
        text(plan.get('source'), '调仓资金 source')
        if instant(plan['availableAt']) > instant(spec['asOf']):
            raise ValueError('调仓计划晚于审查截至日')
        if plan.get('canTrade') is not None and type(plan['canTrade']) is not bool:
            raise ValueError('canTrade 须为布尔或null')
        if plan.get('canTrade') is not True:
            execution_unknowns.append({'id': identifier, 'reason': '交易不可执行或可成交条件未知'})
        amount = plan.get('amount')
        if amount is not None:
            finite(amount, '新增现金净流出', 0)
        # Only new external cash requirements are inserted; sale receipts remain
        # in planned_liquidations to avoid double counting settled funds.
        if plan.get('scope') != 'additional_cash_outflow_not_in_baseline':
            raise ValueError('须确认新增资金需求未重复计入现金底稿；卖出到账沿用planned_liquidations')
        declared['cashflows'].append({'id': 'factor:' + identifier,
                                     'economic_event_id': text(plan.get('economicEventId'), 'economicEventId'),
                                     'source': plan['source'], 'kind': 'necessary_expense',
                                     'date': plan.get('date'), 'amount': amount})
    adjusted = cash_demand(declared)
    scenes = []
    for before, after in zip(baseline['scenarios'], adjusted['scenarios']):
        gaps = [{'date': r['date'], 'amount': r['unfunded_gap']} for r in after['daily_ledger'] if r['unfunded_gap'] > 0]
        unknowns = after['unknowns'] + execution_unknowns
        scenes.append({'id': after['id'], 'status': 'unknown' if unknowns else 'conditional_on_declared_inputs',
                       'conflictDates': None if unknowns else [r['date'] for r in gaps],
                       'conditionalKnownGaps': gaps, 'conflictAmount': None if unknowns else after['peak_additional_net_cash_needed'],
                       'additionalPeakNeedVersusBaseline': None if unknowns or before['unknowns'] else max(0, after['peak_additional_net_cash_needed'] - before['peak_additional_net_cash_needed']),
                       'unknowns': unknowns, 'dailyLedger': after['daily_ledger'],
                       'options': [{'kind': kind, 'status': 'not_evaluated', 'cost': None, 'executionDate': None,
                                    'reason': reason} for kind, reason in (
                           ('defer', '需可成交日历、到账规则及替代日期价格，未据当前底稿推断延后天数'),
                           ('scale', '需可拆单和最小交易量约束，未自动缩放'),
                           ('skip', '需明确放弃交易后的持仓和价格路径，未估机会成本'))]})
    return stamp(spec, {'status': 'unknown' if any(s['unknowns'] for s in scenes) else 'conditional_on_declared_inputs',
                       'conclusion': '调仓资金需求已接入既有现金账本；未知到账或成交条件不会被记成无冲突。',
                       'cashDemandInputSha256': digest(spec['cashDemand']), 'scenarios': scenes,
                       'humanRows': [[s['id'], status_label(s['status'])] for s in scenes],
                       'limitations': adjusted['limitations'] + ['新增资金流出是假设需求，不表示成交已经发生',
                                                                '本动作提供资金冲突核对；方案代价缺少价格与执行资料时保持未知']}, 'cashfit')
