import numpy as np
import pytest

from portfolio_engine.migration import plan_migration
from portfolio_engine.decision import comparison_tradeoffs,decision_summary


def test_equal_l1_solutions_use_balanced_secondary_gap():
    plan=plan_migration([50,10,15,15],[.1,.4,.365,.135],cash=10,new_funds=10,costs=0,locked=[0])
    assert plan["status"]=="ok"
    assert plan["tie_break"]=="minimum_squared_target_gap"
    assert plan["buy"][1]>0 and plan["buy"][2]>0
    assert plan["target_residual_amount"][1]==pytest.approx(plan["target_residual_amount"][2],abs=1e-3)
    assert not plan["target_reached"]
    assert plan["diagnosis"]["additional_funds_lower_bound"]==pytest.approx(390)


def test_locked_zero_target_has_no_finite_dilution_solution():
    plan=plan_migration([50,50],[0,1],locked=[0],mode="one_step")
    assert plan["status"]=="infeasible"
    assert plan["diagnosis"]["additional_funds_lower_bound"] is None
    assert not plan["diagnosis"]["obstacles"][0]["finite_dilution_possible"]


def test_reached_target_and_residual_metrics():
    plan=plan_migration([80,20],[.5,.5],mode="one_step",costs=.001)
    assert plan["target_reached"]
    assert plan["max_target_gap"]<1e-6
    assert plan["total_variation_target_gap"]<1e-6


def test_cost_secondary_keeps_primary_objective_and_is_scale_invariant():
    args=dict(target=[.1,.4,.365,.135],costs=.0001,locked=[0])
    small=plan_migration([50,10,15,15],cash=10,new_funds=10,**args)
    big=plan_migration([50000,10000,15000,15000],cash=10000,new_funds=10000,**args)
    assert small["final_weights"]==pytest.approx(big["final_weights"],abs=1e-5)
    assert np.sum(big["final_holdings"])+big["final_cash"]==pytest.approx(110000-big["cost"])


def test_tradeoffs_distinguish_risk_reduction_from_return_improvement():
    values={"equal_weight":{"cagr":.06,"max_drawdown":.1},"min_variance":{"cagr":.02,"max_drawdown":.05},
            "better":{"cagr":.08,"max_drawdown":.07},"worse":{"cagr":.01,"max_drawdown":.2}}
    rows={r["method"]:r for r in comparison_tradeoffs(values,"equal_weight")["rows"]}
    assert rows["min_variance"]["interpretation"]=="降低回撤，牺牲收益"
    assert rows["min_variance"]["annual_return_difference"]==pytest.approx(-.04)
    assert rows["better"]["interpretation"]=="收益与回撤均改善"
    assert rows["worse"]["interpretation"]=="收益与回撤均不及基准"


def test_no_budget_solution_never_presented_as_selection():
    result=decision_summary({"modules":{"M2":{"selected":None},"M7":{"sharpe_bootstrap":{"interval":[-.1,.5]}}},
        "inputs":{"data":{"return_type":"synthetic_total_return"}}})
    text=" ".join(result["conclusions"])
    assert "没有最终通过" in text
    assert "教学模拟" in text
    assert "包含零" in text
