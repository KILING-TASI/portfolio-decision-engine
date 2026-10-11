# SPDX-License-Identifier: MIT
"""Keep research spreads distinct from a declared long-only cash ledger."""
from .factor_contract import finite, identity, stamp, text, unique_rows, percent, status_label
from .factor_research import panel, ranks
from .review_io import instant, digest


def series(spec):
    identity(spec)
    result = panel(spec)
    periods = []
    plans = []
    previous_end = None
    overlap = False
    cutoff = instant(spec['asOf'])
    for daily in result['daily']:
        rows = [r for r in spec['rows'] if r['signalDate'] == daily['signalDate'] and instant(r['returnAvailableAt']) <= cutoff]
        first = rows[0]
        start, end = instant(first['returnStartAt']), instant(first['returnEndAt'])
        overlap |= previous_end is not None and start < previous_end
        previous_end = max(previous_end, end) if previous_end else end
        ranked = ranks([finite(r['factor'], 'factor') for r in rows])
        buckets = {i: [] for i in range(1, spec['groups'] + 1)}
        for rank, row in zip(ranked, rows):
            buckets[min(spec['groups'], int((rank - 1) * spec['groups'] / len(rows)) + 1)].append(row['security'])
        plans.append({'signalDate': daily['signalDate'], 'groups': {
            str(group): {security: 1 / len(members) for security in members}
            for group, members in buckets.items()}, 'scope': '分层研究权重，不是可执行订单'})
        periods.append({**daily, 'returnStartAt': first['returnStartAt'], 'returnEndAt': first['returnEndAt'],
                        'returnAvailableAt': max(rows, key=lambda r: instant(r['returnAvailableAt']))['returnAvailableAt']})
    return stamp(spec, {'conclusion': '逐期毛价差已整理；账户净值须另用完整持仓、成交及资金底稿计算。',
                       'series': periods, 'researchGroupPlans': plans, 'overlappingWindows': overlap,
                       'accountNetSeries': None, 'cumulative': None, 'maxDrawdown': None,
                       'excluded': result['excluded'], 'panelInputSha256': digest(spec),
                       'humanRows': [['研究期数', len(periods)], ['收益窗口重叠', overlap], ['账户净值', '未知：毛价差不是账户收益']],
                       'limitations': result['limitations'] + ['重叠远期收益不能按日连乘；多空价差未指定资金分母与融券条件']}, 'series')


