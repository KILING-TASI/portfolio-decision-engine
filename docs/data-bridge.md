# v0.6 数据接入与留档

待审增量：`convert-lookthrough`显式转换cn-fund-lookthrough输入v0.1，保留原始字节、披露证据与证券/发行人映射。接口、已有范围、首批验收及后续风险/事件与ETF套利边界见[接入路线](lookthrough-integration-roadmap.md)。不自动切换旧数据、不将局部披露变为实时风险输入。

接续检查支持convert-lookthrough的--as-of/--historical与run的lookthrough_historical。组合截止取data.as_of（缺省收益末日），晚于截止日的披露或声明的版本可得日会在优化前拒绝。持仓期、发布日期、采集日期和可得时点分开；历史模式要求当时可得且冻结的来源版本声明，仍不认证PDF原件真实性。

输出目录均须不存在；失败不发布半份报告，会尽可能保留 failure.json。重复执行需指定新目录。verify 只读取，不联网、不改文件。

## 1. 准备已有资料

```sh
python -m portfolio_engine prepare --input bundle.json --out reports/prepared-01
python -m portfolio_engine run --returns reports/prepared-01/returns.csv --config reports/prepared-01/config.json --out reports/analysis-01
python -m portfolio_engine verify reports/analysis-01
```

bundle.json 格式：

```json
{
  "currency": "CNY", "frequency": "daily", "as_of": "2025-12-31",
  "assets": [
    {"code":"示例资产", "currency":"CNY", "source_url":"https://example.org/nav",
     "basis":"nav_with_events", "event_coverage":"declared_complete_for_window",
     "events":[{"date":"2025-12-30", "cash_per_old_unit":0.1, "source_url":"https://example.org/dividend"}],
     "history":[{"date":"2025-12-29", "nav":1}, {"date":"2025-12-30", "nav":0.9}, {"date":"2025-12-31", "nav":0.99}]
    }
  ]
}
```

以上仅演示字段，观察数不足以运行引擎。总回报指数可用 basis=total_return_index、history[].value。事件现金按事件前份额计；拆分 new_units_per_old_unit 为新/旧份额比。同日事件合并，红利假设按当日净值再投，不代表真实到账与产品分红选择。

无事件也需要显式 events=[] 及完整性声明；自动抓到的 distribution_text 不能当已核验完整事件。累计净值不直接视为复利总回报。所有资产日期必须完全相同，不取交集、不插值；币种须统一，不自动折算汇率。

可加 synthetic=true 标记人工教学输入；engine_config 包含原引擎设置，prepare 自动写入数据口径与年化因子。

## 2. 复用研究工作台档案

```sh
python -m portfolio_engine prepare --workbench --input workbench-bundle.json --events events.json --currency CNY --out reports/prepared-workbench
```

仅接受 type=research-bundle、kind=fund、historyBasis=nav-with-distributions 的基金净值行。事件文件按代码提供：

```json
{"000001":{"event_coverage":"declared_complete_for_window","events":[]}}
```

不能因为档案没有事件文本就填写“已完整核验”。适配不自动认证证券分类、分红或历史可得时点。工作台股票/ETF即时报价和未复权行情拒绝转换。

## 3. 显式在线采集

```sh
python -m portfolio_engine collect --input requests.json --online --out reports/collected-01
python -m portfolio_engine prepare --archive --input reports/collected-01/source-archive.json --events events.json --currency CNY --out reports/prepared-collected
```

requests.json：

```json
{"requests":[{"provider":"eastmoney_fund_nav","code":"000001","start":"2020-01-01","end":"2025-12-31"}]}
```

沪深价格 provider=tencent_cn_price，必须 market=sh 或 sz；每次价格窗口不超过366自然日。请求最多12项，每次响应上限16MiB、超时20秒。无任意 URL、凭据或后台刷新。基金 JavaScript 只提取 JSON，不执行脚本。

归档包含请求/实际起止、观察数、来源、证券身份、获取时间、原始响应及 SHA256。当前修订历史不能冒称当时冻结数据。逐项失败保留原因，partial 不当全部可用。prepare --archive 检查归档清单和原始响应；任一失败资产或 raw_price 均阻止总回报准备。价格可用于收盘净值对照，但不能绕过收益口径。

本版测试使用离线模拟响应，不宣称接口实时可用。数据源许可与使用条件仍需自行核对。

## 4. 频率与日历

