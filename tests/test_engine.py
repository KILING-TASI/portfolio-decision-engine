import json

import numpy as np
import pandas as pd
import pytest
from sklearn.covariance import LedoitWolf

from portfolio_engine.allocation import allocate,estimate_covariance,risk_contributions,black_litterman
from portfolio_engine.attribution import brinson,factor_attribution,trade_counterfactual
from portfolio_engine.backtest import backtest,xirr
from portfolio_engine.bootstrap import stationary_indices,path_metrics,drawdown_budget,quantile_interval
from portfolio_engine.cli import main
from portfolio_engine.engine import run_engine
from portfolio_engine.evaluation import walk_forward,rolling_holding_periods
from portfolio_engine.io import load_returns
from portfolio_engine.migration import plan_migration
from portfolio_engine.risk import maximum_drawdown,expected_shortfall,concentration,cf_quantile
from portfolio_engine.stress import historical_stress,rate_shock
from portfolio_engine.validation import InputError,returns_frame


def frame(x,columns=None,start="2020-01-01"):
    x=np.asarray(x,float)
    if x.ndim==1: x=x[:,None]
    return pd.DataFrame(x,index=pd.bdate_range(start,periods=len(x)),columns=columns or [f"a{i}" for i in range(x.shape[1])])


def test_risk_contribution_euler_and_negative_boundary():
    s=np.array([[.04,.005],[.005,.01]])
    w=np.array([.4,.6]); result=risk_contributions(w,s)
    assert result["share"].sum()==pytest.approx(1)
    assert result["absolute"].sum()==pytest.approx(np.sqrt(w@s@w))
    s=np.array([[1,-.9],[-.9,1]])
    result=risk_contributions([.9,.1],s)
    assert result["share"][1]<0
    assert result["effective_risk_assets"] is None
    assert risk_contributions([.5,.5],np.zeros((2,2)))["share"] is None


def test_erc_symmetry_and_inverse_vol():
    s=np.diag([.01,.04,.09])
    result=allocate(s)
    assert result["status"]=="ok"
    assert result["candidates"]["risk_parity"]==pytest.approx(np.array([1,.5,1/3])/ (1+.5+1/3),abs=1e-5)
    equal=allocate(np.eye(4)+.2*np.ones((4,4)))["candidates"]["risk_parity"]
    assert equal==pytest.approx([.25]*4,abs=1e-6)


def test_diversification_and_no_general_upper_bound():
    s=np.diag([.01,.04,.09])
    w=allocate(s)["candidates"]["max_diversification"]
    assert concentration(w,s)["diversification_ratio"]==pytest.approx(np.sqrt(3),abs=1e-5)
    assert concentration([.5,.5],[[1,-.9],[-.9,1]])["diversification_ratio"]>np.sqrt(2)


def test_allocation_infeasible_and_group_limits():
    assert allocate(np.eye(2),upper=.4)["status"]=="infeasible"
    result=allocate(np.eye(4),upper=.8,groups=[{"indices":[0,1],"upper":.3}])
    assert "equal_weight" not in result["candidates"]
    assert "constrained_equal_reference" in result["candidates"]
    for w in result["candidates"].values():
        assert w[:2].sum()<=.300001
        assert w.sum()==pytest.approx(1)


def test_covariance_matches_reference():
    r=frame(np.random.default_rng(1).normal(0,.01,(120,3)))
    s,info=estimate_covariance(r,100)
    ref=LedoitWolf().fit(r.iloc[-100:])
    assert s==pytest.approx(ref.covariance_)
    assert info["shrinkage"]==pytest.approx(ref.shrinkage_)


def test_bl_zero_confidence_and_view_direction():
    s=np.diag([.001,.002])
    prior=3*s@np.array([.5,.5])
    bl=black_litterman(s,[.5,.5],[[1,0]],[.01],[[1e8]])
    assert bl["mean"]==pytest.approx(prior,abs=1e-10)
    view=black_litterman(s,[.5,.5],[[1,0]],[.01],[[1e-8]])
    assert view["mean"][0]==pytest.approx(.01,abs=1e-5)
    assert view["predictive_covariance"]==pytest.approx(s+view["mean_uncertainty"])


def test_cashflow_is_not_performance():
    r=frame(np.zeros((4,2)))
    result=backtest(r,[.5,.5],costs=0,cashflows={r.index[1]:10000,r.index[2]:-5000})
    assert result.daily.unit_nav.iloc[-1]==pytest.approx(1)
    assert result.daily.value.iloc[-1]==pytest.approx(105000)
    assert result.irr["value"]==pytest.approx(0,abs=1e-8)


