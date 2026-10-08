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
    config={"data":{"return_type":"synthetic_total_return","source":"seeded synthetic demonstration; not market history","currency":"CNY"},
            "seed":seed,"train_fraction":.75,"min_weight":.05,"max_weight":.4,
            "costs":[.0001,.0001,.0001,.0001],"initial_value":100000,
            "initial_weights":[.225,.225,.225,.225],"current_holdings":[50000,10000,15000,15000],
            "current_cash":10000,"new_funds":10000,"locked_indices":[0],
            "cashflows":{str(dates[60].date()):10000,str(dates[120].date()):-5000},
            "factor_csv":"factors.csv","orders_csv":"orders.csv",
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
    args=parser.parse_args(argv)
    try:
        if args.command=="demo":
            returns_path,config_path=make_demo(Path(args.out)/"inputs",args.seed,args.fast)
        else:
            returns_path,config_path=Path(args.returns),Path(args.config)
        config=json.loads(config_path.read_text(encoding="utf-8-sig"))
        frame,snapshot=load_returns(returns_path,config.get("input_kind","returns"))
        report,path=run_engine(frame,config,snapshot,config_path.parent)
        html=save_report(report,path,args.out)
        print(f"Report: {html.resolve()}")
        print(f"Status: {report['status']}; M2: {report['modules'].get('M2',{}).get('status','not_run')}")
        return 0 if report["status"] not in {"invalid_input","infeasible"} else 2
    except (InputError,ValueError,KeyError,OSError,TypeError) as exc:
        print(f"Invalid input: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
