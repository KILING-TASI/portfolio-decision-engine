from html import escape
from pathlib import Path
import json

import numpy as np

from .io import clean_json,write_json
from .decision import METHODS

STATUS={"ok":"计算完成","degraded":"结果有明确限制","infeasible":"约束下不可行","unconverged":"误差未收敛",
        "insufficient_data":"资料不足","invalid_input":"输入不满足条件","not_run":"未运行"}
MODES={"buy_only":"只买不卖","minimum_trade":"最小调仓","one_step":"一步到位"}
ASSETS={"equity_demo":"权益（教学）","bond_demo":"债券（教学）","gold_demo":"黄金（教学）","overseas_demo":"海外权益（教学）"}
WARNING_TEXT={
 "Return-based fractional research model: exchange fills, fund settlement, taxes by date, premium and integer lots are not modeled.":"当前按收益序列与金额模拟，尚未完整处理实际成交、基金结算、税费规则和整数份额。",
 "M2 is exploratory training selection; held-out comparison is a single split, not full walk-forward verification.":"回撤预算的候选筛选仍属训练研究；一次留出比较不等于完整滚动验证。",
 "Frequency spacing checked; applicable observation calendar not supplied or verified.":"已检查日期间隔，但尚未提供或核验适用的交易/净值日历。",
 "SYNTHETIC DATA: all returns, scenarios and results are demonstration only.":"本报告全部使用教学模拟数据，不能当作真实市场表现。",
 "Training window does not cover complete 2015 and 2018: no approved drawdown-budget selection.":"训练区间未完整覆盖2015和2018，因此没有最终通过历史覆盖要求的预算配置。",
 "Covariance uses fewer observations than requested window.":"协方差估计的实际观察数少于指定窗口。",
 "Covariance is sensitive to shrinkage assumptions or high dimensionality.":"协方差可能较依赖收缩假设或受到资产数量较多的影响。"}


def label(value):return escape(METHODS.get(value,MODES.get(value,STATUS.get(value,value))))


def pct(value):
    return "—" if value is None else f"{value:.2%}"