def test_backtest_hand_calculated_drift_and_fees():
    r=frame([[.1,0],[0,.2]])
    path=backtest(r,[.5,.5],initial_value=100,costs=0,rebalance="none")
    assert path.daily.value.to_numpy()==pytest.approx([105,115])
    assert path.daily["weight:a0"].iloc[-1]==pytest.approx(55/115)
    cost=backtest(frame([[0,0]]),[.5,.5],initial_value=100,costs=.01)
    assert cost.daily.value.iloc[0]==pytest.approx(100/1.01)
    assert cost.daily.cost.iloc[0]==pytest.approx(100-100/1.01)


def test_withdrawal_cost_and_conservation():
    r=frame([[0],[0]])
    path=backtest(r,[1],initial_value=100,costs=.01,rebalance="none",cashflows={r.index[1]:-10})
    assert path.daily.value.iloc[-1]==pytest.approx(100/1.01-10/0.99)
    assert path.daily.cash.iloc[-1]==pytest.approx(0,abs=1e-9)
    assert path.daily.unit_nav.iloc[-1]<path.daily.unit_nav.iloc[0]


def test_threshold_zero_target_and_calendar():
    r=frame(np.zeros((70,2)))
    no=backtest(r,[1,0],costs=0,rebalance="threshold")
    assert len(no.transactions)==1
    monthly=backtest(r,[.5,.5],costs=0,rebalance="monthly")
    assert len(monthly.transactions)==4


def test_xirr_known_and_multiple():
    single=xirr([("2020-01-01",-100),("2021-01-01",110)])
    assert single["value"]==pytest.approx(1.1**(365.25/366)-1,abs=1e-8)
    # Integer years under the implemented 365.25-day clock are not necessary
    # for demonstrating two separated sign-changing roots.
    multiple=xirr([("2020-01-01",-100),("2021-01-01",230),("2022-01-01",-132)])
    assert multiple["status"]=="multiple_solutions"


@pytest.mark.parametrize("bad",[np.nan,np.inf,-1,-1.1])
def test_reject_nonfinite_and_bankruptcy_returns(bad):
    with pytest.raises(InputError): returns_frame(frame([0,bad]))


def test_reject_unknown_flows_and_unfunded_orders():
    r=frame([0,0,0])
    with pytest.raises(InputError): backtest(r,[1],cashflows={"2030-01-01":10})
    orders=pd.DataFrame([[1000]],index=[r.index[1]],columns=r.columns)
    with pytest.raises(InputError): backtest(r,[1],orders=orders)


def test_mdd_and_fractional_es():
    assert maximum_drawdown([.1,.1])==0
    assert maximum_drawdown([-.2,.25])==pytest.approx(.2)
    # alpha=.7: empirical tail has 1.2 observations, not two full observations.
    es=expected_shortfall([-.4,-.2,0,.1],.7)
    assert es["es"]==pytest.approx((.4+.2*.2)/1.2)


def test_cf_normal_and_nonmonotone():
    from scipy.stats import norm
    assert cf_quantile(0,0)["quantile"]==pytest.approx(norm.ppf(.95))
    assert cf_quantile(2,0,z_range=(-4,4))["status"]=="invalid_input"
    # The old patch's S=2,K=10 failure example is actually monotone here.
    assert cf_quantile(2,10,z_range=(-4,4))["status"]=="ok"


def test_stationary_indices_distribution_and_reproducibility():
    a=stationary_indices(100,2000,100,20,123)
    assert np.array_equal(a,stationary_indices(100,2000,100,20,123))
    assert a.min()>=0 and a.max()<100
    assert abs(a[:,0].mean()-a[:,-1].mean())<3
    breaks=np.mean(a[:,1:]!=(a[:,:-1]+1)%100)
    assert breaks==pytest.approx(.05*.99,abs=.004)


def test_vectorized_bootstrap_matches_ledger_with_costs():
    rng=np.random.default_rng(2)
    r=frame(rng.normal(.001,.01,(40,3)))
    ix=stationary_indices(40,4,40,10,2)
    metrics=path_metrics(r.to_numpy(),ix,[.3,.3,.3],costs=.002,rebalance_every=0)
    for i in range(4):
        path=backtest(frame(r.to_numpy()[ix[i]]),[.3,.3,.3],initial_value=1,costs=.002,rebalance="none")
        assert metrics["terminal_nav"][i]==pytest.approx(path.daily.value.iloc[-1],abs=1e-9)
        assert metrics["mdd"][i]==pytest.approx(maximum_drawdown(path.returns),abs=1e-9)


