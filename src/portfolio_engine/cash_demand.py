"""Date-level conditional cash needs; no automatic sale, probability, or execution."""
import datetime as dt
import hashlib
import json
import math

from .account_exposure import account_exposure, amount, evidence
from .disclosure_time import observation_day
from .validation import InputError

METHOD = "conditional-dated-cash-demand-v1"


def fraction(value, name):
    v = amount(value)
    if v > 1: raise InputError(name + " must be a fraction in [0,1]")
    return v


def cash_demand(spec):
    if not isinstance(spec, dict) or spec.get("schema") != "cash-demand-input-v1":
        raise InputError("cash-demand-input-v1 required")
    if spec.get("requested_method_version", METHOD) != METHOD: raise InputError("unsupported cash-demand method")
    account = account_exposure(spec["account"])
    start = observation_day(account["valuation_date"]); end = observation_day(spec["horizon_end"])
    if not 1 <= (end - start).days <= 3660: raise InputError("cash horizon must be 1..3660 days after valuation")
    positions = {p["position_id"]: p for p in account["root_positions"]}
    flows = spec.get("cashflows"); releases = spec.get("frozen_releases"); sales = spec.get("planned_liquidations")
    liquidity = spec.get("liquidity"); scenarios = spec.get("scenarios")
    if not all(isinstance(x, list) for x in [flows, releases, sales, scenarios]) or not isinstance(liquidity, dict) or not 1 <= len(scenarios) <= 10:
        raise InputError("declare cashflows, frozen releases, planned liquidations, liquidity and scenarios explicitly")
    if len(flows) + len(releases) + len(sales) > 10000: raise InputError("too many cash events")
    if set(liquidity) - positions.keys(): raise InputError("liquidity must refer to root account positions, not derived leaves")
    if any(positions[k]["kind"] == "cash" for k in liquidity): raise InputError("cash is not a liquidation asset; use frozen-release terms")
    ids = set(); economic_ids = set(); reserved = {}; release_reserved = {}
    for group in [flows, releases, sales]:
        for event in group:
            if not isinstance(event, dict): raise InputError("events must be objects")
            ident = evidence(event.get("id"), "cash event identity")
            econ = evidence(event.get("economic_event_id"), "economic cash event")
            if ident in ids or econ in economic_ids: raise InputError("duplicate economic event; release/sale proceeds must not be entered again as income")
            ids.add(ident); economic_ids.add(econ)
            evidence(event.get("source"), "cash event assumption")
    for f in flows:
        if f.get("kind") not in {"income", "necessary_expense"} or "position_id" in f:
            raise InputError("only external income/necessary expenses; account releases and sales belong to their own lists")
        if f.get("amount") is not None: amount(f["amount"])
        if f.get("date") is not None and not start < observation_day(f["date"]) <= end:
            raise InputError("cashflow dates must follow closing valuation and lie in the horizon")
    for release in releases:
        p = positions.get(release.get("position_id"))
        if p is None or p["kind"] != "cash": raise InputError("releases must refer to frozen root account cash")
        v = amount(release["amount"])
        key = p["position_id"]; release_reserved[key] = release_reserved.get(key, 0.) + v
        if release_reserved[key] > p["frozen_amount"]: raise InputError("release schedule exceeds original frozen cash")
        if release.get("condition_met") is not None and type(release["condition_met"]) is not bool: raise InputError("release condition must be true, false or unknown")
        evidence(release.get("condition"), "freeze release condition")
        if release.get("date") is not None and observation_day(release["date"]) <= start: raise InputError("release must follow closing valuation")
    for sale in sales:
        p = positions.get(sale.get("position_id"))
        if p is None or p["kind"] == "cash": raise InputError("only non-cash root positions can be planned for liquidation")
        v = amount(sale["book_amount"]); key = p["position_id"]
        reserved[key] = reserved.get(key, 0.) + v
        if reserved[key] > p["amount"]: raise InputError("planned sales exceed root book amount")
        if not start < observation_day(sale["trade_date"]) <= end: raise InputError("trade date outside forward horizon")
    for key, terms in liquidity.items():
        if not isinstance(terms, dict): raise InputError("liquidity terms must be objects")
        if set(terms) - {"can_sell", "haircut", "fee_rate", "fee_timing", "settlement_days", "settlement_day_basis", "earliest_sale_date", "source"}: raise InputError("unsupported liquidity term; do not ignore timing/fee assumptions")
        if terms.get("settlement_day_basis") not in {None, "calendar"}: raise InputError("only explicit calendar-day settlement assumptions supported")
        if terms.get("can_sell") is not None and type(terms["can_sell"]) is not bool: raise InputError("can_sell must be true, false or unknown")
        for field in ["haircut", "fee_rate"]:
            if terms.get(field) is not None: fraction(terms[field], field)
        delay = terms.get("settlement_days")
        if delay is not None and (type(delay) is not int or not 0 <= delay <= 3660): raise InputError("settlement_days must be explicit nonnegative calendar days or unknown")
        if terms.get("earliest_sale_date") is not None and observation_day(terms["earliest_sale_date"]) <= start: raise InputError("earliest sale must follow closing valuation")
    results = []; scene_ids = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict): raise InputError("scenario must be an object")
        if set(scenario) - {"id", "income_multiplier", "income_change_from", "additional_haircut", "settlement_delay_days", "freeze_release_enabled", "release_condition_overrides"}: raise InputError("unsupported pressure parameter; no probability forecast")
        sid = evidence(scenario.get("id"), "scenario identity")
        if sid in scene_ids: raise InputError("duplicate scenario")
        scene_ids.add(sid)
        factor = fraction(scenario["income_multiplier"], "income multiplier")
        if factor != 1 and scenario.get("income_change_from") is None: raise InputError("income pressure needs an explicit change date")
        extra = fraction(scenario["additional_haircut"], "additional haircut")
        delay = scenario["settlement_delay_days"]
        if type(delay) is not int or not 0 <= delay <= 3660: raise InputError("invalid pressure settlement delay")
        enabled = scenario.get("freeze_release_enabled")
        if type(enabled) is not bool: raise InputError("explicit freeze_release_enabled boolean required")
        interruption = observation_day(scenario["income_change_from"]) if scenario.get("income_change_from") else start + dt.timedelta(days=1)
        overrides = scenario.get("release_condition_overrides", {})
        if not isinstance(overrides, dict) or set(overrides) - {r["id"] for r in releases} or any(v is not None and type(v) is not bool for v in overrides.values()): raise InputError("invalid release overrides")
        ledger_events = {}; unknown = []; blocked = []; receivables = []; asset_values = []
        def insert(date, key, value):
            if date > end: return False
            row = ledger_events.setdefault(date, {"income": 0., "expense": 0., "release": 0., "sale_net": 0.})
            row[key] += value
            return True
        for f in flows:
            if f.get("amount") is None or f.get("date") is None:
                unknown.append({"id": f["id"], "kind": f["kind"], "reason": "unknown_cashflow_amount_or_date"}); continue
            date = observation_day(f["date"])
            value = f["amount"] * (factor if f["kind"] == "income" and date >= interruption else 1.)
            insert(date, "income" if f["kind"] == "income" else "expense", value)
        for release in releases:
            condition = overrides.get(release["id"], release.get("condition_met"))
            if not enabled or condition is False:
                blocked.append({"id": release["id"], "amount": release["amount"], "reason": "release_disabled_or_condition_false"}); continue
            if condition is None or release.get("date") is None:
                unknown.append({"id": release["id"], "amount": release["amount"], "reason": "unknown_release_condition_or_date"}); continue
            date = observation_day(release["date"])
            if not insert(date, "release", release["amount"]): receivables.append({"id": release["id"], "amount": release["amount"], "date": str(date), "reason": "release_after_horizon"})
        def sale_terms(key):
            terms = liquidity.get(key, {})
            missing = [k for k in ["can_sell", "haircut", "fee_rate", "settlement_days", "earliest_sale_date", "source"] if terms.get(k) is None]
            if terms.get("settlement_day_basis") != "calendar": missing.append("settlement_day_basis")
            if terms.get("fee_timing") != "deduct_from_settlement_proceeds": missing.append("fee_timing")
            if terms.get("can_sell") is False: return None, "explicitly_not_sellable"
            if missing or not isinstance(terms.get("source"), str) or not terms["source"].strip(): return None, "unknown_liquidity:" + ",".join(missing or ["source"])
            haircut = min(1., terms["haircut"] + extra)
            return {"net_factor": (1 - haircut) * (1 - terms["fee_rate"]), "haircut": haircut, "fee_rate": terms["fee_rate"], "delay": terms["settlement_days"] + delay, "earliest": observation_day(terms["earliest_sale_date"]), "source": terms["source"]}, None
        for key, p in positions.items():
            if p["kind"] == "cash": continue
            terms, reason = sale_terms(key)
            asset_values.append({"position_id": key, "book_amount": p["amount"], "conditional_net_liquidation_value": p["amount"] * terms["net_factor"] if terms else None,
                                 "remaining_unplanned_book_amount": p["amount"] - reserved.get(key, 0.), "liquidity_status": reason or "explicit_input_assumptions_only"})
        for sale in sales:
            terms, reason = sale_terms(sale["position_id"])
            if terms is None:
                (blocked if reason == "explicitly_not_sellable" else unknown).append({"id": sale["id"], "reason": reason}); continue
            trade = observation_day(sale["trade_date"])
            if trade < terms["earliest"]: raise InputError("planned sale precedes declared earliest sale date")
            arrival = trade + dt.timedelta(days=terms["delay"])
            net = sale["book_amount"] * terms["net_factor"]
            proceeds = {"id": sale["id"], "position_id": sale["position_id"], "book_amount": sale["book_amount"], "net_amount": net, "settlement_date": str(arrival), "haircut": terms["haircut"], "fee_rate": terms["fee_rate"]}
            proceeds["estimated_fee"] = sale["book_amount"] * (1 - terms["haircut"]) * terms["fee_rate"]
            if not insert(arrival, "sale_net", net): proceeds["reason"] = "not_available_within_horizon"
            receivables.append(proceeds)
        balance = account["cash"]["available_account_cash"]; frozen = account["cash"]["frozen_account_cash"]
        without_sales = balance; rows = []; first = None; peak = no_sale_peak = 0.
        for offset in range((end - start).days + 1):
            date = start + dt.timedelta(days=offset)
            e = ledger_events.get(date, {"income": 0., "expense": 0., "release": 0., "sale_net": 0.})
            opening = balance
            balance += e["income"] + e["release"] + e["sale_net"] - e["expense"]
            without_sales += e["income"] + e["release"] - e["expense"]
            frozen -= e["release"]
            if not math.isfinite(balance) or frozen < -1e-8: raise InputError("cash conservation overflow or negative frozen cash")
            gap = max(0., -balance)
            if gap > 0 and first is None: first = {"date": str(date), "amount": gap}
            peak = max(peak, gap); no_sale_peak = max(no_sale_peak, -without_sales)
            rows.append({"date": str(date), "opening_available_cash": opening, **e, "closing_available_cash_conditional": balance,
                         "remaining_frozen_cash": frozen, "unfunded_gap": gap, "balance_without_planned_sales": without_sales})
        candidates = []
        for asset in asset_values:
            terms, reason = sale_terms(asset["position_id"])
            arrive = terms["earliest"] + dt.timedelta(days=terms["delay"]) if terms else None
            timely = arrive <= observation_day(first["date"]) if first and arrive else None
            factor_net = terms["net_factor"] if terms else None
            needed = peak / factor_net if peak and factor_net and timely else None
            if needed is not None and not math.isfinite(needed): raise InputError("required liquidation book amount overflow")
            candidates.append({"position_id": asset["position_id"], "earliest_conditional_receipt_date": str(arrive) if arrive else None,
                               "in_time_for_first_gap": timely, "book_amount_for_peak_net_need": needed,
                               "remaining_book_amount": asset["remaining_unplanned_book_amount"], "sufficient_alone_under_assumptions": needed <= asset["remaining_unplanned_book_amount"] if needed is not None else None,
                               "reason": reason or "individual conditional comparison, not an automatic sale plan"})
        results.append({"id": sid, "parameters": scenario, "status": "conditional_with_unknowns" if unknown else "conditional_on_declared_inputs",
                        "complete_projection_status":"not_estimable_with_unknown_cash_events" if unknown else "conditional_arithmetic_only_not_execution_verified",
                        "complete_cash_balance": None if unknown else balance,
                        "first_gap": first, "peak_additional_net_cash_needed": peak, "net_liquidation_needed_without_planned_sales": max(0., no_sale_peak),
                        "gross_book_amount_required": None, "gross_amount_scope": "depends on which asset, discount, fees and timely settlement; individual comparisons only",
                        "closing_available_cash_conditional": balance, "closing_frozen_cash": frozen, "unknowns": unknown,
                        "blocked_events": blocked, "settlement_proceeds": receivables, "asset_liquidation_values": asset_values,
                        "additional_liquidity_comparisons": candidates, "daily_ledger": rows})
    return {"schema": "cash-demand-result-v1", "method_version": METHOD, "input_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
            "currency": account["currency"], "amount_unit": "base", "valuation_date": account["valuation_date"], "horizon_end": spec["horizon_end"],
            "data_kind": account["data_kind"], "opening_cash": account["cash"], "account_book_amount": account["total_amount"],
            "scenarios": results, "limitations": ["Conditional date-level arithmetic, not an executable liquidation plan or probability forecast",
                "Unknown cash amounts, dates and planned settlements are unresolved, not zero; reported balances and gaps only include resolved events",
                "Negative projected balance means unfunded need, not a loan or payment already executed",
                "Same-day receipts are assumed available for same-day expenses; intraday timing is not modeled",
                "Calendar-day settlement and fee deduction at receipt are explicit input assumptions, not exchange/fund settlement validation",
                "Root assets only; fund underlying assets and disclosed fund cash are not additional available account cash",
                "No insurance, tax planning, real account verification or trading instructions"]}
