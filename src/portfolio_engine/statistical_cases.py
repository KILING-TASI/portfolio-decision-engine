"""Original offline counterexamples, not book figures, code, or market evidence."""
import numpy as np
import pandas as pd

from .bootstrap import drawdown_budget, quantile_interval
from .m2_evaluation import m2_walk_forward
from .risk import expected_shortfall, maximum_drawdown
from .validation import InputError


def tail_and_mc_case():
    returns = np.r_[np.zeros(19), -.4]
    tail = expected_shortfall(returns, .95)
    extreme = expected_shortfall(returns, np.nextafter(1., 0.))
    repeated = expected_shortfall(np.tile(returns, 100), .95)
    unsupported = False
    try:
        quantile_interval(np.arange(20), .95, .95)
    except InputError:
        unsupported = True
    # Both columns share the same observed row; their gains/losses cancel.
    a = np.tile([.02, -.02], 50)
    joint = pd.DataFrame({"a": a, "b": -a}, index=pd.bdate_range("2020-01-01", periods=len(a)))
    simulation = drawdown_budget(joint, {"balanced": [.5, .5]}, budget=.01, horizon=20,
                                 paths=100, max_paths=100, block_lengths=[5], costs=0,
                                 rebalance_every=1, mc_tolerance=.001, seed=7)
    block = simulation["candidates"]["balanced"]["blocks"][0]
    future_stress = maximum_drawdown([-.2])
    return {"case": "sparse-tail-and-conditionally-perfect-mc", "data_kind": "synthetic_counterexample_not_market_history",
            "parameters": {"tail_alpha": .95, "min_raw_tail_mass_policy": 30, "mc_paths": 100, "mc_horizon": 20, "block_length": 5, "seed": 7},
            "tail": tail, "near_one_alpha_tail": extreme, "duplicated_history_tail": repeated,
            "finite_interval_with_20_paths_rejected": unsupported,
            "conditional_simulation": simulation, "unseen_joint_stress_drawdown": future_stress,
            "acceptance": {"es_retains_worst_loss": np.isclose(extreme["es"], .4),
                "sparse_tail_labeled_insufficient": tail["tail_sample_status"] == "insufficient_data",
                "duplicates_do_not_certify_independence": repeated["effective_independent_tail_observations"] is None,
                "unsupported_interval_rejected": unsupported,
                "joint_rows_preserve_cancellation": block["p95"] == 0 and block["p95_mc_interval"] == [0., 0.],
                "conditional_convergence_not_model_accuracy": block["converged"] and future_stress > simulation["budget"],
                "p95_convergence_not_p99_support": block["p99_tail_sample_status"] == "insufficient_data"}}


def repeated_selection_case():
    rng = np.random.default_rng(19)
    repetitions, candidates, observations = 200, 64, 60
    train = rng.normal(0, .01, (repetitions, observations, candidates))
    test = rng.normal(0, .01, train.shape)
    def sr(x):
        return x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(252)
    train_sr, test_sr = sr(train), sr(test)
    winners = train_sr.argmax(axis=1)
    frozen_test = test_sr[np.arange(repetitions), winners]
    # This is deliberately contaminated: choose on the same test you report.
    contaminated = test_sr.max(axis=1)
    r = np.random.default_rng(5).normal(.0003, [.003, .009], (150, 2))
    frame = pd.DataFrame(r, index=pd.bdate_range("2020-01-01", periods=150), columns=["a", "b"])
    config = {"data": {"return_type": "synthetic_total_return", "source": "original seeded isolation case", "currency": "CNY", "frequency": "daily"},
              "require_china_bear_coverage": False, "costs": .001, "seed": 11,
              "bootstrap": {"paths": 100, "max_paths": 100, "horizon": 30, "block_lengths": [5, 10], "rebalance_every": 10, "budget": .9, "mc_tolerance": .05},
              "m2_walk_forward": {"min_train": 90, "validation_steps": 30, "test_steps": 30, "max_folds": 2}}
    original, _, _ = m2_walk_forward(frame, config)
    changed = frame.copy(); changed.iloc[90:120] = [.2, -.2]
    counterfactual, _, _ = m2_walk_forward(changed, config)
    first, mutated = original["folds"][0], counterfactual["folds"][0]
    identical_target = np.array_equal(first["target_weights"], mutated["target_weights"])
    return {"case": "repeated-winner-and-next-test-isolation", "data_kind": "synthetic_null_strategies_not_market_performance",
            "parameters": {"seed": 19, "repetitions": repetitions, "candidates_per_repetition": candidates, "training_observations": observations, "test_observations": observations, "periods_per_year": 252, "true_mean": 0},
            "mean_predeclared_candidate_train_sharpe": float(train_sr[:, 0].mean()),
            "mean_best_of_64_train_sharpe": float(train_sr.max(axis=1).mean()),
            "mean_frozen_winner_test_sharpe": float(frozen_test.mean()),
            "mean_posthoc_test_winner_sharpe": float(contaminated.mean()),
            "m2_first_fold": {k: first[k] for k in ["fit_end", "calibration_start", "calibration_end", "test_start", "target_weights", "selected", "fit_sha256", "calibration_sha256"]},
            "m2_config": config, "m2_source_series": frame.to_dict("split"),
            "next_test_mutation": {"start_row": 90, "end_row_exclusive": 120, "replacement_returns": [.2, -.2]},
            "m2_changed_test_first_fold": {k: mutated[k] for k in ["target_weights", "selected", "fit_sha256", "calibration_sha256"]},
            "local_selection_audit": original["selection_audit"],
            "acceptance": {"training_winner_inflation": train_sr.max(axis=1).mean() > train_sr[:, 0].mean() + 1,
                "frozen_test_not_training_winner_score": abs(frozen_test.mean()) < .5,
                "posthoc_test_choice_contaminates_holdout": contaminated.mean() > frozen_test.mean() + 1,
                "fit_then_independent_calibration_then_test": first["fit_end"] < first["calibration_start"] <= first["calibration_end"] < first["test_start"],
                "next_test_cannot_choose_its_own_target": identical_target and first["selected"] == mutated["selected"] and first["fit_sha256"] == mutated["fit_sha256"] and first["calibration_sha256"] == mutated["calibration_sha256"],
                "no_dsr_probability_from_local_counts": original["selection_audit"]["deflated_sharpe"]["probability"] is None}}


