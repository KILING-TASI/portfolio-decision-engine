from html import escape
import json
from pathlib import Path

from .io import write_json


def save_exposure_report(spec, result, directory):
    root = Path(directory)
    write_json(root / "account-exposure.json", result)
    kinds = {"stock": "股票", "bond": "普通债券", "plain_bond": "普通债券", "convertible_bond": "转债", "cash": "现金", "other": "其他", "unknown": "未知"}
    rows = ""
    for r in result["exposure_paths"] + [{"security": "未知", "instrument_type": "unknown", "amount": result["unknown_amount"], "weight": result["unknown_weight"], "position_id": "未披露/缺映射", "timing": {}}]:
        k = r["instrument_type"]; timing = r["timing"]
        rows += f'<tr data-kind="{escape(k, quote=True)}"><td>{escape(r["security"])}</td><td>{escape(kinds.get(k,k))}</td><td data-value="{r["amount"]}">{r["amount"]:,.2f}</td><td data-value="{r["weight"]}">{r["weight"]:.2%}</td><td>{escape(r.get("issuer") or "未知/不适用")}</td><td>{escape(r.get("industry") or "未知/不适用")}</td><td>{escape(r["position_id"])}</td><td>{escape(timing.get("report_date") or result["valuation_date"])}</td><td>{escape(timing.get("published_at") or "未提供")}</td></tr>'
    cash = result["cash"]
    data = json.dumps({"input": spec, "result": result}, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    notes = "".join(f"<li>{escape(x)}</li>" for x in result["limitations"])
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声明持仓与披露敞口</title>
<style>body{font-family:system-ui,'Microsoft YaHei',sans-serif;color:#19333e;background:#f2f6f8;margin:0}main{max-width:1250px;margin:auto;padding:28px}section{background:white;border-radius:12px;padding:22px;margin:18px 0}.badge{background:#fff2d6;padding:14px;border-radius:8px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px 6px;border-bottom:1px solid #dce5e9;text-align:left}button,select,input{padding:8px;margin:4px}a{color:#117467}.table{overflow:auto}li{margin:8px}</style><main>
'''
    html += f'<h1>声明持仓与披露敞口</h1><p class="badge">{escape(result["data_kind"])} · 方法 {escape(result["method_version"])}<br>估值日 {escape(result["valuation_date"])} · 资料截止 {escape(result["as_of"])} · {escape(result["currency"])} 基础金额单位<br>旧期披露比例连接声明持仓金额；不是实时全量穿透或全组合风险。</p>'
    html += f'<section><h2>金额守恒与现金占用</h2><p>账户总额 {result["total_amount"]:,.2f}；已知 {result["known_amount"]:,.2f}（{result["known_weight"]:.2%}）；未知 {result["unknown_amount"]:,.2f}（{result["unknown_weight"]:.2%}）。</p><p>可用账户现金 {cash["available_account_cash"]:,.2f}；冻结账户现金 {cash["frozen_account_cash"]:,.2f}；基金披露现金 {cash["fund_disclosed_cash"]:,.2f}（不可作账户可用现金）。冻结部分已包含在账户总额中，不再次相加。</p><p>同证券的基金间接与直持按不同经济持仓路径相加，不按名称删去真实敞口。未知、缺发行人/行业映射均保留。</p></section>'
    root_rows = ''.join(f'<tr><td>{escape(p["position_id"])}</td><td>{escape(p["kind"])}</td><td>{escape(p.get("node",p.get("security","未知")))}</td><td>{p["amount"]:,.2f}</td><td>{p["weight"]:.2%}</td></tr>' for p in result["root_positions"])
    html += '<section><h2>根持仓：账户金额层</h2><p>本表与底层敞口是同一账户的两种描述，不能把基金金额再加到穿透后的底层资产上。</p><div class="table"><table><tr><th>经济持仓</th><th>类型</th><th>基金/直持身份</th><th>估值金额</th><th>账户权重</th></tr>'+root_rows+'</table></div></section>'
    html += '<section><h2>显式情景</h2><label>情景 <select id="scenario"></select></label><button id="save-input">另存所选情景输入</button><button id="save-result">另存所选情景结果</button><p id="scenario-text"></p><p>情景不改变资产权重；普通债仅在有来源的修正久期声明下计算一阶估计。缺条款、转债含权风险和未知部分不强算，不将未估计当作零损失。</p></section>'
    html += f'<section><h2>敞口路径：筛选与排序</h2><label>类型 <select id="filter"><option value="all">全部</option>'+''.join(f'<option value="{k}">{v}</option>' for k,v in kinds.items())+'</select></label><label>身份搜索 <input id="search" placeholder="证券、发行人或行业"></label><button id="sort-amount">金额排序</button><button id="sort-weight">权重排序</button><p>筛选只改变显示，权重始终使用完整账户总额，不归一化。</p><div class="table"><table><thead><tr><th>证券</th><th>类型</th><th>敞口金额</th><th>账户权重</th><th>发行人</th><th>行业</th><th>根持仓</th><th>持仓期/估值日</th><th>披露日</th></tr></thead><tbody id="rows">'+rows+'</tbody></table></div></section>'
    html += f'<section><h2>依据与边界</h2><p>发行人/行业依据、逐路径来源、债券条款声明、根金额和情景参数保留在 JSON。缺失映射金额：发行人 {result["unmapped_amounts"]["issuer"]:,.2f}，行业 {result["unmapped_amounts"]["industry"]:,.2f}（另有未分类未知敞口）。</p><ul>{notes}</ul><a href="account-exposure.json">完整结果</a> · <a href="source-input.json">冻结原输入</a> · <a href="report-manifest.json">方法及完整性清单</a></section>'
    html += '<script id="data" type="application/json">'+data+'</script>'
    html += '''<script>
const payload=JSON.parse(document.getElementById('data').textContent),result=payload.result;
const select=document.getElementById('scenario');
for(const s of result.scenarios){const o=document.createElement('option');o.value=s.id;o.textContent=s.id;select.append(o)}
select.value=result.selected_scenario;
function renderScenario(){const s=result.scenarios.find(x=>x.id===select.value);document.getElementById('scenario-text').textContent=s.description+'；参数 '+JSON.stringify(s.parameters)+'；已估计金额变化 '+(s.estimated_change===null?'未估计':s.estimated_change.toFixed(2))+'；覆盖金额 '+(s.covered_amount===undefined?'不适用':s.covered_amount.toFixed(2))+'；未估计金额 '+(s.unestimated_amount===undefined?'不适用':s.unestimated_amount.toFixed(2));}
select.addEventListener('change',renderScenario);renderScenario();
function download(name,value){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
document.getElementById('save-input').onclick=()=>download('scenario-input-'+select.value+'.json',{...payload.input,selected_scenario:select.value,requested_method_version:result.method_version,parent_input_sha256:result.input_sha256});
document.getElementById('save-result').onclick=()=>download('scenario-result-'+select.value+'.json',{schema:'account-exposure-scenario-export-v1',source_input_sha256:result.input_sha256,method_version:result.method_version,valuation_date:result.valuation_date,as_of:result.as_of,scenario:result.scenarios.find(x=>x.id===select.value),note:'separate scenario view, historical source/result unchanged'});
function filter(){const kind=document.getElementById('filter').value,term=document.getElementById('search').value.toLowerCase();for(const r of document.querySelectorAll('#rows tr'))r.hidden=!(kind==='all'||r.dataset.kind===kind)||!r.textContent.toLowerCase().includes(term)}
document.getElementById('filter').onchange=filter;document.getElementById('search').oninput=filter;
let descending=true;function sort(column){const body=document.getElementById('rows'),rows=[...body.children];rows.sort((a,b)=>(Number(a.cells[column].dataset.value)-Number(b.cells[column].dataset.value))*(descending?-1:1));rows.forEach(r=>body.append(r));descending=!descending}
document.getElementById('sort-amount').onclick=()=>sort(2);document.getElementById('sort-weight').onclick=()=>sort(3);
</script></main></html>'''
    (root / "exposure-report.html").write_text(html, encoding="utf-8")
