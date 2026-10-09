import copy
from pathlib import Path

import pytest

from portfolio_engine.archive import read_json,verify
from portfolio_engine.cli import main
from portfolio_engine.workbench_contract import compatible_history,compare_legacy_reference


ROOT=Path(__file__).parents[1]/"examples"


def fixture():return read_json(ROOT/"workbench-buy-hold.json")


def test_identical_input_matches_frozen_current_workbench_method_subset():
    result,path=compatible_history(fixture())
    comparison=compare_legacy_reference(result,read_json(ROOT/"workbench-buy-hold-reference.json"))
    assert comparison["status"]=="matched_supported_subset"
    assert result["compatible_fields"]["totalReturnPct"]==pytest.approx(10)
    assert result["compatible_fields"]["maximumDrawdownPct"]==pytest.approx(-10)
    assert result["native_fields"]["maximum_drawdown_loss_fraction"]==pytest.approx(.1)
    assert path.daily.value.iloc[-1]==pytest.approx(1.1)
    assert result["cost_rate"]==0 and result["unknown_policy"].startswith("no imputation")


@pytest.mark.parametrize("key,value",[("cost_rate",.001),("external_cashflows",[{"date":"2026-01-05","amount":10}]),("amount_unit","million")])
def test_not_equivalent_scope_is_rejected_without_defaulting_to_zero(key,value):
    spec=fixture();spec[key]=value
    result,path=compatible_history(spec)
    assert result["status"]=="unsupported_not_equivalent" and path is None


def test_new_modes_unknown_scope_or_missing_dates_not_silently_migrated():
    spec=fixture();spec["payload"]["historicalPortfolioMode"]="fixed-observation-weights"
    assert compatible_history(spec)[0]["status"]=="unsupported_not_equivalent"
    spec=fixture();spec["payload"]["unknownExposure"]=.2
    assert compatible_history(spec)[0]["status"]=="unsupported_not_equivalent"
    spec=fixture();spec["payload"]["holdings"][1]["history"].pop(1)
    assert compatible_history(spec)[0]["status"]=="unsupported_not_equivalent"


def test_reference_binds_input_and_mismatch_does_not_pass():
    result,_=compatible_history(fixture());reference=read_json(ROOT/"workbench-buy-hold-reference.json")
    reference["payload_sha256"]="0"*64
    assert compare_legacy_reference(result,reference)["status"]=="input_mismatch"
    reference=read_json(ROOT/"workbench-buy-hold-reference.json");reference["compatible_fields"]["totalReturnPct"]+=1
    assert compare_legacy_reference(result,reference)["status"]=="not_equivalent"


def test_legacy_unique_date_sorting_is_explicitly_preserved():
    spec=fixture()
    for row in spec["payload"]["holdings"]:row["history"].reverse()
    result,_=compatible_history(spec)
    assert result["compatible_fields"]["totalReturnPct"]==pytest.approx(10)
    assert "sort" in result["date_normalization"]


def test_cli_comparison_freezes_both_inputs_and_manifest(tmp_path):
    out=tmp_path/"compatibility"
    assert main(["workbench-buy-hold","--input",str(ROOT/"workbench-buy-hold.json"),"--reference",str(ROOT/"workbench-buy-hold-reference.json"),"--out",str(out)])==0
    result=read_json(out/"compatibility-result.json")
    assert result["equivalence_status"]=="matched_supported_subset"
    assert (out/"source-input.json").read_bytes()==(ROOT/"workbench-buy-hold.json").read_bytes()
    assert verify(out)["status"]=="stored_content_verified"
