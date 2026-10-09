from importlib.metadata import version
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from . import __version__
from .allocation import allocate,estimate_covariance,black_litterman
from .attribution import brinson,factor_attribution,trade_counterfactual
from .backtest import backtest
from .bootstrap import drawdown_budget,sharpe_interval
from .io import load_returns
from .evaluation import walk_forward,rolling_holding_periods
from .migration import plan_migration
from .risk import summary,concentration
from .stress import historical_stress
from .validation import InputError,returns_frame,vector,weights
from .data_bridge import validate_context,closing_premium,lookthrough
from .archive import read_json
from .decision import decision_summary


def run_engine(returns,config,snapshot_id="in_memory",base_dir=None):
    frame=returns_frame(returns)
    if not isinstance(config,dict):
        raise InputError("config must be an object")
    allowed_config={"data","periods_per_year","train_fraction","costs","seed","risk_free_annual",
                    "covariance_window","min_weight","max_weight","groups","black_litterman","bootstrap",
                    "require_china_bear_coverage","cashflows","initial_value","rebalance","threshold","flow_rule",
                    "current_holdings","current_cash","new_funds","locked_indices","migration_penalty",
                    "brinson","factor_csv","orders_csv","initial_weights","input_kind","walk_forward","premium_file","lookthrough_file"}
    if set(config)-allowed_config:
        raise InputError(f"unknown config fields: {sorted(set(config)-allowed_config)}")
    metadata=config.get("data",{})
    if metadata.get("return_type") not in {"total_return","synthetic_total_return"}:
        raise InputError("declare data.return_type: total_return or synthetic_total_return; adjusted prices alone are insufficient")
    if not metadata.get("source") or not metadata.get("currency"):
        raise InputError("declare data source and common currency")
    n=len(frame.columns)
    data_quality=validate_context(frame,metadata,config.get("periods_per_year"))
    periods=data_quality["periods_per_year"]
    if not isinstance(periods,int) or periods<=0:
        raise InputError("periods_per_year must be a positive integer")
    fraction=config.get("train_fraction",.7)
    if not 0.2<=fraction<=.9:
        raise InputError("train_fraction must be between .2 and .9")
    split=int(len(frame)*fraction)
    if split<30 or len(frame)-split<10:
        raise InputError("need >=30 training and >=10 held-out observations")
    train,test=frame.iloc[:split],frame.iloc[split:]
    fees=vector(config.get("costs",.0001),n,"costs",True)
    seed=config.get("seed",42)
    if not isinstance(seed,int) or seed<0:
        raise InputError("seed must be a nonnegative integer")
    risk_free=config.get("risk_free_annual",0.0)
    if not np.isfinite(risk_free) or risk_free<=-1:
        raise InputError("invalid risk free rate")
    sigma,cov_report=estimate_covariance(train,config.get("covariance_window",500))
    allocation=allocate(sigma,config.get("min_weight",0.0),config.get("max_weight",1.0),config.get("groups"))
    candidates=allocation["candidates"]
    warnings=["Return-based fractional research model: exchange fills, fund settlement, taxes by date, premium and integer lots are not modeled.",
              "M2 is exploratory training selection; held-out comparison is a single split, not full walk-forward verification."]
    if data_quality["calendar_status"]=="not_provided":
        warnings.append("Frequency spacing checked; applicable observation calendar not supplied or verified.")
    if metadata["return_type"]=="synthetic_total_return":
        warnings.append("SYNTHETIC DATA: all returns, scenarios and results are demonstration only.")
    if cov_report["observations"]<config.get("covariance_window",500):
        warnings.append("Covariance uses fewer observations than requested window.")
    if cov_report["shrinkage"]>.5 or n/cov_report["observations"]>.1:
        warnings.append("Covariance is sensitive to shrinkage assumptions or high dimensionality.")
    if not candidates:
        return {"schema_version":"0.4","engine_version":__version__,"status":allocation["status"],
                "modules":{"M1":allocation},"warnings":warnings,"data_snapshot_id":snapshot_id},None
    bl=None
    if config.get("black_litterman"):
        views=config["black_litterman"]
        if views.get("frequency","daily")!=data_quality["frequency"]:
            raise InputError("BL view frequency must match return data")
        if not views.get("sources") or len(views["sources"])!=len(views["Q"]):
            raise InputError("BL needs one source per view")
        bl=black_litterman(sigma,views["market_weights"],views["P"],views["Q"],views["Omega"],views.get("tau",.05),views.get("risk_aversion",3))
        bl["sources"]=views["sources"]
        bl_allocation=allocate(bl["predictive_covariance"],config.get("min_weight",0),config.get("max_weight",1),config.get("groups"),
                            expected_returns=bl["mean"],risk_aversion=views.get("risk_aversion",3))
        if "black_litterman_utility" in bl_allocation["candidates"]:
            candidates["black_litterman_utility"]=bl_allocation["candidates"]["black_litterman_utility"]
        # Risk-only methods retain their original covariance; BL is a separate candidate.
        allocation["candidates"]=candidates
        allocation["bl_solver_failures"]=bl_allocation["failures"]
        warnings.append("BL views match the input return frequency and are user inputs, not model-generated forecasts.")
    boot=dict(config.get("bootstrap",{}))
    allowed={"budget","horizon","paths","block_lengths","rebalance_every","mc_tolerance","max_paths","strict"}
    if set(boot)-allowed:
        raise InputError(f"unknown bootstrap options: {sorted(set(boot)-allowed)}")
    budget_report=drawdown_budget(train,candidates,costs=fees,seed=seed,periods=periods,**boot)
    coverage={}
    for year in [2015,2018]:
        rows=train.loc[f"{year}-01-01":f"{year}-12-31"]
        if data_quality["frequency"]=="monthly":
            coverage[str(year)]=len(rows)==12 and rows.index[0].month==1 and rows.index[-1].month==12
        else:
            coverage[str(year)]=len(rows)>=200 and rows.index.min()<=pd.Timestamp(f"{year}-01-10") and rows.index.max()>=pd.Timestamp(f"{year}-12-20")
    if config.get("require_china_bear_coverage",True) and not all(coverage.values()):
        budget_report["status"]="insufficient_data"
        budget_report["exploratory_candidate"]=budget_report["selected"]
        budget_report["selected"]=None
        warnings.append("Training window does not cover complete 2015 and 2018: no approved drawdown-budget selection.")
    budget_report["historical_coverage"]=coverage
    frontier=[]; highest_score=-np.inf
    for name,row in sorted(budget_report["candidates"].items(),key=lambda item:item[1]["worst_p95"]):
        if row["score"]>highest_score:
            frontier.append({"method":name,"p95":row["worst_p95"],"score":row["score"]})
            highest_score=row["score"]
    budget_report["empirical_candidate_frontier"]=frontier
    if metadata["return_type"]=="synthetic_total_return" and budget_report["selected"]:
        budget_report["status"]="degraded"
    # Report a comparison reference when budget rejected, never substitute it as a solution.
    reference=budget_report["selected"] or next(iter(candidates))
    w=candidates[reference]
    historical={}; out_of_sample={}
    for name,target in candidates.items():
        full_path=backtest(frame,target,costs=fees,rebalance="quarterly")
        historical[name]={**summary(full_path.returns,periods,risk_free),"cost":float(full_path.daily.cost.sum()),
                          "comparison_scope":"full-history fixed weights estimated from training; descriptive, not OOS"}
        path=backtest(test,target,costs=fees,rebalance="quarterly")
        out_of_sample[name]={**summary(path.returns,periods,risk_free),"cost":float(path.daily.cost.sum())}
    flows=None
    if config.get("cashflows"):
        flows=pd.Series(config["cashflows"],dtype=float)
    path=backtest(frame,w,initial_value=config.get("initial_value",100000),costs=fees,
                  rebalance=config.get("rebalance","quarterly"),threshold=config.get("threshold",.2),cashflows=flows,
                  flow_rule=config.get("flow_rule","target"))
    threshold_path=backtest(frame,w,initial_value=config.get("initial_value",100000),costs=fees,
                            rebalance="threshold",threshold=config.get("threshold",.2),cashflows=flows,flow_rule=config.get("flow_rule","target"))
    calendar_path=backtest(frame,w,initial_value=config.get("initial_value",100000),costs=fees,
                           rebalance="quarterly",cashflows=flows,flow_rule=config.get("flow_rule","target"))
    risk={**summary(path.returns,periods,risk_free),**concentration(w,sigma),
          "sharpe_bootstrap":sharpe_interval(path.returns,paths=500,seed=seed,periods=periods,risk_free=risk_free),
          "irr":path.irr,"scope":"reference strategy; not a budget solution when M2.selected is null"}
    risk["historical_holding_periods"]=rolling_holding_periods(path.returns,periods)
    if risk["tail95"]["tail_mass_observations"]<30:
        warnings.append("ES95 is based on fewer than 30 tail observations; ES90 is supplied for comparison.")
    migration={"status":"insufficient_data","reason":"current_holdings not supplied"}
    if "current_holdings" in config:
        migration={mode:plan_migration(config["current_holdings"],w,cash=config.get("current_cash",0),
                   new_funds=config.get("new_funds",0),costs=fees,locked=config.get("locked_indices"),mode=mode,
                   penalty=config.get("migration_penalty",1.0)) for mode in ["buy_only","minimum_trade","one_step"]}
        if budget_report["selected"] is None:
            migration["warning"]="Illustrative migration to comparison reference; M2 returned no budget solution."
        current=np.asarray(config["current_holdings"],float)
        current_total=current.sum()+config.get("current_cash",0)
        for plan in migration.values():
            if not isinstance(plan,dict) or plan.get("status")!="ok":continue
            final_weights=np.asarray(plan["final_weights"])
            current_weights=current/current_total if current_total>0 else np.zeros(n)
            plan["risk_change"]={"current_annual_volatility":float(np.sqrt(current_weights@sigma@current_weights*periods)),
                "final_annual_volatility":float(np.sqrt(final_weights@sigma@final_weights*periods)),
                "target_annual_volatility":float(np.sqrt(w@sigma@w*periods)),
                "scope":"same training covariance estimate, not forecast or actual account drawdown",
                "budget_status":"not_revalidated_after_migration"}
    attribution={"status":"insufficient_data","reason":"segment history/factors not supplied"}
    provenance_files={}
    if config.get("brinson"):
        attribution={"brinson":brinson(**config["brinson"])}
    if config.get("factor_csv"):
        factor_path=Path(base_dir or ".")/config["factor_csv"]
        factors,_=load_returns(factor_path)
        # Factors can have long-short returns; load_returns rejects <=-100%.
        if not factors.index.equals(frame.index):
            raise InputError("factor CSV dates must exactly match portfolio dates")
        excess=path.returns-((1+risk_free)**(1/periods)-1)
        attribution["factor"]=factor_attribution(excess,factors)
        attribution.pop("status",None); attribution.pop("reason",None)
        provenance_files["factors_sha256"]=hashlib.sha256(factor_path.read_bytes()).hexdigest()
    trade={"status":"insufficient_data","reason":"complete orders CSV not supplied"}
    if config.get("orders_csv"):
        order_path=Path(base_dir or ".")/config["orders_csv"]
        orders=pd.read_csv(order_path,parse_dates=["date"]).set_index("date")
        initial=weights(config.get("initial_weights",w),n)
        trade=trade_counterfactual(frame,initial,orders,cashflows=flows,costs=fees,initial_value=config.get("initial_value",100000),periods=periods)
        provenance_files["orders_sha256"]=hashlib.sha256(order_path.read_bytes()).hexdigest()
    baseline="equal_weight" if "equal_weight" in candidates else "constrained_equal_reference"
    baseline_score=out_of_sample.get(baseline,{}).get("cagr")
    outperform=out_of_sample[reference]["cagr"]>baseline_score if baseline_score is not None else None
    modules={"M1":{"allocation":allocation,"covariance":cov_report,"black_litterman":bl},
             "M2":budget_report,"M3":attribution,"M4":migration,"M5":historical_stress(frame,w,costs=fees,periods=periods),
             "M6":trade,"M7":risk}
    supplemental={}
    for field,calculator in [("premium_file",closing_premium),("lookthrough_file",lookthrough)]:
        if config.get(field):
            file=Path(base_dir or ".")/config[field]
            supplemental[field.removesuffix("_file")]=calculator(read_json(file))
            provenance_files[field+"_sha256"]=hashlib.sha256(file.read_bytes()).hexdigest()
    wf_config=config.get("walk_forward",{})
    if not isinstance(wf_config,dict) or set(wf_config)-{"min_train","test_steps"}:
        raise InputError("walk_forward allows min_train and test_steps")
    wf=walk_forward(frame,covariance_window=config.get("covariance_window",500),
                    lower=config.get("min_weight",0),upper=config.get("max_weight",1),groups=config.get("groups"),
                    costs=fees,periods=periods,**wf_config)
    report={"schema_version":"0.4","engine_version":__version__,"status":"degraded",
            "data_snapshot_id":snapshot_id,"data_quality":data_quality,"supplemental":supplemental,"inputs":config,"assets":frame.columns.tolist(),
            "sample":{"start":str(frame.index[0].date()),"end":str(frame.index[-1].date()),
                      "train_end":str(train.index[-1].date()),"test_start":str(test.index[0].date())},
            "modules":modules,"reference_method":reference,"historical_comparison":historical,
            "out_of_sample_comparison":out_of_sample,"baseline_comparison":{"method":baseline,"reference_outperforms_cagr":outperform,
               "conclusion":"Single held-out window; no proof of persistent optimization value."},"walk_forward":wf,
            "rebalance_comparison":{name:{**summary(p.returns,periods,risk_free),"cost":float(p.daily.cost.sum()),
                                    "turnover_notional":float(p.daily.turnover_notional.sum())} for name,p in
                                    [("quarterly",calendar_path),("threshold",threshold_path)]},
            "warnings":warnings,"constraints_hit":[budget_report["status"]] if budget_report["status"]!="ok" else [],
            "confidence":"unassessed","assumptions":["constant linear two-sided fees; fractional units; zero cash yield",
                  "flows and predetermined trades before row return; supplied data calendar",
                  "bootstrap step-based rebalancing differs from dated historical calendar"],
            "provenance":{"seed":seed,"library_versions":{name:version(name) for name in
                           ["numpy","pandas","scipy","scikit-learn","statsmodels"]},**provenance_files}}
    report["decision_summary"]=decision_summary(report)
    return report,path
