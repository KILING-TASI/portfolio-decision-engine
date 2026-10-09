"""Versioned migration of observed account review; standard library only.

The number/calculate functions and bounded bisection XIRR are adapted from
research-workbench, Copyright (c) 2026 research-workbench contributors (MIT).
Original notice: licenses/research-workbench-MIT.txt; source binding and scope
are recorded in THIRD_PARTY_NOTICES.md. Native backtest XIRR is separate.
"""
import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

METHOD = "observed-review-workbench-bisection-v1"
SCHEMA = "workbench-observed-review-input-v1"
DECLARATIONS = {
    "valuation_timing": "before-and-after-external-flow",
    "fee_basis": "included-in-observed-values",
    "frozen_basis": "included-in-total-value-not-available-cash",
    "settlement_basis": "observed-values-not-guaranteed-receipts",
}


def strict_load(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def finite(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON number")
        return result
    def constant(value):
        raise ValueError("nonfinite JSON constant: " + value)
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_float=finite, parse_constant=constant)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def review(spec):
    """Envelope validates versions; payload uses unchanged legacy semantics."""
    if not isinstance(spec, dict) or spec.get("schema") != SCHEMA:
        raise ValueError("unsupported observed review schema")
    if set(spec) - {"schema", "requested_method_version", "payload", *DECLARATIONS}:
        raise ValueError("unknown review envelope field")
    if spec.get("requested_method_version") != METHOD:
        raise ValueError("unsupported observed review method; no silent upgrade")
    for key, value in DECLARATIONS.items():
        if spec.get(key) != value:
            raise ValueError("unsupported or unknown declaration: " + key)
    result = calculate(spec.get("payload"))
    return {"schema": "workbench-observed-review-result-v1", "method_version": METHOD,
            "xirr_method": "workbench-bisection-xirr-v1", "result": result,
            "payload_sha256": digest(json.dumps(spec["payload"], ensure_ascii=False,
                                               sort_keys=True, allow_nan=False,
                                               separators=(",", ":")).encode()),
            "scope": "observed valuations and declared complete external flows; no receipt/source verification or simulation"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="versioned JSON file; '-' reads stdin")
    parser.add_argument("--out", required=True, help="new directory; existing outputs never overwritten")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read() if args.input == "-" else Path(args.input).read_bytes()
        result = review(strict_load(raw))
        result["input_sha256"] = digest(raw)
        result["method_source_sha256"] = digest(Path(__file__).read_bytes())
        result_raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode("utf8")
        destination = Path(args.out)
        if destination.exists():
            raise FileExistsError("output exists; select a new directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".observed-review-", dir=destination.parent) as temp:
            stage = Path(temp) / "result"
            stage.mkdir()
            (stage / "source-input.json").write_bytes(raw)
            (stage / "observed-review-result.json").write_bytes(result_raw)
            manifest = {"schema": "observed-review-files-v1", "method_version": METHOD,
                        "files": {"source-input.json": digest(raw),
                                  "observed-review-result.json": digest(result_raw)},
                        "method_source_sha256": result["method_source_sha256"],
                        "scope": "stored bytes and method binding only; not evidence or account verification"}
            (stage / "report-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
            if destination.exists():
                raise FileExistsError("output appeared during calculation; nothing overwritten")
            os.rename(stage, destination)
        # Isolated Python ignores PYTHONIOENCODING; JSON transport is UTF-8
        # even on a Windows host whose console encoding is different.
        sys.stdout.buffer.write(result_raw + b"\n")
        return 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as error:
        sys.stderr.buffer.write(("Observed review unavailable: " + str(error) + "\n").encode("utf8"))
        return 2

def xirr(flows):
    origin=date.fromisoformat(flows[0][0]);ts=[((date.fromisoformat(d)-origin).days/365.25,v) for d,v in flows]
    if ts[-1][0]<=0:return None
    def npv(r):
        exps=[-t*math.log1p(r) for t,v in ts];scale=max(exps)
        return sum(v*math.exp(e-scale) for (t,v),e in zip(ts,exps))
    lo=-.999999999;hi=1.
    while npv(hi)>0 and hi<1e8:hi=hi*2+1
    if npv(lo)<0 or npv(hi)>0:return None
    for _ in range(150):
        mid=(lo+hi)/2
        if npv(mid)>0:lo=mid
        else:hi=mid
    return (lo+hi)/2*100

def number(value):
    if isinstance(value,bool):raise ValueError('金额不能是布尔值')
    try:result=float(value)
    except (ValueError,TypeError) as error:raise ValueError('金额须为有限数字') from error
    if not math.isfinite(result):raise ValueError('金额须为有限数字')
    return result

def calculate(spec):
    from datetime import date
    if not isinstance(spec,dict) or spec.get('cashFlowCoverage')!='declared-complete':raise ValueError('需要声明本区间外部现金流完整；未知不能按零处理')
    if not isinstance(spec.get('basis'),str) or not spec['basis'].strip():raise ValueError('请提供账户估值与现金流的依据')
    if not isinstance(spec.get('currency'),str) or len(spec['currency'])!=3 or not spec['currency'].isalpha() or not spec['currency'].isupper():raise ValueError('需要三位大写币种声明，不能假定人民币')
    if spec.get('amountUnit') not in ('base','thousand','million'):raise ValueError('金额单位须明确为base、thousand或million；不自动缩放')
    label=spec.get('accountLabel')
    if label is not None and (not isinstance(label,str) or not label.strip() or len(label)>100 or '\n' in label or '\r' in label):raise ValueError('账户研究名称须为1至100字单行文字，不必提供真实账号')
    unit_scale={'base':1,'thousand':1000,'million':1000000}[spec['amountUnit']]
    rows=spec.get('observations')
    if not isinstance(rows,list) or not 2<=len(rows)<=20000:raise ValueError('需要2至20000条流入前后估值记录')
    ledger=[];previous=None;product=1.;flows=defaultdict(float);external=0.
    for row in rows:
        if not isinstance(row,dict):raise ValueError('估值记录须为对象')
        day=row['date'];date.fromisoformat(day)
        if date.fromisoformat(day).isoformat()!=day or (previous and day<=previous['date']):raise ValueError('日期须唯一、严格递增且为YYYY-MM-DD')
        before=number(row['beforeFlowValue']);flow=number(row['externalFlow']);after=number(row['afterFlowValue'])
        tolerance=max(.01/unit_scale,math.ulp(max(abs(before),abs(after),abs(flow)))*8)
        if before<0 or after<0 or abs(after-before-flow)>tolerance:raise ValueError('外部现金流前后估值不勾稽；交易成本不得伪装成外部出入金')
        period=None
        if previous:
            if previous['afterFlowValue']<=0:raise ValueError('前次出入金后资产为零，不能拼接时间加权收益')
            period=before/previous['afterFlowValue']-1;product*=1+period
        else:flows[day]-=before
        flows[day]-=flow;external+=flow
        previous={'date':day,'beforeFlowValue':before,'externalFlow':flow,'afterFlowValue':after,'periodReturnPct':None if period is None else period*100}
        ledger.append(previous)
    flows[ledger[-1]['date']]+=ledger[-1]['afterFlowValue']
    ordered=[(day,value) for day,value in sorted(flows.items()) if value]
    signs=[1 if value>0 else -1 for _,value in ordered];changes=sum(a!=b for a,b in zip(signs,signs[1:]))
    rate=xirr(ordered) if changes==1 and signs[0]<0 and signs[-1]>0 else None
    twr=(product-1)*100
    if not math.isfinite(twr):raise ValueError('时间加权收益超出支持数值范围')
    return {'type':'portfolio-observed-cashflow-review','start':ledger[0]['date'],'end':ledger[-1]['date'],'twrPct':twr,'xirrPct':rate,'xirrStatus':'calculated-conventional-flows' if rate is not None else 'unresolved-or-nonconventional-flows','netExternalFlow':external,'openingValue':ledger[0]['beforeFlowValue'],'endingValue':ledger[-1]['afterFlowValue'],'profit':ledger[-1]['afterFlowValue']-ledger[0]['beforeFlowValue']-external,'ledger':ledger,'basis':spec['basis']}


if __name__ == "__main__":
    raise SystemExit(main())