def save_report(report,path,output):
    out=Path(output); out.mkdir(parents=True,exist_ok=True)
    write_json(out/"report.json",report)
    if path is not None:
        path.daily.to_csv(out/"ledger.csv",encoding="utf-8-sig")
        path.transactions.to_csv(out/"transactions.csv",index=False,encoding="utf-8-sig")
    safe=clean_json(report)
    modules=safe["modules"]
    allocation=modules.get("M1",{}).get("allocation",{}).get("candidates",{})
    assets=safe.get("assets",[])
    headings="".join(f"<th>{escape(ASSETS.get(a,a))}</th>" for a in assets)
    rows="".join(f"<tr><td>{label(name)}</td>"+"".join(f"<td>{pct(v)}</td>" for v in w)+"</tr>" for name,w in allocation.items())
    comparison="".join(f"<tr><td>{label(name)}</td><td>{pct(v['cagr'])}</td><td>{pct(v['max_drawdown'])}</td><td>{pct(v['annual_volatility'])}</td></tr>"
                       for name,v in safe.get("out_of_sample_comparison",{}).items())
    warnings="".join(f"<li>{escape(WARNING_TEXT.get(w,w))}</li>" for w in safe.get("warnings",[]))
    budget=modules.get("M2",{})
    budgets="".join(f"<tr><td>{label(name)}</td><td>{pct(v['worst_p95'])}</td><td>{'是' if v['converged'] else '否'}</td><td>{'是' if v['feasible'] else '否'}</td></tr>"
                    for name,v in budget.get("candidates",{}).items())
    migration_rows="";migration_detail=""
    for mode,plan in modules.get("M4",{}).items():
        if not isinstance(plan,dict): continue
        buy=sum(plan.get("buy",[])); sell=sum(plan.get("sell",[]))
        solved=plan.get("status")=="ok"
        outcome="已达到目标" if plan.get("target_reached") else "可执行，尚未达到目标" if solved else "不可行"
        gap=f"{plan['max_target_gap']*100:.2f}" if plan.get("max_target_gap") is not None else "—"
        migration_rows+=f"<tr><td>{label(mode)}</td><td>{outcome}</td><td>{buy:,.2f}</td><td>{sell:,.2f}</td><td>{plan.get('cost',0):,.2f}</td><td>{gap}</td></tr>"
        if solved:
            detail_rows="".join(f"<tr><td>{escape(ASSETS.get(asset,asset))}</td><td>{plan['buy'][i]:,.2f}</td><td>{plan['sell'][i]:,.2f}</td><td>{pct(plan['final_weights'][i])}</td><td>{pct(allocation.get(safe.get('reference_method'),[0]*len(assets))[i])}</td></tr>" for i,asset in enumerate(assets))
            migration_detail+=f"<details><summary>{label(mode)}：逐资产差距</summary><table><tr><th>资产</th><th>买入金额</th><th>卖出金额</th><th>方案后权重</th><th>目标权重</th></tr>{detail_rows}</table><p>{escape(plan.get('conclusion',''))} 调整后的回撤预算尚未重新校验。</p></details>"
        diagnosis=plan.get("diagnosis",{})
        if mode=="one_step" and diagnosis.get("obstacles"):
            additional=diagnosis.get("additional_funds_lower_bound")
            amount=f"{additional:,.2f}" if additional is not None else "不存在有限金额"
            migration_detail+=f"<p class='badge'>锁定或禁止卖出的高配资产阻碍精确迁移。当前资金之外，必要的稀释资金下界为 {amount}；忽略费用和其他约束，不保证足够，也不是追加资金建议。</p>"
    stress_rows="".join(f"<tr><td>{escape(name)}</td><td>{pct(v.get('max_drawdown'))}</td><td>{pct(v.get('worst_month'))}</td><td>{'未恢复' if v.get('recovery_status')=='right_censored' else format(v['recovery_months_from_trough'],'.1f') if v.get('recovery_months_from_trough') is not None else '数据不足'}</td></tr>"
                        for name,v in modules.get("M5",{}).items())
    risk=modules.get("M7",{})
    risk_rows="".join(f"<tr><td>{label}</td><td>{pct(risk.get(key))}</td></tr>" for key,label in
                      [("max_drawdown","历史最大回撤"),("annual_volatility","年化波动"),("cagr","时间加权年化收益")])
    for key,tail_label in [("tail95","95% 损失 ES"),("tail90","90% 损失 ES")]:
        tail=risk.get(key,{})
        risk_rows+=f"<tr><td>{tail_label}</td><td>{pct(tail.get('es'))}（尾部观测质量：{tail.get('tail_mass_observations',0):.1f}）</td></tr>"
    wf=safe.get("walk_forward",{})
    wf_rows="".join(f"<tr><td>{label(name)}</td><td>{pct(v['cagr'])}</td><td>{pct(v['max_drawdown'])}</td><td>{v['cost']:,.2f}</td></tr>"
                    for name,v in wf.get("results",{}).items())
    linked=modules.get("M3",{}).get("brinson",{}).get("linked",{})
    attribution_rows="".join(f"<tr><td>{escape(name)}</td><td>{pct(value)}</td></tr>" for name,value in linked.items()) or "<tr><td colspan='2'>未提供板块输入</td></tr>"
    wealth=modules.get("M6",{}).get("wealth_differences",{})
    trade_rows="".join(f"<tr><td>{escape(name)}</td><td>{value:,.2f}</td></tr>" for name,value in wealth.items()) or "<tr><td colspan='2'>未提供完整订单</td></tr>"
    quality=safe.get("data_quality",{})
    supplemental=safe.get("supplemental",{})
    premium_rows="".join(f"<tr><td>{escape(row['date'])}</td><td>{row['close']:.4f}</td><td>{row['nav']:.4f}</td><td>{pct(row['premium'])}</td></tr>"
                         for row in supplemental.get("premium",{}).get("rows",[]))
    lt=supplemental.get("lookthrough",{})
    look_rows="".join(f"<tr><td>{escape(name)}</td><td>{pct(weight)}</td></tr>" for name,weight in lt.get("leaves",{}).items())
    supplement_section=""
    if supplemental:
        supplement_section=f'''<section><h2>ETF 收盘价与净值对照</h2><p>同日收盘偏离不是盘中 IOPV，也不是可成交价差。</p><table><tr><th>日期</th><th>收盘价</th><th>单位净值</th><th>偏离</th></tr>{premium_rows}</table></section>
<section><h2>披露持仓穿透</h2><p>已知权重 {pct(lt.get('known_weight'))}；未知权重 {pct(lt.get('unknown_weight'))}。循环、缺少子基金及未披露部分保留为未知，不按零风险处理。披露快照不是实时持仓；发行人映射为输入依据，不由部分股票穿透推算全组合风险或事件损失。</p><table><tr><th>底层身份</th><th>组合权重</th></tr>{look_rows}</table></section>'''
    selected=label(budget["selected"]) if budget.get("selected") else "无预算通过方案"
    interpretation=safe.get("decision_summary",{})
    conclusions="".join(f"<li>{escape(text)}</li>" for text in interpretation.get("conclusions",[]))
    tradeoff_rows="".join(f"<tr><td>{label(row['method'])}</td><td>{row['annual_return_difference']*100:+.2f}</td><td>{row['drawdown_reduction']*100:+.2f}</td><td>{escape(row['interpretation'])}</td></tr>" for row in interpretation.get("tradeoffs",{}).get("rows",[]))
    svg=""
    if path is not None:
        series=path.daily.unit_nav.to_numpy()
        sampled=series[np.linspace(0,len(series)-1,min(500,len(series))).astype(int)]
        low,high=float(min(1,sampled.min())),float(max(1,sampled.max()))
        if high==low: high=low+1
        points=" ".join(f"{30+840*i/max(1,len(sampled)-1):.1f},{200-170*(v-low)/(high-low):.1f}" for i,v in enumerate(sampled))
        svg=f'<svg viewBox="0 0 900 240" role="img" aria-label="扣费后的时间加权净值"><line x1="30" y1="200" x2="870" y2="200" stroke="#b9c9d3"/><polyline points="{points}" fill="none" stroke="#16867a" stroke-width="3"/><text x="30" y="230">{escape(str(path.daily.index[0].date()))}</text><text x="760" y="230">{escape(str(path.daily.index[-1].date()))}</text></svg>'
    detail=escape(json.dumps(safe,ensure_ascii=False,indent=2))
    html=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>组合决策报告</title>
