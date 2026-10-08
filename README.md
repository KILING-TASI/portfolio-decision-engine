# 组合决策引擎 · Portfolio Decision Engine

以回撤预算为中心的组合研究与决策工具设计，适用于 ETF、基金和跨资产账户。

**当前状态：v0.5.0 可安装、可运行的研究引擎。** 输入 CSV 与配置，输出离线 HTML、JSON、账户账本和模拟交易。M1–M7 已有基础实现；实盘制度与自动国内取数尚未实现。本仓库不执行交易，也不承诺未来收益或最大亏损。

## 立即运行

需要 Python 3.10 或以上，在仓库目录执行：

```sh
python -m pip install -e .
python -m portfolio_engine demo --fast --out reports/demo
```

打开 `reports/demo/report.html`。Windows 可双击 `Run-Demo.cmd`，自动创建虚拟环境、安装并打开快速报告。首次运行需要网络和已安装的 Python。

示例是固定随机种子生成的**合成数据，不是市场历史**。去掉 `--fast` 使用 2000 起步、最多 8000 条路径与四组块长。

自己的数据：

```sh
python -m portfolio_engine run --returns your_returns.csv --config your_config.json --out reports/my-portfolio
```

CSV 第一列是 date，其余列是资产日收益，1% 写 0.01。配置格式、数据口径及失败状态见 [使用说明](docs/usage.md)，完整合成输入见 [examples](examples)。配置数组顺序须与 CSV 资产列一致。

## 当前能力与边界

| 模块 | 已实现 | 尚未实现 |
|---|---|---|
| M1 | Ledoit–Wolf、等权/受约束参考、GMV、ERC、最大分散、显式观点 BL 效用、资产/组别约束 | 常数相关目标、整数约束 |
| M2 | 联合平稳自举、路径内费用与再平衡、p95/p99、MC 区间/标准误、块长敏感性、无解拒绝、候选经验前沿 | 完整 M2 筛选的 walk-forward、多重选择检验、制度联合抽样 |
| M3 | Brinson–Fachler、Cariño、多期对账、输入因子 HAC/VIF | 因子自动构建、Frongello、风格漂移告警 |
| M4 | 金额 LP、现金守恒、新增资金、三方案、锁定不可卖、情景回本期 API | 整数份额、最低佣金、非线性冲击、确认状态 |
| M5 | 历史固定配置回放、恢复时间与删失、久期/凸性情景 API | 通胀/信用联合情景、代理映射 |
| M6 | 完整订单输入的 A/B/C、净财富差、全交易毛净贡献与成本复利拖累 | 逐笔精确择时/换仓分解 |
| M7 | MDD、ES/VaR、尾部样本、Sharpe 分块区间、集中度、负风险贡献边界、CF API、历史持有期分布 | Student-t、自动危机相关性、统计校准置信等级 |

底座支持线性双边费用、现金流、TWR/XIRR、日历/阈值再平衡、预先给定的研究订单。**未适配真实成交、QDII 溢价、基金确认、涨跌停及税率日历；CSV 须预先统一币种与总回报口径。**

报告整体为 degraded，避免将简化模型当实盘工具。M2 无解时比较参考不会冒充预算解。M1 连续账本 walk-forward 与冻结权重留出比较分别提供，不能称为已验证 M2 筛选。自举误差仅是条件蒙特卡洛误差。

## 测试与构建

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

首版直接使用 NumPy、pandas、SciPy、scikit-learn、statsmodels，未集成 skfolio/Riskfolio/arch。平稳自举在仓库内实现并测试，配置/迁移用 SciPy，收缩用 scikit-learn。验证环境见 [requirements-tested.txt](requirements-tested.txt)。

## 阅读入口

- [完整设计方案 v0.4](docs/design-v0.4.md)：数据、回测、M1–M7、输出契约、验收和路线图。
- [开源组件与选型](docs/open-source-components.md)：可复用能力、边界和官方来源。
- [修订记录](CHANGELOG.md)：对 v0.2 方案与 v0.3 补丁的纠错与合并。

## 模块

| 模块 | 回答的问题 |
|---|---|
| M1 配置求解器 | 资金怎样分配？ |
| M2 回撤预算器 | 哪些候选在指定模型和期限下满足风险预算？ |
| M3 持仓归因 | 相对基准的收益来自配置、选择还是因子暴露？ |
| M4 迁移规划 | 当前持仓怎样转向目标？ |
| M5 压力测试 | 历史冲击和合成情景下会怎样？ |
| M6 交易归因 | 实际调仓相对持有与机械再平衡贡献多少？ |
| M7 风险度量 | 当前承担什么风险，估计有多可靠？ |

## 建设原则

默认采用风险导向配置；公平比较等权基准；显式记录成本、现金流、数据缺口和估计误差；无解明确报告；区分历史结果、模型模拟与用户观点。

v0.4 文档是目标设计，不代表其中全部能力已经实现。首版的实际范围以上表和使用说明为准。

文档依据用户提供的两份设计材料修订。仓库未选择开源许可证；第三方组件及其许可证见选型文档，接入时须单独核验。
