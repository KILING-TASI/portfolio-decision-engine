import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from portfolio_engine.archive import atomic_output,manifest,verify,read_json
from portfolio_engine.cli import main
from portfolio_engine.collect import collect_requests
from portfolio_engine.data_bridge import total_return_index,prepare_bundle,validate_context,closing_premium,lookthrough,workbench_adapter
from portfolio_engine.validation import InputError


def nav_asset():
    return {"code":"fund","currency":"CNY","source_url":"https://example.org/nav","basis":"nav_with_events",
            "event_coverage":"declared_complete_for_window","events":[{"date":"2020-01-02","cash_per_old_unit":.1,"source_url":"https://example.org/event"}],
            "history":[{"date":"2020-01-01","nav":1},{"date":"2020-01-02","nav":.9},{"date":"2020-01-03","nav":.99}]}


def test_dividend_drop_is_not_loss_and_split_is_not_gain():
    asset=nav_asset();value,_=total_return_index(asset)
    assert value.to_numpy()==pytest.approx([1,1,1.1])
    asset["events"]=[{"date":"2020-01-02","new_units_per_old_unit":2,"source_url":"https://example.org/event"}]
    asset["history"][1]["nav"]=.5;asset["history"][2]["nav"]=.55
    assert total_return_index(asset)[0].to_numpy()==pytest.approx([1,1,1.1])


def test_raw_price_and_incomplete_events_are_rejected():
    asset=nav_asset();asset["basis"]="raw_price"
    with pytest.raises(InputError,match="raw prices"):total_return_index(asset)
    asset=nav_asset();asset["event_coverage"]="unverified"
    with pytest.raises(InputError,match="complete-event"):total_return_index(asset)
    asset=nav_asset();asset["events"]*=2
    with pytest.raises(InputError):total_return_index(asset)


def test_prepare_exact_alignment_and_currency():
    a=nav_asset();b=copy.deepcopy(a);b["code"]="second"
    spec={"currency":"CNY","frequency":"daily","assets":[a,b],"synthetic":True}
    # Two return observations are insufficient for spacing inference, but an
    # explicit matching calendar permits this small arithmetic example.
    spec["calendar"]={"source_url":"https://example.org/calendar","start":"2020-01-01","end":"2020-01-03",
                      "dates":["2020-01-01","2020-01-02","2020-01-03"],"applicability_confirmed":True}
    frame,meta,quality=prepare_bundle(spec)
    assert frame.iloc[:,0].to_numpy()==pytest.approx([0,.1])
    assert meta["return_type"]=="synthetic_total_return"
    assert quality["calendar_status"]=="dates_aligned"
    b["currency"]="USD"
    with pytest.raises(InputError,match="currencies"):prepare_bundle(spec)
    b["currency"]="CNY";b["history"][1]["date"]="2020-01-04"
    with pytest.raises(InputError):prepare_bundle(spec)


def test_monthly_cannot_use_daily_annualization():
    frame=pd.DataFrame({"fund":[0]*40},index=pd.date_range("2020-01-31",periods=40,freq="ME"))
    meta={"currency":"CNY","frequency":"monthly"}
    assert validate_context(frame,meta)["periods_per_year"]==12
    with pytest.raises(InputError,match="conflict"):validate_context(frame,meta,252)
    with pytest.raises(InputError):validate_context(frame.drop(frame.index[3]),meta)


def test_calendar_missing_date_rejected_not_filled():
    dates=pd.bdate_range("2020-01-01",periods=6)
    frame=pd.DataFrame({"fund":[0]*5},index=dates.delete(2))
    meta={"frequency":"daily","calendar":{"source_url":"https://example.org/calendar","start":"2020-01-01","end":"2020-01-08",
                                              "dates":[str(d.date()) for d in dates],"applicability_confirmed":True}}
    with pytest.raises(InputError,match="calendar mismatch"):validate_context(frame,meta)


def test_premium_common_dates_and_not_iopv():
    spec={"code":"fund","price_source_url":"https://example.org/p","nav_source_url":"https://example.org/n",
          "prices":[{"date":"2020-01-01","close":1.1},{"date":"2020-01-02","close":1.2}],
          "nav":[{"date":"2020-01-01","nav":1},{"date":"2020-01-03","nav":1.1}]}
    result=closing_premium(spec)
    assert result["rows"][0]["premium"]==pytest.approx(.1)
    assert result["missing_nav_dates"]==["2020-01-02"]
    assert "IOPV" in result["limitations"][0]


def holding_spec():
    return {"root":"root","currency":"CNY","as_of":"2020-03-31","nodes":{
        "root":{"currency":"CNY","report_date":"2019-12-31","published_at":"2020-03-01","source_url":"https://example.org/holdings",
                "holdings":[{"kind":"fund","node":"missing","weight":.3},{"kind":"stock","id":"stock","weight":.5}]}}}


