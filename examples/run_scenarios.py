"""Run bounded teaching scenarios through installed CLIs; no other repositories."""
import argparse
import copy
import csv
from datetime import date, timedelta
import hashlib
from html import escape
import json
import os
from pathlib import Path
import subprocess
import sys


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    resources = Path(__file__).resolve().parent
    cases = []
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("PYTHONPATH", "PYTHONHOME", "RESEARCH_WORKBENCH_")):
            env.pop(key, None)

    def cli(name, operation, spec, result_file, expected, check, returncode=0):
        folder = root / name
        folder.mkdir()
        input_path = folder / "input.json"
        save(input_path, spec)
        save(folder / "expected.json", expected)
        output = folder / "result"
        input_args = [str(input_path)] if operation == ["portfolio_engine.observed_review"] else ["--input", str(input_path)]
        command = [sys.executable, "-I", "-m", *operation, *input_args, "--out", str(output)]
        run = subprocess.run(command, cwd=root, env=env, capture_output=True)
        (folder / "stdout.txt").write_bytes(run.stdout)
        (folder / "stderr.txt").write_bytes(run.stderr)
        assert run.returncode == returncode, run.stderr[-1500:]
        actual = json.loads((output / result_file).read_text("utf8"))
        check(actual)
        if (output / "report-manifest.json").exists():
            manifest = json.loads((output / "report-manifest.json").read_text("utf8"))
            for filename, digest in manifest["files"].items():
                assert sha(output / filename) == digest
        save(folder / "actual.json", actual)
        cases.append({"id": name, "status": "passed", "expected": expected,
                      "returncode": run.returncode, "command": command,
                      "input_sha256": sha(input_path), "report": str((output / "cash-demand-report.html" if (output / "cash-demand-report.html").exists() else output / result_file).relative_to(root)),
                      "method_version": actual.get("method_version"),
                      "method_manifest": json.loads((output / "report-manifest.json").read_text("utf8"))
                      if (output / "report-manifest.json").exists() else None})
        return output

    observed = json.loads((resources / "observed-review-demo.json").read_text("utf8"))
    observed["payload"]["basis"] = "Teaching only: 1000 opening +1000 deposit, unchanged investment values"
    observed["payload"]["observations"] = [
        {"date": "2025-01-01", "beforeFlowValue": 1000, "externalFlow": 0, "afterFlowValue": 1000},
        {"date": "2025-07-01", "beforeFlowValue": 1000, "externalFlow": 1000, "afterFlowValue": 2000},
        {"date": "2026-01-01", "beforeFlowValue": 2000, "externalFlow": 0, "afterFlowValue": 2000}]
    def no_return(actual):
        result = actual["result"]
        assert result["profit"] == 0 and result["twrPct"] == 0
        assert abs(result["xirrPct"]) < 1e-8
        assert result["endingValue"] == 2000 and result["netExternalFlow"] == 1000
    cli("deposit-no-performance", ["portfolio_engine.observed_review"], observed,
        "observed-review-result.json", {"ending": 2000, "profit": 0, "TWR_pct": 0, "XIRR_pct": 0,
        "basis": "1000 +1000 external deposit; investment value unchanged"}, no_return)

    cash = json.loads((resources / "cash-demand-demo.json").read_text("utf8"))
    def normal(actual):
        a, b, c = actual["scenarios"]
        assert a["closing_available_cash_conditional"] == 1900 and a["first_gap"] is None
        assert b["first_gap"] == {"date": "2026-10-20", "amount": 8070}
        assert b["peak_additional_net_cash_needed"] == 13070
        assert c["first_gap"] == {"date": "2026-10-28", "amount": 3100} and c["closing_frozen_cash"] == 5000
        for scene in actual["scenarios"]:
            assert scene["closing_frozen_cash"] + sum(d["release"] for d in scene["daily_ledger"]) == 5000
            for row in scene["daily_ledger"]:
                assert abs(row["opening_available_cash"] + row["income"] + row["release"] + row["sale_net"] - row["expense"] - row["closing_available_cash_conditional"]) < 1e-8
    cash_out = cli("cash-release-pressure", ["portfolio_engine", "cash-demand"], cash, "cash-demand.json",
        {"normal_ending": 1900, "stress_first_gap": 8070, "stress_peak": 13070, "unreleased_gap": 3100,
         "basis": "10000+12000+5000+9900-35000=1900; interrupted income net sale6930 gives -13070"}, normal)
    late = copy.deepcopy(cash)
    late["liquidity"]["bond-lot"]["settlement_days"] = 30
    def delayed(actual):
        result = actual["scenarios"][0]
        assert result["first_gap"] == {"date": "2026-10-20", "amount": 3000}
        assert result["peak_additional_net_cash_needed"] == 8000
        assert all(d["sale_net"] == 0 for d in result["daily_ledger"])
    cli("cash-delayed-after-horizon", ["portfolio_engine", "cash-demand"], late, "cash-demand.json",
        {"first_gap": 3000, "peak": 8000, "sale_in_window": 0, "basis": "10000+12000+5000-35000=-8000"}, delayed)
    unknown = copy.deepcopy(cash)
    unknown["liquidity"]["bond-lot"]["fee_rate"] = None
    unknown["frozen_releases"][0]["condition_met"] = None
    def missing(actual):
        result = actual["scenarios"][0]
        assert result["complete_cash_balance"] is None and result["status"] == "conditional_with_unknowns"
        assert {u["id"] for u in result["unknowns"]} == {"sale-1", "release-1"}
    cli("cash-unknown-evidence", ["portfolio_engine", "cash-demand"], unknown, "cash-demand.json",
        {"complete_balance": None, "unknown_ids": ["sale-1", "release-1"],
         "basis": "unknown fee/release condition cannot prove net proceeds or complete cash balance"}, missing)
    bad = copy.deepcopy(cash)
    bad["cashflows"][1]["economic_event_id"] = "release-1"
    def duplicate(actual):
        assert actual["status"] == "blocked" and "duplicate economic event" in actual["reason"]
    cli("reject-double-cash", ["portfolio_engine", "cash-demand"], bad, "failure.json",
        {"status": "blocked", "basis": "same release cannot be counted again as external income"}, duplicate, 2)
    before = {str(p.relative_to(cash_out)): sha(p) for p in cash_out.rglob("*") if p.is_file()}
    refused = subprocess.run([sys.executable, "-I", "-m", "portfolio_engine", "cash-demand",
        "--input", str(cash_out.parent / "input.json"), "--out", str(cash_out)], cwd=root, env=env, capture_output=True)
    assert refused.returncode == 2 and before == {str(p.relative_to(cash_out)): sha(p) for p in cash_out.rglob("*") if p.is_file()}

    dates = []
    day = date(2025, 1, 1)
    while len(dates) < 80:
        if day.weekday() < 5:
            dates.append(day)
        day += timedelta(days=1)
    for name, losses in [("fees-monthly-rebalance", False), ("budget-no-solution", True)]:
        folder = root / name
        folder.mkdir()
        values = [[-.01 + (.0001 if i % 2 else -.0001),
                   -.01 + (.0001 if i % 4 < 2 else -.0001)] for i in range(80)] if losses else [
            [.001 if i % 2 else -.001, .001 if i % 4 < 2 else -.001] for i in range(80)]
        if not losses:
            values[56:] = [[.1, 0], [0, .2]] + [[0, 0]] * 22
        csv_path = folder / "returns.csv"
        with csv_path.open("w", newline="", encoding="utf8") as handle:
            writer = csv.writer(handle); writer.writerow(["date", "a", "b"])
            writer.writerows([[d.isoformat(), *r] for d, r in zip(dates, values)])
        config = {"data": {"return_type": "synthetic_total_return", "source": "manual teaching returns; not market history",
                  "currency": "CNY", "frequency": "daily"}, "seed": 42, "train_fraction": .7,
                  "min_weight": .5, "max_weight": .5, "initial_value": 100, "costs": .01,
                  "rebalance": "monthly", "require_china_bear_coverage": False,
                  "bootstrap": {"budget": .000001 if losses else .95, "horizon": 20,
                     "paths": 100, "max_paths": 100, "block_lengths": [5, 10], "mc_tolerance": .05}}
        save(folder / "config.json", config)
        output = folder / "result"
        command = [sys.executable, "-I", "-m", "portfolio_engine", "run", "--returns", str(csv_path),
                   "--config", str(folder / "config.json"), "--out", str(output)]
        run = subprocess.run(command, cwd=root, env=env, capture_output=True)
        (folder / "stdout.txt").write_bytes(run.stdout); (folder / "stderr.txt").write_bytes(run.stderr)
        assert run.returncode == 0, run.stderr[-1500:]
        actual = json.loads((output / "report.json").read_text("utf8"))
        ledger = list(csv.DictReader((output / "ledger.csv").open(encoding="utf-8-sig")))
        # Independent closed-form self-financing two-asset 50/50 rebalance:
        # fee=c*|h1-h2|; initial net=100/(1+c). No optimizer reused.
        holdings = [0., 0.]; previous = None; expected = []
        for d, returns in zip(dates, values):
            period = (d.year, d.month); fee = 0.
            if previous is None:
                net = 100 / 1.01; fee = 100-net; holdings = [net/2, net/2]
            elif period != previous:
                fee = .01 * abs(holdings[0]-holdings[1]); net = sum(holdings)-fee; holdings = [net/2, net/2]
            holdings = [h*(1+r) for h,r in zip(holdings, returns)]
            expected.append({"date": d.isoformat(), "value": sum(holdings), "fee": fee}); previous = period
        for row, ref in zip(ledger, expected):
            assert row["date"] == ref["date"] and abs(float(row["value"])-ref["value"]) < 1e-8
            assert abs(float(row["cost"])-ref["fee"]) < 1e-8
        assert len(ledger) == len(expected) == 80
        manifest = json.loads((output / "report-manifest.json").read_text("utf8"))
        for filename, digest in manifest["files"].items():
            assert sha(output / filename) == digest
        if losses:
            assert actual["modules"]["M1"]["allocation"]["status"] == "ok"
            assert actual["modules"]["M2"]["status"] == "infeasible" and actual["modules"]["M2"]["selected"] is None
            assert "not a budget solution" in actual["modules"]["M7"]["scope"]
        save(folder / "expected.json", {"basis": "closed-form fee and cash conservation; fixed declared50/50 weights",
             "wealth_and_fees": expected, "budget": "all candidates rejected: each invested day loses at least0.99%; 1-.9901**20 exceeds1e-6" if losses else "not asserted as investment proof"})
        save(folder / "actual.json", actual)
        cases.append({"id": name, "status": "passed", "command": command,
                      "expected_final_value": expected[-1]["value"], "actual_final_value": float(ledger[-1]["value"]),
                      "budget_status": actual["modules"]["M2"]["status"], "selected": actual["modules"]["M2"]["selected"],
                      "calibration_status": actual["modules"]["M1"]["allocation"]["status"],
                      "report": str((output / "report.html").relative_to(root)),
                      "engine_version": actual["engine_version"],
                      "method_manifest": json.loads((output / "report-manifest.json").read_text("utf8"))})
    save(root / "scenario-results.json", {"status": "passed", "data_kind": "synthetic teaching only",
         "cases": cases, "output_exists_failure": "rejected; all old file hashes unchanged",
         "scope": "conditional arithmetic, not real accounts, actual receipts, probability or visual certification"})
    rows = "".join(f'<tr><td>{escape(c["id"])}</td><td>通过</td><td><a href="{escape(c["id"])}/expected.json">预期</a> · <a href="{escape(c["id"])}/actual.json">实际</a> · <a href="{escape(c["report"])}">报告</a></td></tr>' for c in cases)
    (root / "scenario-index.html").write_text('<meta charset="utf-8"><h1>组合引擎情景实例</h1><p>全部合成教学；非真实覆盖、到账保证或投资有效认证。</p><table>'+rows+'</table><p><a href="scenario-results.json">输入/预期/实际/方法与范围</a></p>', encoding="utf8")
    print(json.dumps({"status": "passed", "cases": len(cases), "output": str(root)}))


if __name__ == "__main__":
    main()
