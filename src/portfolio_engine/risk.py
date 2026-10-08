import numpy as np
from scipy.stats import norm

from .allocation import risk_contributions
from .validation import InputError


def maximum_drawdown(returns):
    r = np.asarray(returns, float)
    if r.ndim != 1 or not len(r) or not np.isfinite(r).all() or (r<=-1).any():
        raise InputError("invalid return vector")
    nav = np.r_[1.0, np.cumprod(1+r)]
    return float(np.max(1-nav/np.maximum.accumulate(nav)))


def expected_shortfall(returns, alpha=0.95):
    """Exact empirical tail integral, including fractional boundary mass."""
    r = np.asarray(returns, float)
    if not 0<alpha<1 or not len(r) or not np.isfinite(r).all():
        raise InputError("invalid ES input")
    losses = np.sort(-r)[::-1]
    tail = (1-alpha)*len(losses)
    whole = int(np.floor(tail))
    fraction = tail-whole
    integral = losses[:whole].sum() + (fraction*losses[whole] if fraction>1e-12 else 0)
    return {"var":float(np.quantile(-r,alpha)), "es":float(integral/tail),
            "tail_mass_observations":float(tail)}


def cf_quantile(skew, excess_kurtosis, alpha=0.95, z_range=(-4,4)):
    if not np.isfinite([skew,excess_kurtosis,alpha,*z_range]).all() or not 0<alpha<1 or z_range[0]>=z_range[1]:
        raise InputError("invalid CF input")
    z = np.linspace(*z_range, 2001)
    derivative = 1+z*skew/3+(3*z*z-3)*excess_kurtosis/24-(6*z*z-5)*skew*skew/36
    q = norm.ppf(alpha)
    if not z_range[0]<=q<=z_range[1] or (derivative<=0).any():
        return {"status":"invalid_input","quantile":None,"z_range":z_range}
    value = q+(q*q-1)*skew/6+(q**3-3*q)*excess_kurtosis/24-(2*q**3-5*q)*skew*skew/36
    return {"status":"ok","quantile":float(value),"z_range":z_range}


def summary(returns, periods=252, risk_free=0.0):
    r = np.asarray(returns,float)
    maximum_drawdown(r)  # validate
    if periods<=0 or not np.isfinite(risk_free) or risk_free<=-1:
        raise InputError("invalid annualization or risk-free rate")
    rf = (1+risk_free)**(1/periods)-1
    excess = r-rf
    std = float(np.std(excess,ddof=1)) if len(r)>1 else 0.0
    downside = float(np.sqrt(np.mean(np.minimum(excess,0)**2)))
    cagr = float(np.expm1(np.log1p(r).sum()*periods/len(r)))
    dd = maximum_drawdown(r)
    nav = np.r_[1,np.cumprod(1+r)]
    underwater = 1-nav/np.maximum.accumulate(nav)
    return {"observations":len(r),"periods_per_year":periods,"total_twr":float(np.prod(1+r)-1),
            "cagr":cagr,"annual_volatility":std*np.sqrt(periods),
            "sharpe":float(excess.mean()/std*np.sqrt(periods)) if std>1e-15 else None,
            "sortino":float(excess.mean()/downside*np.sqrt(periods)) if downside>1e-15 else None,
            "calmar":cagr/dd if dd>1e-15 else None,"max_drawdown":dd,
            "ulcer_index":float(np.sqrt(np.mean(underwater**2))),
            "tail95":expected_shortfall(r,.95),"tail90":expected_shortfall(r,.90)}


def concentration(w, sigma):
    w=np.asarray(w,float)
    rc=risk_contributions(w,sigma)
    variance=float(w@np.asarray(sigma)@w)
    return {"effective_weight_assets":float(w.sum()**2/(w@w)) if w@w>0 else None,
            "effective_risk_assets":rc["effective_risk_assets"],"risk_share":rc["share"],
            "diversification_ratio":float(w@np.sqrt(np.diag(sigma))/np.sqrt(variance)) if variance>1e-18 else None,
            "cash_weight":float(1-w.sum())}
