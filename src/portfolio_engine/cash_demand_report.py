from html import escape
import json
from pathlib import Path

import pandas as pd

from .io import clean_json, write_json


def save_cash_demand(spec, result, directory):
    root = Path(directory); write_json(root / "cash-demand.json", result)
    for i, s in enumerate(result["scenarios"]):
        pd.DataFrame(s["daily_ledger"]).to_csv(root / f"cash-ledger-{i}.csv", index=False, encoding="utf-8-sig")
    rows = ""
    for s in result["scenarios"]:
        first = s["first_gap"]
        date = first["date"] if first else "已解析部分未见缺口" if s["unknowns"] else "本情景未见缺口"
        value = f'{first["amount"]:,.2f}' if first else "—"
        rows += f'<tr><td>{escape(s["id"])}</td><td>{escape(date)}</td><td>{value}</td><td>{s["peak_additional_net_cash_needed"]:,.2f}</td><td>{s["closing_available_cash_conditional"]:,.2f}</td><td>{s["closing_frozen_cash"]:,.2f}</td><td>{len(s["unknowns"])}</td></tr>'
    data = json.dumps(clean_json(result), ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    notes = "".join(f'<li>{escape(n)}</li>' for n in result["limitations"])
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>现金需求压力情景</title>
<style>body{{font-family:system-ui,'Microsoft YaHei',sans-serif;color:#19333e;background:#f2f6f8;margin:0}}main{{max-width:1250px;margin:auto;padding:28px}}section{{background:white;border-radius:12px;padding:22px;margin:18px 0}}.badge{{background:#fff2d6;padding:14px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px;border-bottom:1px solid #dce5e9;text-align:left}}.table{{overflow:auto}}select{{padding:8px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}a{{color:#117467}}</style><main>
<h1>现金需求压力情景</h1><p class="badge">{escape(result['data_kind'])}<br>起点估值日 {escape(result['valuation_date'])} → {escape(result['horizon_end'])}；{escape(result['currency'])} 基础金额单位；方法 {escape(result['method_version'])}<br>仅用户声明的条件测算，不是概率、实际成交或变现指令。</p>
<section><h2>账面金额与可用现金分开</h2><p>起点账户账面市值 {result['account_book_amount']:,.2f}；可用账户现金 {result['opening_cash']['available_account_cash']:,.2f}；冻结账户现金 {result['opening_cash']['frozen_account_cash']:,.2f}；基金间接现金 {result['opening_cash']['fund_disclosed_cash']:,.2f}（不可直接使用）。</p><p>冻结现金已从起点可用现金中分出，解冻只转换状态，不再扣一次。资产账面金额不是预计到账金额；折价、费用和到账日均为输入假设。</p></section>
<section class="table"><h2>情景比较：已解析事件下的条件结果</h2><table><tr><th>情景</th><th>首次缺口日期</th><th>首次缺口</th><th>最大追加净现金需求</th><th>期末条件余额</th><th>仍冻结现金</th><th>未知事件数</th></tr>{rows}</table><p>未知现金事件未当作0。存在未知时，本表仅为已解析部分的条件账；完整余额不可估。缺口金额不逐日相加；负余额表示未补足需求，不表示已经借款或支出执行。</p></section>
<section><h2>查看明确情景</h2><select id="scenario"></select><p id="status"></p><h3>压力参数</h3><pre id="parameters"></pre><h3>起点账面与条件可变现估值</h3><p>这是起点全额资产估值，不能再次加入现金账。追加变现比较只使用扣除预定变现后的未预定账面金额，不重新承诺同一资产。</p><div class="table"><table><thead><tr><th>根资产</th><th>账面金额</th><th>起点全额条件净估值</th><th>未预定账面金额</th><th>流动性状态</th></tr></thead><tbody id="assets"></tbody></table></div><h3>日期现金账</h3><div class="table"><table><thead><tr><th>日期</th><th>期初可用</th><th>收入</th><th>必要支出</th><th>解冻</th><th>变现净到账</th><th>期末条件可用</th><th>仍冻结</th></tr></thead><tbody id="ledger"></tbody></table></div><h3>未知与受阻事件</h3><pre id="unknown"></pre><h3>需变现的金额口径</h3><p id="need"></p><pre id="candidates"></pre><p>各资产只是独立条件比较，不能相加当成自动卖出方案；是否有足够且及时到账的变现依据尚未认证。</p></section>
<section><h2>边界与留档</h2><ul>{notes}</ul><a href="cash-demand.json">完整结果与逐情景账本</a> · <a href="source-input.json">冻结输入与参数</a> · <a href="report-manifest.json">方法和文件清单</a></section>
<script id="data" type="application/json">{data}</script><script>
const result=JSON.parse(document.getElementById('data').textContent),sel=document.getElementById('scenario');
for(const s of result.scenarios){{const o=document.createElement('option');o.value=s.id;o.textContent=s.id;sel.append(o)}}
function table(id,rows){{const body=document.getElementById(id);body.replaceChildren();for(const values of rows){{const r=document.createElement('tr');for(const value of values){{const c=document.createElement('td');c.textContent=value;r.append(c)}}body.append(r)}}}}
const money=x=>x===null?'未知/不可估':Number(x).toLocaleString('zh-CN',{{minimumFractionDigits:2,maximumFractionDigits:2}});
function render(){{const s=result.scenarios.find(x=>x.id===sel.value);document.getElementById('status').textContent=s.unknowns.length?'存在未知现金事件；完整预测不可估，下面只含已解析事件。':'全部列入的现金事件按声明条件计算；未认证实际可执行。';document.getElementById('parameters').textContent=JSON.stringify(s.parameters,null,2);table('assets',s.asset_liquidation_values.map(a=>[a.position_id,money(a.book_amount),money(a.conditional_net_liquidation_value),money(a.remaining_unplanned_book_amount),a.liquidity_status]));table('ledger',s.daily_ledger.filter(r=>r.date===result.valuation_date||r.income||r.expense||r.release||r.sale_net||r.date===result.horizon_end).map(r=>[r.date,money(r.opening_available_cash),money(r.income),money(r.expense),money(r.release),money(r.sale_net),money(r.closing_available_cash_conditional),money(r.remaining_frozen_cash)]));document.getElementById('unknown').textContent=JSON.stringify({{unknowns:s.unknowns,blocked:s.blocked_events,settlements:s.settlement_proceeds}},null,2);document.getElementById('need').textContent='无预定变现时，已解析事件的最大净现金需求 '+money(s.net_liquidation_needed_without_planned_sales)+'；计入已明确到账的预定变现后，仍需追加净现金 '+money(s.peak_additional_net_cash_needed)+'。对应账面变现金额取决于资产、折价、费用和到账日期，整体金额不推断。';document.getElementById('candidates').textContent=JSON.stringify(s.additional_liquidity_comparisons,null,2)}}
sel.addEventListener('change',render);render();
</script></main></html>'''
    (root / "cash-demand-report.html").write_text(html, encoding="utf-8")