data.frequency=daily/monthly；缺失时按间隔推断并披露。月频必须逐月连续，年化12；日频年化252。稀疏或不规则序列不会默认视为日频。月频不自动变为日频策略。

data.calendar 可提供 source_url、start、end、dates、applicability_confirmed=true。适用区间须覆盖输入，缺日或额外日期拒绝计算；日期齐备只证明与声明日历对齐，不证明价格/分红真实。日历不随网络自动更新。

## 5. 收盘偏离和持仓穿透

配置 premium_file 指向 JSON：code、price_source_url、nav_source_url、prices（date/close）、nav（date/nav）。只匹配同日，缺净值日期单列。输出 premium 为小数；不等同盘中 IOPV、可成交价差或当时已披露净值。

配置 lookthrough_file 指向 JSON：currency、as_of、root、nodes。每个 node 含 currency、source_url、report_date、published_at、holdings。基金持仓用 kind=fund、node、weight；底层持仓用 kind=stock/bond/cash/other、id、weight。递归合并底层 id，循环、深度限制、缺子基金、未披露权重留为未知；已知+未知=1。不同报告期逐路径保留；不是实时持仓，不能还原交易。底层 id 必须由用户规范化，未自动识别证券别名与发行人。

demo 自带完整教学格式。二者进入 supplemental 和 HTML，不修改收益序列，也不自动变成优化约束。

## 6. 报告留档

report-manifest.json 记录生成文件、输入原始字节、附加资料快照及全部 Python 方法摘要。run 保存 source-input.csv 和 source-config.json；prepare 保存 bundle 与事件声明；collect 保存原始响应。verify 区分内容变化和方法变化。此处摘要检查不是防篡改签名；同时替换内容与清单可绕过，不能证明外部来源真假、数值正确或页面排版合格。


## 7. 有界数据入口目录与候选旁挂（2026-10-10）

上一批观察收益去重迁移已结案，见[单一迁移说明](workbench-cashflow-integration.md)。本批只盘点现有数据入口和既有样本复用，不增加采集器、后台服务、自动更新或全市场数据。八项可审目录见 [data-entry-inventory.json](data-entry-inventory.json)，分别记录实际命令/模块、原发布者、取得渠道与接口库、身份、单位/币种/频率、各时间角色与精度、原始/解析/方法版本、覆盖/更新、权利与维护职责。目录是本仓库范围，不代表九仓统一。

| 链 | 当前实际范围 | 缺口 |
|---|---|---|
| 公告原文 | 消费专业库声明的披露节点/来源与版本，做组合截止和穿透核对 | 不负责公告/PDF原文解析或真伪认证；原文核验在专业库，不能升级为估值审计 |
| 净值+分红拆分 | 明确基金接口采集实现、离线响应测试、显式事件转换、同日再投教学对照 | 此批未实时取数；事件完整性只是输入声明，累计净值不能冒充复利总回报 |
| 行情+交易日历 | 限定沪深原始日价格采集实现、调用方日历对齐 | 实际交易所/再分发链、价格/成交量单位、发布时点/权益调整未认证；没有官方日历采集 |
| 宏观修订 | 可接受通用数值因子CSV，保留原输入摘要 | 没有宏观原发布、修订vintage与更正关系接口，不把CSV哈希叫数据发布版本 |

采集实现与接口文档不等于本批已取得真实数据。基金净值渠道是东方财富，行情渠道是腾讯；代码使用urllib，不是某外部库自动认证来源。渠道不能代替原发布者身份：接口档案没有独立核实基金管理人/交易所发布链。代码/名称匹配只能核对所声明标的，不证明份额类别、证券类别、币种、量单位或完整事件。

### 时间与版本差异

净值接口x毫秒戳转为上海日期，原戳保留在本地原始响应；归一化只到日，不把它解释成公告发布时间。retrieved_at是UTC取得时刻；published_at、effective_at、available_at或历史vintage未给出时保持未知。披露接口能保留这些声明，但截止核对是上海日期级，不能认证盘中已知信息。现金的“可用余额/到账日”属于账户会计条件，不能混同材料的历史available_at。

软件仍0.7.0；main、开发PR、旧Release和已安装包分别按实际内容判断。旧API有的仅type标识、无独立parser/method/source版本，不为了对齐伪造版本或升级旧schema。数据快照哈希、原件/接口响应哈希、规范化输入哈希和方法文件哈希分别记录；字节不变不是正式版本未更正或来源真实的证明。规则版本不承担数据修订或计算方法版本含义。

