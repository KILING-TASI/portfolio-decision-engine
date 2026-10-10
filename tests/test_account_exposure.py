import copy
import json
from pathlib import Path

import pytest

from portfolio_engine.account_exposure import account_exposure
from portfolio_engine.archive import verify
from portfolio_engine.cli import main
from portfolio_engine.validation import InputError


def teaching():
    return json.loads((Path(__file__).parents[1] / "examples/account-exposure-demo.json").read_text(encoding="utf-8"))


def test_conservation_and_separate_cash():
    r = account_exposure(teaching())
    assert r["total_amount"] == 100000
    assert sum(r["root_kind_amounts"].values()) == 100000
    assert r["root_kind_amounts"]["fund"] == 40000
    assert r["known_amount"] == 92000
    assert r["unknown_amount"] == pytest.approx(8000)
    assert r["cash"]["available_account_cash"] == 10000
    assert r["cash"]["frozen_account_cash"] == 5000
    assert r["cash"]["fund_disclosed_cash"] == 4000
    assert r["security_amounts"]["STOCK_A"] == 35000
    assert r["security_amounts"]["BOND_A"] == 28000
    assert sum(r["security_amounts"].values()) + r["unknown_amount"] == r["total_amount"]
    assert r["scenarios"][1]["estimated_change"] == -1120
    assert r["scenarios"][1]["covered_amount"] == 28000
    assert r["scenarios"][1]["unestimated_amount"] == 72000


def test_convertible_weight_is_not_option_risk():
    spec = teaching(); spec["securities"]["CB_A"]["modified_duration"] = 6
    r = account_exposure(spec)
    cb = next(row for row in r["exposure_paths"] if row["security"] == "CB_A")
    assert cb["weight"] == .1
    assert cb["risk_inputs"]["modified_duration"] is None
    assert cb["risk_inputs"]["option_risk"] == "unknown_without_terms_and_option_model"
    assert r["scenarios"][1]["covered_amount"] == 28000


def test_missing_terms_not_zero_risk():
    spec = teaching(); spec["securities"]["BOND_A"].pop("modified_duration")
    r = account_exposure(spec)
    assert r["scenarios"][1]["estimated_change"] is None
    assert r["scenarios"][1]["unestimated_amount"] == 100000
    assert r["known_amount"] == 92000


def test_missing_identity_and_mapping_stay_unknown():
    spec = teaching(); spec["securities"].pop("STOCK_A")
    r = account_exposure(spec)
    assert r["unknown_amount"] == pytest.approx(43000)
    assert r["known_amount"] == 57000
    spec = teaching(); spec["securities"]["STOCK_A"].pop("industry")
    assert account_exposure(spec)["unmapped_amounts"]["industry"] == 73000


@pytest.mark.parametrize("case", ["duplicate_lot", "derived_as_direct", "currency", "valuation", "future_disclosure", "frozen_exceeds_cash", "issuer_without_source", "industry_without_source", "future_terms", "rate_too_large", "unknown_scenario", "unknown_method", "kind_conflict", "fund_lock", "unknown_unit", "overflow"])
def test_reject_unsafe_join(case):
    s = teaching()
    if case == "duplicate_lot": s["positions"][1]["economic_lot_id"] = "fund-lot"
    elif case == "derived_as_direct": s["positions"][1]["origin"] = "fund_disclosure"
    elif case == "currency": s["positions"][1]["currency"] = "USD"
    elif case == "valuation": s["positions"][1]["valuation_date"] = "2026-09-29"
    elif case == "future_disclosure": s["nodes"]["fund-demo"]["published_at"] = "2026-10-10"
    elif case == "frozen_exceeds_cash": s["positions"][-1]["frozen_amount"] = 15001
    elif case == "issuer_without_source": s["securities"]["STOCK_A"].pop("issuer_source")
    elif case == "industry_without_source": s["securities"]["STOCK_A"].pop("industry_source")
    elif case == "future_terms": s["securities"]["BOND_A"]["terms_as_of"] = "2026-10-10"
    elif case == "rate_too_large": s["rate_scenarios"][0]["rate_change"] = .1
    elif case == "unknown_scenario": s["selected_scenario"] = "hidden"
    elif case == "unknown_method": s["requested_method_version"] = "other"
    elif case == "kind_conflict": s["securities"]["STOCK_A"]["kind"] = "bond"
    elif case == "fund_lock": s["positions"][0]["frozen_amount"] = 1000
    elif case == "unknown_unit": s["amount_unit"] = "million"
    elif case == "overflow":
        s["positions"][2]["amount"] = 9e307
        s["securities"]["BOND_A"]["modified_duration"] = 100
        s["rate_scenarios"][0]["rate_change"] = .02
    with pytest.raises(InputError): account_exposure(s)


def test_cycle_unknown_and_stale_period_preserved():
    s = teaching(); s["nodes"]["fund-demo"]["holdings"].append({"kind": "fund", "node": "fund-demo", "weight": .1})
    r = account_exposure(s)
    assert r["unknown_amount"] == pytest.approx(8000)
    assert any(u["reason"] == "cycle" for u in r["unknown"])
    assert r["exposure_paths"][0]["timing"]["report_date"] == "2026-06-30"
    assert r["valuation_date"] == "2026-09-30"


def test_limited_real_nav_does_not_invent_holdings():
    s = json.loads((Path(__file__).parents[1] / "examples/account-exposure-limited-real.json").read_text(encoding="utf-8"))
    r = account_exposure(s)
    assert r["unknown_weight"] == 1
    assert r["known_amount"] == 0
    assert r["scenarios"][1]["estimated_change"] is None
    assert all(u["reason"] == "missing_fund_disclosure" for u in r["unknown"])


def test_cli_freeze_and_scenario_replay(tmp_path):
    s = teaching(); before = copy.deepcopy(s)
    path = tmp_path / "input.json"; path.write_text(json.dumps(s), encoding="utf-8")
    out = tmp_path / "base"
    assert main(["account-exposure", "--input", str(path), "--out", str(out)]) == 0
    assert verify(out)["status"] == "stored_content_verified"
    html = (out / "exposure-report.html").read_text(encoding="utf-8")
    assert 'id="filter"' in html and 'id="scenario"' in html and 'id="save-input"' in html
    s["selected_scenario"] = "rate_up_100bp"
    s["requested_method_version"] = "declared-account-exposure-v1"
    path.write_text(json.dumps(s), encoding="utf-8")
    assert main(["account-exposure", "--input", str(path), "--out", str(tmp_path / "scenario")]) == 0
    assert json.loads((out / "source-input.json").read_text(encoding="utf-8")) == before
    assert main(["account-exposure", "--input", str(path), "--out", str(out)]) == 2
