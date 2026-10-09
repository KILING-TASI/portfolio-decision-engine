from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from .validation import InputError, returns_frame, vector, weights


def xirr(flows):
    """Find sign-changing XIRR roots; flag multiple or absent roots."""
    dates, amounts = zip(*flows)
    times = np.array([(pd.Timestamp(d) - pd.Timestamp(dates[0])).total_seconds()/86400/365.25 for d in dates])
    amounts = np.asarray(amounts, float)
    if times.max() <= 0 or not (np.any(amounts > 0) and np.any(amounts < 0)):
        return {"status": "no_solution", "value": None}
    # Solve in log(1+r), allowing very large positive and near -100% rates.
    def fn(y):
        return float(amounts @ np.exp(np.clip(-y * times, -700, 700)))
    grid = np.linspace(-20, 20, 2001)
    roots = []
    for left, right in zip(grid[:-1], grid[1:]):
        a, b = fn(left), fn(right)
        if a == 0:
            roots.append(left)
        elif np.sign(a) != np.sign(b):
            roots.append(brentq(fn, left, right))
    roots = sorted(set(round(r, 10) for r in roots))
    return {"status": "ok" if len(roots)==1 else "multiple_solutions" if roots else "no_solution",
            "value": float(np.expm1(roots[0])) if len(roots)==1 else None,
            "roots": [float(np.expm1(r)) for r in roots], "search_log_rate_range": [-20,20]}


def rebalance_amounts(holdings, cash, target, rates):
    """Self-financing fractional-share rebalance with linear two-sided costs."""
    total = float(holdings.sum() + cash)
    def balance(net):
        return net + np.abs(target * net - holdings) @ rates - total
    if total <= 0 or balance(0) > 0:
        raise InputError("insufficient capital to pay transaction costs")
    net = brentq(balance, 0, total, xtol=max(1e-10, total*1e-12))
    delta = target * net - holdings
    fee = float(np.abs(delta) @ rates)
    return target * net, float(net*(1-target.sum())), delta, fee


@dataclass
class BacktestResult:
    daily: pd.DataFrame
    transactions: pd.DataFrame
    initial_value: float
    initial_date: pd.Timestamp
    irr: dict

    @property
    def returns(self):
        return self.daily["twr_return"]


