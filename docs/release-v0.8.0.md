# 组合决策引擎 v0.8.0 发布说明

状态：已于 2026-10-10 发布 [v0.8.0](https://github.com/KILING-TASI/portfolio-decision-engine/releases/tag/v0.8.0)，来源提交 `84afe336ac521bf35d39d91428783d7a64f87418`。发布页提供 wheel、sdist、干净源码 ZIP 及 SHA256SUMS.txt。

本版将当前源码中的新增能力打包：基金披露转换和未知敞口、完整 M2 滚动预算检验、尾部与分位区间边界修复、账户可用与冻结资金、按日期的现金需求情景、工作台观察收益计算迁移，以及数据来源目录和七组教学实例。

安装需要 Python 3.10 以上，以及 NumPy、pandas、SciPy、scikit-learn、statsmodels 的普通依赖。无需安装 research-workbench 或其他自家仓库，也不需要 dev 依赖。引擎是独立 CLI，仓内没有 SKILL.md，不作为可直接发现的 Skill。

下载 wheel 后执行：

```sh
python -m pip install portfolio_decision_engine-0.8.0-py3-none-any.whl
python -m portfolio_engine demo --fast --out reports/demo-01
```

打开输出目录中的 report.html。已有目录不会覆盖，重跑请换新名字。干净源码 ZIP 与 sdist 另附文档、许可和 examples；解压后执行 `python -m pip install .`。源码中的 `examples/run_scenarios.py` 可以生成七组情景索引。演示使用合成教学数据，运行离线；安装普通依赖需要联网。

本版不执行交易，不保证收益，也不确认未来成交或到账。事件、披露或费用依据不完整时保留未知。真实输入仍有完整事件和历史可得时间缺口；通过程序检查不代表投资有效或来源认证。定投与行业退出的后续迁移未实现。

软件版本升级为 0.8.0，既有接口与计算方法版本保持。旧 v0.7.0 tag、资产、截图及历史报告原样保留。未完成专项验收的四文件 CLI 易用性草稿已私有保存，不包含在此候选中。机器标准输出与计算算法不因本次发行准备而变化。

原创代码采用 MIT；第三方许可和数据权利分别适用，详见 LICENSE、THIRD_PARTY_NOTICES.md 与 docs/license-scope.md。公共资产只含代码、公开文档与教学样例，不含真实账户、原始档案或本地报告。
