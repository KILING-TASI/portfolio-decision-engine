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
    config={"data":{"return_type":"synthetic_total_return","source":"test","currency":"CNY","frequency":"daily","as_of":"2026-09-30"},
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


def frozen_fixture():
    spec=fixture()
    for node in spec["nodes"].values():
        node.update(retrievedAt="2026-10-09T10:00:00+08:00",availableAt="2026-07-20",frozenAt="2026-07-21",
                    versionId="original-report",sourceSha256="a"*64)
    return spec


def test_historical_frozen_declaration_and_current_acquisition_separate():
    converted=cn_lookthrough_input(frozen_fixture());result=lookthrough(converted,historical=True)
    assert result["unknown_weight"]==pytest.approx(.16)
    proof=result["disclosure_timing"]["etf"]
    assert proof["holdings_period"]=="2026-06-30"
    assert proof["published_at"]=="2026-07-20"
    assert proof["retrieved_at"].startswith("2026-10-09")
    assert proof["available_at"]=="2026-07-20"
    assert proof["point_in_time_status"]=="frozen_version_declared_not_independently_verified"


def test_historical_mode_requires_version_and_freeze_evidence():
    with pytest.raises(InputError,match="historical input requires"):
        lookthrough(cn_lookthrough_input(fixture()),historical=True)
    for field,value in [("frozenAt","2026-10-02"),("versionId",None),("sourceSha256",None)]:
        spec=frozen_fixture();spec["nodes"]["etf"][field]=value
        with pytest.raises(InputError):lookthrough(cn_lookthrough_input(spec),historical=True)


def test_late_revised_version_and_early_acquisition_are_rejected():
    spec=frozen_fixture();spec["nodes"]["etf"]["availableAt"]="2026-10-02"
    with pytest.raises(InputError,match="availability exceeds"):cn_lookthrough_input(spec)
    spec=frozen_fixture();spec["nodes"]["etf"]["retrievedAt"]="2026-06-01"
    with pytest.raises(InputError,match="acquisition predates"):cn_lookthrough_input(spec)


def test_additional_research_cutoff_cannot_be_extended_by_source_input():
    with pytest.raises(InputError,match="cutoff"):
        lookthrough(cn_lookthrough_input(fixture()),research_as_of="2026-06-30")


def test_engine_cutoff_rejects_later_disclosure_file(tmp_path):
    import numpy as np
    import pandas as pd
    from portfolio_engine.engine import run_engine
    from portfolio_engine.io import write_json
    file=tmp_path/"disclosure.json";write_json(file,cn_lookthrough_input(fixture()))
    returns=pd.DataFrame(np.random.default_rng(1).normal(0,.002,(120,2)),index=pd.bdate_range("2020-01-01",periods=120),columns=["a","b"])
    config={"data":{"return_type":"synthetic_total_return","source":"test","currency":"CNY","frequency":"daily","as_of":"2026-06-30"},
            "require_china_bear_coverage":False,"lookthrough_file":str(file),
            "bootstrap":{"paths":100,"max_paths":100,"horizon":20,"block_lengths":[10]}}
    from unittest.mock import patch
    with patch("portfolio_engine.engine.estimate_covariance",side_effect=AssertionError("late input should reject before optimization")):
        with pytest.raises(InputError,match="cutoff"):run_engine(returns,config)


def test_historical_cli_converts_declared_version_without_claiming_authentication(tmp_path):
    source=tmp_path/"frozen.json";source.write_text(json.dumps(frozen_fixture(),ensure_ascii=False),encoding="utf8")
    output=tmp_path/"converted"
    assert main(["convert-lookthrough","--input",str(source),"--out",str(output),"--historical","--as-of","2026-09-30"])==0
    assert read_json(output/"conversion-result.json")["historical_mode"]
    assert verify(output)["source_verification"]=="not_verified"


def test_cli_directory_alias_matches_and_rejects_ambiguous_output(tmp_path):
    source=Path(__file__).parents[1]/"examples/cn-lookthrough-demo.json"
    old=tmp_path/"old";new=tmp_path/"new"
    assert main(["convert-lookthrough","--input",str(source),"--out",str(old)])==0
    assert main(["convert-lookthrough","--input",str(source),"--out-dir",str(new)])==0
    assert read_json(old/"conversion-result.json")==read_json(new/"conversion-result.json")
    with pytest.raises(SystemExit) as error:
        main(["convert-lookthrough","--input",str(source),"--out",str(tmp_path/"a"),"--out-dir",str(tmp_path/"b")])
    assert error.value.code==2
    assert not (tmp_path/"a").exists() and not (tmp_path/"b").exists()