def backtest(returns, target, initial_value=100000.0, costs=0.0001,
             rebalance="quarterly", threshold=0.2, cashflows=None,
             cash_return=0.0, flow_rule="target", initial_date=None, orders=None, target_schedule=None,
             initial_weights=None,rebalance_every_steps=None):
    """Return-based research ledger, not an exchange execution simulator.

    Cash flows and scheduled rebalances occur before each row's return.
    Orders are per-asset signed currency notionals before that row's return.
    """
    frame = returns_frame(returns)
    n = len(frame.columns)
    target, rates = weights(target, n), vector(costs, n, "costs", True)
    if np.any(rates >= 1) or initial_value <= 0 or not np.isfinite(initial_value):
        raise InputError("invalid capital or linear fee rate")
    if rebalance not in {"none", "monthly", "quarterly", "yearly", "threshold"}:
        raise InputError("unknown rebalance mode")
    if flow_rule not in {"target", "cash"} or not np.isfinite(threshold) or threshold <= 0:
        raise InputError("invalid cashflow rule or threshold")
    if not np.isfinite(cash_return) or cash_return <= -1:
        raise InputError("invalid cash return")
    if rebalance_every_steps is not None and (type(rebalance_every_steps) is not int or rebalance_every_steps<0):
        raise InputError("step rebalance must be a nonnegative integer")
    flows = pd.Series(0.0, index=frame.index)
    if cashflows is not None:
        supplied = pd.Series(cashflows, dtype=float)
        supplied.index = pd.to_datetime(supplied.index)
        if supplied.index.has_duplicates or not supplied.index.isin(frame.index).all() or not np.isfinite(supplied).all():
            raise InputError("cashflow dates must be unique observed dates with finite amounts")
        flows.loc[supplied.index] = supplied
    if orders is not None:
        if not isinstance(orders, pd.DataFrame) or orders.columns.tolist()!=frame.columns.tolist() or orders.index.has_duplicates:
            raise InputError("orders must have the same asset columns and unique dates")
        if not orders.index.isin(frame.index).all() or not np.isfinite(orders.to_numpy()).all():
            raise InputError("invalid orders or unobserved trade dates")
    if target_schedule is not None:
        if orders is not None or not isinstance(target_schedule,pd.DataFrame) or target_schedule.columns.tolist()!=frame.columns.tolist():
            raise InputError("target schedule requires matching asset columns and no explicit orders")
        if target_schedule.index.has_duplicates or not target_schedule.index.isin(frame.index).all():
            raise InputError("schedule dates must be unique observed dates")
        for proposed in target_schedule.to_numpy():
            weights(proposed,n)
    start = pd.Timestamp(initial_date) if initial_date is not None else frame.index[0]-pd.Timedelta(days=1)
    if start >= frame.index[0]:
        raise InputError("initial_date must precede first return")
    deployed=weights(initial_weights,n) if initial_weights is not None else np.zeros(n)
    holding, cash = deployed*initial_value, float(initial_value*(1-deployed.sum()))
    nav_unit, records, trades = 1.0, [], []
    investor_flows = [(start, -initial_value)]
    prev_period = None
    freq = {"monthly":"M", "quarterly":"Q", "yearly":"Y"}
    for k, (date, row) in enumerate(frame.iterrows()):
        before = float(holding.sum()+cash)
        flow = float(flows.loc[date])
        if before+flow <= 0:
            raise InputError("cashflow exhausts account")
        cash += flow
        fee, turnover = 0.0, 0.0
        if flow:
            investor_flows.append((date, -flow))
        if cash < 0:
            proceeds = float(holding @ (1-rates))
            fraction = -cash/proceeds if proceeds>0 else np.inf
            if fraction > 1:
                raise InputError("cannot fund withdrawal and fees")
            delta = -holding*fraction
            liquidation_cost = float(np.abs(delta)@rates)
            holding += delta
            cash += -delta.sum()-liquidation_cost
            fee += liquidation_cost
            turnover += float(np.abs(delta).sum())
            trades.append({"date":date,"reason":"withdrawal","notionals":delta.tolist(),"cost":liquidation_cost})
        period = date.to_period(freq[rebalance]) if rebalance in freq else None
        trigger = k==0 or (period is not None and prev_period is not None and period!=prev_period)
        if rebalance_every_steps is not None:
            trigger=k==0 or (rebalance_every_steps>0 and k%rebalance_every_steps==0)
        if rebalance=="threshold" and k>0:
            current = holding/(holding.sum()+cash)
            deviations = np.abs(current-target)/np.where(target>0,target,1)
            trigger = bool((deviations>threshold).any())
        if flow>0 and flow_rule=="target":
            trigger = True
        if target_schedule is not None and date in target_schedule.index:
            target=weights(target_schedule.loc[date].to_numpy(float),n)
            trigger=True
        if orders is None and trigger:
            holding,cash,delta,cost = rebalance_amounts(holding,cash,target,rates)
            fee += cost
            turnover += float(np.abs(delta).sum())
            trades.append({"date":date,"reason":"rebalance","notionals":delta.tolist(),"cost":cost})
        elif orders is not None:
            # Initial target is deployed equally in all counterfactual paths.
            if k==0:
                holding,cash,delta,cost = rebalance_amounts(holding,cash,target,rates)
                fee+=cost
                turnover+=float(np.abs(delta).sum())
                trades.append({"date":date,"reason":"initial","notionals":delta.tolist(),"cost":cost})
            if date in orders.index:
                delta = orders.loc[date].to_numpy(float)
                cost = float(np.abs(delta)@rates)
                if (holding+delta < -1e-8).any() or cash-delta.sum()-cost < -1e-8:
                    raise InputError("order would create short holdings or negative cash")
                holding += delta
                cash -= delta.sum()+cost
                fee+=cost
                turnover+=float(np.abs(delta).sum())
                trades.append({"date":date,"reason":"actual_order","notionals":delta.tolist(),"cost":cost})
        holding *= 1+row.to_numpy()
        cash *= 1+cash_return
        total = float(holding.sum()+cash)
        daily_return = total/(before+flow)-1
        nav_unit *= 1+daily_return
        records.append({"date":date,"value":total,"cash":cash,"external_flow":flow,
                        "cost":fee,"turnover_notional":turnover,"twr_return":daily_return,
                        "unit_nav":nav_unit, **{f"weight:{a}":float(holding[i]/total) for i,a in enumerate(frame.columns)}})
        prev_period = period
    investor_flows.append((frame.index[-1], records[-1]["value"]))
    return BacktestResult(pd.DataFrame(records).set_index("date"),pd.DataFrame(trades),initial_value,start,xirr(investor_flows))
