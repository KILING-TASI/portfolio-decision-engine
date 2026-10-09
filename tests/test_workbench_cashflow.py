import copy
from pathlib import Path

import pytest

from portfolio_engine.archive import read_json, verify
from portfolio_engine.cli import main
from portfolio_engine.validation import InputError
from portfolio_engine.workbench_cashflow import observed_cashflow, canonical_hash

ROOT = Path(__file__).parents[1] / "examples"


@pytest.mark.parametrize("case", read_json(ROOT / "workbench-observed-reference.json")["cases"])
def test_same_input_matches_bound_workbench_reference(case):
    assert canonical_hash(case["input"]["payload"]) == case["payload_sha256"]
    result = observed_cashflow(case["input"])
    for key, expected in case["reference_fields"].items():
        if expected is None:
            assert result["compatible_fields"][key] is None
        else:
            assert result["compatible_fields"][key] == pytest.approx(expected, abs=1e-6)
    assert result["start"] == case["input"]["payload"]["observations"][0]["date"]
    assert result["end"] == case["input"]["payload"]["observations"][-1]["date"]


@pytest.mark.parametrize("key,value", [
    ("valuation_timing", "flow-before-period-return"),
    ("fee_basis", "deduct-again"), ("frozen_basis", "spendable"),
    ("settlement_basis", "guaranteed"), ("requested_method_version", "v2"),
])
def test_incompatible_basis_and_method_rejected(key, value):
    spec = read_json(ROOT / "workbench-observed-cashflow.json")
    spec[key] = value
    with pytest.raises(InputError):
        observed_cashflow(spec)


@pytest.mark.parametrize("key,value", [("currency", "USD"), ("amountUnit", "thousand"),
                                       ("cashFlowCoverage", "unknown")])
def test_scope_unknown_not_silently_converted(key, value):
    spec = read_json(ROOT / "workbench-observed-cashflow.json")
    spec["payload"][key] = value
    with pytest.raises(InputError):
        observed_cashflow(spec)


def test_missing_valuation_dates_and_conservation():
    original = read_json(ROOT / "workbench-observed-cashflow.json")
    for mutate in [lambda r: r.update(beforeFlowValue=None),
                   lambda r: r.update(afterFlowValue=999),
                   lambda r: r.update(date="2025-01-01"),
                   lambda r: r.update(externalFlow=True)]:
        spec = copy.deepcopy(original)
        mutate(spec["payload"]["observations"][1])
        with pytest.raises(InputError):
            observed_cashflow(spec)


def test_cli_frozen_exact_input_and_new_directory(tmp_path):
    source = ROOT / "workbench-observed-cashflow.json"
    out = tmp_path / "observed"
    assert main(["workbench-observed-cashflow", "--input", str(source), "--out", str(out)]) == 0
    assert (out / "source-input.json").read_bytes() == source.read_bytes()
    assert verify(out)["status"] == "stored_content_verified"
    assert main(["workbench-observed-cashflow", "--input", str(source), "--out", str(out)]) == 2


def test_flow_before_return_simulation_is_not_observed_flow_after_return():
    import pandas as pd
    from portfolio_engine.backtest import backtest
    spec = read_json(ROOT / "workbench-observed-cashflow.json")
    observed = observed_cashflow(spec)
    frame = pd.DataFrame({"synthetic": [.1, .05]}, index=pd.to_datetime(["2025-07-01", "2026-01-01"]))
    simulated = backtest(frame, [1], initial_value=100, costs=0, rebalance="none",
                         initial_date="2025-01-01", cashflows=pd.Series({pd.Timestamp("2025-07-01"): 50}))
    # Remove the final withdrawal from the observed account to isolate timing.
    spec["payload"]["observations"][-1].update(externalFlow=0, afterFlowValue=168)
    observed = observed_cashflow(spec)
    assert simulated.daily.value.iloc[-1] == pytest.approx(173.25)
    assert observed["compatible_fields"]["endingValue"] == 168