### 最小候选记录：提案而非生产统一schema

采用可选旁挂词汇：record_id/subject_id/metric_id/value/unit/currency；期间或观察时点；published/effective/acquired/available及精度；producer/provider/interface/source_url/raw_sha256/source_version/parser_version/method_version；verification/missing/conflicts/coverage/rights与专业extensions。不是必填共同标准，不强迫其他库使用相同供应商、频率、字段或状态枚举。没有无损对应时null+原因，原payload完整保留；不向旧prepare、run或消费者强塞新字段。

[候选教学旁挂](../examples/data-record-candidate-nav.json) 保留原bundle、事件声明和工作台专业扩展；未知净值单位、发布/生效/取得/可得时间、原件哈希和各版本均为null+原因。调用方币种声明仍注明为声明。input_snapshot_sha256只绑定本次教学输入，不能填成真实基金原件raw_sha256。专业模型的再投/现金分红路径、声明事件完整性和推断频率仍留在原结构/派生扩展，不覆盖原始净值事实。此旁挂仅示例和候选映射，没有新增候选记录解析器/CLI。

下载收到字节、找到原页、字段语义/主体期间核验、事件/日期覆盖与历史可得性是不同维度；原status不抹平为单一“verified”。unknown/conflict/failed不填零，不用另一口径兜底。现有再投模型在完整事件声明下采用中性未发生组件，这是模型输入约定，不可旁挂成“原文证明无现金/无拆分”。实际到账、延迟再投、税费和产品允许的分红选择不在此局部数学等价范围。

### 既有样本复用与重复入口清单

[教学源快照](../examples/data-reuse-teaching.json) 同时保留research-bundle和事件声明，两个库用同一NAV/现金分红/拆分数据。引擎既有workbench_adapter+total_return_index与工作台fund_series_tools.distributions的同日再投序列匹配，区间收益差<=1e-15；[对照回执](../examples/data-reuse-reference.json) 固定方法源码/提交和输入摘要。三组共同拒绝反例：未知事件完整性、缺事件数量、起点发生事件；引擎另明确拒绝把股票/raw-price标签转成总回报。全部是人工教学，无实时接口/原页/语义/历史可得或到账认证，也未把工作台现金分红或DCA路径说等价。

归一化适配器没有无损携带所有上游字段，教学标签与时间/来源元数据等必须保留原输入/旁挂；此次没有改变旧适配行为。engine_metadata的通用total_return标签不证明真实市场数据，跨仓对照仅覆盖明确再投算术。已发现的元数据映射缺口具体列在目录，而不是宣称全量元信息统一。

| 重复或相似入口 | 实际处理 |
|---|---|
| 原账户观察收益calculate | 上一批工作台核心已移除、旧名转发，未重新引入 |
| 基金同日再投算术 | 局部同输入对照通过；工作台还有现金分红/质量/基准等专业扩展，暂未迁移，不在数据盘点中偷删 |
| 原始NAV取得/解析 | 已有本库限定collector和工作台渠道；语义/权利/更新职责不同，本批目录登记不强制合并 |
| 披露原页解析 | 在专业库；本引擎只消费声明节点与组合关联，不能以同类名字称重复已消除 |
| 宏观/公告/日历统一底座 | 未在本库实现，本批不创建服务、不塞回工作台或规则库 |

本批结案点为目录、候选旁挂、现有适配的同教学样本复用与反例、链接/样本/打包检查和可审提交。剩余缺口包括真实原文/原始数据的跨九仓复用、语义证据、权利授权、历史vintage/更正、盘中可得、实到账、专业元信息无损映射；本批不继续叠加新采集。原件和真实账户不发布，只有人工样例进入Git，数据权利独立于原创MIT，原第三方许可保持。


已有真实响应的实际范围：本地忽略档案有两只公开基金的净值接口样本，请求2026-08-01至09-30，实际2026-08-03至09-30各42条，档案记录UTC取得时间2026-10-09T10:28:30左右。本批只核对响应字节SHA与原档案一致，没有重新取数，没有把原始净值/响应放入Git。代码级身份/数值解析与字节收到不等于基金原发布者、公告原页、事件完整性、交易日历或历史可得性认证；这些仍未验证。此范围不是真实账户、实盘绩效或全市场覆盖。
