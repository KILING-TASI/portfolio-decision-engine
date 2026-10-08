import numpy as np
from scipy.optimize import linprog

from .validation import InputError, vector, weights


def plan_migration(current,target,cash=0.0,new_funds=0.0,costs=.0001,
                   locked=None,mode="minimum_trade",penalty=1.0,expected_improvement=None):
    """LP in currency amounts with exact cash conservation under linear costs."""
    x=np.asarray(current,float)
    if x.ndim!=1 or not len(x) or not np.isfinite(x).all() or (x<0).any():
        raise InputError("invalid current holdings")
    n=len(x); target=weights(target,n); rates=vector(costs,n,"costs",True)
    if not np.isfinite([cash,new_funds,penalty]).all() or min(cash,new_funds,penalty)<0 or (rates>=1).any():
        raise InputError("invalid migration funds, penalty or costs")
    if mode not in {"buy_only","minimum_trade","one_step"}:
        raise InputError("unknown migration mode")
    locked=set(locked or [])
    if any(not isinstance(i,int) or i<0 or i>=n for i in locked):
        raise InputError("invalid locked indices")
    total=float(x.sum()+cash+new_funds)
    if total<=0:
        raise InputError("empty migration account")
    # Variables: buys[n], sells[n], deviations[n+1] (including cash).
    objective=np.r_[rates,rates,np.full(n+1,penalty)]
    if mode=="one_step":
        objective=np.r_[rates,rates,np.zeros(n+1)]
    rows=[]; rhs=[]
    cash_row=np.r_[1+rates,-(1-rates),np.zeros(n+1)]
    rows.append(cash_row); rhs.append(cash+new_funds)
    # final_total = total - rates @ (buys+sells).
    for i in range(n+1):
        tgt=target[i] if i<n else 1-target.sum()
        row=np.r_[tgt*rates,tgt*rates,np.zeros(n+1)]
        constant=(x[i] if i<n else cash+new_funds)-tgt*total
        if i<n:
            row[i]+=1; row[n+i]-=1
        else:
            row[:n]-=1+rates; row[n:2*n]+=1-rates
        for sign in [1,-1]:
            bound=sign*row.copy(); bound[2*n+i]=-1
            rows.append(bound); rhs.append(-sign*constant)
    bounds=[(0,None)]*n+[(0,0 if mode=="buy_only" or i in locked else float(x[i])) for i in range(n)]
    bounds += [(0,0 if mode=="one_step" else None)]*(n+1)
    result=linprog(objective,A_ub=np.asarray(rows),b_ub=np.asarray(rhs),bounds=bounds,method="highs")
    if not result.success:
        return {"status":"infeasible","mode":mode,"reason":result.message}
    buy,sell=result.x[:n],result.x[n:2*n]
    # Remove simultaneous buys/sells and re-solve is not needed: positive fees
    # discourage this; fail explicitly for a solver artifact instead of hiding it.
    if np.any(np.minimum(buy,sell)>1e-6):
        return {"status":"invalid_input","reason":"simultaneous buy/sell solution"}
    cost=float((buy+sell)@rates)
    final=x+buy-sell
    final_cash=float(cash+new_funds+sell.sum()-buy.sum()-cost)
    final_total=float(final.sum()+final_cash)
    if final_cash < -1e-6 or abs(final_total-(total-cost))>1e-6:
        raise RuntimeError("migration conservation failure")
    critical=None; payback_status="no_expected_return_input"
    if expected_improvement is not None:
        if not np.isfinite(expected_improvement):
            raise InputError("invalid expected improvement")
        if expected_improvement>0:
            critical=cost/(expected_improvement*total); payback_status="first_order_scenario"
        else:
            payback_status="no_finite_positive_payback"
    return {"status":"ok","mode":mode,"buy":buy,"sell":sell,"cost":cost,
            "final_holdings":final,"final_cash":max(0,final_cash),"final_value":final_total,
            "final_weights":final/final_total,"target_residual_amount":final-target*final_total,
            "penalty":penalty,"critical_holding_years":critical,"payback_status":payback_status,
            "execution_scope":"fractional amounts with linear costs; no exchange orders"}
