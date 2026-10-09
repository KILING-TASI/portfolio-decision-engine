"""Plain-language interpretation grounded in reported comparisons, not advice."""
METHODS={"equal_weight":"等权","constrained_equal_reference":"受约束等权参考","min_variance":"最小方差",
         "risk_parity":"风险平价","max_diversification":"最大分散","black_litterman_utility":"观点配置"}


def comparison_tradeoffs(results,baseline):
    if baseline not in results:return {"status":"insufficient_data","rows":[]}
    reference=results[baseline];rows=[]
    for name,result in results.items():
        gain=result["cagr"]-reference["cagr"]
        reduction=reference["max_drawdown"]-result["max_drawdown"]
        label="基准" if name==baseline else "收益与回撤均改善" if gain>1e-8 and reduction>1e-8 else "降低回撤，牺牲收益" if gain<-1e-8 and reduction>1e-8 else "提高收益，承担更大回撤" if gain>1e-8 and reduction<-1e-8 else "收益与回撤均不及基准" if gain<-1e-8 and reduction<-1e-8 else "差异较小或方向混合"
        rows.append({"method":name,"annual_return_difference":gain,"drawdown_reduction":reduction,"interpretation":label})
    return {"status":"ok","baseline":baseline,"rows":rows,
            "scope":"observed comparison; no statistical significance or persistence claim"}


def decision_summary(report):
    modules=report["modules"];budget=modules.get("M2",{});selected=budget.get("selected")
    synthetic=report.get("inputs",{}).get("data",{}).get("return_type")=="synthetic_total_return"
    conclusions=["本次使用教学模拟数据，结果用于检查计算行为，不代表市场业绩。"] if synthetic else []
    if selected:
        risk=budget["candidates"][selected]
        upper=max(row["p95_mc_interval"][1] for row in risk["blocks"])
        horizon=risk["blocks"][0]["horizon_steps"]
        conclusions.append(f"{METHODS.get(selected,selected)}在{horizon}步模拟期限内满足已声明预算条件；最差回撤p95为{risk['worst_p95']:.2%}，蒙特卡洛区间上端最高为{upper:.2%}。这不是未来亏损保证。")
    else:
        conclusions.append("本次没有最终通过回撤预算的配置；后续权重和迁移仅供比较。")
    baseline=report.get("baseline_comparison",{}).get("method")
    tradeoffs=comparison_tradeoffs(report.get("out_of_sample_comparison",{}),baseline)
    for row in tradeoffs["rows"]:
        if row["method"]==selected and selected!=baseline:
            conclusions.append(f"留出区间相对{METHODS.get(baseline,baseline)}：年化收益差{row['annual_return_difference']*100:+.2f}个百分点，最大回撤减少{row['drawdown_reduction']*100:+.2f}个百分点；{row['interpretation']}。")
    migration=modules.get("M4",{})
    for name in ["minimum_trade","buy_only"]:
        plan=migration.get(name,{})
        if plan.get("status")=="ok" and not plan.get("target_reached",False):
            conclusions.append(f"{'最小调仓' if name=='minimum_trade' else '只买不卖'}方案仍有最大{plan['max_target_gap']*100:.2f}个百分点的目标偏离；可执行不等于达到目标。")
            estimate=plan.get("risk_change",{})
            if estimate:
                conclusions.append(f"同一训练协方差下，方案后估计年化波动为{estimate['final_annual_volatility']:.2%}，目标配置为{estimate['target_annual_volatility']:.2%}；迁移后的回撤预算尚未重新校验。")
            break
    risk=modules.get("M7",{})
    interval=risk.get("sharpe_bootstrap",{}).get("interval")
    if interval is not None and interval[0]<=0<=interval[1]:
        conclusions.append("Sharpe自举区间包含零，当前样本不能提供稳定风险调整优势的证据。")
    return {"conclusions":conclusions,"tradeoffs":tradeoffs,
            "scope":"descriptive interpretation, not a recommendation or verified personal risk suitability"}
