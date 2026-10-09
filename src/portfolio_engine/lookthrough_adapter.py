"""Explicit cn-fund-lookthrough input v0.1 conversion; no guessed identities."""
import copy
import datetime as dt
import hashlib
import json
import math

from .validation import InputError


def day(value):
    if not isinstance(value,str) or dt.date.fromisoformat(value).isoformat()!=value:
        raise InputError("lookthrough dates must be YYYY-MM-DD")
    return dt.date.fromisoformat(value)


def weight(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
        raise InputError("disclosed weights must be finite fractions in [0,1]")
    return float(value)


def cn_lookthrough_input(spec):
    if not isinstance(spec,dict):raise InputError("cn-fund-lookthrough input must be an object")
    cutoff=day(spec["asOf"]);currency=spec.get("currency")
    if not isinstance(currency,str) or len(currency)!=3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        raise InputError("declare common three-letter currency; no FX conversion")
    positions=spec.get("positions");nodes=spec.get("nodes");master=spec.get("securities",{})
    if not isinstance(positions,list) or not 1<=len(positions)<=100 or not isinstance(nodes,dict) or len(nodes)>1000 or not isinstance(master,dict):
        raise InputError("invalid positions, nodes or security mapping")
    ids=[]
    for position in positions:
        if not isinstance(position,dict) or not isinstance(position.get("id"),str) or not position["id"].strip() or not isinstance(position.get("node"),str) or not position["node"]:
            raise InputError("root positions require id and node")
        ids.append(position["id"]);weight(position["weight"])
    if len(set(ids))!=len(ids) or abs(math.fsum(p["weight"] for p in positions)-1)>1e-9:
        raise InputError("root ids must be unique and weights sum to 1; cash explicit")
    converted={};warnings=[];evidence={}
    for security,meta in master.items():
        if not isinstance(security,str) or not security or not isinstance(meta,dict) or meta.get("kind") not in {"stock","bond","cash","other"}:
            raise InputError("invalid security mapping")
        if not isinstance(meta.get("source"),str) or not meta["source"].strip():
            raise InputError("security/issuer mapping needs explicit source evidence")
        if meta.get("issuer") is not None and (not isinstance(meta["issuer"],str) or not meta["issuer"].strip()):
            raise InputError("issuer must be a nonempty string or absent")
    for key,node in nodes.items():
        if not isinstance(key,str) or not key or not isinstance(node,dict):raise InputError("invalid disclosure node")
        report=day(node["reportDate"]);published=day(node["publishedAt"])
        if not report<=published<=cutoff:raise InputError("future or inconsistent disclosure dates")
        if node.get("currency")!=currency:raise InputError("node currency mismatch")
        if not isinstance(node.get("source"),str) or not node["source"].strip():raise InputError("disclosure source required")
        holdings=node.get("holdings")
        if not isinstance(holdings,list) or len(holdings)>5000:raise InputError("invalid holdings list")
        if any(not isinstance(row,dict) for row in holdings):raise InputError("holding rows must be objects")
        if math.fsum(weight(row["weight"]) for row in holdings)>1+1e-9:raise InputError("leveraged/gross weights are unsupported; not truncated")
        rows=[]
        # Duplicate disclosed rows are aggregated only by exact security/node id,
        # never by name or issuer. Their raw records remain in the frozen input.
        grouped={}
        for holding in holdings:
            kind=holding.get("kind")
            if kind not in {"fund","stock","bond","cash","other"}:raise InputError("invalid holding kind")
            ident=holding.get("node") if kind=="fund" else holding.get("security")
            if not isinstance(ident,str) or not ident:raise InputError("holding identity required")
            if kind!="fund" and ident in master and master[ident]["kind"]!=kind:raise InputError("holding and security kind conflict")
            item_key=(kind,ident)
            grouped[item_key]=grouped.get(item_key,0)+holding["weight"]
        for (kind,ident),amount in grouped.items():
            row={"kind":kind,"weight":amount}
            if kind=="fund":row["node"]=ident
            elif ident not in master:
                row.update(kind="unknown",id=ident,reason="security_identity_or_classification_missing")
            else:
                meta=master[ident]
                row.update(id=ident,issuer=meta.get("issuer"),mapping_source=meta["source"])
            rows.append(row)
        raw_meta=copy.deepcopy({k:v for k,v in node.items() if k!="holdings"})
        evidence[key]={"report_date":node["reportDate"],"published_at":node["publishedAt"],"currency":currency,
                       "source_reference":node["source"],"disclosure_scope":node.get("disclosureScope","not_declared"),
                       "weight_basis":node.get("weightBasis","upstream_parent_fraction_contract_not_independently_verified"),
                       "raw_metadata":raw_meta}
        converted[key]={"currency":currency,"report_date":node["reportDate"],"published_at":node["publishedAt"],
                        "source_reference":node["source"],"holdings":rows}
        if node.get("disclosureScope") in {"top10","top_ten"}:warnings.append(f"{key}: top-ten disclosure; weights were not normalized")
    root="__cn_account_root__"
    reserved=set(converted)|{p["node"] for p in positions}
    for node in converted.values():
        reserved.update(row["node"] for row in node["holdings"] if row["kind"]=="fund")
    while root in reserved:root+="_"
    converted[root]={"currency":currency,"report_date":spec["asOf"],"published_at":spec["asOf"],
        "source_reference":"synthetic account wrapper for declared root weights; not a fund disclosure",
        "holdings":[{"kind":"fund","node":p["node"],"weight":p["weight"],"position_id":p["id"]} for p in positions]}
    # Different root positions may target the same fund. Keep them separately;
    # downstream uniqueness uses position_id, not a fabricated child identity.
    value={"as_of":spec["asOf"],"currency":currency,"root":root,"root_is_account_wrapper":True,"max_depth":20,
           "nodes":converted,"disclosure_evidence":evidence,"security_metadata":copy.deepcopy(master),
           "root_positions":copy.deepcopy(positions),"adapter":{
               "name":"cn-fund-lookthrough-input-v0.1","reference_commit":"72bf3651269ef156f3f002641b224a968adbb3e0",
               "input_sha256":hashlib.sha256(json.dumps(spec,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest(),
               "source_verification":"input_declared_not_independently_verified","warnings":warnings}}
    return value
