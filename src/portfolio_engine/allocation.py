import numpy as np
from scipy.optimize import linprog, minimize
from sklearn.covariance import LedoitWolf

from .validation import InputError, covariance, returns_frame, vector


def estimate_covariance(returns, window=500):
    frame = returns_frame(returns)
    if not isinstance(window, int) or window < 2:
        raise InputError("window must be an integer >=2")
    x = frame.iloc[-window:].to_numpy()
    if len(x) < 2:
        raise InputError("at least two observations required")
    fitted = LedoitWolf().fit(x)
    sample = np.cov(x, rowvar=False, ddof=0).reshape(x.shape[1], x.shape[1])
    return fitted.covariance_, {
        "target": "constant_variance", "shrinkage": float(fitted.shrinkage_),
        "observations": len(x), "requested_window": window,
        "condition_before": float(np.linalg.cond(sample)),
        "condition_after": float(np.linalg.cond(fitted.covariance_)),
        "minimum_eigenvalue": float(np.linalg.eigvalsh(fitted.covariance_).min()),
    }


def risk_contributions(w, sigma):
    s = covariance(sigma)
    w = vector(w, len(s), "weights")
    variance = float(w @ s @ w)
    if variance <= 1e-18:
        return {"absolute": None, "share": None, "effective_risk_assets": None}
    share = w * (s @ w) / variance
    return {"absolute": share * np.sqrt(variance), "share": share,
            "effective_risk_assets": float(1 / (share @ share)) if np.all(share >= -1e-12) else None}


def allocate(sigma, lower=0.0, upper=1.0, groups=None, expected_returns=None, risk_aversion=3.0):
    """Solve long-only fully-invested candidates; report constrained ERC residual."""
    s = covariance(sigma)
    n = len(s)
    lo, hi = vector(lower, n, "lower", True), vector(upper, n, "upper", True)
    if (lo > hi).any():
        raise InputError("lower bounds exceed upper bounds")
    # Each group is {indices: [...], lower: ..., upper: ...}.
    rows, limits = [], []
    for group in groups or []:
        row = np.zeros(n)
        indices = group["indices"]
        if not indices or len(set(indices)) != len(indices) or any(i < 0 or i >= n for i in indices):
            raise InputError("invalid group indices")
        row[indices] = 1
        rows.extend([row, -row])
        limits.extend([group.get("upper", 1), -group.get("lower", 0)])
    a = np.array(rows).reshape(-1, n) if rows else None
    b = np.array(limits) if rows else None
    feasible = linprog(np.zeros(n), A_ub=a, b_ub=b, A_eq=np.ones((1, n)),
                       b_eq=[1], bounds=list(zip(lo, hi)), method="highs")
    if not feasible.success:
        return {"status": "infeasible", "candidates": {}, "reason": feasible.message}
    scale = np.trace(s) / n
    if scale <= 1e-18:
        return {"status": "invalid_input", "candidates": {}, "reason": "zero covariance"}
    scaled = s / scale
    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    if rows:
        constraints.append({"type": "ineq", "fun": lambda w: b - a @ w})

    def valid(w):
        return abs(w.sum() - 1) < 1e-7 and np.all(w >= lo - 1e-7) and np.all(w <= hi + 1e-7) and (a is None or np.all(a @ w <= b + 1e-7))

    candidates, failures = {}, {}
    equal = np.full(n, 1 / n)
    start = equal if valid(equal) else feasible.x
    if valid(equal):
        candidates["equal_weight"] = equal
    else:
        projected = minimize(lambda w: np.sum((w - equal)**2), start, method="SLSQP",
                             bounds=list(zip(lo, hi)), constraints=constraints)
        if projected.success and valid(projected.x):
            candidates["constrained_equal_reference"] = projected.x

    def erc(w):
        variance = w @ scaled @ w
        if variance <= 1e-18:
            return 1e12
        rc = w * (scaled @ w) / variance
        return np.sum((rc - 1/n)**2)

    def diversification(w):
        variance = w @ scaled @ w
        return -(w @ np.sqrt(np.diag(scaled))) / np.sqrt(max(variance, 1e-18))

    objectives=[("min_variance", lambda w: w @ scaled @ w),
                ("risk_parity", erc), ("max_diversification", diversification)]
    if expected_returns is not None:
        mu=vector(expected_returns,n,"expected_returns")
        if not np.isfinite(risk_aversion) or risk_aversion<=0:
            raise InputError("invalid risk aversion")
        objectives.append(("black_litterman_utility",lambda w:(.5*risk_aversion*(w@s@w)-mu@w)/scale))
    for name, objective in objectives:
        result = minimize(objective, start, method="SLSQP", bounds=list(zip(lo, hi)),
                          constraints=constraints, options={"ftol": 1e-12, "maxiter": 2000})
        if result.success and valid(result.x):
            candidates[name] = result.x
        else:
            failures[name] = str(result.message)
    return {"status": "degraded" if failures else "ok", "candidates": candidates,
            "failures": failures, "erc_residual": erc(candidates["risk_parity"]) if "risk_parity" in candidates else None}


def black_litterman(sigma, market_weights, p, q, omega, tau=0.05, risk_aversion=3.0):
    s = covariance(sigma)
    w = vector(market_weights, len(s), "market_weights", True)
    p, q, omega = np.asarray(p, float), np.asarray(q, float), np.asarray(omega, float)
    if abs(w.sum()-1) > 1e-9 or tau <= 0 or risk_aversion <= 0:
        raise InputError("invalid BL parameters")
    if p.ndim != 2 or p.shape[1] != len(s) or q.shape != (len(p),) or omega.shape != (len(p), len(p)):
        raise InputError("BL view dimensions mismatch")
    if not all(np.isfinite(x).all() for x in [p,q,omega]) or len(p)==0:
        raise InputError("BL requires finite, explicit views")
    if not np.allclose(omega, omega.T) or np.linalg.eigvalsh(omega).min() <= 0:
        raise InputError("view uncertainty must be positive definite")
    prior = risk_aversion * s @ w
    t = tau * s
    middle = p @ t @ p.T + omega
    gain = np.linalg.solve(middle, p @ t).T
    mean = prior + gain @ (q - p @ prior)
    mean_cov = t - gain @ p @ t
    return {"mean": mean, "mean_uncertainty": mean_cov, "predictive_covariance": s + mean_cov,
            "views": {"P": p, "Q": q, "Omega": omega, "tau": tau, "risk_aversion": risk_aversion}}
