import numpy as np
from scipy.optimize import linprog,minimize

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
    restricted=set(range(n)) if mode=="buy_only" else locked
    obstacles=[];capital_required=total
    for i in sorted(restricted):
        minimum_weight=float(x[i]/total)
        if minimum_weight>target[i]+1e-9:
            impossible=target[i]==0 and x[i]>0
            required=None if impossible else float(x[i]/target[i])
            if required is not None:capital_required=max(capital_required,required)
            obstacles.append({"asset_index":i,"reason":"selling_prohibited","current_amount":float(x[i]),
                "target_weight":float(target[i]),"minimum_weight_before_cost":minimum_weight,
                "excess_weight_lower_bound":float(minimum_weight-target[i]),
                "additional_funds_lower_bound":None if impossible else max(0,required-total),
                "finite_dilution_possible":not impossible})
    diagnosis={"obstacles":obstacles,"additional_funds_lower_bound":None if any(not o["finite_dilution_possible"] for o in obstacles) else capital_required-total,
               "scope":"necessary dilution condition only, ignores fees and other constraints; not a funding recommendation"}
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
        return {"status":"infeasible","mode":mode,"reason":result.message,"diagnosis":diagnosis,"target_reached":False,
                "conclusion":"禁止卖出的高配资产无法稀释到目标。" if obstacles else "当前资金与交易约束无法精确达到目标。"}
    tie_break="not_needed" if mode=="one_step" else "primary_only"
    if mode!="one_step":
        # L1 has many equally optimal solutions. Keep the primary objective
        # within a disclosed tolerance, then minimize squared monetary gaps.
        # Normalize by account size to avoid currency-dependent numerics.
        tolerance=max(1e-8,abs(result.fun)*1e-9)
        matrix=np.asarray(rows);limits=np.asarray(rhs)/total
        def secondary(v):
            buy,sell=v[:n],v[n:2*n]
            net=1-(buy+sell)@rates
            residual=np.r_[x/total+buy-sell-target*net,
                           (cash+new_funds)/total+(sell-buy).sum()-(buy+sell)@rates-(1-target.sum())*net]
            return residual@residual+1e-10*(buy+sell).sum()
        normalized_bounds=[(a/total if a is not None else None,b/total if b is not None else None) for a,b in bounds]
        constraints=[{"type":"ineq","fun":lambda v:limits-matrix@v},
                     {"type":"ineq","fun":lambda v:(result.fun+tolerance)/total-objective@v}]
        refined=minimize(secondary,result.x/total,method="SLSQP",bounds=normalized_bounds,constraints=constraints,
                         options={"ftol":1e-12,"maxiter":1000})
        conflicting=np.minimum(refined.x[:n],refined.x[n:2*n])*total
        if refined.success and not np.any((conflicting>1e-6)&(rates>0)) and np.all(matrix@refined.x<=limits+1e-9) and objective@refined.x*total<=result.fun+tolerance+1e-7:
            result.x=refined.x*total;tie_break="minimum_squared_target_gap"
    buy,sell=result.x[:n],result.x[n:2*n]
    # Zero-fee trades may be algebraically offsetting in a degenerate solver
    # solution. Net them without changing holdings, cash or either objective.
    offset=np.where(rates==0,np.minimum(buy,sell),0)
    buy=buy-offset;sell=sell-offset
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
    final_weights=final/final_total
    residual_weights=np.r_[final_weights-target,final_cash/final_total-(1-target.sum())]
    max_gap=float(np.max(np.abs(residual_weights)))
    reached=max_gap<1e-6
    return {"status":"ok","mode":mode,"buy":buy,"sell":sell,"cost":cost,
            "final_holdings":final,"final_cash":max(0,final_cash),"final_value":final_total,
            "final_weights":final_weights,"target_residual_amount":final-target*final_total,
            "target_residual_weights":residual_weights,"max_target_gap":max_gap,
            "total_variation_target_gap":float(np.abs(residual_weights).sum()/2),
            "target_reached":reached,"diagnosis":diagnosis,"tie_break":tie_break,
            "primary_objective_tolerance_amount":tolerance if mode!="one_step" else 0.0,
            "conclusion":"已达到目标容差。" if reached else "方案可执行，但仍偏离目标；不能视为目标配置已落实。",
            "penalty":penalty,"critical_holding_years":critical,"payback_status":payback_status,
            "execution_scope":"fractional amounts with linear costs; no exchange orders"}
