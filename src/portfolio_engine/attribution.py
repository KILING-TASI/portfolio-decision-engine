import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from .backtest import backtest
from .risk import summary
from .validation import InputError


def brinson(portfolio_weights,benchmark_weights,portfolio_returns,benchmark_returns):
    """Single or multiple periods; exact arithmetic and Carino-linked reconciliation."""
    wp,wb,rp,rb=[np.atleast_2d(np.asarray(x,float)) for x in
                 [portfolio_weights,benchmark_weights,portfolio_returns,benchmark_returns]]
    if len({x.shape for x in [wp,wb,rp,rb]})!=1 or any(not np.isfinite(x).all() for x in [wp,wb,rp,rb]):
        raise InputError("Brinson arrays must share finite period x segment shape")
    if (wp<0).any() or (wb<0).any() or not np.allclose(wp.sum(axis=1),1) or not np.allclose(wb.sum(axis=1),1):
        raise InputError("Brinson weights must be long-only and sum to 1 each period")
    if (rp<=-1).any() or (rb<=-1).any():
        raise InputError("segment returns must exceed -1")
    p=(wp*rp).sum(axis=1); b=(wb*rb).sum(axis=1)
    effects={"allocation":((wp-wb)*(rb-b[:,None])).sum(axis=1),
             "selection":(wb*(rp-rb)).sum(axis=1),"interaction":((wp-wb)*(rp-rb)).sum(axis=1)}
    total_p=float(np.prod(1+p)-1); total_b=float(np.prod(1+b)-1)
    def coefficient(p,b):
        p,b=np.asarray(p),np.asarray(b)
        delta=p-b
        out=np.array(1/(1+b),dtype=float)
        np.divide(np.log1p(p)-np.log1p(b),delta,out=out,where=np.abs(delta)>1e-10)
        return out
    k=coefficient(p,b); K=float(coefficient(np.array(total_p),np.array(total_b)))
    linked={name:float(np.sum(value*k/K)) for name,value in effects.items()}
    residual=sum(linked.values())-(total_p-total_b)
    return {"status":"ok","single_period":effects,"single_period_excess":p-b,
            "linked":linked,"linking":"Carino","portfolio_total_return":total_p,
            "benchmark_total_return":total_b,"total_excess":total_p-total_b,
            "reconciliation_residual":float(residual)}


def factor_attribution(excess_returns,factors,lags=None):
    if not isinstance(factors,pd.DataFrame) or not isinstance(excess_returns,pd.Series):
        raise InputError("factor attribution requires a Series and DataFrame")
    if factors.columns.has_duplicates or "const" in factors.columns or len(factors.columns)==0:
        raise InputError("invalid factor names")
    if not excess_returns.index.equals(factors.index) or factors.index.has_duplicates:
        raise InputError("factor and excess return dates must match exactly")
    if not np.isfinite(factors.to_numpy()).all() or not np.isfinite(excess_returns.to_numpy()).all():
        raise InputError("missing/nonfinite factor observations")
    n,k=factors.shape
    if n<=k+5:
        return {"status":"insufficient_data","reason":"too few observations"}
    design=sm.add_constant(factors,has_constant="add")
    if np.linalg.matrix_rank(design.to_numpy())<k+1:
        return {"status":"invalid_input","reason":"rank-deficient factors"}
    bandwidth=int(np.floor(4*(n/100)**(2/9))) if lags is None else lags
    if not isinstance(bandwidth,int) or bandwidth<0 or bandwidth>=n:
        raise InputError("invalid HAC bandwidth")
    fit=sm.OLS(excess_returns,design).fit(cov_type="HAC",cov_kwds={"maxlags":bandwidth})
    vif={name:float(variance_inflation_factor(design.to_numpy(),i+1)) for i,name in enumerate(factors.columns)}
    return {"status":"degraded" if any(v>10 for v in vif.values()) else "ok",
            "coefficients":fit.params.to_dict(),"t_values":fit.tvalues.to_dict(),
            "p_values":fit.pvalues.to_dict(),"confidence_intervals":fit.conf_int().to_dict(orient="index"),
            "r_squared":float(fit.rsquared),"hac_lags":bandwidth,"vif":vif,
            "factor_correlations":factors.corr().to_dict(),"observations":n,
            "interpretation":"descriptive exposures, not proof of skill or causality"}


def trade_counterfactual(returns,target,orders,cashflows=None,**kwargs):
    """Three self-financing paths using identical start, flows and fee rules."""
    if orders is None:
        return {"status":"insufficient_data","reason":"complete signed-notional orders required"}
    if "rebalance" in kwargs:
        raise InputError("counterfactual rebalance is defined by each path")
    actual=backtest(returns,target,orders=orders,cashflows=cashflows,rebalance="none",**kwargs)
    held=backtest(returns,target,cashflows=cashflows,rebalance="none",flow_rule="cash",**{k:v for k,v in kwargs.items() if k!="flow_rule"})
    mechanical=backtest(returns,target,cashflows=cashflows,rebalance="quarterly",**kwargs)
    paths={"A_actual":actual,"B_hold":held,"C_mechanical":mechanical}
    values={name:float(path.daily.value.iloc[-1]) for name,path in paths.items()}
    metrics={name:{**summary(path.returns),"terminal_value":values[name],
                   "cost":float(path.daily.cost.sum())} for name,path in paths.items()}
    zero_kwargs={k:v for k,v in kwargs.items() if k not in {"costs","flow_rule"}}
    gross_actual=backtest(returns,target,orders=orders,cashflows=cashflows,rebalance="none",costs=0,**zero_kwargs)
    gross_held=backtest(returns,target,cashflows=cashflows,rebalance="none",flow_rule="cash",costs=0,**zero_kwargs)
    gross=float(gross_actual.daily.value.iloc[-1]-gross_held.daily.value.iloc[-1])
    net=values["A_actual"]-values["B_hold"]
    return {"status":"ok","paths":metrics,
            "wealth_differences":{"A_minus_B":net,"A_minus_C":values["A_actual"]-values["C_mechanical"],
                                 "C_minus_B":values["C_mechanical"]-values["B_hold"]},
            "all_trade_gross_contribution":gross,"all_trade_net_contribution":net,
            "cost_and_compounding_drag":gross-net,
            "decomposition_status":"per-trade timing/switching decomposition not implemented",
            "assumptions":["fractional holdings; linear costs; supplied complete orders",
                           "positive inflows in buy-and-hold remain cash; other paths follow their declared rules"]}
