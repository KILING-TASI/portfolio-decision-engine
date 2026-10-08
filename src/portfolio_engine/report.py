from html import escape
from pathlib import Path
import json

import numpy as np

from .io import clean_json,write_json


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
    headings="".join(f"<th>{escape(a)}</th>" for a in assets)
    rows="".join(f"<tr><td>{escape(name)}</td>"+"".join(f"<td>{pct(v)}</td>" for v in w)+"</tr>" for name,w in allocation.items())
    comparison="".join(f"<tr><td>{escape(name)}</td><td>{pct(v['cagr'])}</td><td>{pct(v['max_drawdown'])}</td><td>{pct(v['annual_volatility'])}</td></tr>"
                       for name,v in safe.get("out_of_sample_comparison",{}).items())
    warnings="".join(f"<li>{escape(w)}</li>" for w in safe.get("warnings",[]))
    budget=modules.get("M2",{})
    budgets="".join(f"<tr><td>{escape(name)}</td><td>{pct(v['worst_p95'])}</td><td>{'是' if v['converged'] else '否'}</td><td>{'是' if v['feasible'] else '否'}</td></tr>"
                    for name,v in budget.get("candidates",{}).items())
    migration_rows=""
    for mode,plan in modules.get("M4",{}).items():
        if not isinstance(plan,dict): continue
        buy=sum(plan.get("buy",[])); sell=sum(plan.get("sell",[]))
        migration_rows+=f"<tr><td>{escape(mode)}</td><td>{escape(plan.get('status','—'))}</td><td>{buy:,.2f}</td><td>{sell:,.2f}</td><td>{plan.get('cost',0):,.2f}</td></tr>"
    stress_rows="".join(f"<tr><td>{escape(name)}</td><td>{pct(v.get('max_drawdown'))}</td><td>{pct(v.get('worst_month'))}</td><td>{'未恢复' if v.get('recovery_status')=='right_censored' else format(v['recovery_months_from_trough'],'.1f') if v.get('recovery_months_from_trough') is not None else '数据不足'}</td></tr>"
                        for name,v in modules.get("M5",{}).items())
    risk=modules.get("M7",{})
    risk_rows="".join(f"<tr><td>{label}</td><td>{pct(risk.get(key))}</td></tr>" for key,label in
                      [("max_drawdown","历史最大回撤"),("annual_volatility","年化波动"),("cagr","时间加权年化收益")])
    for key,label in [("tail95","95% 损失 ES"),("tail90","90% 损失 ES")]:
        tail=risk.get(key,{})
        risk_rows+=f"<tr><td>{label}</td><td>{pct(tail.get('es'))}（尾部观测质量：{tail.get('tail_mass_observations',0):.1f}）</td></tr>"
    wf=safe.get("walk_forward",{})
    wf_rows="".join(f"<tr><td>{escape(name)}</td><td>{pct(v['cagr'])}</td><td>{pct(v['max_drawdown'])}</td><td>{v['cost']:,.2f}</td></tr>"
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
<section><h2>披露持仓穿透</h2><p>已知权重 {pct(lt.get('known_weight'))}；未知权重 {pct(lt.get('unknown_weight'))}。循环、缺少子基金及未披露部分保留为未知，不按零风险处理。</p><table><tr><th>底层身份</th><th>组合权重</th></tr>{look_rows}</table></section>'''
    selected=budget.get("selected") or "无预算通过方案"
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
<p class="badge">状态：{escape(safe['status'])} · 回撤预算状态：{escape(budget.get('status','not_run'))} · {escape(selected)}</p>
<p>历史、自举模拟与样本外结果分别展示。模拟分位数不构成未来亏损保证。</p>
<p>频率：{escape(quality.get('frequency','未登记'))}；年化因子：{quality.get('periods_per_year','—')}；日历状态：{escape(quality.get('calendar_status','未登记'))}。<a href="report-manifest.json">留档清单</a>记录输入、来源快照、报告文件和计算方法。</p>
<section><h2>已知边界</h2><ul>{warnings}</ul></section>
<section><h2>配置候选</h2><table><tr><th>方法</th>{headings}</tr>{rows}</table></section>
<section><h2>回撤预算</h2><p>预算 {pct(budget.get('budget'))}；采用所选块长中的最差 p95；严格模式还检查蒙特卡洛区间上端。</p><table><tr><th>方法</th><th>最差 p95</th><th>误差收敛</th><th>满足预算</th></tr>{budgets}</table></section>
<section><h2>冻结权重后的留出区间比较</h2><table><tr><th>方法</th><th>年化收益</th><th>最大回撤</th><th>年化波动</th></tr>{comparison}</table><p>单次留出比较不代表长期优化有效。</p></section>
<section><h2>M1 滚动样本外比较</h2><p>{len(wf.get('folds',[]))} 个窗口；新权重使用此前数据，连续账本计入换仓费用。本表不验证 M2 筛选。</p><table><tr><th>方法</th><th>年化收益</th><th>最大回撤</th><th>模拟累计费用</th></tr>{wf_rows}</table></section>
<section><h2>迁移方案</h2><p>金额方案，包含新增资金、锁定不可卖和线性费用。不可行方案不会放宽约束。</p><table><tr><th>方案</th><th>状态</th><th>买入金额</th><th>卖出金额</th><th>费用</th></tr>{migration_rows}</table></section>
<section><h2>情景回放</h2><p>固定配置反事实；合成数据报告中的历史命名窗口不代表真实市场损失。</p><table><tr><th>情景</th><th>最大回撤</th><th>最差月</th><th>谷底至恢复月数</th></tr>{stress_rows}</table></section>
<section><h2>持仓归因与交易对比</h2><p>板块归因按用户输入与基准计算；交易对比依赖完整订单，不代表择时能力的证明。</p><table><tr><th>多期归因项</th><th>贡献</th></tr>{attribution_rows}</table><table><tr><th>路径财富差</th><th>金额</th></tr>{trade_rows}</table></section>
<section><h2>风险卡片</h2><table>{risk_rows}</table><p>Sharpe：{escape(str(risk.get('sharpe','—')))}；分块区间：{escape(str(risk.get('sharpe_bootstrap',{}).get('interval','—')))}。有效风险资产数：{escape(str(risk.get('effective_risk_assets','—')))}。</p></section>
{supplement_section}
<section><h2>参考配置的全历史描述净值</h2><p>参考方法：{escape(safe.get('reference_method','—'))}。权重使用训练数据估计，本图不是全历史样本外业绩。</p>{svg}</section>
<section><h2>下载与完整结果</h2><p><a href="report.json">完整 JSON</a> · <a href="ledger.csv">账户账本</a> · <a href="transactions.csv">模拟交易</a></p><details><summary>查看全部模块与假设</summary><pre>{detail}</pre></details></section></main></html>'''
    (out/"report.html").write_text(html,encoding="utf-8")
    return out/"report.html"