def test_drawdown_infeasible_no_relaxation_and_determinism():
    r=frame(np.full((100,2),-.01))
    kwargs=dict(budget=.01,horizon=20,paths=100,max_paths=100,block_lengths=[10],costs=0,seed=2)
    result=drawdown_budget(r,{"equal":[.5,.5]},**kwargs)
    assert result["status"]=="infeasible"
    assert result["selected"] is None
    assert result==drawdown_budget(r,{"equal":[.5,.5]},**kwargs)


def test_mc_interval_contains_population_quantile():
    values=np.random.default_rng(4).uniform(size=10000)
    lower,upper=quantile_interval(values)
    assert lower<.95<upper


def test_migration_conservation_funds_and_locked_dilution():
    result=plan_migration([80,20],[.5,.5],new_funds=60,costs=.01,locked=[0])
    assert result["status"]=="ok"
    assert result["sell"][0]==0
    assert result["final_value"]==pytest.approx(160-result["cost"])
    assert result["final_cash"]>=0
    assert result["final_weights"][0]<.8
    assert result["buy"].sum()<=60+result["sell"].sum()-result["cost"]+1e-6


def test_migration_uses_sale_proceeds_and_one_step():
    result=plan_migration([90,10],[.5,.5],costs=.01,mode="one_step")
    assert result["status"]=="ok"
    assert result["buy"][1]>0 and result["sell"][0]>0
    assert result["final_weights"]==pytest.approx([.5,.5],abs=1e-6)
    assert result["final_value"]==pytest.approx(100-result["cost"])
    assert plan_migration([90,10],[.5,.5],locked=[0],mode="one_step")["status"]=="infeasible"


def test_buy_only_and_critical_horizon():
    result=plan_migration([90,10],[.5,.5],new_funds=30,mode="buy_only",costs=.01,expected_improvement=.01)
    assert result["status"]=="ok"
    assert result["sell"].sum()==0
    assert result["critical_holding_years"]==pytest.approx(result["cost"]/(.01*130))
    no=plan_migration([90,10],[.5,.5],expected_improvement=-.01)
    assert no["critical_holding_years"] is None


def test_brinson_single_and_carino_reconciliation():
    result=brinson([[.6,.4],[.4,.6]],[[.5,.5],[.5,.5]],[[.1,.03],[-.1,.04]],[[.08,.02],[-.08,.03]])
    assert sum(result["single_period"].values())==pytest.approx(result["single_period_excess"])
    assert sum(result["linked"].values())==pytest.approx(result["total_excess"],abs=1e-12)
    same=brinson([.5,.5],[.5,.5],[.1,.2],[.1,.2])
    assert same["total_excess"]==0
    assert same["reconciliation_residual"]==0


def test_factor_hac_and_rank_deficiency():
    rng=np.random.default_rng(2); factors=frame(rng.normal(0,.01,(400,2)))
    y=.001+1.2*factors.iloc[:,0]-.4*factors.iloc[:,1]+rng.normal(0,.0001,400)
    result=factor_attribution(y,factors)
    assert result["coefficients"]["a0"]==pytest.approx(1.2,abs=.01)
    assert result["coefficients"]["a1"]==pytest.approx(-.4,abs=.01)
    assert result["hac_lags"]>=1
    factors["duplicate"]=factors.iloc[:,0]
    assert factor_attribution(y,factors)["status"]=="invalid_input"


def test_trade_counterfactual_empty_orders_equals_hold_before_first_rebalance():
    r=frame(np.random.default_rng(1).normal(0,.01,(20,2)))
    orders=pd.DataFrame(columns=r.columns,index=pd.DatetimeIndex([]),dtype=float)
    result=trade_counterfactual(r,[.5,.5],orders,costs=.001)
    assert result["wealth_differences"]["A_minus_B"]==pytest.approx(0)
    assert result["all_trade_gross_contribution"]==pytest.approx(0)
    assert trade_counterfactual(r,[.5,.5],None)["status"]=="insufficient_data"


def test_stress_censored_recovery_and_missing():
    r=frame(np.full(60,-.001),start="2020-01-01")
    result=historical_stress(r,[1],scenarios={"test":("2020-01-01","2020-02-28")},costs=0)
    assert result["test"]["recovery_status"]=="right_censored"
    assert result["test"]["recovery_months_from_trough"] is None
    assert historical_stress(r,[1])["2015_drawdown"]["status"]=="insufficient_data"
    assert rate_shock(5,30,.02)["return"]==pytest.approx(-.094)


