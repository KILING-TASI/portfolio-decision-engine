# 引擎使用说明（v0.6）

v0.6 增加 [数据接入与留档](data-bridge.md)。旧命令保留，但输出目录必须不存在；失败保留原因，旧报告不覆盖。Windows 快捷入口自动创建唯一报告目录。

## 输入

`python -m portfolio_engine demo --fast` 生成合成示例并执行全部基础模块。
真实分析用 `run --returns 文件 --config 文件 --out 目录`。
退出码 0 表示报告生成，不表示预算通过；退出码 2 表示非法输入或 M1 不可行，预算状态必须读 JSON。

CSV 第一列 date，日期有序且唯一，其余列资产收益，1% 为 0.01。拒绝缺失、无限值、重复列和 ≤−1 的收益。不静默填补缺失，不自动进行汇率转换。

最小配置示例（仅为格式示例）：

```json
{
  "data": {"return_type": "total_return", "source": "填写真实来源和总回报口径", "currency": "CNY"},
  "train_fraction": 0.7,
  "costs": 0.0001,
  "bootstrap": {"budget": 0.25, "horizon": 252, "paths": 2000, "max_paths": 8000,
                "block_lengths": [10,20,40,60], "rebalance_every": 63, "mc_tolerance": 0.01, "strict": true}
}
```

data.return_type 必须是 total_return 或 synthetic_total_return；来源与共同币种必须声明。这是用户声明而非自动数据审计。`input_kind: "prices"` 可转换用户声明的总回报价格指数；首行作为基准价。普通未调整价格不能冒充总回报。

## 配置与账本

所有数组按资产列顺序；未知顶层配置拒绝，防止拼错参数后使用默认值。

| 参数 | 含义 |
|---|---|
| initial_value | 初始账户金额，默认 100000 |
| costs | 双边线性成交费率，标量或每资产数组；默认 0.0001 |
| min_weight/max_weight | M1 下限/上限，默认 0/1，M1 长仓满仓 |
| groups | 如 [{"indices":[0,1],"lower":0.1,"upper":0.6}]，indices 从 0 开始 |
| covariance_window | 训练段 Ledoit–Wolf 窗口，默认 500 |
| train_fraction | 冻结权重留出比例的训练部分，默认 0.7 |
| cashflows | {"日期":金额}，正入金、负赎回；日期须在 CSV 中 |
| flow_rule | target：正入金重新按目标配置；cash：保留现金 |
| rebalance | none/monthly/quarterly/yearly/threshold |
| threshold | 默认相对目标偏离 0.2，零目标使用绝对偏离 |
| periods_per_year | 日频252/月频12；与频率相冲突拒绝计算 |
| risk_free_annual | 有效年化无风险收益，默认 0；仅用于指标，账户现金收益为 0 |
| seed | 默认 42，保留在来源记录 |

每天顺序：先现金流与预先给定的配置/订单，再本行收益。研究订单不是当日收盘信号，不能用当日收益反推订单。赎回现金不足按比例变现并扣费；不可透支。初始交易费用进入首日 TWR。

XIRR 初始日默认第一行前一天，现金流用行日期记录；这是日内时点的日频近似。有限 log(1+r) 搜索区间中检查符号变化根，无解或多解明确返回；不承诺发现全部重根。

BL 使用 `black_litterman` 对象：market_weights、P、Q、Omega、sources，每个观点一个来源；可设置 tau、risk_aversion、frequency。观点频率默认daily，月频输入须明确frequency=monthly，收益与协方差同频。风险导向候选保留基础协方差，BL 单列后验预测协方差的效用候选。walk-forward 不验证 BL 观点。

## M2 预算

bootstrap 的 horizon 是模拟步数，预算属于该期限。联合抽样所有资产；模拟内重做权重漂移、费用和再平衡。rebalance_every 为固定步数，0 为买入持有，63 步不严格等于季度日历。

每组块长从 paths 自动增倍到 max_paths。p95 MC 区间按二项次序统计量，MC 标准误按模拟回撤重复抽样；误差不含历史样本与模型错误。mc_tolerance 是区间半宽容差。strict=true 用区间上端检查预算；false 用点值，但仍要求收敛。所有块长均满足才通过；按各块长中最小中位年化收益评分选择，属于训练选择。

默认训练段需覆盖完整 2015 和 2018；否则不给最终 selected，探索候选另列。其他市场可显式设置 require_china_bear_coverage=false。覆盖检查仅日期与数量，不能证明数据真实。合成数据永远降级。

候选 feasible 只表示数值条件；最终 selected 还通过覆盖规则。无解不放宽预算，误差未收敛不冒充可行。经验前沿只针对实际候选集。

