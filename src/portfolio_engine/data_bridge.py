"""Explicit research-workbench compatible boundaries; no raw-price relabeling."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

from .validation import InputError,returns_frame


def source_url(value):
    parsed=urlsplit(value) if isinstance(value,str) else None
    if parsed is None or parsed.scheme not in {"https","http"} or not parsed.hostname or parsed.username or parsed.password:
        raise InputError("a public source URL without credentials is required")
    return value


def dated_rows(rows,field):
    if not isinstance(rows,list) or len(rows)<2:
        raise InputError("at least two dated observations required")
    dates=[];values=[]
    for row in rows:
        if not isinstance(row,dict): raise InputError("observations must be objects")
        date=pd.Timestamp(row["date"])
        if date.tzinfo is not None or date != date.normalize():
            raise InputError("observations require date-only, timezone-free dates")
        value=row[field]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or value<=0:
            raise InputError("observation values must be positive finite numbers")
        dates.append(date);values.append(value)
    index=pd.DatetimeIndex(dates)
    if index.has_duplicates or not index.is_monotonic_increasing:
        raise InputError("observation dates must be unique and increasing")
    return pd.Series(values,index=index,dtype=float)


def total_return_index(asset):
    """Declared complete events, same-date reinvestment; not available cash."""
    basis=asset.get("basis")
    if basis=="total_return_index":
        return dated_rows(asset["history"],"value"),{"basis":"user_declared_total_return_index"}
    if basis!="nav_with_events":
        raise InputError("raw prices cannot be labeled total return; provide total_return_index or nav_with_events")
    nav=dated_rows(asset["history"],"nav")
    if asset.get("event_coverage")!="declared_complete_for_window" or not isinstance(asset.get("events"),list):
        raise InputError("NAV conversion requires an explicit complete-event declaration and events list")
    events={}
    for event in asset["events"]:
        day=pd.Timestamp(event["date"])
        if day not in nav.index or day==nav.index[0] or day in events:
            raise InputError("events must be unique, observed and after the initial date")
        source_url(event.get("source_url"))
        if not ({"cash_per_old_unit","new_units_per_old_unit"}&set(event)):
            raise InputError("event quantity is required")
        cash=event.get("cash_per_old_unit",0);split=event.get("new_units_per_old_unit",1)
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) for v in [cash,split]) or cash<0 or split<=0:
            raise InputError("invalid dividend or split")
        events[day]=(cash,split)
    units=1.;values=[]
    for day,value in nav.items():
        cash,split=events.get(day,(0,1))
        units*=split+cash/value
        total=units*value/nav.iloc[0]
        if not np.isfinite(total) or total<=0: raise InputError("total return calculation overflow")
        values.append(total)
    return pd.Series(values,index=nav.index),{"basis":"same_date_nav_reinvestment",
        "event_verification":"input_declared_not_independently_verified",
        "limitations":["same-date reinvestment is a research assumption, not cash settlement or verified product entitlement"]}


def validate_context(frame,metadata,periods=None):
    frame=returns_frame(frame)
    dates=frame.index
    gaps=np.diff(dates.values).astype("timedelta64[D]").astype(int)
    months=np.array([d.year*12+d.month for d in dates])
    monthly=len(months)>1 and np.all(np.diff(months)==1)
    daily=len(gaps)>1 and np.median(gaps)<=4 and np.max(gaps)<=14
    frequency=metadata.get("frequency") or ("monthly" if monthly else "daily" if daily else None)
    if frequency not in {"daily","monthly"}:
        raise InputError("irregular dates: declare a supported frequency and provide a matching calendar")
    calendar=metadata.get("calendar")
    if frequency=="monthly" and not monthly: raise InputError("monthly observations must be consecutive unique months")
    if frequency=="daily" and not daily and calendar is None: raise InputError("daily spacing is inconsistent; provide an applicable calendar")
    expected_periods=252 if frequency=="daily" else 12
    if periods is not None and periods!=expected_periods:
        raise InputError("frequency and periods_per_year conflict (daily=252, monthly=12)")
    if metadata.get("as_of") is not None and dates[-1]>pd.Timestamp(metadata["as_of"]):
        raise InputError("observations exceed data.as_of")
    quality={"frequency":frequency,"periods_per_year":expected_periods,"frequency_basis":"declared" if metadata.get("frequency") else "spacing_inferred",
             "calendar_status":"not_provided","calendar_verified":False,"coverage":None,
             "limitations":["spacing is not exchange-calendar or point-in-time verification"]}
    if calendar is not None:
        source_url(calendar.get("source_url"))
        if calendar.get("applicability_confirmed") is not True:
            raise InputError("calendar applicability must be explicitly confirmed")
        expected=pd.DatetimeIndex(pd.to_datetime(calendar["dates"]))
        if expected.has_duplicates or not expected.is_monotonic_increasing or len(expected)==0:
            raise InputError("calendar dates must be ordered and unique")
        if pd.Timestamp(calendar["start"])>dates[0] or pd.Timestamp(calendar["end"])<dates[-1]:
            raise InputError("calendar scope does not cover observations")
        if (expected<pd.Timestamp(calendar["start"])).any() or (expected>pd.Timestamp(calendar["end"])).any():
            raise InputError("calendar contains out-of-scope dates")
        expected=expected[(expected>=dates[0])&(expected<=dates[-1])]
        missing=expected.difference(dates);extra=dates.difference(expected)
        quality.update(calendar_status="dates_aligned" if len(missing)==len(extra)==0 else "date_gaps",
                       missing_dates=[str(d.date()) for d in missing],unexpected_dates=[str(d.date()) for d in extra],
                       coverage=len(dates.intersection(expected))/len(expected) if len(expected) else None,
                       calendar_verification="input_declared_not_independently_verified")
        if len(missing) or len(extra): raise InputError("calendar mismatch: missing or unexpected observations; no filling")
    records=metadata.get("assets")
    if records is not None:
        if not isinstance(records,list) or [r.get("code") for r in records]!=frame.columns.tolist():
            raise InputError("asset metadata must match asset columns exactly")
        for record in records:
            if record.get("currency")!=metadata["currency"]: raise InputError("asset currencies are not aligned")
            source_url(record.get("source_url"))
    return quality


def prepare_bundle(spec):
    if not isinstance(spec,dict) or not isinstance(spec.get("assets"),list) or not spec["assets"]:
        raise InputError("bundle requires assets")
    currency=spec.get("currency")
    if not isinstance(currency,str) or not currency: raise InputError("bundle currency required")
    series=[];records=[];codes=[]
    for asset in spec["assets"]:
        if not isinstance(asset,dict): raise InputError("asset records must be objects")
        code=asset.get("code")
        if not isinstance(code,str) or not code or code in codes: raise InputError("unique asset codes required")
        if asset.get("currency")!=currency: raise InputError("all asset currencies must match the bundle")
        source_url(asset.get("source_url"))
        value,basis=total_return_index(asset)
        if series and not value.index.equals(series[0].index): raise InputError("asset dates must match exactly; no intersection or fill")
        series.append(value);codes.append(code)
        records.append({"code":code,"currency":currency,"source_url":asset["source_url"],**basis,
                        "upstream":{k:asset[k] for k in ["provider","retrieved_at","response_sha256","point_in_time"] if k in asset},
                        "input_sha256":hashlib.sha256(json.dumps(asset,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()})
    prices=pd.concat(series,axis=1);prices.columns=codes
    frame=returns_frame(prices.pct_change(fill_method=None).iloc[1:])
    metadata={"return_type":"synthetic_total_return" if spec.get("synthetic") is True else "total_return",
              "source":"research bundle adapter; per-asset source records retained","currency":currency,
              "assets":records,"as_of":spec.get("as_of",str(frame.index[-1].date()))}
    if "frequency" in spec: metadata["frequency"]=spec["frequency"]
    if "calendar" in spec: metadata["calendar"]=spec["calendar"]
    quality=validate_context(frame,metadata)
    metadata["frequency"]=quality["frequency"]
    return frame,metadata,quality


def workbench_adapter(bundle,currency,event_declarations=None):
    """Convert actual workbench research-bundle NAV rows, preserving incomplete events."""
    if bundle.get("type")!="research-bundle" or not isinstance(bundle.get("rows"),list):
        raise InputError("expected workbench research-bundle")
    declarations=event_declarations or {};assets=[]
    for row in bundle["rows"]:
        if row.get("kind")!="fund" or row.get("historyBasis")!="nav-with-distributions":
            raise InputError("workbench quotes/raw prices cannot be converted to total return")
        declaration=declarations.get(row["code"],{})
        assets.append({"code":row["code"],"currency":currency,"source_url":row["source"],
                       "basis":"nav_with_events","history":row["history"],
                       "events":declaration.get("events"),"event_coverage":declaration.get("event_coverage")})
    return {"currency":currency,"as_of":bundle["asOf"],"assets":assets}


def collected_adapter(bundle,currency,event_declarations=None):
    if bundle.get("type")!="portfolio-source-archive" or not isinstance(bundle.get("results"),list):
        raise InputError("expected collected source archive")
    assets=[];declarations=event_declarations or {}
    for row in bundle["results"]:
        if row.get("status")!="observed" or row.get("basis")!="nav_with_unverified_events":
            raise InputError("all requested assets must have NAV; raw-price/failed assets cannot be converted")
        declaration=declarations.get(row["code"],{})
        assets.append({"code":row["code"],"currency":currency,"source_url":row["source_url"],"basis":"nav_with_events",
                       "history":row["history"],"events":declaration.get("events"),"event_coverage":declaration.get("event_coverage"),
                       **{k:row[k] for k in ["provider","retrieved_at","response_sha256","point_in_time"] if k in row}})
    return {"currency":currency,"assets":assets}


def closing_premium(spec):
    if not isinstance(spec,dict) or not isinstance(spec.get("code"),str) or not spec["code"]:
        raise InputError("premium input needs an asset code")
    prices=dated_rows(spec["prices"],"close");nav=dated_rows(spec["nav"],"nav")
    source_url(spec.get("price_source_url"));source_url(spec.get("nav_source_url"))
    common=prices.index.intersection(nav.index)
    rows=[{"date":str(d.date()),"close":float(prices[d]),"nav":float(nav[d]),"premium":float(prices[d]/nav[d]-1)} for d in common]
    if any(not np.isfinite(row["premium"]) for row in rows): raise InputError("premium overflow")
    return {"status":"available" if rows else "insufficient_data","code":spec["code"],"rows":rows,
            "missing_nav_dates":[str(d.date()) for d in prices.index.difference(nav.index)],
            "price_source_url":spec["price_source_url"],"nav_source_url":spec["nav_source_url"],
            "limitations":["same-date closing deviation, not intraday IOPV or an executable spread",
                            "NAV belonging date does not establish historical publication availability"]}


def lookthrough(spec):
    if not isinstance(spec,dict):raise InputError("lookthrough input must be an object")
    nodes=spec["nodes"];root=spec["root"];cutoff=pd.Timestamp(spec["as_of"])
    depth=spec.get("max_depth",10)
    if not isinstance(nodes,dict) or root not in nodes or type(depth) is not int or not 1<=depth<=20:
        raise InputError("invalid lookthrough nodes or depth")
    leaves={};kinds={};unknown=[];traces=[];visits=0
    wrapper=spec.get("root_is_account_wrapper",False)
    if not isinstance(wrapper,bool):raise InputError("root wrapper marker must be boolean")
    def walk(key,weight,path,root_position=None):
        nonlocal visits
        visits+=1
        if visits>100000:raise InputError("too many disclosure paths")
        if weight==0:return
        effective_depth=len(path)-(1 if wrapper and path else 0)
        reason="cycle" if key in path else "depth_limit" if effective_depth>=depth else "missing_child" if key not in nodes else None
        if reason:
            unknown.append({"path":path+[key],"weight":weight,"reason":reason,"root_position":root_position});return
        node=nodes[key]
        if not isinstance(node,dict) or not isinstance(node.get("holdings",[]),list):raise InputError("invalid lookthrough node")
        if node.get("source_url") is not None:source_url(node["source_url"])
        elif not isinstance(node.get("source_reference"),str) or not node["source_reference"].strip():
            raise InputError("disclosure requires a source URL or explicit source reference")
        if node.get("currency")!=spec["currency"]: raise InputError("lookthrough currency mismatch")
        report=pd.Timestamp(node["report_date"]);published=pd.Timestamp(node["published_at"])
        if pd.isna(report) or pd.isna(published) or not report<=published<=cutoff:
            raise InputError("lookthrough report/publication exceeds cutoff")
        total=0;seen=set()
        for holding in node.get("holdings",[]):
            if not isinstance(holding,dict):raise InputError("holding must be an object")
            w=holding["weight"];kind=holding["kind"];ident=holding.get("node") if kind=="fund" else holding.get("id")
            if isinstance(w,bool) or not isinstance(w,(int,float)) or not np.isfinite(w) or not 0<=w<=1:
                raise InputError("invalid disclosed holding weight")
            seen_key=holding.get("position_id",ident) if key==root and wrapper else ident
            if not isinstance(ident,str) or not ident or seen_key in seen: raise InputError("duplicate or missing holding identity")
            seen.add(seen_key);total+=w
            if kind=="fund": walk(ident,weight*w,path+[key],root_position or holding.get("position_id"))
            elif kind=="unknown":
                unknown.append({"path":path+[key,ident],"weight":weight*w,"reason":holding.get("reason","unclassified"),"root_position":root_position})
            elif kind in {"stock","bond","cash","other"}:
                if ident in kinds and kinds[ident]!=kind: raise InputError("conflicting leaf kind")
                kinds[ident]=kind;leaves[ident]=leaves.get(ident,0)+weight*w
                traces.append({"path":path+[key,ident],"security":ident,"kind":kind,"weight":weight*w,
                    "report_date":str(report.date()),"published_at":str(published.date()),"currency":node["currency"],
                    "source_reference":node.get("source_reference",node.get("source_url")),
                    "issuer":holding.get("issuer"),"mapping_source":holding.get("mapping_source"),"root_position":root_position})
            else: raise InputError("unknown holding kind")
        if total>1+1e-10: raise InputError("disclosed weights exceed 1")
        if total<1: unknown.append({"path":path+[key],"weight":weight*(1-total),"reason":"undisclosed","root_position":root_position})
    walk(root,1,[])
    if abs(sum(leaves.values())+sum(r["weight"] for r in unknown)-1)>1e-9: raise InputError("lookthrough conservation failed")
    issuer_exposure={};unmapped=0.
    for trace in traces:
        if trace["kind"]!="stock":continue
        if trace["issuer"]:
            if not isinstance(trace["mapping_source"],str) or not trace["mapping_source"].strip():raise InputError("issuer mapping requires evidence")
            issuer_exposure[trace["issuer"]]=issuer_exposure.get(trace["issuer"],0)+trace["weight"]
        else:unmapped+=trace["weight"]
    return {"status":"degraded" if unknown else "ok","leaves":leaves,"leaf_kinds":kinds,"unknown":unknown,"paths":traces,
            "issuer_exposure":issuer_exposure,"unmapped_stock_issuer_weight":unmapped,
            "disclosure_evidence":spec.get("disclosure_evidence",{}),"security_metadata":spec.get("security_metadata",{}),
            "root_positions":spec.get("root_positions",[]),"adapter":spec.get("adapter"),
            "analysis_scope":"disclosed security structure only; no full-portfolio risk or event impact inference",
            "known_weight":sum(leaves.values()),"unknown_weight":sum(r["weight"] for r in unknown),
            "limitations":["disclosed snapshots, not current positions or actual trades; mixed report dates retained per path"]}
