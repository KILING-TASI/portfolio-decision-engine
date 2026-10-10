"""Declared account amounts joined to disclosure fractions, never a live risk feed."""
import hashlib
import json
import math
import re

from .data_bridge import lookthrough
from .disclosure_time import observation_day
from .validation import InputError

METHOD = "declared-account-exposure-v1"


def amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise InputError("amounts must be finite nonnegative base-currency amounts")
    return float(value)


def evidence(value, name):
    if not isinstance(value, str) or not value.strip():
        raise InputError(name + " requires explicit evidence")
    return value


def account_exposure(spec):
    if not isinstance(spec, dict) or spec.get("schema") != "account-exposure-input-v1":
        raise InputError("explicit account-exposure-input-v1 schema required")
    if spec.get("requested_method_version", METHOD) != METHOD:
        raise InputError("unsupported requested method version")
    currency = spec.get("currency")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        raise InputError("one common three-letter currency required; no inferred FX")
    if spec.get("amount_unit") != "base":
        raise InputError("explicit base amount unit required")
    cutoff = observation_day(spec["as_of"])
    date = observation_day(spec["valuation_date"])
    evidence(spec.get("data_kind", "input_declared_not_verified"), "data kind")
    if date > cutoff:
        raise InputError("valuation date exceeds as-of")
    positions = spec.get("positions")
    master = spec.get("securities", {})
    if not isinstance(positions, list) or not 1 <= len(positions) <= 100 or not isinstance(master, dict) or not isinstance(spec.get("nodes", {}), dict):
        raise InputError("bounded root positions and security map required")
    if any(not isinstance(p, dict) for p in positions): raise InputError("root positions must be objects")
    for key, meta in master.items():
        evidence(key, "security identity")
        if not isinstance(meta, dict) or meta.get("kind") not in {"stock", "bond", "cash", "other"}:
            raise InputError("invalid security classification")
    ids = set(); lots = set(); rows = []; unknown = []; roots = []
    available = frozen = fund_cash = 0.0
    def add(security, kind, value, position, proof, source):
        nonlocal fund_cash
        meta = master.get(security)
        if isinstance(meta, dict) and meta.get("kind") != kind:
            raise InputError("disclosure/direct kind conflicts with security classification")
        if not isinstance(meta, dict) or not meta.get("source"):
            unknown.append({"position_id": position, "security": security, "amount": value, "reason": "missing_security_identity_or_kind_evidence", "timing": proof})
            return
        evidence(meta["source"], "security classification")
        if meta.get("currency", currency) != currency:
            raise InputError("security currency mismatch; no implicit FX")
        for stamp in ["published_at", "available_at", "mapping_as_of"]:
            if meta.get(stamp) is not None and observation_day(meta[stamp]) > cutoff:
                raise InputError("security mapping evidence exceeds cutoff")
        subtype = meta.get("instrument_type", kind)
        if kind == "bond" and subtype not in {"bond", "plain_bond", "convertible_bond"}:
            raise InputError("unsupported bond type")
        mapped = {}
        for field in ["issuer", "industry"]:
            identity = meta.get(field)
            if identity is not None:
                evidence(identity, field); evidence(meta.get(field + "_source"), field + " mapping")
            mapped[field] = identity
            mapped[field + "_source"] = meta.get(field + "_source") if identity is not None else None
        risk = {"status": "not_estimated", "modified_duration": None, "source": None, "option_risk": "not_applicable"}
        if kind == "bond":
            risk["status"] = "missing_terms_unknown"
            if subtype == "convertible_bond":
                risk["option_risk"] = "unknown_without_terms_and_option_model"
            elif meta.get("modified_duration") is not None:
                duration = amount(meta["modified_duration"])
                if duration > 100: raise InputError("duration exceeds supported linear scenario range")
                evidence(meta.get("terms_source"), "duration input")
                if observation_day(meta["terms_as_of"]) > date:
                    raise InputError("bond terms exceed account valuation date")
                risk.update(status="declared_duration_linear_scenario_only", modified_duration=duration, source=meta["terms_source"], terms_as_of=meta["terms_as_of"])
        if kind == "cash" and source == "fund_disclosure": fund_cash += value
        rows.append({"security": security, "kind": kind, "instrument_type": subtype, "amount": value,
                     "position_id": position, "exposure_source": source, "classification_source": meta["source"],
                     "timing": proof, "risk_inputs": risk, **mapped})
    try:
        total = math.fsum(amount(p["amount"]) for p in positions)
    except OverflowError as exc:
        raise InputError("account total overflow") from exc
    if not math.isfinite(total) or total <= 0: raise InputError("finite positive account total required")
    for p in positions:
        ident = evidence(p.get("position_id"), "root position")
        lot = evidence(p.get("economic_lot_id"), "economic lot")
        if ident in ids or lot in lots: raise InputError("duplicate root position/economic lot; do not ingest a fund's underlying assets again as direct lots")
        ids.add(ident); lots.add(lot)
        value = amount(p["amount"])
        if p.get("currency") != currency or observation_day(p["valuation_date"]) != date:
            raise InputError("all root positions must share currency and valuation date")
        evidence(p.get("source"), "root valuation")
        kind = p.get("kind")
        roots.append({**p, "weight": value / total})
        if kind == "fund":
            if p.get("frozen_amount", 0): raise InputError("fund lock is not frozen account cash")
            node = evidence(p.get("node"), "fund disclosure node")
            if node not in spec.get("nodes", {}):
                unknown.append({"position_id": ident, "amount": value, "reason": "missing_fund_disclosure", "node": node})
                continue
            result = lookthrough({"as_of": spec["as_of"], "currency": currency, "root": node,
                                  "nodes": spec.get("nodes", {}), "max_depth": 20}, research_as_of=spec["as_of"])
            for trace in result["paths"]:
                proof = {k: trace.get(k) for k in ["report_date", "published_at", "retrieved_at", "available_at", "source_reference"]}
                proof["account_valuation_date"] = spec["valuation_date"]
                proof["relationship"] = "current declared amount times older disclosed fraction; not a same-date full holding valuation"
                add(trace["security"], trace["kind"], value * trace["weight"], ident, proof, "fund_disclosure")
            unknown.extend({"position_id": ident, "amount": value * u["weight"], "reason": u["reason"], "path": u["path"]} for u in result["unknown"])
        elif kind in {"stock", "bond", "cash", "other"}:
            if p.get("origin") != "direct_account_lot": raise InputError("direct positions require origin=direct_account_lot; fund disclosure rows are not new account assets")
            proof = {"account_valuation_date": spec["valuation_date"], "source_reference": p["source"], "published_at": p.get("published_at"), "available_at": p.get("available_at"), "retrieved_at": p.get("retrieved_at")}
            for key in ["published_at", "available_at"]:
                if p.get(key) is not None and observation_day(p[key]) > cutoff: raise InputError("account evidence exceeds cutoff")
            if p.get("published_at") and p.get("available_at") and observation_day(p["available_at"]) < observation_day(p["published_at"]): raise InputError("availability predates publication")
            if p.get("retrieved_at") is not None:
                acquired = observation_day(p["retrieved_at"])
                if p.get("published_at") and acquired < observation_day(p["published_at"]): raise InputError("acquisition predates publication")
            if kind == "cash":
                locked = amount(p["frozen_amount"])
                if locked > value: raise InputError("frozen cash exceeds total cash")
                frozen += locked; available += value - locked
            elif p.get("frozen_amount", 0): raise InputError("non-cash frozen amount cannot be available cash")
            add(evidence(p.get("security"), "direct security"), kind, value, ident, proof, "direct_account")
        elif kind == "unknown":
            unknown.append({"position_id": ident, "amount": value, "reason": "root_classification_unknown"})
        else: raise InputError("unsupported root kind")
    known = math.fsum(r["amount"] for r in rows); missing = math.fsum(r["amount"] for r in unknown)
    if not math.isclose(known + missing, total, rel_tol=1e-10, abs_tol=1e-7): raise InputError("account amount conservation failed")
    security_totals = {}; issuer = {}; industry = {}; kinds = {}; root_kinds = {}; unmapped = {"issuer": 0., "industry": 0.}
    for p in roots:
        root_kinds[p["kind"]] = root_kinds.get(p["kind"], 0.) + p["amount"]
    for r in rows:
        r["weight"] = r["amount"] / total
        security_totals[r["security"]] = security_totals.get(r["security"], 0.) + r["amount"]
        kinds[r["instrument_type"]] = kinds.get(r["instrument_type"], 0.) + r["amount"]
        if r["kind"] != "cash":
            for field, bucket in [("issuer", issuer), ("industry", industry)]:
                if r[field] is None: unmapped[field] += r["amount"]
                else: bucket[r[field]] = bucket.get(r[field], 0.) + r["amount"]
    scenarios = [{"id": "disclosure_base", "parameters": {}, "estimated_change": None, "description": "披露支持的结构视图；不估计收益或风险"}]
    shocks = spec.get("rate_scenarios", [])
    if not isinstance(shocks, list) or len(shocks) > 10: raise InputError("at most ten declared rate scenarios")
    for shock in shocks:
        if not isinstance(shock, dict) or set(shock) != {"id", "rate_change"}: raise InputError("explicit rate scenario id and rate_change required")
        evidence(shock["id"], "scenario identity")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", shock["id"]): raise InputError("scenario id must be a short portable identifier")
        change = shock["rate_change"]
        if isinstance(change, bool) or not isinstance(change, (int, float)) or not math.isfinite(change) or abs(change) > .02: raise InputError("small linear rate shock requires absolute change <= 0.02")
        if any(s["id"] == shock["id"] for s in scenarios): raise InputError("duplicate scenario identity")
        eligible = [r for r in rows if r["risk_inputs"]["modified_duration"] is not None]
        covered = math.fsum(r["amount"] for r in eligible)
        try:
            estimate = math.fsum((-change * r["risk_inputs"]["modified_duration"]) * r["amount"] for r in eligible) if eligible else None
        except OverflowError as exc:
            raise InputError("rate scenario amount overflow") from exc
        if estimate is not None and not math.isfinite(estimate): raise InputError("rate scenario amount overflow")
        scenarios.append({"id": shock["id"], "parameters": {"rate_change": change}, "estimated_change": estimate,
                          "covered_amount": covered, "unestimated_amount": total - covered, "description": "仅已声明普通债修正久期的一阶平行利率变化；忽略凸性、信用、转债含权及其他资产，未估计部分不等于零损失"})
    selected = spec.get("selected_scenario", "disclosure_base")
    if selected not in {s["id"] for s in scenarios}: raise InputError("selected scenario must be explicitly declared")
    return {"schema": "account-exposure-result-v1", "method_version": METHOD, "selected_scenario": selected, "input_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
            "status": "degraded", "currency": currency, "amount_unit": "base", "as_of": spec["as_of"], "valuation_date": spec["valuation_date"], "data_kind": spec.get("data_kind", "input_declared_not_verified"),
            "total_amount": total, "known_amount": known, "unknown_amount": missing, "known_weight": known / total, "unknown_weight": missing / total,
            "root_positions": roots, "root_kind_amounts": root_kinds, "root_vs_leaf": "two descriptions of the same account; never add root funds to their underlying exposure amounts", "exposure_paths": rows, "unknown": unknown, "security_amounts": security_totals, "issuer_amounts": issuer, "industry_amounts": industry, "kind_amounts": kinds, "unmapped_amounts": unmapped,
            "cash": {"available_account_cash": available, "frozen_account_cash": frozen, "fund_disclosed_cash": fund_cash, "note": "fund cash is exposure, not withdrawable account cash; frozen cash is already part of account cash, never added twice"},
            "scenarios": scenarios, "limitations": ["Declared valuation joined to mixed disclosure dates, not verified live full holdings or portfolio risk", "Overlapping direct and fund exposure is aggregated once per distinct economic lot; shared issuer does not justify deleting legitimate holdings", "Issuer/industry mappings require their own evidence; missing mappings stay unknown", "Cash status and valuations are input declarations, not settlement authentication", "No real-return M2 evaluation or trade instructions"]}
