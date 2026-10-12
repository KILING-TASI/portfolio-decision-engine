# K线形态、条件统计与CNN对照

本页记录PDE冻结v0.12研究实现。后续因子增量以独立 [factor-research](https://github.com/KILING-TASI/factor-research) 为维护入口，旧命令兼容见 [迁移说明](FACTOR_MIGRATION.md)。
本仓新增11种可解释规则：十字线、锤头、上吊线、倒锤头、流星线、看涨/看跌吞没、晨星/暮星、三白兵/三只乌鸦。规则为原创 `original-candle-rules/1`，不是对第三方网站或TA-Lib算法的复刻。

## 单仓试用

基础识别和统计只需标准库，不需要其他仓库、行情软件或PyTorch。使用本仓完整源码或wheel：

```text
python -m pip install .
portfolio-decision-engine pattern identify --input examples/cnn-teaching/patterns.json --out-dir reports/pattern-events
portfolio-decision-engine pattern study --input examples/cnn-teaching/patterns.json --out-dir reports/pattern-study
```

对照计算另装 `[cnn]`：

```text
python -m pip install ".[cnn]"
portfolio-decision-engine cnn compare --input examples/cnn-teaching/patterns.json --out-dir reports/pattern-comparison
```

也支持 `python -m portfolio_engine pattern ...`。输入沿用 [CNN时点与OHLCV契约](CNN_RESEARCH.md)，`schemaVersion=cnn-factor/1`；来源、股数、价格口径、当期股票池和历史可得时点必须明确。识别不读取未来标签，因此可以只有行情；统计收益另核，不把未知收益补零。教学文件为64个合成样本、四只虚构证券，不能证明A股效果。

每次输出新目录，保留输入、结果、HTML报告和回执；不覆盖旧结果。示例来自原创生成器 [make_patterns.py](examples/cnn-teaching/make_patterns.py)，专门含未知收益/基准、尚未可得收益及无法确认成交条件，记录日不冒称中国交易日。

本轮形态报告最多1000个合格样本，避免生成无法复查的大文件；大样本需声明拆批身份，不能把各批统计均值直接再取平均冒充全样本结果。

## 规则与前置条件

实体为 `abs(close-open)`，振幅为 `high-low`，上影线为 `high-max(open,close)`，下影线为 `min(open,close)-low`。零振幅不作为十字线，避免把一字板当犹豫信号。

`patternParameters` 可声明以下阈值，未提供字段使用版本默认值；未知参数拒绝。变更阈值属于新试验，需留档。

| 参数 | 默认值 | 含义 |
|---|---:|---|
| dojiBodyMax | 0.1 | 十字实体/振幅上限 |
| smallBodyMax | 0.3 | 小实体上限 |
| longBodyMin | 0.5 | 长实体下限 |
| shadowBodyMin | 2 | 长影线/实体下限 |
| oppositeShadowMax | 0.1 | 对侧短影线/振幅上限 |
| trendRecords | 3 | 完全早于形态的趋势窗口 |
| trendReturnMin | 0.01 | 前置收盘变化绝对阈值 |
| starPenetration | 0.5 | 晨暮星第三根进入第一根实体的比例 |

锤头等小实体要求实体比大于十字阈值，避免零实体导致影线/实体比例失真。锤头/倒锤头要求前置下跌，上吊/流星要求前置上涨。吞没要求前后实体颜色相反、第二实体严格更大且完整覆盖第一实体，另核前置趋势。

晨暮星要求第一根长实体、第二根小实体与第一根实体严格跳空、第三根反向并穿入第一根实体；没有跳空不放宽成同名信号。三白兵/乌鸦要求三个同向长实体、收盘依次推进、后两根开盘位于前一实体内、方向端短影线，并确认反向前置趋势。十字线本身无预测方向。

事件逐项给出实体/影线数据、几何条件、前置趋势、状态和命中列表。`matched` 为两者满足；`context-unknown` 为外形符合但历史不足；`context-not-matched` 为趋势不符；`not-matched` 为外形不符。完整历史窗口仍需契约规定的记录数，不自动补日期。形态可重叠，不把多个命中当成独立证据。

## 条件统计及CN成交边界

`studyHorizons` 声明最多8个唯一期限，单位为记录数。每条样本的 `outcomes` 列表提供 `horizonRecords/returnStartAt/returnEndAt/availableAt/forwardReturn/source`；没有列表时可沿用单个 `label`。时点顺序必须成立，晚于复查截止的收益列为排除，缺期限保留未知。

有基准时还需 `benchmarkReturn/benchmarkSource/benchmarkStartAt/benchmarkEndAt/benchmarkAvailableAt`，与事件收益区间一致且复查时已可得；基准超额是同区间简单收益之差，未知基准不补零。

每种形态、每个期限分别给样本ID和数量、毛收益均值/中位数、正收益比例、方向符合比例、观察极值、已知基准超额和缺口。看跌形态的方向符合比例为负收益占比；十字线方向符合比例未知。二者都不是可执行交易胜率。最差观察收益不是路径最大回撤，均值并非复利组合净值。

可选 `cnExecution` 声明 `entryTradable/exitTradable/tPlusOneSatisfied/settlementAvailable/feesKnown`（布尔或null），全为true还需 `source`。这是人工声明，不认证成交；出现false标为 `blocked-or-incomplete`，有未知标为 `unknown`。统计始终保留事件，列出各状态数量，不能事后删掉停牌、涨跌停或坏收益事件来美化结果。没有实现交易撮合、费率扣减、融券或现金到账模拟。

收益事件重叠、同一证券多次触发以及多形态重叠均可能相关；不输出显著性或独立试验概率，不按样本内胜率推荐最优形态。

## 三路线对照

`comparisonPlan=ohlcv-vs-rules-vs-geometry/1` 必须预声明；训练参数与 `split/folds` 沿用CNN契约，区间、标签清洗和可选隔离缓冲相同，测试区间不重叠。

1. 原五通道OHLCV CNN。
2. 显式形态规则：对命中方向求和后取符号；按训练集方向组拟合未来收益均值，缺组回退训练均值。不把 ±1 信号直接拿去与小数收益比较误差。
3. OHLCV加五个逐记录因果几何通道：带符号实体/振幅、上影/振幅、下影/振幅、开盘相对前收盘跳空、最近最多三条收盘变化。零振幅通道取0，这不是十字线命中；每条只用截至该条的信息。

两条CNN仅按各自验证损失选轮数，标准化只拟合各自训练集。三路线测试样本、标签期限、数据版本相同；报告并列MSE、逐截面rank IC、基线、选型记录、样本ID和模型权重，`selectedWinner=null`，不按测试结果自动择优。增强模型参数更多，因此改善不证明收益只来自形态语义；改善也可能为负。它是输入特征对照，不是已完成全套消融或因果归因。

增强模型结构为 `ohlcv-geometry-conv1d-8x8-average/1`，只用于冻结对照，旧五通道predict入口拒绝加载。原v0.11.0模型及入口继续保留。全部是回顾性研究，不证明模型历史实盘存在。

## 参考与权利

[Markpro形态目录](https://mark.hcquant.com/products.php)、[锤头说明](https://mark.hcquant.com/product-details.php?sid=24)、[统计展示](https://mark.hcquant.com/stat.php)仅作为功能设计参考。未复制其代码、图片、统计数据库或收益数字；本站未公开完整识别/交易算法，不能宣称复现它的胜率。原创规则、示例和代码MIT；PyTorch和原始数据仍按各自许可与权利范围处理。

## 本轮验证记录

2026-10-12：完整组件323项测试与146个子用例通过，形态专项22项通过。覆盖11种规则的正例、阈值边界、趋势不足、严格跳空、一字板、未来行情/标签、基准窗口、未知收益、重复期限、CN成交缺口和报告规模上限。对照攻击验证：改测试标签不会改变两条CNN权重/标准化或规则训练均值；更改未来行情不会改变较早几何通道。

v0.11.0五通道CNN权重、标准化、选型、得分和测试指标逐项未变化。基础识别/统计及CNN对照在单仓wheel、空用户/工作目录、运行时禁网环境走通。浏览器核对教学性质、成交未知/资料不全、双重比例定义和同样本误差表。

[可复现教学记录](examples/cnn-teaching/pattern-acceptance-record.json)保留环境、输入摘要、参数、命令耗时和两窗口误差。合成例的几何增强误差较低，规则未胜过CNN；不据此选择实盘方案或证明真实A股有效。记录为一次教学验收，未认证最大规模吞吐。
