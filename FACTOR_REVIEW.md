# 因子进入组合前的条件审查

先核对因子、持仓与资金条件，再解释能否继续评估组合应用。研究毛价差、声明账户收益和条件风险模拟分开展示。基础功能可单独安装，无需其他仓库或作者缓存。

## 最短流程

在完整源码目录安装并运行：

```console
python -m pip install .
portfolio-decision-engine factor exposure --input examples/factor-review/exposure.json --out-dir reports/factor-exposure
```

打开输出目录的 report.html。教学例子有70%持仓提供因子值、30%缺值：已知加权贡献1.4，已知部分均值2，未知权重0.3，完整暴露保持未知。数据为原创合成，不能当真实研究。

所有动作格式为 `portfolio-decision-engine factor 动作 --input 底稿.json --out-dir 新目录`，也支持 `python -m portfolio_engine factor ...`。旧入口 `python -m portfolio_engine.factor_research panel/trials` 继续可用；原有底稿和结果不变。

每次使用新目录。成功生成冻结输入、JSON结果、HTML和文件摘要；摘要不认证原文。成功退出0，资料无效、输出冲突或缺必要组件退出2，不覆盖旧结果或自动安装。

## 入口与依赖

| 动作 | 回答什么 | 依赖 |
|---|---|---|
| panel | 横截面IC、分层毛价差 | 标准库，旧输入兼容 |
| trials | 成功、失败、选型留档 | 标准库，旧输入兼容 |
| series | 毛价差的收益窗口与研究分层权重 | 标准库 |
| exposure | 已知贡献、已知均值和未知权重 | 标准库 |
| cost | 明确持仓、成交金额下的毛净收益和成本敏感性 | 标准库 |
| cashfit | 新增调仓资金需求与既有现金事件的冲突 | 标准库 |
| decay | 不同声明持期的样本表现 | 标准库 |
| stability | IC正值占比、符号变化和连续非正记录 | 标准库 |
| budget | 净收益桥接导出；按需计算条件回撤预算 | 导出标准库；compute=true需analysis |
| multi | 标准化、中性化、顺序正交、共线性和声明权重合成 | analysis |

完整分析安装 `python -m pip install ".[analysis]"`。基础因子、暴露、现金和成本无需科学计算包。安装CLI与在助手中注册完整仓库Skill是两项操作。

## 输入版本

新动作要求 `schemaVersion="factor-review/2"`、factorId、factorVersion、factorDefinition、factorSource、含时区的asOf。参数可放入parameters，完整输入摘要绑定所有字段。字段是声明，不证明数据真实。

旧panel/trials按原契约继续使用，不为补字段修改冻结结果。新schema的panel要求完整定义并随结果保存。定义、数据或预处理变化应更新版本，另存底稿。逐动作完整输入见[原创教学输入](examples/factor-review)。

## 收益窗口与成交会计

series沿用panel行结构和时点校验，输出毛价差、窗口、当时已可得资料、组内等权方案及重叠状态。并列因子同组；空组不补0。研究权重不是可执行订单。

毛价差没有账户资金分母或融券条件，不能直接连乘净值；账户收益、累计收益及最大回撤保持未知。cost另用完整账户底稿核算，结果不自动证明复现了分层策略。

account字段：

- mode为long-only-fixed-notional，currency明确，cashReturn=0、externalFlows=[]。
- settlementMode须为same-start-tradable-proceeds并提供settlementSource，明确卖出资金可用于同一期初交易；缺结算假设拒绝计算，不把待到账款作可用现金。
- initialCash为实际可用现金，不含冻结或待到账资金；initialHoldings为证券到金额的映射。
- costBps为声明的单边总费率；未声明则净收益未知。costBpsRange可选，用于敏感性比较。
- periods严格连续且不重叠，每期含startAt/endAt/availableAt/source、assetReturns和trades。
- trades含security、正买负卖的固定notional、等于期初的tradeAt、availableAt/source和canTrade。

账本先买卖、扣费用，再按证券总收益让持仓自然漂移。单边费率乘两侧绝对成交额，费用只扣一次；初次建仓和退出同样处理。毛净路径使用相同成交金额，差异通过现金和费用体现，不自动重算权重。

教学手算：A50+现金50，卖A20买B20，单边10bps，费用40×0.001=0.04。首期期末106.96，第二期期末103.66，净累计收益3.66%。这是会计核对，不是策略绩效。

卖出超持仓、现金不足、窗口空档、期中交易或外部现金流拒绝本账本计算，应改用适用的完整回测。停牌、涨跌停或交易条件未知时不生成完整收益；canTrade来自声明，程序不认证实际可成交。当前不支持空头/杠杆，未知融券条件不能产生可执行多空收益。缺持仓收益或费用不填0。

未建模期中交易、税率变化、滑点和自动权重再平衡；声明费率若未涵盖相关损耗，计算仍不等于完整执行成本。

## 暴露与覆盖

exposure仅支持weightBasis=long-only-account-equity。持仓kind明确security/cash，含现金权重合计1，负权重或杠杆不静默归一。另声明snapshotAt和factorScale。

