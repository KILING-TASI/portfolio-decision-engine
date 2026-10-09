"""Narrow explicit workbench path contract, not a replacement for its reports."""
import datetime as dt
import hashlib
import json

import numpy as np
import pandas as pd

from .backtest import backtest
from .risk import maximum_drawdown
from .validation import InputError


INPUT_SCHEMA="workbench-buy-hold-input-v1"
OUTPUT_SCHEMA="workbench-buy-hold-result-v1"


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()


def compatible_history(spec):
    if not isinstance(spec,dict) or spec.get("schema_version")!=INPUT_SCHEMA:
        raise InputError("explicit workbench-buy-hold-input-v1 contract required")
    common={"schema_version":OUTPUT_SCHEMA,"method_version":"buy-hold-zero-fee-v1","input_sha256":canonical_hash(spec)}
    def unsupported(reason):
        return {**common,"status":"unsupported_not_equivalent","reason":reason,"unknown_policy":"not_imputed"},None
    if isinstance(spec.get("cost_rate"),bool) or spec.get("cost_rate")!=0 or spec.get("external_cashflows")!=[]:
        return unsupported("only explicitly zero costs and no external cashflows are supported")
    if spec.get("amount_unit")!="base":return unsupported("declare a common base currency amount unit")
    payload=spec.get("payload")
    if not isinstance(payload,dict):raise InputError("legacy payload must be an object")
    supported_payload={"baseCurrency","asOf","historicalPortfolioMode","minimumObservations","holdings","windows","scenarios"}
    if set(payload)-supported_payload:return unsupported("additional legacy fields need a separate explicit migration contract")
    if payload.get("windows") or payload.get("scenarios"):return unsupported("window/scenario reports are outside this first path contract")
    if payload.get("historicalPortfolioMode")!="buy-and-hold":return unsupported("other rebalance/portfolio modes are not migrated")
    currency=payload.get("baseCurrency")
    if not isinstance(currency,str) or not currency.strip():raise InputError("common currency required")
    cutoff=dt.date.fromisoformat(payload["asOf"])
    rows=payload.get("holdings")
    if not isinstance(rows,list) or not rows:raise InputError("holdings required")
    codes=[];values=[];histories=[];sources=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("code"),str) or not row["code"] or row["code"] in codes:
            raise InputError("unique asset identity required")
        if row.get("currency")!=currency or row.get("basis")!="total-return":raise InputError("common currency and declared total-return required")
        if not isinstance(row.get("sourceUrl"),str) or not row["sourceUrl"].strip():raise InputError("source reference required")
        value=row["marketValue"]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or value<=0:
            raise InputError("positive finite market values required")
        history=row.get("history")
        if not isinstance(history,list) or not history:return unsupported("missing history is not filled or treated as zero")
        observed={}
        for observation in history:
            day=observation["date"];date=dt.date.fromisoformat(day)
            if date.isoformat()!=day or date>cutoff or day in observed:raise InputError("future, duplicate or invalid observation date")
            number=observation["value"]
            if isinstance(number,bool) or not isinstance(number,(int,float)) or not np.isfinite(number) or number<=0:
                raise InputError("positive finite total-return index required")
            observed[day]=number
        dates=sorted(observed)
        if histories and dates!=histories[0][0]:return unsupported("unequal dates/intersection or disconnected-path behavior needs a separate contract")
        codes.append(row["code"]);values.append(value);histories.append((dates,observed))
        sources.append({"code":row["code"],"source_reference":row["sourceUrl"],"currency":currency,"basis":"total-return",
                        "period_end":payload["asOf"],"published_at":row.get("publishedAt"),"retrieved_at":row.get("retrievedAt"),
                        "available_at":row.get("availableAt"),"source_verification":"input_declared_not_verified"})
    minimum=payload.get("minimumObservations",60)
    if type(minimum) is not int or minimum<3:raise InputError("minimumObservations must be an integer >=3")
    dates=histories[0][0]
    if len(dates)-1<minimum:
        return {**common,"status":"insufficient_data","reason":"same declared minimum observation rule","unknown_policy":"not_imputed"},None
    weights=np.asarray(values,float)/sum(values)
    prices=pd.DataFrame({code:[history[d] for d in dates] for code,(_,history) in zip(codes,histories)},index=pd.to_datetime(dates))
    returns=prices.pct_change(fill_method=None).iloc[1:]
    path=backtest(returns,weights,initial_value=1,costs=0,rebalance="none",initial_date=prices.index[0])
    wealth=np.r_[1,path.daily.unit_nav.to_numpy()]
    contributions=weights*(prices.iloc[-1].to_numpy()/prices.iloc[0].to_numpy()-1)
    result={**common,"status":"calculated_supported_subset","payload_sha256":canonical_hash(payload),
            "currency":currency,"amount_unit":"base","cost_rate":0.0,"external_cashflows":[],
            "date_normalization":"sort unique input dates, as in the legacy path; no intersection or filling",
            "source_records":sources,"unknown_policy":"no imputation; unknown holdings are outside this path contract",
            "compatible_fields":{"totalReturnPct":float((wealth[-1]-1)*100),
                "maximumDrawdownPct":-maximum_drawdown(path.returns)*100,
                "returnContributions":[{"code":code,"contributionPp":float(v*100)} for code,v in zip(codes,contributions)],
                "path":[{"date":date,"wealth":float(v)} for date,v in zip(dates,wealth)]},
            "native_fields":{"total_return_fraction":float(wealth[-1]-1),"maximum_drawdown_loss_fraction":maximum_drawdown(path.returns)},
            "equivalence_status":"not_checked_without_same-input_legacy_reference",
            "not_migrated":["peak/trough tie date rules","rolling/correlation/tail/scenario outputs","costs, trades and cashflow review","report prose and evidence verification"],
            "limitations":["input market amounts define assumed initial weights, not verified historical holdings",
                "total return and source times are declarations; no dividend/version authentication",
                "no rounding before calculation; percent/fraction and negative/positive MDD translations explicit"]}
    return result,path


def compare_legacy_reference(result,reference):
    if result.get("status")!="calculated_supported_subset":return {"status":"not_compared","reason":result.get("reason")}
    if reference.get("payload_sha256")!=result["payload_sha256"]:
        return {"status":"input_mismatch","reason":"reference does not bind the identical legacy payload"}
    expected=reference["compatible_fields"];actual=result["compatible_fields"]
    problems=[];deltas={}
    for key in ["totalReturnPct","maximumDrawdownPct"]:
        delta=abs(actual[key]-expected[key]);deltas[key]=delta
        if delta>1e-8:problems.append(key)
    if [p["date"] for p in actual["path"]]!=[p["date"] for p in expected["path"]]:problems.append("path_dates")
    else:
        delta=max(abs(a["wealth"]-b["wealth"]) for a,b in zip(actual["path"],expected["path"]))
        deltas["maximum_wealth_difference"]=delta
        if delta>1e-10:problems.append("wealth")
    left={r["code"]:r["contributionPp"] for r in actual["returnContributions"]}
    right={r["code"]:r["contributionPp"] for r in expected["returnContributions"]}
    if set(left)!=set(right):problems.append("contribution_assets")
    elif max(abs(left[k]-right[k]) for k in left)>1e-8:problems.append("contributions")
    return {"status":"matched_supported_subset" if not problems else "not_equivalent","problems":problems,"differences":deltas,
            "percent_point_tolerance":1e-8,"wealth_tolerance":1e-10,"reference_method":reference.get("reference_method"),
            "scope":"one declared zero-cost buy-and-hold subset only; not full workbench replacement"}
