"""Bounded, explicit online collection; collected NAV/events are not total return."""
import datetime as dt
import hashlib
import re
from urllib.parse import urlencode
from urllib.request import Request,urlopen

import numpy as np

from .archive import strict_json
from .data_bridge import dated_rows
from .validation import InputError


MAX_BYTES=16*1024*1024


def fetch(url):
    request=Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://fund.eastmoney.com/"})
    with urlopen(request,timeout=20) as response:
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise InputError("response exceeds 16MiB")
    return raw


def embedded(text,name):
    match=re.search(r"var\s+"+re.escape(name)+r"\s*=\s*",text)
    if not match: raise InputError("missing provider field: "+name)
    # Extract JSON via raw_decode without executing provider JavaScript; strict
    # parsing of the exact span rejects duplicates and nonfinite constants.
    _,end=__import__("json").JSONDecoder().raw_decode(text[match.end():])
    return strict_json(text[match.end():match.end()+end])


def collect_requests(spec,online=False,fetcher=None):
    if not online: raise InputError("online collection requires --online")
    requests=spec.get("requests")
    if not isinstance(requests,list) or not 1<=len(requests)<=12: raise InputError("provide 1 to 12 collection requests")
    fetcher=fetcher or fetch;results=[];raw_files={}
    for index,request in enumerate(requests):
        try:
            if not isinstance(request,dict) or set(request)-{"provider","code","market","start","end"}:
                raise InputError("unsupported request fields; no arbitrary URLs or credentials")
            code=request["code"];provider=request["provider"]
            if not isinstance(code,str) or not re.fullmatch(r"\d{6}",code): raise InputError("six-digit code required")
            start=dt.date.fromisoformat(request["start"]);end=dt.date.fromisoformat(request["end"])
            if start>=end or end>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date(): raise InputError("invalid requested window")
            if provider=="eastmoney_fund_nav":
                if "market" in request: raise InputError("fund NAV request does not use market")
                url="https://fund.eastmoney.com/pingzhongdata/"+code+".js"
            elif provider=="tencent_cn_price":
                if request.get("market") not in {"sh","sz"}: raise InputError("market must be sh or sz")
                if (end-start).days>366: raise InputError("price request window <=366 days; use separate audited windows")
                symbol=request["market"]+code
                url="https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"+urlencode({"param":f"{symbol},day,{start},{end},640,"})
            else: raise InputError("unsupported provider")
            raw=fetcher(url)
            if not isinstance(raw,bytes) or len(raw)>MAX_BYTES: raise InputError("invalid response")
            raw_name=f"response-{index}.txt";raw_files[raw_name]=raw
            text=raw.decode("utf-8-sig")
            if provider=="eastmoney_fund_nav":
                if str(embedded(text,"fS_code"))!=code: raise InputError("provider identity mismatch")
                name=embedded(text,"fS_name");history=[]
                for row in embedded(text,"Data_netWorthTrend"):
                    timestamp=row["x"]
                    if isinstance(timestamp,bool) or not isinstance(timestamp,(int,float)) or not np.isfinite(timestamp): raise InputError("invalid NAV timestamp")
                    day=dt.datetime.fromtimestamp(timestamp/1000,dt.timezone(dt.timedelta(hours=8))).date()
                    value=row["y"]
                    if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or value<=0: raise InputError("invalid NAV")
                    if start<=day<=end: history.append({"date":day.isoformat(),"nav":value,"distribution_text":row.get("unitMoney","")})
                dated_rows(history,"nav");basis="nav_with_unverified_events"
            else:
                payload=strict_json(text);item=(payload.get("data") or {}).get(symbol)
                if payload.get("code")!=0 or not isinstance(item,dict): raise InputError("no valid price response")
                quote=item.get("qt",{}).get(symbol,[])
                if len(quote)<3 or quote[2]!=code: raise InputError("price identity mismatch")
                name=quote[1];rows=item.get("day")
                if not isinstance(rows,list) or len(rows)>=640: raise InputError("missing or potentially truncated price response")
                history=[]
                for row in rows:
                    day=dt.date.fromisoformat(row[0]);op,close,high,low,volume=map(float,row[1:6])
                    if not np.isfinite([op,close,high,low,volume]).all() or min(op,close,high,low)<=0 or volume<0 or high<max(op,close,low) or low>min(op,close,high): raise InputError("invalid OHLC row")
                    if not start<=day<=end: raise InputError("price observation outside requested dates")
                    history.append({"date":day.isoformat(),"close":close,"open":op,"high":high,"low":low,"volume":volume})
                dated_rows(history,"close");basis="raw_price"
            if not isinstance(name,str) or not name.strip(): raise InputError("provider name missing")
            results.append({"status":"observed","code":code,"name":name,"provider":provider,"basis":basis,"history":history,
                            "requested_start":start.isoformat(),"requested_end":end.isoformat(),
                            "actual_start":history[0]["date"],"actual_end":history[-1]["date"],"observations":len(history),
                            "source_url":url,"response_file":raw_name,"response_sha256":hashlib.sha256(raw).hexdigest(),
                            "retrieved_at":dt.datetime.now(dt.timezone.utc).isoformat(),"calendar_verified":False,
                            "event_coverage":"unverified","point_in_time":"current revised history, not historical frozen knowledge"})
        except (ValueError,KeyError,TypeError,OSError,OverflowError,IndexError) as exc:
            results.append({"status":"failed","request":request,"reason":str(exc)})
    return {"type":"portfolio-source-archive","status":"observed" if all(r["status"]=="observed" for r in results) else "partial",
            "results":results,"limitations":["successful response is not complete calendar, event or source verification; raw prices cannot enter total-return engine"]},raw_files