def test_cli_end_to_end_synthetic_report(tmp_path):
    assert main(["demo","--fast","--out",str(tmp_path)])==0
    report=json.loads((tmp_path/"report.json").read_text(encoding="utf8"))
    assert set(report["modules"])=={f"M{i}" for i in range(1,8)}
    assert report["status"]=="degraded"
    assert "SYNTHETIC" in " ".join(report["warnings"])
    assert (tmp_path/"report.html").exists()
    assert (tmp_path/"ledger.csv").exists()
    assert report["modules"]["M3"]["brinson"]["reconciliation_residual"]==pytest.approx(0,abs=1e-12)
    assert report["modules"]["M6"]["status"]=="ok"
    assert report["modules"]["M2"]["historical_coverage"]=={"2015":True,"2018":True}


def test_coverage_gate_does_not_return_budget_solution():
    r=frame(np.random.default_rng(1).normal(.0001,.001,(120,2)))
    config={"data":{"return_type":"total_return","source":"test","currency":"CNY"},
            "bootstrap":{"paths":100,"max_paths":100,"horizon":20,"block_lengths":[10],"budget":.9}}
    report,_=run_engine(r,config)
    assert report["modules"]["M2"]["status"]=="insufficient_data"
    assert report["modules"]["M2"]["selected"] is None


def test_csv_invalid_does_not_fill_gaps(tmp_path):
    path=tmp_path/"bad.csv"
    path.write_text("date,a\n2020-01-01,100\n2020-01-02,\n2020-01-03,110\n")
    with pytest.raises(InputError): load_returns(path,"prices")


def test_cli_bad_config_exits_cleanly(tmp_path,capsys):
    path=tmp_path/"returns.csv"; frame(np.zeros((40,2))).to_csv(path,index_label="date")
    cfg=tmp_path/"config.json"; cfg.write_text("{}")
    assert main(["run","--returns",str(path),"--config",str(cfg),"--out",str(tmp_path/"out")])==2
    assert "declare data.return_type" in capsys.readouterr().err


def test_causal_walk_forward_does_not_use_future_for_initial_weights():
    rng=np.random.default_rng(8)
    data=frame(rng.normal(0,.01,(150,3)))
    first=walk_forward(data,min_train=60,test_steps=30,costs=.001)
    changed=data.copy()
    changed.iloc[60:]*=10
    second=walk_forward(changed,min_train=60,test_steps=30,costs=.001)
    assert len(first["folds"])==3
    for method in first["results"]:
        schedule=first["results"][method]["weight_schedule"]
        date=next(iter(schedule))
        assert schedule[date]==pytest.approx(second["results"][method]["weight_schedule"][date])
        assert first["folds"][0]["train_end"]<first["folds"][0]["test_start"]


def test_target_schedule_charges_continuous_ledger_sales_and_buys():
    data=frame(np.zeros((3,2)))
    schedule=pd.DataFrame([[0,1]],index=[data.index[1]],columns=data.columns)
    path=backtest(data,[1,0],initial_value=100,costs=.01,rebalance="none",target_schedule=schedule)
    initial=100/1.01
    # Liquidate first asset and buy second: net + .01*(initial+net)=initial.
    assert path.daily.value.iloc[-1]==pytest.approx(initial*.99/1.01)
    assert path.daily.cost.iloc[1]>initial*.01


def test_holding_periods_are_labeled_and_need_enough_history():
    result=rolling_holding_periods(np.zeros(300),252)
    assert result["1"]["loss_probability"]==0
    assert result["3"]["status"]=="insufficient_data"
    assert result["5"]["status"]=="insufficient_data"


def test_bl_utility_uses_explicit_means_under_constraints():
    result=allocate(np.eye(2)*.001,upper=.8,expected_returns=[.01,0])
    assert result["candidates"]["black_litterman_utility"][0]==pytest.approx(.8,abs=1e-6)


def test_duplicate_csv_columns_rejected(tmp_path):
    path=tmp_path/"duplicate.csv"
    path.write_text("date,a,a\n2020-01-01,0,0\n2020-01-02,0,0\n")
    with pytest.raises(InputError,match="duplicate CSV columns"):
        load_returns(path)


def test_unknown_parameter_rejected_instead_of_silent_default():
    with pytest.raises(InputError,match="unknown config fields"):
        run_engine(frame(np.zeros((60,2))),{"max_weigth":.4})