模拟长度达到对应期限才输出 1/3/5 年模拟分布；历史滚动持有期单独标记，重叠窗口不独立。

## M3–M6 输入

M4：current_holdings 为各资产市值金额，可选 current_cash、new_funds、locked_indices、migration_penalty。锁定仅禁止卖出，仍允许资金稀释。三方案输出金额而非可成交份额。API plan_migration 的 expected_improvement 是用户收益改善情景，无可靠预期不生成回本期。M2 无解时迁移明确标记为比较参考。

M3：brinson 对象包含 portfolio_weights、benchmark_weights、portfolio_returns、benchmark_returns，均为期间×板块的同形数组，各期权重和为 1。使用期初权重，相容分类和基准由用户提供。factor_csv 是 date 与用户构造的多空因子日收益，日期须与收益 CSV 完全一致；报告 HAC 系数、区间、相关性与 VIF，不自动构造因子。

M6：orders_csv 包含 date 和完全相同顺序的资产列，金额买入为正/卖出为负，不是份额或权重。订单时点在本行收益前。初始配置 initial_weights 默认参考权重。A/B/C 使用同初始配置、费用和现金流。B 的新增资金留现金，C 按季度部署；财富差也包含这些明确的部署差异。缺少完整订单时拒绝可靠交易归因。毛贡献用零费反事实，毛净差含成本复利影响，不是费用简单相加；逐笔精确分解未实现。

factor_csv/orders_csv 相对配置所在目录解析。M5 以固定配置回放指定历史窗口，恢复时间从谷底到此前高点，未恢复返回 right_censored；合成例的“历史命名窗口”不代表真实股灾表现。久期凸性情景通过 stress.rate_shock API 调用。

## 评估与输出

walk_forward 可设置 min_train=500、test_steps=252；每折仅用此前数据估计 M1，并在连续账本扣除切换配置的买卖费用。它不验证 M2 筛选或执行多重检验校正。

生成 report.html、report.json、ledger.csv、transactions.csv。JSON 保存输入、文件 SHA256、随机种子、版本、假设与全部状态。

M2 状态为 ok/degraded/infeasible/unconverged/insufficient_data；整体当前固定 degraded，因尚无实盘制度适配与完整模型验证。无解时展示的参考权重不是预算解。

真实持仓、数据和密钥放 private-data/。reports/ 被忽略，避免意外上传账户结果。


## 单仓安装与最短流程验收（独立有界批次）

标准安装为 `python -m pip install .`（或经审阅wheel），不要求其他自家仓库。完整引擎需要pyproject声明的NumPy、pandas、SciPy、scikit-learn、statsmodels及其普通依赖；dev的pytest/build不是教学报告运行依赖。既有代码归属、版本与待审/发布区别见[迁移说明](workbench-cashflow-integration.md)，不因软件都叫0.7.0认定旧发布包含新模块。

本批只提供本仓待审wheel，在新目录和新venv按声明联网安装普通第三方依赖，清除作者Python/专业仓路径变量并给子进程独立HOME/缓存/临时目录。系统HOME和真实作者缓存不改；宿主仍存在其他仓库，所以这是目录/进程隔离验收，不是全新OS。源码包不含.git、reports、作者数据/缓存，非editable安装；没有复制或安装另一个自家仓库。

运行 `python -m portfolio_engine demo --fast --out NEW` 的同等模块入口并生成完整HTML/JSON/账本，校验seed42、引擎0.7.0、合成总回报输入、已知86%与未知14%守恒、字节/方法清单及本地文件链接。先前标准-m命令和新增runpy模块入口均实跑，后者在报告计算完成后检查sys.path及全部已加载模块origin，不只跑help或测试。已存在输出须拒绝且旧报告不变；指定的可选披露资料缺失须blocked；无dev包和无工作台/专业包时主报告仍能运行。

可重复验收脚本 `tests/standalone_acceptance.py --wheel WHEEL --out NEW` 只用标准库做隔离、普通依赖安装和真实CLI流程。CI新增standalone job仅checkout本仓、构建wheel、新建隔离venv运行；不安装工作台或其他专业库。结果区分程序独立通过与资料/视觉/投资验证；记录包摘要、依赖版本、命令返回码、起始和计算后模块来源及报告检查。普通软件源解析/下载失败单列为环境问题，不临时装其他自家库或恢复重复算法。

本批待审运行范围是教学最短CLI，不含联网真实取数、Windows双击入口、Skill自然语言安装发现或浏览器视觉验收。旧Release本批未运行；前次旧发布资产许可/摘要检查不冒充旧版运行验收。用户现有安装与旧Release资产不改，不合并/发布。此验收明确结案后不继续扩功能或采集。