<style>body{{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#f2f6f8;color:#19333e;margin:0}}main{{max-width:1050px;margin:auto;padding:32px}}h1{{margin-bottom:8px}}section{{background:white;border-radius:12px;padding:24px;margin:20px 0}}.badge{{background:#fff2d6;padding:10px;border-radius:6px}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:right;padding:12px;border-bottom:1px solid #e5edef}}th:first-child,td:first-child{{text-align:left}}svg{{width:100%;max-height:300px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}li{{margin:10px 0}}a{{color:#117467}}</style>
<main><h1>组合决策报告</h1><p>研究引擎 v{escape(safe['engine_version'])} · 费用后净值与风险比较</p>
<p class="badge">整体：{label(safe['status'])} · 回撤预算：{label(budget.get('status','not_run'))} · {selected}</p>
<section><h2>本次结果怎样理解</h2><ul>{conclusions}</ul></section>
<p>历史、自举模拟与样本外结果分别展示。模拟分位数不构成未来亏损保证。</p>
<p>频率：{escape(quality.get('frequency','未登记'))}；年化因子：{quality.get('periods_per_year','—')}；日历状态：{escape(quality.get('calendar_status','未登记'))}。<a href="report-manifest.json">留档清单</a>记录输入、来源快照、报告文件和计算方法。</p>
<section><h2>已知边界</h2><ul>{warnings}</ul></section>
<section><h2>配置候选</h2><table><tr><th>方法</th>{headings}</tr>{rows}</table></section>
<section><h2>回撤预算</h2><p>预算 {pct(budget.get('budget'))}。p95表示模型模拟中约95%的路径回撤不超过该数值，不能当未来亏损上限。比较采用所选块长中的最差p95；严格模式还检查其蒙特卡洛区间上端。</p><table><tr><th>方法</th><th>最差 p95</th><th>误差收敛</th><th>模拟条件满足预算</th></tr>{budgets}</table></section>
<section><h2>冻结权重后的留出区间比较</h2><table><tr><th>方法</th><th>年化收益</th><th>最大回撤</th><th>年化波动</th></tr>{comparison}</table><p>单次留出比较不代表长期优化有效。</p></section>
<section><h2>相对基准的收益与风险取舍</h2><table><tr><th>方法</th><th>年化收益差（百分点）</th><th>回撤减少（百分点）</th><th>观察结论</th></tr>{tradeoff_rows}</table><p>比较结果不代表统计显著性或长期优势。</p></section>
<section><h2>M1 滚动样本外比较</h2><p>{len(wf.get('folds',[]))} 个窗口；新权重使用此前数据，连续账本计入换仓费用。本表不验证 M2 筛选。</p><table><tr><th>方法</th><th>年化收益</th><th>最大回撤</th><th>模拟累计费用</th></tr>{wf_rows}</table></section>
<section><h2>迁移方案</h2><p>金额方案，包含新增资金、锁定不可卖和线性费用。目标权重满足预算不代表受约束的迁移后账户也满足预算。</p><table><tr><th>方案</th><th>目标落实</th><th>买入金额</th><th>卖出金额</th><th>费用</th><th>最大目标偏离（百分点）</th></tr>{migration_rows}</table>{migration_detail}</section>
<section><h2>情景回放</h2><p>固定配置反事实；合成数据报告中的历史命名窗口不代表真实市场损失。</p><table><tr><th>情景</th><th>最大回撤</th><th>最差月</th><th>谷底至恢复月数</th></tr>{stress_rows}</table></section>
<section><h2>持仓归因与交易对比</h2><p>板块归因按用户输入与基准计算；交易对比依赖完整订单，不代表择时能力的证明。</p><table><tr><th>多期归因项</th><th>贡献</th></tr>{attribution_rows}</table><table><tr><th>路径财富差</th><th>金额</th></tr>{trade_rows}</table></section>
<section><h2>风险卡片</h2><table>{risk_rows}</table><p>Sharpe：{escape(str(risk.get('sharpe','—')))}；分块区间：{escape(str(risk.get('sharpe_bootstrap',{}).get('interval','—')))}。有效风险资产数：{escape(str(risk.get('effective_risk_assets','—')))}。</p></section>
{supplement_section}
<section><h2>参考配置的全历史描述净值</h2><p>参考方法：{label(safe.get('reference_method','—'))}。权重使用训练数据估计，本图不是全历史样本外业绩。</p>{svg}</section>
<section><h2>下载与完整结果</h2><p><a href="report.json">完整 JSON</a> · <a href="ledger.csv">账户账本</a> · <a href="transactions.csv">模拟交易</a></p><details><summary>查看全部模块与假设</summary><pre>{detail}</pre></details></section></main></html>'''
    (out/"report.html").write_text(html,encoding="utf-8")
    return out/"report.html"
