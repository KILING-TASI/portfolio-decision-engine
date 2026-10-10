import json
from pathlib import Path

import pytest

from portfolio_engine.archive import verify
from portfolio_engine.cash_demand import cash_demand
from portfolio_engine.cli import main
from portfolio_engine.validation import InputError


def teaching():
    return json.loads((Path(__file__).parents[1] / "examples/cash-demand-demo.json").read_text(encoding="utf-8"))


def test_dated_pressure_and_cash_conservation():
    r = cash_demand(teaching())
    normal, stressed, frozen = r["scenarios"]
    assert normal["first_gap"] is None
    assert normal["closing_available_cash_conditional"] == 1900
    assert normal["net_liquidation_needed_without_planned_sales"] == 8000
    assert stressed["first_gap"] == {"date": "2026-10-20", "amount": 8070}
    assert stressed["peak_additional_net_cash_needed"] == 13070
    assert frozen["first_gap"] == {"date": "2026-10-28", "amount": 3100}
    assert frozen["closing_frozen_cash"] == 5000
    assert r["opening_cash"]["available_account_cash"] == 10000
    for s in r["scenarios"]:
        for row in s["daily_ledger"]:
            assert row["opening_available_cash"] + row["income"] + row["release"] + row["sale_net"] - row["expense"] == pytest.approx(row["closing_available_cash_conditional"])
        assert s["closing_frozen_cash"] + sum(d["release"] for d in s["daily_ledger"]) == 5000
    assert stressed["settlement_proceeds"][0]["estimated_fee"] == 70
    assert stressed["settlement_proceeds"][0]["net_amount"] == pytest.approx(6930)


def test_late_receipt_cannot_cover_earlier_gap():
    s = teaching(); s["liquidity"]["bond-lot"]["settlement_days"] = 30
    r = cash_demand(s)["scenarios"][0]
    assert r["first_gap"] == {"date": "2026-10-20", "amount": 3000}
    assert r["peak_additional_net_cash_needed"] == 8000
    assert r["settlement_proceeds"][0]["reason"] == "not_available_within_horizon"
    assert all(d["sale_net"] == 0 for d in r["daily_ledger"])


@pytest.mark.parametrize("field", ["can_sell", "haircut", "fee_rate", "settlement_days", "settlement_day_basis", "earliest_sale_date", "source", "fee_timing"])
def test_missing_liquidity_terms_not_assumed_zero_or_timely(field):
    s = teaching(); s["liquidity"]["bond-lot"].pop(field)
    r = cash_demand(s)["scenarios"][0]
    assert r["status"] == "conditional_with_unknowns"
    assert r["complete_cash_balance"] is None
    assert any(u["id"] == "sale-1" for u in r["unknowns"])
    assert all(d["sale_net"] == 0 for d in r["daily_ledger"])
    bond = next(a for a in r["asset_liquidation_values"] if a["position_id"] == "bond-lot")
    assert bond["conditional_net_liquidation_value"] is None


def test_unknown_income_and_release_not_a_complete_zero_forecast():
    s = teaching(); s["cashflows"][1]["amount"] = None
    s["frozen_releases"][0]["condition_met"] = None
    r = cash_demand(s)["scenarios"][0]
    assert r["complete_projection_status"] == "not_estimable_with_unknown_cash_events"
    assert r["complete_cash_balance"] is None
    assert {u["id"] for u in r["unknowns"]} == {"income-1", "release-1"}
    assert r["closing_frozen_cash"] == 5000


@pytest.mark.parametrize("case", ["same_economic_event", "release_exceeds_frozen", "sales_exceed_book", "same_day_flow", "root_cash_as_sale", "derived_leaf_sale", "wrong_currency", "before_liquidity_date", "unknown_pressure", "wrong_method", "missing_income_date", "probability", "business_day_basis"])
def test_reject_double_count_or_invalid_dates(case):
    s = teaching()
    if case == "same_economic_event": s["cashflows"][1]["economic_event_id"] = "release-1"
    elif case == "release_exceeds_frozen": s["frozen_releases"][0]["amount"] = 5001
    elif case == "sales_exceed_book": s["planned_liquidations"][0]["book_amount"] = 20001
    elif case == "same_day_flow": s["cashflows"][0]["date"] = "2026-10-09"
    elif case == "root_cash_as_sale": s["planned_liquidations"][0]["position_id"] = "cash-lot"
    elif case == "derived_leaf_sale": s["planned_liquidations"][0]["position_id"] = "BOND_A"
    elif case == "wrong_currency": s["account"]["positions"][0]["currency"] = "USD"
    elif case == "before_liquidity_date": s["liquidity"]["bond-lot"]["earliest_sale_date"] = "2026-10-14"
    elif case == "unknown_pressure": s["scenarios"][0]["additional_haircut"] = None
    elif case == "wrong_method": s["requested_method_version"] = "other"
    elif case == "missing_income_date": s["scenarios"][1].pop("income_change_from")
    elif case == "probability": s["scenarios"][0]["probability"] = .9
    elif case == "business_day_basis": s["liquidity"]["bond-lot"]["settlement_day_basis"] = "business"
    with pytest.raises(InputError): cash_demand(s)


def test_root_book_vs_net_value_and_no_automatic_sales():
    s = teaching(); s["planned_liquidations"] = []
    r = cash_demand(s)["scenarios"][0]
    assert r["first_gap"] == {"date": "2026-10-20", "amount": 3000}
    assert r["peak_additional_net_cash_needed"] == 8000
    assert all(row["sale_net"] == 0 for row in r["daily_ledger"])
    assert r["gross_book_amount_required"] is None
    bond = next(a for a in r["asset_liquidation_values"] if a["position_id"] == "bond-lot")
    assert bond["book_amount"] == 20000 and bond["conditional_net_liquidation_value"] == 19800
    compare = next(a for a in r["additional_liquidity_comparisons"] if a["position_id"] == "bond-lot")
    assert compare["book_amount_for_peak_net_need"] == pytest.approx(8000 / .99)
    assert compare["sufficient_alone_under_assumptions"]


def test_cli_frozen_input_and_new_result_directory(tmp_path):
    s = teaching(); source = tmp_path / "source.json"; source.write_text(json.dumps(s), encoding="utf-8")
    out = tmp_path / "normal"
    assert main(["cash-demand", "--input", str(source), "--out", str(out)]) == 0
    original = (out / "source-input.json").read_bytes()
    assert verify(out)["status"] == "stored_content_verified"
    assert main(["cash-demand", "--input", str(source), "--out", str(out)]) == 2
    s["cashflows"][0]["amount"] = 50000
    source.write_text(json.dumps(s), encoding="utf-8")
    assert main(["cash-demand", "--input", str(source), "--out", str(tmp_path / "new")]) == 0
    assert (out / "source-input.json").read_bytes() == original
