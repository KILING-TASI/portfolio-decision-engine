import numpy as np
from scipy.stats import binom

from .validation import InputError, returns_frame, vector, weights


def stationary_indices(observations, paths, horizon, block_length, seed=42):
    if any(not isinstance(v, (int,np.integer)) or v<=0 for v in [observations,paths,horizon]):
        raise InputError("sample, paths and horizon must be positive integers")
    if not np.isfinite(block_length) or block_length<1:
        raise InputError("block_length must be >=1")
    rng=np.random.default_rng(seed)
    indices=np.empty((paths,horizon),dtype=np.int64)
    indices[:,0]=rng.integers(observations,size=paths)
    for t in range(1,horizon):
        restart=rng.random(paths)<1/block_length
        indices[:,t]=np.where(restart,rng.integers(observations,size=paths),(indices[:,t-1]+1)%observations)
    return indices


def path_metrics(returns, indices, target, costs=0.0001, rebalance_every=63, periods=252):
    """Vectorized paths: fractional holdings, linear costs, cash and calendar steps.

    A step interval is explicit; it is not an exchange quarterly calendar.
    """
    x=np.asarray(returns,float)
    if x.ndim!=2 or not np.isfinite(x).all() or (x<=-1).any():
        raise InputError("invalid joint return matrix")
    target=weights(target,x.shape[1])
    rates=vector(costs,x.shape[1],"costs",True)
    if (rates>=1).any() or not isinstance(rebalance_every,int) or rebalance_every<0:
        raise InputError("invalid simulation cost or rebalance interval")
    if indices.ndim!=2 or indices.shape[1]<1 or (indices<0).any() or (indices>=len(x)).any():
        raise InputError("invalid bootstrap indices")
    b,h=indices.shape
    holdings=np.zeros((b,len(target)))
    cash=np.ones(b)
    high=np.ones(b)
    mdd=np.zeros(b)
    cumulative_cost=np.zeros(b)
    checkpoints={}
    for t in range(h):
        if t==0 or (rebalance_every>0 and t%rebalance_every==0):
            total=holdings.sum(axis=1)+cash
            net=total.copy()
            for _ in range(64):
                updated=total-np.abs(net[:,None]*target-holdings)@rates
                if np.max(np.abs(updated-net)/np.maximum(total,1e-15))<1e-11:
                    net=updated
                    break
                net=updated
            else:
                raise InputError("simulation fee fixed point did not converge; lower rates or use ledger")
            if (net<=0).any():
                raise InputError("simulation depleted by costs")
            cumulative_cost+=np.abs(net[:,None]*target-holdings)@rates
            holdings=net[:,None]*target
            cash=net*(1-target.sum())
        holdings*=1+x[indices[:,t]]
        total=holdings.sum(axis=1)+cash
        high=np.maximum(high,total)
        mdd=np.maximum(mdd,1-total/high)
        if t+1 in {periods,3*periods,5*periods}:
            checkpoints[str((t+1)//periods)]=total.copy()
    return {"mdd":mdd,"terminal_nav":total,"cost":cumulative_cost,"checkpoints":checkpoints}


def quantile_interval(values,p=.95,confidence=.95):
    """Conditional MC interval by binomial/order-statistic inversion."""
    x=np.sort(np.asarray(values,float))
    if len(x)<20 or not 0<p<1 or not 0<confidence<1:
        raise InputError("quantile interval needs >=20 paths and valid probabilities")
    n=len(x); tail=(1-confidence)/2
    # 1-indexed order bounds K_low and K_high+1; clamp endpoints.
    low=max(0,int(binom.ppf(tail,n,p))-1)
    high=min(n-1,int(binom.ppf(1-tail,n,p)))
    return [float(x[low]),float(x[high])]


def drawdown_budget(returns,candidates,budget=.25,horizon=252,paths=2000,
                    block_lengths=(10,20,40,60),costs=.0001,rebalance_every=63,
                    seed=42,mc_tolerance=.01,max_paths=8000,strict=True,periods=252):
    frame=returns_frame(returns)
    if not 0<=budget<1 or not np.isfinite(budget) or mc_tolerance<=0 or not np.isfinite(mc_tolerance):
        raise InputError("invalid budget or MC tolerance")
    if not isinstance(paths,int) or paths<100 or not isinstance(max_paths,int) or max_paths<paths or periods<=0:
        raise InputError("paths>=100 and max_paths>=paths required")
    if not block_lengths or not candidates:
        raise InputError("nonempty blocks and candidates required")
    x=frame.to_numpy()
    records={name:{"blocks":[]} for name in candidates}
    for block in block_lengths:
        count=paths
        while True:
            indices=stationary_indices(len(x),count,horizon,block,seed+int(block))
            results={}
            all_converged=True
            for name,target in candidates.items():
                metrics=path_metrics(x,indices,target,costs,rebalance_every,periods)
                ci=quantile_interval(metrics["mdd"])
                converged=(ci[1]-ci[0])/2<=mc_tolerance
                all_converged &= converged
                # Independent conditional resampling of MC draws estimates MC SE.
                rng=np.random.default_rng(seed+int(block)+7919)
                quantiles=[np.quantile(rng.choice(metrics["mdd"],len(metrics["mdd"]),replace=True),.95) for _ in range(100)]
                checkpoints={year:{"annualized_quantiles":np.quantile(nav**(1/int(year))-1,[.05,.25,.5,.75,.95]),
                                   "loss_probability":float(np.mean(nav<1))} for year,nav in metrics["checkpoints"].items()}
                results[name]={"block_length":block,"paths":count,"horizon_steps":horizon,
                    "p95":float(np.quantile(metrics["mdd"],.95)),"p99":float(np.quantile(metrics["mdd"],.99)),
                    "p95_mc_interval":ci,"p95_mc_standard_error":float(np.std(quantiles,ddof=1)),
                    "converged":bool(converged),"budget_exceedance":float(np.mean(metrics["mdd"]>budget)),
                    "median_annualized_return":float(np.median(metrics["terminal_nav"]**(periods/horizon)-1)),
                    "holding_period_distributions":checkpoints}
            if all_converged or count>=max_paths:
                break
            count=min(count*2,max_paths)
        for name in records:
            records[name]["blocks"].append(results[name])
    feasible=[]
    for name,record in records.items():
        rows=record["blocks"]
        record["worst_p95"]=max(r["p95"] for r in rows)
        record["block_sensitivity"]=max(r["p95"] for r in rows)-min(r["p95"] for r in rows)
        record["converged"]=all(r["converged"] for r in rows)
        record["feasible"]=record["converged"] and all((r["p95_mc_interval"][1] if strict else r["p95"])<=budget for r in rows)
        record["score"]=min(r["median_annualized_return"] for r in rows)
        if record["feasible"]:
            feasible.append(name)
    # Robust across requested blocks; no relaxation when none qualify.
    selected=max(feasible,key=lambda name:records[name]["score"]) if feasible else None
    converged=all(r["converged"] for r in records.values())
    sensitive=any(r["block_sensitivity"]>.05 for r in records.values())
    return {"status":("degraded" if sensitive else "ok") if selected else "infeasible" if converged else "unconverged",
            "selected":selected,"budget":budget,"strict_mc_upper_bound":strict,"candidates":records,
            "least_risk_candidate":min(records,key=lambda name:records[name]["worst_p95"]),
            "seed":seed,"rebalance_every_steps":rebalance_every,
            "error_scope":"conditional Monte Carlo only; excludes model and historical-sample uncertainty",
            "selection_scope":"in-sample exploratory; independent walk-forward evidence required"}


def sharpe_interval(returns,paths=500,block_length=20,seed=42,periods=252,risk_free=0):
    r=np.asarray(returns,float)
    if r.ndim!=1 or len(r)<2 or not np.isfinite(r).all():
        raise InputError("invalid Sharpe sample")
    sampled=r[stationary_indices(len(r),paths,len(r),block_length,seed)]
    rf=(1+risk_free)**(1/periods)-1
    std=np.std(sampled,axis=1,ddof=1)
    valid=std>1e-15
    if valid.sum()<paths*.9:
        return {"status":"insufficient_data","interval":None}
    sr=(sampled[valid].mean(axis=1)-rf)/std[valid]*np.sqrt(periods)
    return {"status":"ok","interval":np.quantile(sr,[.025,.975]),"paths":paths,
            "block_length":block_length,"seed":seed}