def ledger(spec, rate_override=None):
    """Explicit currency amounts, start-of-period orders, no external cash flows.

    Gross and net paths use identical fixed signed notionals. Cash funds costs;
    positions drift with declared total returns. No short or leveraged execution.
    """
    identity(spec)
    account = spec['account']
    if not isinstance(account, dict) or not isinstance(account.get('initialHoldings'), dict):
        raise ValueError('账户与初始持仓须为对象')
    if account.get('mode') != 'long-only-fixed-notional' or account.get('cashReturn') != 0:
        raise ValueError('账户须声明 long-only-fixed-notional 及 cashReturn=0')
    text(account.get('currency'), 'currency')
    if account.get('externalFlows') != []:
        raise ValueError('本账本只支持明确无外部现金流；有现金流须使用既有账户回测')
    if account.get('settlementMode') != 'same-start-tradable-proceeds':
        raise ValueError('须声明卖出资金可用于同一期初交易的结算假设；未知到账不能当可用现金')
    text(account.get('settlementSource'), '结算依据 settlementSource')
    holdings = {k: finite(v, '初始持仓金额', 0) for k, v in account['initialHoldings'].items()}
    for key in holdings:
        text(key, 'security')
    cash = finite(account['initialCash'], '初始可用现金', 0)
    initial = cash + sum(holdings.values())
    if initial <= 0:
        raise ValueError('初始账户资金须大于0')
    raw_rate = account.get('costBps') if rate_override is None else rate_override
    rate = None if raw_rate is None else finite(raw_rate, '单边费用bps', 0, 9999) / 10000
    periods = account['periods']
    if not isinstance(periods, list) or not periods or len(periods) > 10000:
        raise ValueError('账户收益期不能为空')
    cutoff = instant(spec['asOf'])
    previous = None
    checked = []
    missing = []
    for index, period in enumerate(periods):
        if not isinstance(period, dict) or not isinstance(period.get('assetReturns'), dict):
            raise ValueError('收益期与证券收益须为对象')
        start, end = instant(period['startAt']), instant(period['endAt'])
        if end <= start or (previous is not None and start != previous):
            raise ValueError('账户窗口须严格连续且不重叠；空档现金收益不能默认补0')
        previous = end
        if instant(period['availableAt']) < end or instant(period['availableAt']) > cutoff:
            raise ValueError('账户收益可得时点无效或晚于截至日')
        text(period.get('source'), '账户收益 source')
        returns = {k: finite(v, '持仓总收益', -1) for k, v in period['assetReturns'].items()}
        trades = unique_rows(period['trades'])
        for security, trade in trades.items():
            finite(trade['notional'], '成交金额')
            if instant(trade['tradeAt']) != start:
                raise ValueError('本账本仅支持期初交易，不能用期中交易冒充整期持有')
            text(trade.get('source'), '交易条件 source')
            if instant(trade['availableAt']) > start:
                raise ValueError('交易条件晚于交易时点，存在前视')
            if trade.get('canTrade') is not True:
                if trade.get('canTrade') is not None and type(trade['canTrade']) is not bool:
                    raise ValueError('canTrade 须为布尔或null')
                missing.append({'period': index, 'security': security, 'reason': '不可成交或交易条件未知'})
        checked.append((period, returns, trades))
    if missing:
        return {'status': 'blocked_or_unknown', 'periods': [], 'accountNetSeries': None,
                'grossCumulative': None, 'netCumulative': None, 'maxDrawdown': None, 'unknowns': missing}
    gross_cash, net_cash = cash, cash if rate is not None else None
    gross_nav = net_nav = high = 1.0
    mdd = 0.0
    records = []
    for period, returns, trades in checked:
        opening_gross = gross_cash + sum(holdings.values())
        opening_net = None if net_cash is None else net_cash + sum(holdings.values())
        finite(opening_gross, '账户资金', 0)
        turnover_amount = sum(abs(finite(t['notional'], '成交金额')) for t in trades.values())
        trade_net = sum(finite(t['notional'], '成交金额') for t in trades.values())
        for security, trade in trades.items():
            next_amount = holdings.get(security, 0) + finite(trade['notional'], '成交金额')
            if next_amount < -1e-8:
                raise ValueError('卖出超过持仓；本账本不支持空头或借券')
            holdings[security] = max(0, next_amount)
        gross_cash -= trade_net
        fee = None if rate is None else turnover_amount * rate
        if net_cash is not None:
            net_cash -= trade_net + fee
        if gross_cash < -1e-8 or (net_cash is not None and net_cash < -1e-8):
            raise ValueError('可用现金不足以支付成交及费用；不自动借款或缩单')
        unknown = [security for security, value in holdings.items() if value > 0 and security not in returns]
        if unknown:
            return {'status': 'unknown', 'periods': records, 'accountNetSeries': None,
                    'grossCumulative': None, 'netCumulative': None, 'maxDrawdown': None,
                    'unknowns': [{'reason': '持仓收益缺失', 'securities': unknown}]}
        holdings = {security: value * (1 + returns.get(security, 0)) for security, value in holdings.items()}
        gross_total = gross_cash + sum(holdings.values())
        net_total = None if net_cash is None else net_cash + sum(holdings.values())
        finite(gross_total, '账户期末资金', 0)
        if net_total is not None:
            finite(net_total, '账户期末净资金', 0)
        if gross_total <= 0 or (net_total is not None and net_total <= 0):
            raise ValueError('账户资金耗尽，不能继续生成收益路径')
        gross_return = gross_total / opening_gross - 1
        net_return = None if net_total is None else net_total / opening_net - 1
        gross_nav = gross_total / initial
        if net_total is not None:
            net_nav = net_total / initial
            high = max(high, net_nav)
            mdd = max(mdd, 1 - net_nav / high)
        records.append({'startAt': period['startAt'], 'endAt': period['endAt'],
                        'availableAt': period['availableAt'], 'absoluteTradedAmount': turnover_amount,
                        'twoWayTurnoverOnOpeningGrossEquity': turnover_amount / opening_gross,
                        'costAmount': fee, 'grossReturn': gross_return, 'netReturn': net_return,
                        'grossEquity': gross_total, 'netEquity': net_total,
                        'netAvailableCash': net_cash, 'driftedHoldings': dict(holdings)})
    return {'status': 'conditional_on_declared_inputs' if rate is not None else 'unknown_cost',
            'periods': records, 'accountNetSeries': None if rate is None else [r['netReturn'] for r in records],
            'grossCumulative': gross_nav - 1, 'netCumulative': None if rate is None else net_nav - 1,
            'maxDrawdown': None if rate is None else mdd, 'unknowns': [] if rate is not None else [{'reason': '费用未声明'}]}


def cost(spec):
    result = ledger(spec)
    sensitivity = []
    for bps in spec.get('costBpsRange', []):
        outcome = ledger(spec, finite(bps, '敏感性bps', 0, 9999))
        sensitivity.append({'costBps': bps, 'status': outcome['status'], 'netCumulative': outcome['netCumulative']})
    return stamp(spec, {**result, 'sensitivity': sensitivity,
                       'conclusion': '按声明的固定成交金额核算账户毛净收益；未扣费或不可成交时保留未知。',
                       'humanRows': [['状态', status_label(result['status'])], ['毛累计收益', percent(result['grossCumulative'])], ['净累计收益', percent(result['netCumulative'])]],
                       'limitations': ['账户只支持只多、无杠杆、无外部现金流、期初固定金额成交；现金收益明确为0',
                                       '单边费用乘买卖绝对成交额，已包含买卖两侧；费用只扣一次',
                                       '未建模期中交易、税率变化、滑点、融券及自动权重再平衡；这些费用须计入声明费率或使用完整回测',
                                       '卖出资金同一期初可交易是明确的输入结算假设，不认证所有证券或基金的实际到账规则',
                                       '账户底稿是独立声明路径，不自动证明复现了 panel 的分层策略']}, 'cost')
