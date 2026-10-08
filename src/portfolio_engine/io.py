import hashlib
import json
import csv
from pathlib import Path

import numpy as np
import pandas as pd

from .validation import InputError,returns_frame


def load_returns(path,kind="returns"):
    path=Path(path)
    with path.open(encoding="utf-8-sig",newline="") as handle:
        header=next(csv.reader(handle),[])
    if len(header)!=len(set(header)):
        raise InputError("duplicate CSV columns")
    table=pd.read_csv(path)
    if "date" not in table or len(table.columns)<2:
        raise InputError("CSV requires date and one or more asset columns")
    if table.columns.duplicated().any():
        raise InputError("duplicate CSV columns")
    table["date"]=pd.to_datetime(table["date"],errors="raise")
    frame=table.set_index("date").astype(float)
    if kind=="prices":
        if not np.isfinite(frame.to_numpy()).all() or (frame<=0).any().any():
            raise InputError("prices must be finite and positive")
        # Validate original dates before dropping the first price row.
        returns_frame(frame*0)
        frame=frame.pct_change(fill_method=None).iloc[1:]
    elif kind!="returns":
        raise InputError("input_kind must be returns or prices")
    return returns_frame(frame),hashlib.sha256(path.read_bytes()).hexdigest()


def clean_json(value):
    if isinstance(value,dict):
        return {str(k):clean_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):
        return [clean_json(v) for v in value]
    if isinstance(value,(np.integer,)):
        return int(value)
    if isinstance(value,(np.bool_,)):
        return bool(value)
    if isinstance(value,(float,np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value,(pd.Timestamp,)):
        return value.isoformat()
    return value


def write_json(path,value):
    Path(path).write_text(json.dumps(clean_json(value),ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
