import numpy as np
import pandas as pd


class InputError(ValueError):
    """An input violates the declared research contract."""


def returns_frame(data):
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise InputError("returns must be a nonempty DataFrame")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise InputError("returns index must contain dates")
    if data.index.has_duplicates or not data.index.is_monotonic_increasing:
        raise InputError("dates must be unique and increasing")
    if data.columns.has_duplicates or any(not isinstance(c, str) for c in data.columns):
        raise InputError("asset names must be unique strings")
    x = data.to_numpy(dtype=float)
    if not np.isfinite(x).all() or np.any(x <= -1):
        raise InputError("returns must be finite and greater than -1; missing values are not filled")
    return data.astype(float)


def vector(value, n, name, nonnegative=False):
    result = np.broadcast_to(np.asarray(value, dtype=float), (n,)).copy()
    if not np.isfinite(result).all() or (nonnegative and (result < 0).any()):
        raise InputError(f"invalid {name}")
    return result


def weights(value, n):
    w = vector(value, n, "weights", True)
    if w.sum() > 1 + 1e-9:
        raise InputError("asset weights exceed 1; remaining weight is cash")
    return w


def covariance(value):
    s = np.asarray(value, dtype=float)
    if s.ndim != 2 or s.shape[0] != s.shape[1] or not np.isfinite(s).all():
        raise InputError("invalid covariance matrix")
    if not np.allclose(s, s.T, atol=1e-12) or np.linalg.eigvalsh(s).min() < -1e-12:
        raise InputError("covariance must be symmetric positive semidefinite")
    return s
