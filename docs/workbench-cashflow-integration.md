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


### 最终工作台提交的验收

入口随后补充规则报告展示字段，实际源码摘要改变；先前回执只代表各自当时的代码，不能拿旧摘要认证最终入口。最终工作台提交 `32e42b41a33688a47decd2540d823ff475b19b44` 的两个 portfolio 入口重新完成同样 12 次实际调用，全部通过。[最终回执](../examples/workbench-cashflow-joint-receipt-final.json) 记录提交号、实际调用文件摘要、Git blob 摘要及每案输入摘要。每次原生响应中的 gatewaySourceSha256 都与本次冻结文件一致；Git 文件仅 CRLF/LF 换行规范化，原始摘要分别记录，不称二者相等。调用期间入口和工作台观察计算文件均未改变。前两批回执及完整输出保持原样。范围只含本引擎的观察收益与现金需求；不为其他独立引擎或规则报告展示签字，不执行交易，未合并发布。


## 第一批实际去重迁移：旧观察收益

本批范围为工作台原 `portfolio_cashflow_review.number/calculate` 与它所调用的150次二分XIRR，不新增研究能力。原计算函数搬迁至 `portfolio_engine.observed_review`，保留原上游MIT署名；报告、自然语言解释、资料找回以及公司经营/估值和基金综合判断留在工作台。模拟账本、配置、尾部风险和未来现金压力仍由本引擎负责各自显式输入方法，不能冒充真实账户复核、实际成交或到账认证。独立端不要求安装工作台。

### 版本与运行

软件版本仍是0.7.0，不为文档任意升级。main和旧Release缺少本模块；待审分支新增模块，安装版必须按实际文件及方法检查，不能只看0.7.0。输入 `workbench-observed-review-input-v1`、方法 `observed-review-workbench-bisection-v1`、输出 `workbench-observed-review-result-v1`；XIRR子方法 `workbench-bisection-xirr-v1`。数据快照、数据提供者版本、规则版本、软件版本、接口版本和计算方法不是同一项。本入口无规则版本，也不认证源数据版本。

```sh
# 从经审阅的可信源码独立运行，仅标准库；仓库src为当前目录
python -S -m portfolio_engine.observed_review /path/to/observed-review-demo.json --out /path/to/new-result
# 或明确安装经审阅wheel后运行；安装由用户执行，工作台不会自动安装
python -m pip install /path/to/reviewed/portfolio_decision_engine-0.7.0-py3-none-any.whl
python -m portfolio_engine.observed_review /path/to/input.json --out /path/to/new-result
```

模块可用 `-` 代替输入路径读stdin；stdout为版本化JSON，`result`就是旧calculate返回对象。输出新目录包含 `source-input.json`（确切输入字节）、`observed-review-result.json` 与 `report-manifest.json`。这里的标准库清单为 `observed-review-files-v1`，通过逐文件SHA256校验；不要用需要科学计算依赖的旧CLI verify套用此不同清单。清单只证明字节和方法绑定，不证明资料真实性、计算投资有效性或视觉验收。现有老冻结结果和旧输入不改写、不静默升级。

四项估值/费用/冻结/到账外围声明与原窄桥相同；旧spec放在payload中，保留所有JSON附加元数据，按旧函数原语义解释，不把未知元数据当金额或完整性证明。币种须明确三位大写字母，base/thousand/million单位保留，数值字符串允许，bool/nonfinite拒绝，名称沿用单行1至100字校验；勾稽容差仍为0.01/unit_scale及浮点误差界。计算结果金额仍为输入单位，报告显示基础单位的转换由工作台原publish负责。不换汇、不自动插值、不默认现金流完整。

### 根选择和迁移边界

新专用模块保留旧150次二分与原括区下限、上限扩展规则，非传统观察现金流不选根，旧calculated/unresolved状态完整保留。原生 `backtest.xirr` 仍是另一种对数搜索方法，原窄v1仍用它，两者不被同名替换。已观察账户流前/流后估值与回测当期收益前入金也保持不同方法。

边界实际反例（2023-01-01至2024-01-01，无外部流）：100至1.5e-7，旧观察法约-99.9999998521%，原生搜索无解；1至2e8，旧括区无法估计，原生约20263554580.0338%。专用搬迁模块与旧法完整一致，不能据此宣称原生搜索与观察法在任意CNY/base输入等价。

### 去重清单与批次收尾

| 入口/函数 | 独立端与消费者职责 | 本批状态 |
|---|---|---|
| portfolio_cashflow_review.calculate | 独立模块保存旧算术；工作台旧名字只转发result | 独立端已实现；消费者移除/转发待工作台实际提交和联调 |
| portfolio_cashflow_review.publish / start cashflow | 解释、报告、找回保持工作台；通过旧名字调用 | 消费者负责验证输出和接续 |
| account_benchmark_review | 沿用旧import取账户收益；经营/差异解释留工作台 | 消费者负责联动验证，不重复搬判断逻辑 |
| fund_dca.xirr / industry_exit_scenarios | 本批不改独立定投与退出调用路径 | 暂未迁移，保留原函数，不宣称已去重 |
| 原生回测/原窄桥 | 时点与根方法不同 | 不替代观察函数，保持原版本 |
| cash-demand 可选入口 | 透传现有未来条件账本 | 已联调；无工作台重复现金压力算法可移除 |

缺可信独立项目、入口或Python时，消费者须明确不可用并给安装/源码配置指引，不自动下载安装，不静默回原重复算法。用户明确配置 `RESEARCH_WORKBENCH_PORTFOLIO_DIR` 和 `RESEARCH_WORKBENCH_PORTFOLIO_PYTHON` 后隔离调用；具体消费者代码和默认行为在工作台自身提交，独立库不修改其工作区。

本批教学强对照绑定工作台提交21543ea9：15个完整结果对象精确相等、11个原失败消息相等，含单位/币种/字符串/名称/未知元数据/首末流/费用/非传统和根边界；另验证版本错误、stdin快照、已有目录拒绝和-I/-S标准库运行。源文件摘要和完整夹具在 [搬迁参考](../examples/observed-review-reference.json)。真实账户暂停，数据真实性、实际到账、投资有效性和新报告视觉未验收，CI或空闲状态不代表这些完成。

本批结案条件是独立端固定提交、消费者薄转发和重复函数物理移除、同输入/失败/原报告与接续测试、实际独立安装运行及许可打包检查；未通过项必须具体列明。后置数据目录/共用记录适配另开有界小批次，优先公告、净值事件、行情日历和宏观修订，不叠成全量重构或自动更新；不发布私有账户/原件，不把数据权利纳入原创MIT。当前迁移不声称九仓统一。
