from html import escape
from pathlib import Path

from .decision import METHODS
from .io import write_json


def save_m2_evaluation(result,actual,baseline,directory):
    root=Path(directory);write_json(root/"m2-evaluation.json",result)
    for name,path in [("actual",actual),("baseline",baseline)]:
        path.daily.to_csv(root/(name+"-ledger.csv"),encoding="utf-8-sig")
        path.transactions.to_csv(root/(name+"-transactions.csv"),index=False,encoding="utf-8-sig")
    rows=""
    for fold in result["folds"]:
        selected=METHODS.get(fold["selected"],fold["selected"]) if fold["selected"] else "无预算解："+fold["no_solution_action"]
        breach="超过预算" if fold["budget_breach"] else "未超过" if fold["budget_breach"] is False else "不计入同期限统计"
        rows+=f"<tr><td>{fold['fold_id']}</td><td>{fold['fit_end']}</td><td>{fold['calibration_end']}</td><td>{fold['test_start']}—{fold['test_end']}</td><td>{escape(selected)}</td><td>{fold['test_max_drawdown']:.2%}</td><td>{breach}</td><td>{fold['cost']:.2f}</td><td>{fold['ending_cash']:.2f}</td></tr>"
    notes="".join(f"<li>{escape(note)}</li>" for note in result["limitations"])
    synthetic=result["inputs"]["data"]["return_type"]=="synthetic_total_return"
    badge="教学模拟数据，不是市场业绩。" if synthetic else "输入来源、总回报与历史版本仍需独立核验。"
    actual_metrics=result["actual"];base=result["baseline"]
    html=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>M2滚动样本外验证</title>
<style>body{{font-family:system-ui,'Microsoft YaHei',sans-serif;background:#f2f6f8;color:#19333e}}main{{max-width:1200px;margin:auto;padding:24px}}section{{padding:20px;background:white;margin:16px 0;border-radius:12px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;border-bottom:1px solid #dce5e9;text-align:right}}td:first-child,th:first-child{{text-align:left}}.table{{overflow:auto}}li{{margin:8px}}</style>
<main><h1>M2完整滚动样本外验证</h1><p>{badge} 未经统计校正的一次运行不证明未来预算控制有效。</p>
<section><h2>每个窗口实际执行什么</h2><p>重新估计协方差 → 生成候选 → 使用此前资料进行回撤预算筛选 → 冻结配置 → 仅评价下一测试窗口。无解按预先声明的研究策略处理，不放宽预算。</p><p>配置估计：{escape(result['purposes']['fit'])}<br>校验用途：{escape(result['purposes']['validation'])}<br>测试用途：{escape(result['purposes']['test'])}</p></section>
<section><h2>整体观察</h2><p>窗口数 {len(result['folds'])}；无解率 {result['no_solution_rate']:.2%}；同期限、已选中配置的预算突破 {result['budget_breach_count']}/{result['budget_eligible_full_windows']}。末尾不足期限的窗口不计入预算突破率。</p>
<table><tr><th>路径</th><th>年化收益</th><th>最大回撤</th><th>累计费用</th><th>期末资产</th></tr><tr><td>M2滚动选择</td><td>{actual_metrics['cagr']:.2%}</td><td>{actual_metrics['max_drawdown']:.2%}</td><td>{actual_metrics['cost']:.2f}</td><td>{actual_metrics['terminal_value']:.2f}</td></tr><tr><td>等权/受约束参考</td><td>{base['cagr']:.2%}</td><td>{base['max_drawdown']:.2%}</td><td>{base['cost']:.2f}</td><td>{base['terminal_value']:.2f}</td></tr></table><p>参考在全部窗口可用：{'是' if result['baseline_comparable_all_windows'] else '否，有标记的现金替代，不能当完全等价比较'}；计算覆盖全部尾段：{'是' if result['evaluation_complete'] else '否，受max_folds限制'}。</p></section>
<section class="table"><h2>窗口记录</h2><table><tr><th>窗口</th><th>估计截止</th><th>校验截止</th><th>测试期间</th><th>冻结配置/无解动作</th><th>测试回撤</th><th>预算观察</th><th>费用</th><th>期末现金</th></tr>{rows}</table></section>
<section><h2>统计验证与试验记录</h2><p>本次生成候选次数 {result.get('selection_audit',{}).get('generated_candidates_across_folds','未记录')}；候选/块长终批评价次数 {result.get('selection_audit',{}).get('candidate_block_evaluations','未记录')}。这些不是独立策略试验数。没有完整跨运行失败试验与依赖记录，DSR 不可估，概率未输出；本版未实现 DSR。</p><p>p95 模拟收敛只表示条件抽样精度；p99尾部可能仍不足，模型误差与选择偏差未被消除。前一测试段可进入下一次训练，但不能影响自身已冻结配置。</p></section>
<section><h2>边界</h2><ul>{notes}</ul><p>模拟未包含未来外部现金流。真实资料、点时版本和完整历史交易制度仍未认证；不将此首版称为完整实盘验证。</p></section>
<section><a href="m2-evaluation.json">完整协议、候选与窗口结果</a> · <a href="actual-ledger.csv">连续账本</a> · <a href="baseline-ledger.csv">参考账本</a> · <a href="report-manifest.json">内容与方法清单</a></section></main></html>'''
    (root/"m2-report.html").write_text(html,encoding="utf8")