def test_lookthrough_preserves_missing_undisclosed_and_cycles():
    spec=holding_spec();result=lookthrough(spec)
    assert result["known_weight"]==pytest.approx(.5)
    assert result["unknown_weight"]==pytest.approx(.5)
    assert {r["reason"] for r in result["unknown"]}=={"missing_child","undisclosed"}
    spec["nodes"]["root"]["holdings"][0]["node"]="root"
    assert "cycle" in {r["reason"] for r in lookthrough(spec)["unknown"]}
    spec["nodes"]["root"]["published_at"]="2020-04-01"
    with pytest.raises(InputError,match="cutoff"):lookthrough(spec)


def test_workbench_adapter_requires_event_declarations():
    bundle={"type":"research-bundle","asOf":"2020-01-03","rows":[{"kind":"fund","code":"fund","historyBasis":"nav-with-distributions",
            "source":"https://example.org/nav","history":nav_asset()["history"]}]}
    spec=workbench_adapter(bundle,"CNY")
    with pytest.raises(InputError,match="complete-event"):total_return_index(spec["assets"][0])
    event={"fund":{"event_coverage":"declared_complete_for_window","events":nav_asset()["events"]}}
    converted=workbench_adapter(bundle,"CNY",event)
    assert total_return_index(converted["assets"][0])[0].iloc[-1]==pytest.approx(1.1)


def test_manifest_detects_tamper_method_and_extra_files(tmp_path):
    (tmp_path/"result.json").write_text("{}")
    manifest(tmp_path)
    assert verify(tmp_path)["status"]=="stored_content_verified"
    (tmp_path/"result.json").write_text('{"changed":true}')
    assert verify(tmp_path)["status"]=="content_mismatch"
    manifest(tmp_path)
    data=read_json(tmp_path/"report-manifest.json");data["methods"]["cli.py"]="0"*64
    (tmp_path/"report-manifest.json").write_text(json.dumps(data))
    assert verify(tmp_path)["status"]=="stored_content_verified_method_changed"
    (tmp_path/"extra").write_text("extra")
    assert verify(tmp_path)["status"]=="content_mismatch"


def test_manifest_rejects_path_escape(tmp_path):
    (tmp_path/"report-manifest.json").write_text(json.dumps({"schema_version":1,"files":{"../private":"0"*64},"methods":{}}))
    with pytest.raises(InputError,match="escapes"):verify(tmp_path)


def test_atomic_publication_does_not_publish_partial_or_overwrite(tmp_path):
    target=tmp_path/"result"
    with pytest.raises(RuntimeError):
        with atomic_output(target) as stage:
            (stage/"partial").write_text("partial")
            raise RuntimeError("failed")
    assert not target.exists()
    target.mkdir();(target/"old").write_text("keep")
    with pytest.raises(FileExistsError):
        with atomic_output(target):pass
    assert (target/"old").read_text()=="keep"


@pytest.mark.parametrize("text",['{"x":1,"x":2}','{"x":NaN}','{"x":1e999}'])
def test_strict_json_rejects_ambiguous_inputs(tmp_path,text):
    file=tmp_path/"input.json";file.write_text(text)
    with pytest.raises(InputError):read_json(file)


def test_collector_keeps_raw_identity_and_does_not_claim_total_return():
    spec={"requests":[{"provider":"eastmoney_fund_nav","code":"000001","start":"2020-01-01","end":"2020-01-04"}]}
    response=b'var fS_code="000001";var fS_name="demo";var Data_netWorthTrend=[{"x":1577836800000,"y":1},{"x":1577923200000,"y":1.1}];'
    result,raw=collect_requests(spec,True,lambda url:response)
    assert result["status"]=="observed"
    assert result["results"][0]["basis"]=="nav_with_unverified_events"
    assert raw["response-0.txt"]==response
    wrong=response.replace(b'"000001"',b'"000002"')
    result,_=collect_requests(spec,True,lambda url:wrong)
    assert result["status"]=="partial"
    with pytest.raises(InputError,match="online"):collect_requests(spec,False)


def test_cli_refuses_overwrite_and_keeps_failure_explanation(tmp_path):
    output=tmp_path/"report";output.mkdir();(output/"old").write_text("keep")
    assert main(["demo","--fast","--out",str(output)])==2
    assert (output/"old").read_text()=="keep"
    failed=tmp_path/"failed"
    assert main(["run","--returns","missing.csv","--config","missing.json","--out",str(failed)])==2
    assert (failed/"failure.json").exists()
    assert not (failed/"report.html").exists()


