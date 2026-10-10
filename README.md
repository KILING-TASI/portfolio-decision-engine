# 组合决策引擎 · Portfolio Decision Engine

[![Original code: MIT](https://img.shields.io/badge/original_code-MIT-green.svg)](LICENSE)

用 ETF、基金和跨资产收益序列比较配置的收益与回撤取舍，检查模型回撤预算，并生成可核对的离线报告与账本。

[实际教学预览](docs/report-previews.md)：本例最小方差相对等权回撤减少 **4.54 个百分点**，年化收益也减少 **4.88 个百分点**。这是固定种子的合成数据，不是市场绩效或长期优势。

## 两条命令看结果

需要 Python 3.10+，在已下载的仓库目录执行（安装会获取 NumPy、pandas、SciPy、scikit-learn、statsmodels 及其依赖）：

```sh
python -m pip install -e .
python -m portfolio_engine demo --fast --out reports/demo
```

打开 `reports/demo/report.html`，可见配置取舍、预算、迁移、风险及未知穿透；同时生成 JSON、账本、输入快照和完整性清单。**输出目录必须不存在，重复运行请换目录名，旧报告不覆盖。** Windows 也可双击 `Run-Demo.cmd` 自动准备环境并打开报告。

`--fast` 用于快速教学演示；去掉后采用 2000 起步、最多 8000 条模拟路径与四组块长。完整 demo 不等于真实市场验证。

[![实际报告：配置收益与回撤取舍，合成教学数据](docs/previews/allocation.png)](docs/report-previews.md)

[配置 HTML 节选](docs/previews/allocation.html) · [M2 训练与测试截图](docs/previews/m2-windows.png) · [未知穿透截图](docs/previews/lookthrough.png) · [样本与复现说明](docs/report-previews.md)

截图来自实际生成、已检查的教学 HTML；标明引擎 v0.7.0、2026-10-09 与固定种子。配置留出比较是已发布能力；完整 M2 滚动展示来自待审 #2，不能混为公开版或实盘验证。

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

底座支持线性双边费用、现金流、TWR/XIRR、日历/阈值再平衡、预先给定的研究订单。v0.6 新增 ETF 同日收盘偏离观察、披露持仓递归穿透和未知权重。**未适配真实成交、盘中 QDII IOPV、基金确认、涨跌停及税率日历。**

## v0.6 数据接入与留档

- `prepare`：将总回报指数或有明确完整事件声明的净值转换为收益；拒绝未复权价格冒充总回报。
- `prepare --workbench`：适配 research-workbench 的基金 research-bundle；需要独立分红/拆分声明。
- `collect --online`：有限范围归档天天基金净值或腾讯沪深未复权价格，保留原始响应、证券身份、时间和摘要；成功取数不等于数据齐全。
- `prepare --archive`：校验采集档案和原始响应摘要后准备基金总回报输入。
- `verify`：核对报告文件、输入快照和计算方法是否变化，不认证来源真实性或视觉效果。
- 日/月频与 252/12 年化因子一致性检查；可提供明确适用的日历检查缺日，禁止自动填值。

具体字段与完整命令链见 [数据接入指南](docs/data-bridge.md)。代码参考与上游许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

报告整体为 degraded，避免将简化模型当实盘工具。M2 无解时比较参考不会冒充预算解。M1 连续账本 walk-forward 与冻结权重留出比较分别提供，不能称为已验证 M2 筛选。自举误差仅是条件蒙特卡洛误差。

## 测试与构建

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

首版直接使用 NumPy、pandas、SciPy、scikit-learn、statsmodels，未集成 skfolio/Riskfolio/arch。平稳自举在仓库内实现并测试，配置/迁移用 SciPy，收缩用 scikit-learn。验证环境见 [requirements-tested.txt](requirements-tested.txt)。

## 验证范围

v0.7.0 基线为 65 项测试；待审 #1 为 86 项、#2 为 94 项，本分支为 102 项。测试涵盖失败状态、费用和连续账本、前置窗口因果性及限定兼容对照。它们不构成投资效果验证。

有限真实取数取得两只基金各 42 个净值观察，但缺少完整分红/拆分声明，准备环节正确拒绝将其用作总回报。尚未完成真实数据的正向 M2 验证。详见[验收记录](docs/m2-walk-forward.md)。

## 阅读入口

- [声明账户敞口与现金占用](docs/account-exposure.md)：待审增量，普通债/转债与未知分开，支持排序、筛选及情景另存。

- [披露资料接入路线与验收](docs/lookthrough-integration-roadmap.md)：v0.7 基础、待审 cn-fund-lookthrough 输入转换、真实资料与 M2 样本外验证优先级。
- [M2完整滚动验证首版](docs/m2-walk-forward.md)：待审独立批次；每折重新生成候选、预算筛选并冻结，不将M1滚动比较冒充M2。

- [工作台职责与版本契约](docs/workbench-contracts.md)：费用、现金流、时间、单位和不等价边界。
- [完整设计方案 v0.4](docs/design-v0.4.md)：数据、回测、M1–M7、输出契约、验收和路线图。
- [开源组件与选型](docs/open-source-components.md)：可复用能力、边界和官方来源。
- [修订记录](CHANGELOG.md)：对 v0.2 方案与 v0.3 补丁的纠错与合并。

## 建设原则

默认采用风险导向配置；公平比较等权基准；显式记录成本、现金流、数据缺口和估计误差；无解明确报告；区分历史结果、模型模拟与用户观点。

v0.4 文档是目标设计，不代表其中全部能力已经实现。首版的实际范围以上表和使用说明为准。

原创代码及有权授权的原创说明采用 [MIT](LICENSE)。第三方代码保留原许可；公告、研报、行情、字体及其他资料不随根 MIT 授权。详见 [许可范围](docs/license-scope.md) 和 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 免责声明

本项目仅供学习与研究，不构成投资建议或交易指令，不保证收益或结果准确性。请在使用前阅读[免责声明与使用边界](DISCLAIMER.md)，并结合本次数据来源、假设与缺口独立判断。代码许可不包含第三方数据使用授权。

## 发布与待审状态

公开发行仍为 **v0.7.0**。以下增量以依赖顺序分批待审，尚未合并或发行：

1. [披露适配与时间检查 PR #1](https://github.com/KILING-TASI/portfolio-decision-engine/pull/1)。
2. [完整 M2 滚动验证 PR #2](https://github.com/KILING-TASI/portfolio-decision-engine/pull/2)，依赖 #1。
3. [工作台限定兼容及教学预览 PR #3](https://github.com/KILING-TASI/portfolio-decision-engine/pull/3)，依赖 #2；见[兼容边界](docs/workbench-contracts.md)。

本文能力表以 v0.7.0 为准。待审分支已有完整 M2 滚动实现，不代表公开版已提供。


许可收尾是依赖 #3 的独立待审批次；公开 v0.7.0 的历史发行包不因本次分支修改而重新发布。
