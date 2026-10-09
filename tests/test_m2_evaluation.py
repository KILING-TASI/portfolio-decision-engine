import copy
import json

import numpy as np
import pandas as pd
import pytest

from portfolio_engine.archive import verify
from portfolio_engine.backtest import backtest
from portfolio_engine.bootstrap import path_metrics,stationary_indices
from portfolio_engine.cli import main
from portfolio_engine.m2_evaluation import m2_walk_forward
from portfolio_engine.risk import maximum_drawdown
from portfolio_engine.validation import InputError


def sample(length=150):
    return pd.DataFrame(np.random.default_rng(5).normal(.0003,.004,(length,2)),index=pd.bdate_range("2020-01-01",periods=length),columns=["a","b"])


def configuration():
    return {"data":{"return_type":"synthetic_total_return","source":"test","currency":"CNY","frequency":"daily"},
        "require_china_bear_coverage":False,"costs":.001,"initial_value":100,
        "bootstrap":{"paths":100,"max_paths":100,"horizon":30,"block_lengths":[5,10],"rebalance_every":10,"budget":.9,"mc_tolerance":.05},
        "m2_walk_forward":{"min_train":60,"test_steps":30,"max_folds":3,"no_solution_policy":"cash"}}


def test_m2_regenerates_and_screens_each_fold_without_future_leakage():
    data=sample();config=configuration();first,_,_=m2_walk_forward(data,config)
    changed=data.copy();changed.iloc[60:90]+=0.2
    second,_,_=m2_walk_forward(changed,config)
    a,b=first["folds"][0],second["folds"][0]
    assert a["selected"]==b["selected"]
    assert a["target_weights"]==pytest.approx(b["target_weights"])
    assert a["calibration_sha256"]==b["calibration_sha256"]
    assert a["decision_as_of"]<a["test_start"]
    assert a["fit_end"]<a["test_start"] and a["calibration_end"]<a["test_start"]
    assert len(first["folds"])==3
    for f in first["folds"]:
        assert f["all_calibration_candidates"]
        for value in f["all_calibration_candidates"].values():
            assert {row["block_length"] for row in value["blocks"]}=={5,10}


def test_continuous_ledger_matches_single_scheduled_account_with_flows():
    data=sample();config=configuration()
    config["cashflows"]={str(data.index[85].date()):20,str(data.index[115].date()):-10}
    result,actual,baseline=m2_walk_forward(data,config)
    schedule=pd.DataFrame([f["target_weights"] for f in result["folds"]],index=[pd.Timestamp(f["test_start"]) for f in result["folds"]],columns=data.columns)
    reference=backtest(data.iloc[60:],schedule.iloc[0].to_numpy(),initial_value=100,costs=.001,
        rebalance="none",rebalance_every_steps=10,cashflows=config["cashflows"],target_schedule=schedule,initial_date=data.index[59])
    assert actual.daily.value.to_numpy()==pytest.approx(reference.daily.value.to_numpy(),abs=1e-7)
    assert actual.daily.unit_nav.to_numpy()==pytest.approx(reference.daily.unit_nav.to_numpy(),abs=1e-9)
    assert actual.daily.cost.sum()==pytest.approx(reference.daily.cost.sum())
    assert actual.daily.index.equals(baseline.daily.index)
    assert actual.daily.external_flow.equals(baseline.daily.external_flow)


def test_no_solution_stays_recorded_and_cash_liquidation_paid_once():
    data=sample();data-=.02;config=configuration();config["bootstrap"]["budget"]=.000001
    config["initial_weights"]=[.5,.5]
    result,actual,_=m2_walk_forward(data,config)
    assert result["no_solution_rate"]==1
    assert all(f["selected"] is None for f in result["folds"])
    assert all(f["no_solution_action"]=="cash" for f in result["folds"])
    assert result["budget_eligible_full_windows"]==0 and result["budget_breach_rate"] is None
    assert actual.daily.cost.iloc[0]==pytest.approx(.1)
    assert actual.daily.cost.iloc[1:].sum()==pytest.approx(0)
    assert actual.daily.value.iloc[-1]==pytest.approx(99.9)


def test_train_validation_test_purposes_and_coverage_refusal():
    config=configuration();config["m2_walk_forward"]["validation_steps"]=30
    result,_,_=m2_walk_forward(sample(),config)
    assert result["folds"][0]["fit_end"]<result["folds"][0]["calibration_start"]
    assert "separate" in result["purposes"]["validation"]
    config["require_china_bear_coverage"]=True
    result,_,_=m2_walk_forward(sample(),config)
    assert result["selection_status_counts"]=={"insufficient_data":3}
    assert result["no_solution_rate"]==1


def test_short_final_window_and_compute_cap_are_not_hidden():
    result,_,_=m2_walk_forward(sample(137),configuration())
    assert not result["folds"][-1]["full_horizon_test"]
    assert result["folds"][-1]["budget_breach"] is None
    config=configuration();config["m2_walk_forward"]["max_folds"]=1
    limited,_,_=m2_walk_forward(sample(),config)
    assert not limited["evaluation_complete"]
    assert len(limited["folds"])==1


def test_horizon_conflict_and_unmodeled_inputs_rejected():
    config=configuration();config["bootstrap"]["horizon"]=60
    with pytest.raises(InputError,match="equal test_steps"):m2_walk_forward(sample(),config)
    config=configuration();config["orders_csv"]="not-supported"
    with pytest.raises(InputError,match="unsupported"):m2_walk_forward(sample(),config)


def test_bootstrap_warm_start_matches_fee_ledger():
    data=sample(40);indices=stationary_indices(40,3,40,5,2)
    metrics=path_metrics(data.to_numpy(),indices,[.4,.6],costs=.01,rebalance_every=10,initial_weights=[.9,.1])
    for i in range(3):
        sampled=pd.DataFrame(data.to_numpy()[indices[i]],index=data.index,columns=data.columns)
        path=backtest(sampled,[.4,.6],initial_value=1,costs=.01,rebalance="none",rebalance_every_steps=10,initial_weights=[.9,.1])
        assert metrics["terminal_nav"][i]==pytest.approx(path.daily.value.iloc[-1],abs=1e-9)
        assert metrics["mdd"][i]==pytest.approx(maximum_drawdown(path.returns),abs=1e-9)


def test_m2_cli_creates_distinct_evaluation_and_manifest(tmp_path):
    out=tmp_path/"m2"
    assert main(["m2-demo","--fast","--out",str(out)])==0
    result=json.loads((out/"m2-evaluation.json").read_text(encoding="utf8"))
    assert result["schema_version"]=="m2-walk-forward-v1"
    assert len(result["folds"])==3
    assert (out/"actual-ledger.csv").exists()
    assert (out/"baseline-ledger.csv").exists()
    assert verify(out)["status"]=="stored_content_verified"
