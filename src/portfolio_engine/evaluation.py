import numpy as np
import pandas as pd

from .allocation import allocate,estimate_covariance
from .backtest import backtest
from .risk import summary
from .validation import InputError,returns_frame


def walk_forward(returns,min_train=500,test_steps=252,covariance_window=500,
                 lower=0,upper=1,groups=None,costs=.0001,periods=252):
    """Causal expanding-history estimates with a continuous, self-financing ledger.

    M1 methods are updated at fold boundaries. This does not validate M2 selection.
    """
    frame=returns_frame(returns)
    if not isinstance(min_train,int) or min_train<30 or not isinstance(test_steps,int) or test_steps<10:
        raise InputError("walk-forward min_train>=30 and test_steps>=10 required")
    if len(frame)-min_train<10:
        return {"status":"insufficient_data","reason":"no walk-forward holdout"}
    folds=[]; estimates=[]
    for start in range(min_train,len(frame),test_steps):
        end=min(start+test_steps,len(frame))
        training=frame.iloc[:start]
        sigma,_=estimate_covariance(training,covariance_window)
        allocation=allocate(sigma,lower,upper,groups)
        if not allocation["candidates"]:
            return {"status":allocation["status"],"reason":"fold allocation failed","fold":len(folds)}
        estimates.append((frame.index[start],allocation["candidates"]))
        folds.append({"train_end":str(training.index[-1].date()),"test_start":str(frame.index[start].date()),
                      "test_end":str(frame.index[end-1].date()),"training_observations":start})
    methods=set(estimates[0][1])
    for _,estimate in estimates:
        methods &= set(estimate)
    results={}
    for method in sorted(methods):
        schedule=pd.DataFrame([estimate[method] for _,estimate in estimates],
                              index=[date for date,_ in estimates],columns=frame.columns)
        path=backtest(frame.iloc[min_train:],schedule.iloc[0].to_numpy(),costs=costs,
                      rebalance="quarterly",target_schedule=schedule,
                      initial_date=frame.index[min_train-1])
        results[method]={**summary(path.returns,periods),"cost":float(path.daily.cost.sum()),
                         "turnover_notional":float(path.daily.turnover_notional.sum()),
                         "weight_schedule":{str(date.date()):row.tolist() for date,row in schedule.iterrows()}}
    return {"status":"ok" if len(methods)==len(estimates[0][1]) else "degraded",
            "scope":"M1 methods only; no M2 model-selection validation or multi-testing correction",
            "folds":folds,"results":results,"attempted_methods":len(estimates[0][1]),
            "cost_scope":"continuous ledger: new target buys and sells are both charged"}


def rolling_holding_periods(returns,periods=252):
    r=np.asarray(returns,float)
    logs=np.r_[0,np.cumsum(np.log1p(r))]
    output={}
    for year in [1,3,5]:
        span=periods*year
        if len(r)<span:
            output[str(year)]={"status":"insufficient_data","required_observations":span}
        else:
            growth=np.expm1((logs[span:]-logs[:-span])/year)
            output[str(year)]={"status":"ok","annualized_quantiles":np.quantile(growth,[.05,.25,.5,.75,.95]),
                               "loss_probability":float(np.mean(growth<0)),"overlapping_windows":len(growth),
                               "warning":"overlapping historical windows are not independent observations"}
    return output
