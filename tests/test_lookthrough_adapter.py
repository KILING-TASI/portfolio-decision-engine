import copy
import json
from pathlib import Path

import pytest

from portfolio_engine.archive import read_json,verify
from portfolio_engine.cli import main
from portfolio_engine.data_bridge import lookthrough
from portfolio_engine.lookthrough_adapter import cn_lookthrough_input
from portfolio_engine.validation import InputError


def fixture():
    return read_json(Path(__file__).parents[1]/"examples/cn-lookthrough-demo.json")


def test_pinned_upstream_fixture_exposures_and_unknown_match():
    converted=cn_lookthrough_input(fixture());result=lookthrough(converted)
    assert result["leaves"]==pytest.approx({"CN-SSE:DEMO-A":.524,"CN-SSE:DEMO-B":.216,"CN-SSE:DEMO-C":.1})
    assert result["issuer_exposure"]==pytest.approx({"教学公司A":.524,"教学公司B":.216,"教学公司C":.1})
    assert result["known_weight"]==pytest.approx(.84)
    assert result["unknown_weight"]==pytest.approx(.16)
    assert result["known_weight"]+result["unknown_weight"]==pytest.approx(1)
    assert "no full-portfolio risk" in result["analysis_scope"]


def test_source_dates_currency_and_mapping_basis_preserved():
    spec=fixture();spec["nodes"]["active"].update(disclosureScope="top10",weightBasis="parent_net_assets",locator="PDF page 48",version="original")
    result=lookthrough(cn_lookthrough_input(spec))
    evidence=result["disclosure_evidence"]["active"]
    assert evidence["published_at"]=="2026-07-20"
    assert evidence["report_date"]=="2026-06-30"
    assert evidence["currency"]=="CNY"
    assert evidence["raw_metadata"]["locator"]=="PDF page 48"
    assert evidence["disclosure_scope"]=="top10"
    assert result["unknown_weight"]==pytest.approx(.16)
    assert result["security_metadata"]==spec["securities"]
    trace=next(t for t in result["paths"] if t["root_position"]=="主动基金")
    assert trace["source_reference"]==spec["nodes"]["active"]["source"]
    assert trace["mapping_source"]==spec["securities"][trace["security"]]["source"]


def test_missing_security_and_missing_issuer_are_distinct():
    spec=fixture();del spec["securities"]["CN-SSE:DEMO-B"]
    result=lookthrough(cn_lookthrough_input(spec))
    assert result["unknown_weight"]==pytest.approx(.376)
    assert any(u["reason"]=="security_identity_or_classification_missing" for u in result["unknown"])
    spec=fixture();spec["securities"]["CN-SSE:DEMO-B"].pop("issuer")
    result=lookthrough(cn_lookthrough_input(spec))
    assert result["unknown_weight"]==pytest.approx(.16)
    assert result["unmapped_stock_issuer_weight"]==pytest.approx(.216)
    assert result["leaves"]["CN-SSE:DEMO-B"]==pytest.approx(.216)


def test_issuer_aggregation_does_not_merge_securities():
    spec=fixture();spec["securities"]["CN-SSE:DEMO-B"]["issuer"]="教学公司A"
    result=lookthrough(cn_lookthrough_input(spec))
    assert result["issuer_exposure"]["教学公司A"]==pytest.approx(.74)
    assert len(result["leaves"])==3


def test_duplicate_root_fund_positions_preserve_root_ids():
    spec=fixture();spec["positions"][1]["node"]="feeder"
    result=lookthrough(cn_lookthrough_input(spec))
    assert result["known_weight"]==pytest.approx(.9)
    assert {t["root_position"] for t in result["paths"]}=={"联接基金","主动基金"}


def test_cycle_missing_child_and_mixed_periods_are_not_filled():
    spec=fixture();del spec["nodes"]["etf"]
    assert lookthrough(cn_lookthrough_input(spec))["unknown_weight"]==pytest.approx(.7)
    spec=fixture();spec["nodes"]["etf"]["holdings"]=[{"kind":"fund","node":"feeder","weight":1}]
    result=lookthrough(cn_lookthrough_input(spec))
    assert any(u["reason"]=="cycle" for u in result["unknown"])
    spec=fixture();spec["nodes"]["active"]["reportDate"]="2025-12-31";spec["nodes"]["active"]["publishedAt"]="2026-03-31"
    result=lookthrough(cn_lookthrough_input(spec))
    assert {t["report_date"] for t in result["paths"]}=={"2025-12-31","2026-06-30"}


