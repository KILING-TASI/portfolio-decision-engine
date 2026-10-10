"""Full rolling M1 generation + M2 budget selection, followed by untouched tests."""
from collections import Counter
import hashlib

import numpy as np
import pandas as pd

from .allocation import allocate,estimate_covariance
from .backtest import backtest,BacktestResult,xirr
from .bootstrap import drawdown_budget
from .data_bridge import validate_context
from .risk import maximum_drawdown,summary
from .validation import InputError,returns_frame,weights


def _coverage(frame,frequency):
    out={}
    for year in [2015,2018]:
        rows=frame.loc[f"{year}-01-01":f"{year}-12-31"]
        out[str(year)]=(len(rows)==12 and rows.index[0].month==1 and rows.index[-1].month==12) if frequency=="monthly" else (
            len(rows)>=200 and rows.index[0]<=pd.Timestamp(f"{year}-01-10") and rows.index[-1]>=pd.Timestamp(f"{year}-12-20"))
    return out


def m2_walk_forward(returns,config):
    frame=returns_frame(returns);n=len(frame.columns)
    allowed_config={"data","periods_per_year","costs","seed","covariance_window","min_weight","max_weight","groups",
                    "bootstrap","require_china_bear_coverage","cashflows","initial_value","initial_weights","m2_walk_forward","input_kind"}
    if not isinstance(config,dict) or set(config)-allowed_config:raise InputError("unsupported configuration fields for M2 evaluation")
    meta=config.get("data",{})
    if not isinstance(meta,dict) or meta.get("return_type") not in {"total_return","synthetic_total_return"} or not meta.get("source") or not meta.get("currency"):
        raise InputError("M2 evaluation requires declared total return, source and currency")
    context=validate_context(frame,meta,config.get("periods_per_year"));periods=context["periods_per_year"]
    options=dict(config.get("m2_walk_forward",{}))
    allowed={"min_train","train_steps","validation_steps","test_steps","no_solution_policy","max_folds"}
    if set(options)-allowed:raise InputError("unknown M2 walk-forward option")
    min_train=options.get("min_train",752);step=options.get("test_steps",126);validation=options.get("validation_steps",0)
    train_steps=options.get("train_steps");max_folds=options.get("max_folds",20);policy=options.get("no_solution_policy","cash")
    if any(type(v) is not int or v<minimum for v,minimum in [(min_train,30),(step,10),(validation,0),(max_folds,1)]):
        raise InputError("invalid M2 window/count options")
    if train_steps is not None and (type(train_steps) is not int or train_steps<30):raise InputError("train_steps must be >=30 or null")
    if min_train-validation<30 or (validation and validation<30) or (train_steps is not None and train_steps-validation<30):
        raise InputError("each fitting and separate calibration window needs >=30 observations")
    if policy not in {"cash","previous_target"}:raise InputError("unknown no-solution policy")
    if len(frame)-min_train<10:raise InputError("not enough observations for M2 test window")
    boot=dict(config.get("bootstrap",{}));boot_allowed={"budget","horizon","paths","max_paths","block_lengths","rebalance_every","mc_tolerance","strict"}
    if set(boot)-boot_allowed:raise InputError("unknown bootstrap setting")
    if boot.get("horizon",step)!=step:raise InputError("M2 simulation horizon must equal test_steps for budget-break evaluation")
    boot["horizon"]=step
    interval=boot.get("rebalance_every",63 if periods==252 else 3)
    boot["rebalance_every"]=interval
    seed=config.get("seed",42)
    if type(seed) is not int or seed<0:raise InputError("invalid seed")
    initial_value=config.get("initial_value",100000)
    costs=config.get("costs",.0001)
    initial=weights(config.get("initial_weights",np.zeros(n)),n)
    flows=pd.Series(config.get("cashflows",{}),dtype=float)
    flows.index=pd.to_datetime(flows.index)
    if flows.index.has_duplicates or not flows.index.isin(frame.index[min_train:]).all() or not np.isfinite(flows).all():
        raise InputError("M2 cashflows must occur in the evaluation interval, not unmodeled pre-training history")
    folds=[];daily=[];trades=[];base_daily=[];base_trades=[]
    current_value=initial_value;current_weights=initial.copy();previous_target=initial.copy()
    base_value=initial_value;base_weights=initial.copy();last_baseline=None
    state_counter=Counter();selection_counter=Counter();eligible=0;breaches=0
    for fold_id,start in enumerate(range(min_train,len(frame),step)):
        if fold_id>=max_folds:break
        end=min(start+step,len(frame));train_start=max(0,start-train_steps) if train_steps is not None else 0
        prior=frame.iloc[train_start:start]
        fitted=prior.iloc[:-validation] if validation else prior
        calibration=prior.iloc[-validation:] if validation else prior
        sigma,cov_info=estimate_covariance(fitted,config.get("covariance_window",500))
        candidates=allocate(sigma,config.get("min_weight",0),config.get("max_weight",1),config.get("groups"))["candidates"]
        coverage=_coverage(calibration,context["frequency"])
        if config.get("require_china_bear_coverage",True) and not all(coverage.values()):
            screened={"status":"insufficient_data","selected":None,"reason":"risk calibration lacks complete 2015/2018 coverage"}
        elif not candidates:
            screened={"status":"infeasible","selected":None,"reason":"no feasible M1 candidates"}
        else:
            screened=drawdown_budget(calibration,candidates,costs=costs,seed=seed+fold_id*1009,periods=periods,
                                     initial_weights=current_weights,**boot)
        selected=screened.get("selected");state_counter[screened["status"]]+=1
        if selected:
            target=candidates[selected];selection_counter[selected]+=1;previous_target=target.copy()
        else:
            target=np.zeros(n) if policy=="cash" else previous_target.copy()
        baseline_name="equal_weight" if "equal_weight" in candidates else "constrained_equal_reference" if "constrained_equal_reference" in candidates else None
        baseline_target=candidates[baseline_name] if baseline_name else np.zeros(n)
        window=frame.iloc[start:end];window_flows=flows.loc[flows.index.isin(window.index)]
        actual=backtest(window,target,initial_value=current_value,costs=costs,rebalance="none",rebalance_every_steps=interval,
                        cashflows=window_flows,initial_weights=current_weights,initial_date=frame.index[start-1])
        baseline=backtest(window,baseline_target,initial_value=base_value,costs=costs,rebalance="none",rebalance_every_steps=interval,
                          cashflows=window_flows,initial_weights=base_weights,initial_date=frame.index[start-1])
        observed=maximum_drawdown(actual.returns)
        complete=len(window)==step
        violation=bool(observed>boot.get("budget",.25)) if selected and complete else None
        if violation is not None:eligible+=1;breaches+=int(violation)
        actual.daily["fold_id"]=fold_id;baseline.daily["fold_id"]=fold_id
        if not actual.transactions.empty:actual.transactions["fold_id"]=fold_id
        if not baseline.transactions.empty:baseline.transactions["fold_id"]=fold_id
        daily.append(actual.daily);trades.append(actual.transactions);base_daily.append(baseline.daily);base_trades.append(baseline.transactions)
        selected_result=screened.get("candidates",{}).get(selected) if selected else None
        folds.append({"fold_id":fold_id,"fit_start":str(fitted.index[0].date()),"fit_end":str(fitted.index[-1].date()),
            "calibration_start":str(calibration.index[0].date()),"calibration_end":str(calibration.index[-1].date()),
            "test_start":str(window.index[0].date()),"test_end":str(window.index[-1].date()),
            "fit_observations":len(fitted),"calibration_observations":len(calibration),"test_observations":len(window),
            "selection_status":screened["status"],"selection_reason":screened.get("reason"),"selected":selected,
            "target_weights":target,"initial_deployed_weights":current_weights,"candidate_weights":candidates,
            "selected_calibration":selected_result,"all_calibration_candidates":screened.get("candidates",{}),
            "coverage":coverage,"covariance":cov_info,"seed":seed+fold_id*1009,
            "decision_as_of":str(frame.index[start-1].date()),
            "freeze_kind":"replay target frozen for next test; not historical source archive evidence",
            "fit_sha256":hashlib.sha256(fitted.to_csv().encode()).hexdigest(),
            "calibration_sha256":hashlib.sha256(calibration.to_csv().encode()).hexdigest(),
            "test_max_drawdown":observed,"budget_breach":violation,"full_horizon_test":complete,
            "test_summary":summary(actual.returns,periods),"cost":float(actual.daily.cost.sum()),
            "turnover_notional":float(actual.daily.turnover_notional.sum()),"ending_cash":float(actual.daily.cash.iloc[-1]),
            "baseline_method":baseline_name,"baseline_summary":summary(baseline.returns,periods),
            "baseline_cost":float(baseline.daily.cost.sum()),"no_solution_action":None if selected else policy})
        current_value=float(actual.daily.value.iloc[-1]);base_value=float(baseline.daily.value.iloc[-1])
        current_weights=actual.daily.iloc[-1][[f"weight:{a}" for a in frame.columns]].to_numpy(float)
        base_weights=baseline.daily.iloc[-1][[f"weight:{a}" for a in frame.columns]].to_numpy(float)
        last_baseline=baseline_name
    initial_date=frame.index[min_train-1]
    def join(parts,transactions):
        ledger=pd.concat(parts);ledger["unit_nav"]=(1+ledger.twr_return).cumprod()
        records=[t for t in transactions if not t.empty]
        tx=pd.concat(records,ignore_index=True) if records else pd.DataFrame()
        all_flows=[(initial_date,-initial_value),*[(d,-float(v)) for d,v in flows.items() if d<=ledger.index[-1]],
                   (ledger.index[-1],float(ledger.value.iloc[-1]))]
        return BacktestResult(ledger,tx,initial_value,initial_date,xirr(all_flows))
    actual=join(daily,trades);baseline=join(base_daily,base_trades)
    failures=sum(f["selected"] is None for f in folds)
    result={"schema_version":"m2-walk-forward-v1","status":"degraded","data_quality":context,"inputs":config,
            "folds":folds,"selection_frequency":dict(selection_counter),"selection_status_counts":dict(state_counter),
            "no_solution_rate":failures/len(folds),"budget_breach_count":breaches,"budget_eligible_full_windows":eligible,
            "budget_breach_rate":breaches/eligible if eligible else None,"attempted_candidate_sets":len(folds),
            "actual":{**summary(actual.returns,periods),"cost":float(actual.daily.cost.sum()),"terminal_value":current_value,"irr":actual.irr},
            "baseline":{**summary(baseline.returns,periods),"cost":float(baseline.daily.cost.sum()),"terminal_value":base_value,"last_method":last_baseline},
            "baseline_comparable_all_windows":all(f["baseline_method"] is not None for f in folds),
            "turnover_notional":float(actual.daily.turnover_notional.sum()),"ending_cash":float(actual.daily.cash.iloc[-1]),
            "evaluation_complete":actual.daily.index[-1]==frame.index[-1],"no_solution_policy":policy,
            "purposes":{"fit":"covariance estimation and candidate generation before test",
                "validation":"separate pre-test calibration segment" if validation else "MC convergence/block sensitivity on fit data; not an independent validation sample",
                "test":"next non-overlapping observed window, never used to choose its frozen target"},
            "limitations":["all predeclared block lengths must pass; no post-test choice of best block",
                "continuous self-financing ledger with linear fees and declared flows; no live exchange fills",
                "bootstrap does not model future external cashflows; budget versus cashflow tests is descriptive",
                "input return/version truth not independently authenticated; not a full point-in-time market database",
                "one predeclared run is not multiple-testing correction or proof of risk control",
                "cash or previous_target fallback is a declared research policy, not an approved budget solution",
                "short final test windows excluded from budget breach rate; fold outcomes may remain dependent",
                "missing M1 baseline candidates use marked cash fallback; not labeled equivalent equal-weight results"]}
    return result,actual,baseline
