# 开源组件选型与来源

核对日期：2026-10-09。下表是 v0.4 的候选选型，不代表所有项目已集成。v0.5 实际采用 NumPy、pandas、SciPy、scikit-learn 和 statsmodels，并在 requirements-tested.txt 所列环境通过测试与合成示例；未接入 skfolio/Riskfolio/arch。其余候选尚未验证依赖兼容性。

| 项目 | 设计用途 | 边界 |
|---|---|---|
| [skfolio](https://github.com/skfolio/skfolio) | M1 主优化库候选；风险预算、最大分散、BL、约束、模型验证 | 优化器结果须接入账户账本；不自动实现本方案 M2 预算流程 |
| [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | 优化替代或交叉核验；CVaR/CDaR、风险贡献 | 复利/非复利回撤须逐项确认；库的回撤优化不等于再平衡路径自举 p95 |
| [arch](https://github.com/bashtage/arch) | 联合收益平稳自举与块长选择 | 自动块长并非专门为 MDD 分位最优；仍须做敏感性 |
| [bt](https://github.com/pmorissette/bt) | 再平衡与多路径回测底座候选 | 中国市场规则、基金确认与现金流口径须适配验收 |
| [cvxportfolio](https://github.com/cvxgrp/cvxportfolio) | 多期调仓、成本与约束研究 | 迁移的锁定、整数份额及真实申赎状态仍须建模 |
| [PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) | BL/协方差目标交叉核验 | 是优化组件，不是完整账户回测系统 |
| [PortfolioAttribution](https://github.com/R-Finance/PortfolioAttribution) | Brinson 与多期链接参考 | R 项目；移植需核对许可证与数值验收 |
| [AKShare](https://github.com/akfamily/akshare) | 国内取数入口候选 | 不保证接口可用性、数据许可或完整清盘/历史成分覆盖 |
| [statsmodels](https://github.com/statsmodels/statsmodels) | HAC 回归、VIF、自相关诊断 | 显著性不能证明因果或投资能力 |

建议 P0 只选一个优化库和一个回测底座；P1 加 arch，按需引入其余组件。通过验收后锁定依赖版本、求解器版本与环境文件。不要把所有库并行作为核心依赖。

## 官方参考

- [skfolio 最大分散度接口](https://skfolio.org/generated/skfolio.optimization.MaximumDiversification.html)：目标函数、成本与约束。
- [PyPortfolioOpt 风险模型](https://pyportfolioopt.readthedocs.io/en/latest/RiskModels.html)：constant-variance、single-factor 与 constant-correlation 是不同收缩目标。
- [arch 自举示例](https://arch.readthedocs.io/en/stable/bootstrap/bootstrap_examples.html)：StationaryBootstrap、随机种子、Sharpe 区间与 optimal_block_length。
- [cvxportfolio 成本模型](https://www.cvxportfolio.com/en/stable/costs.html)：优化与模拟成本定义。
- [statsmodels VIF](https://www.statsmodels.org/stable/generated/statsmodels.stats.outliers_influence.variance_inflation_factor.html)：共线性诊断。
- [PortfolioAttribution 源码目录](https://github.com/R-Finance/PortfolioAttribution/tree/master/R)：归因与多期链接实现参考。

## 接入前核对

逐项记录组件许可证、版本、求解器许可、支持平台及数据源使用条件。选型名单不代表已集成；已参考/适配的工作台、教学夹具及实际依赖另见 THIRD_PARTY_NOTICES.md。Git 跟踪范围不包含 API 密钥、个人持仓或真实接口归档。
