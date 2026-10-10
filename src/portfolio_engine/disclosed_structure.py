"""Disclosed structure calculation without time-series dependencies."""
import math
from urllib.parse import urlsplit
from .validation import InputError
from .disclosure_time import observation_day,disclosure_timing

def source_url(value):
    parsed=urlsplit(value) if isinstance(value,str) else None
    if parsed is None or parsed.scheme not in {'https','http'} or not parsed.hostname or parsed.username or parsed.password:
        raise InputError('a public source URL without credentials is required')
    return value

def lookthrough(spec,research_as_of=None,historical=False):
    if not isinstance(spec,dict):raise InputError("lookthrough input must be an object")
    nodes=spec["nodes"];root=spec["root"]
    cutoffs=[observation_day(spec["as_of"])]
    if research_as_of is not None:cutoffs.append(observation_day(research_as_of))
    if spec.get("evaluation_as_of") is not None:cutoffs.append(observation_day(spec["evaluation_as_of"]))
    cutoff=min(cutoffs).isoformat()
    stored_historical=spec.get("historical_mode",False)
    if not isinstance(stored_historical,bool) or not isinstance(historical,bool):raise InputError("historical mode must be boolean")
    historical=historical or stored_historical
    depth=spec.get("max_depth",10)
    if not isinstance(nodes,dict) or root not in nodes or type(depth) is not int or not 1<=depth<=20:
        raise InputError("invalid lookthrough nodes or depth")
    leaves={};kinds={};unknown=[];traces=[];visits=0;timing={}
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
        proof=disclosure_timing(node,cutoff,historical and not (key==root and wrapper))
        proof["record_role"]="account_wrapper" if key==root and wrapper else "disclosure"
        timing[key]=proof
        report=observation_day(node["report_date"]);published=observation_day(node["published_at"])
        total=0;seen=set()
        for holding in node.get("holdings",[]):
            if not isinstance(holding,dict):raise InputError("holding must be an object")
            w=holding["weight"];kind=holding["kind"];ident=holding.get("node") if kind=="fund" else holding.get("id")
            if isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or not 0<=w<=1:
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
                    "report_date":report.isoformat(),"published_at":published.isoformat(),"currency":node["currency"],
                    "retrieved_at":node.get("retrieved_at"),"available_at":node.get("available_at"),"version_id":node.get("version_id"),
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
            "evaluated_as_of":cutoff,"historical_mode":historical,"disclosure_timing":timing,
            "analysis_scope":"disclosed security structure only; no full-portfolio risk or event impact inference",
            "known_weight":sum(leaves.values()),"unknown_weight":sum(r["weight"] for r in unknown),
            "limitations":["disclosed snapshots, not current positions or actual trades; mixed report dates retained per path",
                           "cross-period holding differences do not reconstruct buys/sells",
                           "frozen availability is an input declaration; original version bytes not independently authenticated"]}
