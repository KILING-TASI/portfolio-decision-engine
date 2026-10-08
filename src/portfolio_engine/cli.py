import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .engine import run_engine
from .io import load_returns,write_json
from .report import save_report
from .validation import InputError
from .archive import atomic_output,manifest,verify,read_json,digest
from .data_bridge import prepare_bundle,workbench_adapter,collected_adapter
from .collect import collect_requests


def make_demo(directory,seed=42,fast=False):
    out=Path(directory); out.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(seed)
    dates=pd.bdate_range("2014-01-01","2025-12-31")
    # Artificial factor shocks demonstrate risk behavior; these are not market history.
    market=rng.normal(.0002,.009,len(dates))
    for start,end in [("2015-06-01","2015-08-31"),("2018-05-01","2018-10-31"),("2020-02-01","2020-03-31")]:
        market[(dates>=start)&(dates<=end)]-=.0018
    x=np.c_[market+rng.normal(0,.003,len(dates)),rng.normal(.00012,.002,len(dates)),
            -.15*market+rng.normal(.0002,.006,len(dates)),.7*market+rng.normal(.0002,.006,len(dates))]
    frame=pd.DataFrame(x,index=dates,columns=["equity_demo","bond_demo","gold_demo","overseas_demo"])
    frame.index.name="date"; frame.to_csv(out/"returns.csv")
    factors=pd.DataFrame({"market":market,"size":rng.normal(0,.004,len(dates)),"value":rng.normal(0,.004,len(dates))},index=dates)
    factors.index.name="date"; factors.to_csv(out/"factors.csv")
    orders=pd.DataFrame([[-1000,900,0,0],[500,-600,0,0]],index=[dates[50],dates[100]],columns=frame.columns)
    orders.index.name="date"; orders.to_csv(out/"orders.csv")
    write_json(out/"premium.json",{"code":"gold_demo","prices":[{"date":"2025-12-30","close":2.1},{"date":"2025-12-31","close":2.2}],
        "nav":[{"date":"2025-12-30","nav":2},{"date":"2025-12-31","nav":2.05}],
        "price_source_url":"https://example.org/synthetic-price","nav_source_url":"https://example.org/synthetic-nav"})
    write_json(out/"lookthrough.json",{"as_of":"2025-12-31","currency":"CNY","root":"portfolio","nodes":{
        "portfolio":{"currency":"CNY","source_url":"https://example.org/synthetic-holdings","report_date":"2025-09-30","published_at":"2025-10-30",
                     "holdings":[{"kind":"fund","node":"fund_demo","weight":.7},{"kind":"cash","id":"cash_demo","weight":.3}]},
        "fund_demo":{"currency":"CNY","source_url":"https://example.org/synthetic-fund","report_date":"2025-06-30","published_at":"2025-08-30",
                     "holdings":[{"kind":"stock","id":"stock_demo","weight":.8}]}}})
    config={"data":{"return_type":"synthetic_total_return","source":"seeded synthetic demonstration; not market history","currency":"CNY","frequency":"daily"},
            "seed":seed,"train_fraction":.75,"min_weight":.05,"max_weight":.4,
            "costs":[.0001,.0001,.0001,.0001],"initial_value":100000,
            "initial_weights":[.225,.225,.225,.225],"current_holdings":[50000,10000,15000,15000],
            "current_cash":10000,"new_funds":10000,"locked_indices":[0],
            "cashflows":{str(dates[60].date()):10000,str(dates[120].date()):-5000},
            "factor_csv":"factors.csv","orders_csv":"orders.csv","premium_file":"premium.json","lookthrough_file":"lookthrough.json",
            "brinson":{"portfolio_weights":[[.6,.4],[.55,.45]],"benchmark_weights":[[.5,.5],[.5,.5]],
                        "portfolio_returns":[[.1,.03],[-.05,.04]],"benchmark_returns":[[.08,.02],[-.06,.03]]},
            "bootstrap":{"budget":.3,"horizon":252,"paths":200 if fast else 2000,
                         "max_paths":400 if fast else 8000,"block_lengths":[10,20] if fast else [10,20,40,60],
                         "mc_tolerance":.03 if fast else .01,"rebalance_every":63}}
    write_json(out/"config.json",config)
    return out/"returns.csv",out/"config.json"


