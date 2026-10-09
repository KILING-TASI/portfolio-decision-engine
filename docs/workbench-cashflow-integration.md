# 工作台现金入口：有界可选接入（待审）

本批沿用草稿 PR #1–#7，新增估值复核契约，保留引擎和工作台现有入口。安装包版本仍为 0.7.0；不能仅凭版本号判断是否含待审功能，需核对方法版本与源码摘要。未合并、未发布、未恢复真实账户。

## 已观察账户的同输入对照

```sh
python -m portfolio_engine workbench-observed-cashflow --input examples/workbench-observed-cashflow.json --out reports/new-observed-comparison
python -m portfolio_engine verify reports/new-observed-comparison
```

输入 `workbench-observed-cashflow-input-v1`，方法 `observed-flow-link-and-native-xirr-v1`；输出 `workbench-observed-cashflow-result-v1`。`payload` 使用工作台已有出入金前后估值输入，本批只支持明确 CNY、base 单位、完整现金流声明与至少两期严格递增日期。外围四项声明必须逐字匹配样例：流前/流后估值、费用已包含、冻结资金包含在总估值但不是可用现金、估值不保证变现到账。错误或缺失声明拒绝，不默认为零、可用或已验证。

TWR 分段用“本期流前估值 / 上期流后估值”，再链接累计收益。XIRR 从投资者视角记负投入、正取出，期初估值负流、期末估值正流，同日净额合并；实际天数除以 365.25 年化。累计 TWR 与年化 XIRR 不直接相减。仅常规、负流开始正流结束且一次符号变化的现金流尝试原生求解；非传统现金流保留未估计，不任选根。引擎原生对数利率搜索与工作台二分求解有不同范围和误差，不能推广为任意输入等价。

四组教学输入和工作台只读实际调用结果在 [冻结参考](../examples/workbench-observed-reference.json)，记录原工作台提交、`portfolio_cashflow_review.py`/`fund_dca.py` SHA256、每组输入摘要。限定比较起止日、币种/单位及六个字段：累计 TWR、年化 XIRR、净出入金、期初、期末、损益；数值绝对容差 1e-6，`null` 必须两边都是未估计，状态文案分别保留。

| 教学案例 | 范围 |
|---|---|
| 追加本金和期末取出 | 不把投入当收益，不重复期末现金流 |
| 期初有追加 | 期初估值与首日外部投入分别记，再按同日净额对照 |
| 已计费用 | 费用影响流前估值，不再扣第二次，不伪装外部出入金 |
| 非传统现金流 | 两边均不提供选定 XIRR；其他五字段仍可核对 |

## 不等价与失败例

引擎回测把外部流放在当期收益之前，工作台观察值可表示当期收益之后的外部流。100 元先涨 10% 再追加 50，得到 160；若先追加再涨则是 165。下一期涨 5%，对应 168 与 173.25。因此直接把观察分段收益和日期投入原生回测不是等价迁移，测试保留此反例。冻结资金可包含在总资产估值中，但不能因此推断可用现金；期末 XIRR 估值回收也不是实际到账证据。

美元、千单位、未知现金流覆盖、缺估值、重复日期、非有限金额、估值不勾稽、流时点/费用/冻结/到账声明冲突、未知方法均拒绝。不存在自动换汇、缩短期间、插值或交易模拟。费用已包含的声明只是输入条件，不认证账单。

## 现金需求接入

工作台可选接入现有 `cash-demand --input --out`，使用 [现金需求输入](../examples/cash-demand-demo.json) 和 [既有方法](cash-demand.md)。逐字保留账户估值日、截止日、币种、每日外部收支、冻结释放条件、预定变现日期/费用/日历到账天数、未知项及 `conditional-dated-cash-demand-v1` 方法声明。无明确到账依据的预定变现不进已解析条件现金账，完整现金预测仍为未估计。

工作台原观察收益入口没有独立的未来现金压力模型。本批现金需求比较是同输入转交引擎的完整结果一致性检查，而不是两个独立模型的相互验证；也不拿未来条件账本与历史观察收益强作等价。正常、收入中断叠加折价/延期、冻结不能释放以及未知费用/日期的案例分别保留。可选入口失败不删除主包功能，不自动安装依赖或改写历史输出。

联合入口的具体命令、源码摘要与实际结果应另存联调记录；文件内容完整性、数值对照、来源真实性、浏览器验收分别记录。本批不认证真实账户或来源，不执行交易。


## 本批实际联调记录

使用工作台本地待审 `scripts/bounded_engine_gateway.py`，方法 `bounded-native-gateway-1`，调用组合引擎提交 `b29116f`。完整入口源码 SHA256 与引擎各方法文件摘要绑定在 [联调回执](../examples/workbench-cashflow-joint-receipt.json)。工作台当时基提交不等于未提交入口源码，回执明确记录这一状态，不能仅凭提交号认证本次调用。

```sh
python scripts/bounded_engine_gateway.py portfolio-observed --project-dir /path/to/portfolio-decision-engine --engine-python /path/to/engine-python --input /path/to/workbench-observed-cashflow.json --out-dir /path/to/new-observed-output
python scripts/bounded_engine_gateway.py portfolio-cash-demand --project-dir /path/to/portfolio-decision-engine --engine-python /path/to/engine-python --input /path/to/cash-demand-input.json --out-dir /path/to/new-cash-output
```

这些是显式提供可信本地项目的可选命令；工作台不下载或安装引擎，不替换已有 cashflow 入口。项目路径、Python 路径、输入和输出均由调用方明确提供。

共 12 次实际入口调用通过：4 组观察收益，4 组现金需求（正常与两种压力、未知费用及释放条件、截止日后到账、未知收支日期），4 组失败（观察费用声明冲突、观察未知方法、未知现金流完整性、现金需求未知方法）。每次保留确切输入字节与原生响应；成功响应与引擎同输入完整对象一致，失败保持 return code 2、blocked、null 响应及原错误，不升级为成功。未知现金需求只输出已解析事件的条件账本，完整现金余额仍未估计。

联调发现工作台现金需求结果文件误写为 `cash-demand-result.json`，已修为原生实际文件 `cash-demand.json`，修正后才验收透传成功。该修正落在工作台待审 PR #6，引擎侧没有新增另一个现金压力模型。最终入口若改变，需以新源码摘要和新输出目录再次验收，历史回执保持冻结。


### 入口摘要更新后的追加复查

工作台入口增加实际源码摘要后，重新实际调用相同 12 案，另存 [第二批联调回执](../examples/workbench-cashflow-joint-receipt-v2.json)，第一批原样保留。每个原生成功或失败响应中的 gatewaySourceSha256 都与本次冻结入口源码一致，调用前后源码不变。四组观察收益还重新调用当时工作台独立观察函数，六个限定字段仍在 1e-6 容差内匹配；现金需求完整对象与失败保留检查也通过。范围仅两个 portfolio 入口，不为此次新增的 BJX 白名单或 rules 回转路径作验收声明。该入口调用时仍为待提交源码，以摘要而非基提交绑定。