def statistical_cases():
    return {"schema": "statistical-counterexamples-v1", "method_version": "conditional-error-and-local-selection-v1",
            "data_kind": "original_synthetic_teaching_only", "numpy_version": np.__version__,
            "tail_mc": tail_and_mc_case(), "selection_isolation": repeated_selection_case()}


def save_statistical_cases(result, directory):
    from html import escape
    from pathlib import Path
    from .io import write_json
    root = Path(directory)
    write_json(root / "statistical-cases.json", result)
    write_json(root / "case-parameters.json", {"schema": result["schema"], "method_version": result["method_version"], "numpy_version": result["numpy_version"],
        "tail_returns": [0] * 19 + [-.4], "joint_return_rows": [[.02, -.02], [-.02, .02]],
        "tail_mc": result["tail_mc"]["parameters"], "selection": result["selection_isolation"]["parameters"],
        "null_distribution": "independent normal returns, mean zero and standard deviation .01",
        "m2_source_series": result["selection_isolation"]["m2_source_series"], "m2_config": result["selection_isolation"]["m2_config"]})
    tail = result["tail_mc"]; selection = result["selection_isolation"]
    rows = "".join(f"<tr><td>{escape(case['case'])}</td><td>{escape(name)}</td><td>{'通过' if passed else '未通过'}</td></tr>" for case in [tail, selection] for name, passed in case["acceptance"].items())
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>统计验证反例</title>
<style>body{{font-family:system-ui,'Microsoft YaHei',sans-serif;background:#f2f6f8;color:#19333e}}main{{max-width:1150px;margin:auto;padding:24px}}section{{background:white;padding:22px;border-radius:12px;margin:18px 0}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #dde5e9;text-align:left}}.badge{{background:#fff2d6;padding:14px}}a{{color:#117467}}</style><main>
<h1>两个统计验证反例</h1><p class="badge">原创合成教学数据，不是市场绩效。方法 {escape(result['method_version'])}；未实现 DSR，不输出概率。</p>
<section><h2>尾部少，不等于风险小</h2><p>20个观察，仅一次40%亏损：ES95 {tail['tail']['es']:.2%}，尾部质量 {tail['tail']['tail_mass_observations']:.2f} 个等权观察，标记样本不足。置信水平极接近1时仍保留40%最坏损失，不舍成0。</p><p>重复原样本使原始尾部计数变大，不增加新的独立历史证据。20条路径不能支持这里要求的有限双侧p95区间，已明确拒绝。</p><p>联合样本中两个资产正负抵消：100条模拟路径的p95及区间均为0，条件误差收敛；但未见过的共同下跌情景回撤20%，超过1%预算。p99只有1条路径的尾部质量。模拟误差不等于模型误差，p95收敛不代表p99可靠。</p></section>
<section><h2>重复择优使成绩膨胀</h2><p>零技能人工序列：200次教学重复，每次64个候选，训练与测试各60个观察。预定单候选平均训练 Sharpe {selection['mean_predeclared_candidate_train_sharpe']:.3f}；64中择优训练 {selection['mean_best_of_64_train_sharpe']:.3f}；冻结赢家后测试 {selection['mean_frozen_winner_test_sharpe']:.3f}；若事后在测试再选赢家则为 {selection['mean_posthoc_test_winner_sharpe']:.3f}，后者是故意污染的演示。</p><p>实际 M2 再验收：只改变下一测试段，首折权重、选择及拟合/校验输入摘要不变。后续窗口允许使用已经发生的前段数据，但整次研究重复运行/参数试错仍可能污染“样本外”。局部评价次数不等于独立策略试验数，跨运行试验史未知，DSR不可估。</p></section>
<section><h2>验收记录</h2><table><tr><th>案例</th><th>检查</th><th>结果</th></tr>{rows}</table></section>
<section><a href="statistical-cases.json">完整案例结果</a> · <a href="case-parameters.json">冻结参数与 M2 人工输入</a> · <a href="report-manifest.json">方法和文件摘要</a><p>借鉴风险、模拟及绩效展示原则，不宣称 GIPS 合规。未知资产风险不作零处理；真实数据、试验注册、完整费用制度及模型误差校准尚未验证。</p></section></main></html>'''
    (root / "statistical-report.html").write_text(html, encoding="utf-8")