def main(argv=None):
    parser=argparse.ArgumentParser(description="Portfolio decision research engine")
    commands=parser.add_subparsers(dest="command",required=True)
    demo=commands.add_parser("demo",help="generate synthetic inputs and execute all supported modules")
    demo.add_argument("--out",default="reports/demo")
    demo.add_argument("--seed",type=int,default=42)
    demo.add_argument("--fast",action="store_true",help="small MC demo; not research precision")
    run=commands.add_parser("run",help="analyze a return/price CSV and JSON configuration")
    run.add_argument("--returns",required=True)
    run.add_argument("--config",required=True)
    run.add_argument("--out",default="reports/analysis")
    prepare=commands.add_parser("prepare",help="audit total-return indices or NAV plus declared complete events")
    prepare.add_argument("--input",required=True)
    prepare.add_argument("--out",required=True)
    input_formats=prepare.add_mutually_exclusive_group()
    input_formats.add_argument("--workbench",action="store_true",help="input is research-workbench research-bundle")
    input_formats.add_argument("--archive",action="store_true",help="input is this engine's collected source archive")
    prepare.add_argument("--events",help="per-code event declarations for workbench NAV")
    prepare.add_argument("--currency",help="explicit common currency for workbench inputs")
    collect=commands.add_parser("collect",help="archive bounded explicit online sources; does not produce verified total return")
    collect.add_argument("--input",required=True)
    collect.add_argument("--online",action="store_true")
    collect.add_argument("--out",required=True)
    check=commands.add_parser("verify",help="read-only report file/method integrity")
    check.add_argument("directory")
    args=parser.parse_args(argv)
    try:
        if args.command=="verify":
            result=verify(args.directory);print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result["status"]=="stored_content_verified" else 2
        with atomic_output(args.out) as stage:
            if args.command=="collect":
                spec=read_json(args.input);result,raws=collect_requests(spec,args.online)
                write_json(stage/"input.json",spec);write_json(stage/"source-archive.json",result)
                for name,raw in raws.items(): (stage/name).write_bytes(raw)
                manifest(stage);print(f"Source archive: {Path(args.out).resolve()}")
                return 0 if result["status"]=="observed" else 2
            if args.command=="prepare":
                spec=read_json(args.input);write_json(stage/"input.json",spec)
                if args.workbench or args.archive:
                    if not args.currency or not args.events: raise InputError("workbench requires --currency and --events")
                    declarations=read_json(args.events);write_json(stage/"event-declarations.json",declarations)
                    if args.archive:
                        root=Path(args.input).resolve().parent
                        checked=verify(root)
                        if checked["status"]=="content_mismatch":raise InputError("collected source files changed")
                        for row in spec["results"]:
                            if row.get("status")!="observed":continue
                            response=(root/row["response_file"]).resolve()
                            if not response.is_relative_to(root) or digest(response)!=row["response_sha256"]:
                                raise InputError("provider raw response binding mismatch")
                            (stage/("upstream-"+response.name)).write_bytes(response.read_bytes())
                        spec=collected_adapter(spec,args.currency,declarations)
                    else:
                        spec=workbench_adapter(spec,args.currency,declarations)
                frame,metadata,quality=prepare_bundle(spec)
                frame.to_csv(stage/"returns.csv",index_label="date")
                config=dict(spec.get("engine_config",{}));config["data"]=metadata;config["periods_per_year"]=quality["periods_per_year"]
                write_json(stage/"config.json",config);write_json(stage/"data-quality.json",quality)
                manifest(stage);print(f"Prepared input: {Path(args.out).resolve()}")
                return 0
            if args.command=="demo":
                returns_path,config_path=make_demo(stage/"inputs",args.seed,args.fast)
            else:
                returns_path,config_path=Path(args.returns),Path(args.config)
            config=read_json(config_path)
            if not isinstance(config,dict):raise InputError("config must be an object")
            frame,snapshot=load_returns(returns_path,config.get("input_kind","returns"))
            report,path=run_engine(frame,config,snapshot,config_path.parent)
            save_report(report,path,stage)
            # Freeze exact source input/config bytes as well as normalized returns.
            (stage/"source-input.csv").write_bytes(returns_path.read_bytes())
            (stage/"source-config.json").write_bytes(config_path.read_bytes())
            for field in ["factor_csv","orders_csv","premium_file","lookthrough_file"]:
                if config.get(field):
                    (stage/(field+".snapshot")).write_bytes((config_path.parent/config[field]).read_bytes())
            manifest(stage)
        print(f"Report: {(Path(args.out)/'report.html').resolve()}")
        print(f"Status: {report['status']}; M2: {report['modules'].get('M2',{}).get('status','not_run')}")
        return 0 if report["status"] not in {"invalid_input","infeasible"} else 2
    except (InputError,ValueError,KeyError,OSError,TypeError) as exc:
        print(f"Invalid input: {exc}",file=sys.stderr)
        if hasattr(args,"out") and not Path(args.out).exists():
            with atomic_output(args.out) as stage:
                write_json(stage/"failure.json",{"status":"blocked","reason":str(exc),"next_step":"correct input and choose a new output directory"})
        return 2


if __name__=="__main__":
    raise SystemExit(main())
