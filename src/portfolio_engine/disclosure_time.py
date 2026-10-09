"""Date-level knowledge boundaries; acquisition is not publication or availability."""
import datetime as dt
import re

from .validation import InputError


def observation_day(value):
    if not isinstance(value,str) or not value:
        raise InputError("disclosure timing must be an ISO date or offset timestamp")
    try:
        if len(value)==10:
            result=dt.date.fromisoformat(value)
            if result.isoformat()!=value:raise ValueError()
            return result
        stamp=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        if stamp.tzinfo is None:raise ValueError()
        return stamp.astimezone(dt.timezone(dt.timedelta(hours=8))).date()
    except ValueError as exc:
        raise InputError("disclosure timestamps require an explicit offset; cutoff is Asia/Shanghai date-level") from exc


def disclosure_timing(node,as_of,historical=False):
    if not isinstance(historical,bool):raise InputError("historical disclosure mode must be boolean")
    cutoff=observation_day(as_of)
    report=observation_day(node["report_date"]);published=observation_day(node["published_at"])
    if not report<=published<=cutoff:
        raise InputError("disclosure publication/holdings period exceeds research cutoff")
    retrieved=node.get("retrieved_at");available=node.get("available_at");frozen=node.get("frozen_at")
    if retrieved is not None and observation_day(retrieved)<published:
        raise InputError("acquisition predates declared publication")
    if available is not None and not published<=observation_day(available)<=cutoff:
        raise InputError("declared version availability exceeds research cutoff or predates publication")
    if frozen is not None and (available is None or not observation_day(available)<=observation_day(frozen)):
        raise InputError("frozen version must follow declared availability")
    version=node.get("version_id");source_hash=node.get("source_sha256")
    if version is not None and (not isinstance(version,str) or not version.strip()):raise InputError("invalid disclosure version")
    if source_hash is not None and (not isinstance(source_hash,str) or not re.fullmatch(r"[0-9a-f]{64}",source_hash)):
        raise InputError("source_sha256 must identify declared original bytes")
    if historical and (available is None or frozen is None or not version or not source_hash or observation_day(frozen)>cutoff):
        raise InputError("historical input requires an identified source hash/version available and frozen by cutoff")
    return {"holdings_period":node["report_date"],"published_at":node["published_at"],"retrieved_at":retrieved,
            "available_at":available,"frozen_at":frozen,"version_id":version,"source_sha256":source_hash,
            "point_in_time_status":"frozen_version_declared_not_independently_verified" if historical else "publication_cutoff_checked_only",
            "scope":"date-level cutoff; current retrieval of past records does not establish historical version availability"}