factorValues逐证券保存因子ID/版本/尺度、factor、valueAt、availableAt和source。资料在快照前可得，不用事后披露补历史。

knownWeightedContribution以全账户权重加权；knownNormalizedExposure只在已知证券部分归一；unknownWeight/unknownSecurities/cashWeight分列。现金不填因子值0。completeSecurityExposure仅在证券覆盖完整时计算。

benchmark须有相同时点、权重和因子口径。percentile还需referenceUniverse的定义、版本、成员和一致尺度，并且证券暴露完整。它是账户证券部分均值相对参考因子值的中秩百分位，不是风险百分位；缺条件返回null。

## 现金、持期和稳定性

cashfit接收完整cashDemand（既有cash-demand-input-v1），复用冻结、到账、卖出和压力情景处理。rebalanceCashNeeds只加入尚未计入底稿的新增净流出，保留economicEventId防重复。scope明确additional_cash_outflow_not_in_baseline；卖出到账仍通过原planned_liquidations处理，不能再算收入。

计划声明金额、日期、来源、availableAt及canTrade。资料齐全且无冲突才返回空冲突列表；未知金额、日期、结算或成交条件保持未知。推迟、缩放、放弃各列待补条件；本动作不自动计算替代方案代价，也不编造机会成本、最优解或延期天数。

decay的horizons与panels一一对应，声明calendar-days或declared-trading-days。自然日窗口核对天数；交易日须提供calendarSource，程序不认证其完整性。缺持期不插值。非正价差是样本观察，不叫永久失效或“与0不可辨”。signalDates和排除记录显示不同持期的覆盖差异。

stability的records含at/availableAt/group/IC。缺值及分组间断打断连续段；零值打断符号翻转但计入非正记录。长度按记录数，不称交易天数。cumulativeICPathFall是累计IC点的回落，不是账户回撤。minimumObservations最少3，是展示政策，不证明统计有效性。

## 多因子与回撤预算

multi明确每个因子定义、合成权重、快照与逐证券值；缺值完整行排除并列覆盖。neutralize为none或industry-log-market-cap，后一种需industry/marketCap/controlsEvidence。按当前快照均值和总体标准差标准化，使用带截距的行业哑变量及对数市值回归中性化。

orthogonalize=true按因子定义列表顺序处理，顺序会影响分数。合成权重绝对值合计1，由底稿声明，不自动选型。样本、控制矩阵或因子矩阵秩不足不输出分数；VIF>10仅提示degraded，不证明因子应淘汰或采用。

budget接收与cost相同的完整账户底稿。compute=false仅导出；compute=true调用现有drawdown_budget，budgetParameters明确预算、步数、路径、块长度、种子、精度和严格模式。净路径不完整时停止。

模拟将账户作为已投入资金的净收益路径，费率为0避免重复扣费；不重新选股或生成因子订单。区间反映条件重采样与蒙特卡洛精度，不是真实未来概率。periods是声明的每年记录步数，不自动核为交易日；入口最多20000路径、3660步和10档块长度。

回归归因保留p_values/t_values/confidence_intervals。statistical_scope说明OLS/HAC、匹配样本、参数零假设与选型限制。p值不是盈利概率，HAC不认证数据或消除选型偏差。

## 验收和许可

覆盖费用手算、初建退出、自然漂移、未知暴露、缺费用/收益、前视、并列空组、重叠窗口、现金不足、成交未知、重复经济事件、缺持期、矩阵秩及可选依赖失败；旧panel/trials用冻结摘要验证结果兼容。

基础入口在无科学计算依赖、无其他仓库、空用户目录及阻断网络调用的环境验证；多因子和预算另做analysis环境验证。有限测试不认证全市场、全部日历或未来收益。

本轮按职责在仓内拆模块，不按300行机械拆仓。原创代码MIT，第三方许可及公告、研报、数据权利仍分别处理。

## 本版验证记录

2026-10-12，Windows / Python 3.12.10：全仓280项测试、115项子用例通过。因子专项68项测试（含旧8项及新增60项）通过；旧panel/trials结果摘要未变。七份基础报告完成桌面浏览器展示核对，预算页的完整结果可展开，未发现横向溢出。

复现命令：

```console
python -m pip install ".[dev]"
python -m pytest -q
python -m build
python tests/factor_cold_acceptance.py --wheel dist/portfolio_decision_engine-0.10.0-py3-none-any.whl --out reports/cold-factor
```

最后一项在新目录创建只装本仓wheel的环境，通过本包内置资源运行七个基础动作、验证无分析依赖与其他仓库、缺analysis提示及旧输出保留。安装使用--no-index/--no-deps，基础动作运行时阻断网络。命令耗时记录在该目录acceptance.json，属于本机教学样本记录，不代表性能上限。

另在只装本仓及analysis的隔离环境运行15只原创教学证券的多因子样本、25条账户收益的条件预算（200路径、10步、块长2、种子42）。旧完整教学及中国现金情景也验收通过。跨平台检查由GitHub Actions继续运行，实际状态以本次提交的检查结果为准。
