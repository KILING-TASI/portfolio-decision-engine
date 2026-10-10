"""Narrow observed-value contract; does not simulate trades or available cash."""
from collections import defaultdict
from datetime import date
import hashlib
import json
import math

from .backtest import xirr
from .validation import InputError

METHOD = "observed-flow-link-and-native-xirr-v1"
DECLARATIONS = {
    "valuation_timing": "before-and-after-external-flow",
    "fee_basis": "included-in-observed-values",
    "frozen_basis": "included-in-total-value-not-available-cash",
    "settlement_basis": "observed-values-not-guaranteed-receipts",
}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                   allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def observed_cashflow(spec):
    if not isinstance(spec, dict) or spec.get("schema") != "workbench-observed-cashflow-input-v1":
        raise InputError("explicit observed cashflow schema required")
    allowed = {"schema", "payload", "requested_method_version", *DECLARATIONS}
    if set(spec)-allowed or spec.get("requested_method_version") != METHOD:
        raise InputError("unknown field or unsupported observed cashflow method")
    for key, value in DECLARATIONS.items():
        if spec.get(key) != value:
            raise InputError("unsupported or unknown declaration: " + key)
    payload = spec.get("payload")
    if not isinstance(payload, dict) or set(payload)-{
        "cashFlowCoverage", "basis", "currency", "amountUnit", "observations",
        "accountLabel", "exampleType", "dividends"
    }:
        raise InputError("unsupported observed payload")
    if payload.get("cashFlowCoverage") != "declared-complete":
        raise InputError("unknown cashflow coverage cannot be zero")
    if payload.get("currency") != "CNY" or payload.get("amountUnit") != "base":
        raise InputError("only explicit CNY base amounts supported; no conversion")
    if not isinstance(payload.get("basis"), str) or not payload["basis"].strip():
        raise InputError("valuation and cashflow basis required")
    rows = payload.get("observations")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 20000:
        raise InputError("2 to 20000 observed valuation rows required")
    ledger, flows = [], defaultdict(float)
    product, external = 1., 0.
    def number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise InputError("observed amount must be a finite number, not unknown")
        return float(value)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"date", "beforeFlowValue", "externalFlow", "afterFlowValue"}:
            raise InputError("explicit date and before/flow/after amounts required")
        day = row["date"]
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day or (ledger and day <= ledger[-1]["date"]):
            raise InputError("unique strictly increasing ISO dates required")
        before, flow, after = [number(row[k]) for k in ("beforeFlowValue", "externalFlow", "afterFlowValue")]
        tolerance = max(.01, math.ulp(max(abs(before), abs(after), abs(flow))) * 8)
        if before < 0 or after < 0 or abs(after-before-flow) > tolerance:
            raise InputError("observed valuation conservation failed; fees are not external flows")
        period = None
        if ledger:
            if ledger[-1]["afterFlowValue"] <= 0:
                raise InputError("cannot link return after zero account value")
            period = before / ledger[-1]["afterFlowValue"] - 1
            product *= 1 + period
        else:
            flows[day] -= before
        flows[day] -= flow
        external += flow
        ledger.append({**row, "periodReturnPct": None if period is None else period * 100})
    flows[ledger[-1]["date"]] += ledger[-1]["afterFlowValue"]
    ordered = [(d, v) for d, v in sorted(flows.items()) if v]
    if not all(math.isfinite(v) for v in [product, external, *flows.values()]):
        raise InputError("observed result exceeds finite numeric range")
    signs = [1 if v > 0 else -1 for _, v in ordered]
    conventional = bool(signs and signs[0] < 0 and signs[-1] > 0 and
                        sum(a != b for a, b in zip(signs, signs[1:])) == 1)
    irr = xirr(ordered) if conventional else {"status": "unresolved_nonconventional", "value": None}
    fields = {"twrPct": (product-1)*100, "xirrPct": None if irr["value"] is None else irr["value"]*100,
              "netExternalFlow": external, "openingValue": ledger[0]["beforeFlowValue"],
              "endingValue": ledger[-1]["afterFlowValue"],
              "profit": ledger[-1]["afterFlowValue"]-ledger[0]["beforeFlowValue"]-external}
    if any(v is not None and not math.isfinite(v) for v in fields.values()):
        raise InputError("nonfinite observed result")
    return {"schema": "workbench-observed-cashflow-result-v1", "method_version": METHOD,
            "status": "calculated_supported_subset", "start": ledger[0]["date"], "end": ledger[-1]["date"],
            "currency": "CNY", "amount_unit": "base", "payload_sha256": canonical_hash(payload),
            "input_sha256": canonical_hash(spec), "declarations": DECLARATIONS,
            "compatible_fields": fields, "xirr_native": irr, "ledger": ledger,
            "limits": ["declared completeness and valuations are not verified",
                       "TWR is cumulative; XIRR annualized actual days / 365.25",
                       "native XIRR root search differs from workbench; compare only supported conventional cases",
                       "total account values include frozen cash, not spendable cash",
                       "fees already included in observed values; no second cost deduction",
                       "no inference of liquidity, settlement dates or actual trade execution"]}