@pytest.mark.parametrize("change",[dict(publishedAt="2027-01-01"),dict(currency="USD"),dict(source="")])
def test_inconsistent_source_or_cutoff_rejected(change):
    spec=fixture();spec["nodes"]["active"].update(change)
    with pytest.raises(InputError):cn_lookthrough_input(spec)


def test_leverage_mapping_evidence_and_root_normalization_rejected():
    spec=fixture();spec["nodes"]["active"]["holdings"][0]["weight"]=.9
    with pytest.raises(InputError,match="leveraged"):cn_lookthrough_input(spec)
    spec=fixture();spec["securities"]["CN-SSE:DEMO-A"]["source"]=""
    with pytest.raises(InputError,match="evidence"):cn_lookthrough_input(spec)
    spec=fixture();spec["positions"][0]["weight"]=.3
    with pytest.raises(InputError,match="sum to 1"):cn_lookthrough_input(spec)


def test_duplicate_rows_aggregate_exact_identity_without_loss():
    spec=fixture();row=spec["nodes"]["active"]["holdings"][0]
    row["weight"]=.25;spec["nodes"]["active"]["holdings"].append(copy.deepcopy(row))
    result=lookthrough(cn_lookthrough_input(spec))
    assert result["leaves"]["CN-SSE:DEMO-A"]==pytest.approx(.524)


def test_conversion_cli_freezes_bytes_and_attaches_manifest(tmp_path):
    source=tmp_path/"source.json";raw=json.dumps(fixture(),ensure_ascii=False,indent=1).encode("utf8");source.write_bytes(raw)
    out=tmp_path/"converted"
    assert main(["convert-lookthrough","--input",str(source),"--out",str(out)])==0
    assert (out/"source-input.json").read_bytes()==raw
    assert verify(out)["status"]=="stored_content_verified"
    result=read_json(out/"conversion-result.json")
    assert result["unknown_weight"]==pytest.approx(.16)
    assert main(["convert-lookthrough","--input",str(source),"--out",str(out)])==2


def test_conversion_is_explicit_not_a_result_summary_import():
    with pytest.raises(InputError):cn_lookthrough_input({"asOf":"2026-09-30","currency":"CNY","unknownExposure":.16,"securityExposure":{}})


def test_disclosed_structure_does_not_change_allocator_or_risk(tmp_path):
    import numpy as np
    import pandas as pd
    from portfolio_engine.engine import run_engine
    from portfolio_engine.io import write_json
    data=pd.DataFrame(np.random.default_rng(1).normal(.0001,.003,(120,2)),index=pd.bdate_range("2020-01-01",periods=120),columns=["a","b"])
    config={"data":{"return_type":"synthetic_total_return","source":"test","currency":"CNY","frequency":"daily"},
            "require_china_bear_coverage":False,"bootstrap":{"paths":100,"max_paths":100,"horizon":20,"block_lengths":[10],"budget":.9}}
    before,_=run_engine(data,config)
    disclosure=tmp_path/"lookthrough.json";write_json(disclosure,cn_lookthrough_input(fixture()))
    config=copy.deepcopy(config);config["lookthrough_file"]=str(disclosure)
    after,_=run_engine(data,config)
    assert after["supplemental"]["lookthrough"]["unknown_weight"]==pytest.approx(.16)
    for method,allocation in before["modules"]["M1"]["allocation"]["candidates"].items():
        assert after["modules"]["M1"]["allocation"]["candidates"][method]==pytest.approx(allocation)
    assert after["modules"]["M2"]["selected"]==before["modules"]["M2"]["selected"]
    assert after["modules"]["M7"]["annual_volatility"]==before["modules"]["M7"]["annual_volatility"]


def test_account_wrapper_does_not_collide_with_missing_fund_reference():
    spec=fixture();spec["positions"][0]["node"]="__cn_account_root__"
    value=cn_lookthrough_input(spec)
    assert value["root"]!="__cn_account_root__"
    result=lookthrough(value)
    assert any(row["reason"]=="missing_child" and row["root_position"]=="联接基金" for row in result["unknown"])