def test_prepare_then_run_and_verify_end_to_end(tmp_path):
    dates=pd.bdate_range("2020-01-01",periods=160)
    rng=np.random.default_rng(42);assets=[]
    for i in range(2):
        values=np.cumprod(1+rng.normal(.0002,.005+i*.002,len(dates)))
        assets.append({"code":f"asset{i}","currency":"CNY","source_url":"https://example.org/synthetic",
            "basis":"total_return_index","history":[{"date":str(d.date()),"value":float(v)} for d,v in zip(dates,values)]})
    spec={"currency":"CNY","frequency":"daily","synthetic":True,"assets":assets,
          "engine_config":{"require_china_bear_coverage":False,"bootstrap":{"paths":100,"max_paths":100,"horizon":20,"block_lengths":[10],"budget":.9}}}
    file=tmp_path/"bundle.json";file.write_text(json.dumps(spec))
    prepared=tmp_path/"prepared";output=tmp_path/"report"
    assert main(["prepare","--input",str(file),"--out",str(prepared)])==0
    assert verify(prepared)["status"]=="stored_content_verified"
    assert main(["run","--returns",str(prepared/"returns.csv"),"--config",str(prepared/"config.json"),"--out",str(output)])==0
    assert main(["verify",str(output)])==0
    assert (output/"source-input.csv").read_bytes()==(prepared/"returns.csv").read_bytes()


def test_collect_prepare_requires_raw_binding_and_events(tmp_path,monkeypatch):
    import portfolio_engine.collect as collection
    request={"requests":[{"provider":"eastmoney_fund_nav","code":"000001","start":"2020-01-01","end":"2020-01-06"}]}
    rows=[{"x":int(pd.Timestamp(day,tz="Asia/Shanghai").timestamp()*1000),"y":1+i*.01} for i,day in enumerate(["2020-01-01","2020-01-02","2020-01-03","2020-01-06"])]
    raw=('var fS_code="000001";var fS_name="demo";var Data_netWorthTrend='+json.dumps(rows)+';').encode()
    monkeypatch.setattr(collection,"fetch",lambda url:raw)
    file=tmp_path/"request.json";file.write_text(json.dumps(request))
    collected=tmp_path/"collected"
    assert main(["collect","--input",str(file),"--online","--out",str(collected)])==0
    events=tmp_path/"events.json";events.write_text(json.dumps({"000001":{"event_coverage":"declared_complete_for_window","events":[]}}))
    out=tmp_path/"prepared"
    assert main(["prepare","--archive","--input",str(collected/"source-archive.json"),"--events",str(events),"--currency","CNY","--out",str(out)])==0
    assert (out/"upstream-response-0.txt").read_bytes()==raw
    (collected/"response-0.txt").write_bytes(b"changed")
    assert main(["prepare","--archive","--input",str(collected/"source-archive.json"),"--events",str(events),"--currency","CNY","--out",str(tmp_path/"bad")])==2


def test_collector_price_is_explicitly_raw_and_never_prepared():
    request={"requests":[{"provider":"tencent_cn_price","code":"510300","market":"sh","start":"2020-01-01","end":"2020-01-06"}]}
    raw=json.dumps({"code":0,"data":{"sh510300":{"qt":{"sh510300":["1","demo","510300"]},"day":[["2020-01-02","1","1.1","1.2",".9","100"],["2020-01-03","1.1","1.2","1.3","1","100"]]}}}).encode()
    result,_=collect_requests(request,True,lambda url:raw)
    assert result["results"][0]["basis"]=="raw_price"
    from portfolio_engine.data_bridge import collected_adapter
    with pytest.raises(InputError,match="raw-price"):collected_adapter(result,"CNY")


def test_monthly_pipeline_preserves_frequency_in_all_risk_modules():
    from portfolio_engine.engine import run_engine
    dates=pd.date_range("2014-01-31",periods=120,freq="ME")
    rng=np.random.default_rng(1);frame=pd.DataFrame(rng.normal(.005,.02,(120,2)),index=dates,columns=["a","b"])
    config={"data":{"return_type":"synthetic_total_return","source":"synthetic","currency":"CNY","frequency":"monthly"},
            "bootstrap":{"paths":100,"max_paths":100,"horizon":12,"rebalance_every":3,"block_lengths":[3],"budget":.9},
            "orders_csv":None}
    report,_=run_engine(frame,config)
    assert report["data_quality"]["periods_per_year"]==12
    assert report["modules"]["M7"]["periods_per_year"]==12
    assert report["modules"]["M2"]["historical_coverage"]=={"2015":True,"2018":True}
    assert report["modules"]["M5"]["2018"]["periods_per_year"]==12
