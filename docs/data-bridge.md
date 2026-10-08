# v0.6 数据接入与留档

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
