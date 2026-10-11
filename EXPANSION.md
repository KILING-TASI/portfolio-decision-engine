# 本轮研究补强

因子横截面与研究试验留档归属本仓，保持单仓独立运行。新入口：`python -m portfolio_engine.factor_research`；动作：`panel/trials`。各动作均用 `--input 完整底稿.json --out-dir 新目录`。不会自动联网、覆盖历史或认证原文。

先安装本仓，再运行 `--help`。源码未安装时，脚本仓用 `python scripts/脚本名.py`；组合仓用本仓安装后的 `python -m`。教学输入在 `examples/expansion-teaching`（如有）；教学网址、摘要和数值不能当成真实公告来源。

每次保存输入、结果、HTML和摘要记录。成功退出0；缺资料/口径不一致/重复输出退出2。先读报告结论和范围，再展开完整结果。使用范围以本仓说明和输入要求为准，不代表正式审计、合规审批、实时执行、TA或CRM就绪。

## 因子条件审查（v0.10.0）

统一入口 `portfolio-decision-engine factor` 新增 series/exposure/cost/cashfit/decay/stability/budget/multi。旧 panel/trials 底稿和结果保持兼容。基础计算标准库；多因子与预算模型按需使用 analysis。完整输入、示例和已知限制见 [FACTOR_REVIEW.md](FACTOR_REVIEW.md)。不将毛价差当账户净值，不用未知现金作无冲突，也不根据点估计认证因子有效。
