import numpy as np
import pandas as pd

from .backtest import backtest
from .risk import summary
from .validation import InputError,returns_frame


HISTORICAL_SCENARIOS={
    "2015_drawdown":("2015-06-01","2016-01-31"),
    "2018":("2018-01-01","2018-12-31"),
    "2020_covid":("2020-01-01","2020-03-31"),
    "2022":("2022-01-01","2022-10-31"),
}


def historical_stress(returns,target,scenarios=None,costs=.0001,periods=252):
    frame=returns_frame(returns)
    result={}
    for name,(start,end) in (scenarios or HISTORICAL_SCENARIOS).items():
        start,end=pd.Timestamp(start),pd.Timestamp(end)
        if start>=end:
            raise InputError("scenario start must precede end")
        window=frame.loc[start:end]
        # Allow weekend endpoints, but do not silently accept truncated coverage.
        if len(window)<2 or frame.index.min()>start+pd.Timedelta(days=7) or frame.index.max()<end-pd.Timedelta(days=7):
            result[name]={"status":"insufficient_data","start":str(start.date()),"end":str(end.date())}
            continue
        path=backtest(frame.loc[start:],target,costs=costs,rebalance="quarterly")
        observed=path.daily.loc[:end]
        nav=np.r_[1,observed.unit_nav.to_numpy()]
        dd=1-nav/np.maximum.accumulate(nav)
        trough=int(np.argmax(dd))
        peak=int(np.argmax(nav[:trough+1]))
        dates=[path.initial_date,*path.daily.index]
        full_nav=np.r_[1,path.daily.unit_nav.to_numpy()]
        recovered=np.where(full_nav[trough:]>=nav[peak]-1e-12)[0]
        recovered_at=trough+int(recovered[0]) if len(recovered) else None
        monthly=(1+observed.twr_return).resample("ME").prod()-1
        result[name]={"status":"ok","kind":"historical_fixed_target_counterfactual",
                      **summary(observed.twr_return,periods),"cost":float(observed.cost.sum()),
                      "worst_month":float(monthly.min()),
                      "recovery_months_from_trough":(dates[recovered_at]-dates[trough]).days/30.4375 if recovered_at is not None else None,
                      "recovery_status":"recovered" if recovered_at is not None else "right_censored",
                      "peak_date":str(dates[peak].date()),"trough_date":str(dates[trough].date()),
                      "observed_until":str(path.daily.index[-1].date())}
    return result


def rate_shock(modified_duration,convexity,delta_yield=.02):
    if not np.isfinite([modified_duration,convexity,delta_yield]).all() or modified_duration<0:
        raise InputError("invalid duration scenario")
    return {"kind":"synthetic_duration_approximation","return":float(-modified_duration*delta_yield+.5*convexity*delta_yield**2),
            "delta_yield":delta_yield,"limitations":"does not include carry, credit spread, FX or nonlinear repricing"}
