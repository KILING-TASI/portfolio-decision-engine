# 统一格式覆盖范围与版本

共同格式首先统一请求、身份、指标、单位、范围、资料时间、来源版本、未知与失败语义，保留各源适配。不是把所有数据都改成基金净值，更不是强制安装其他作者仓库。

|资料|格式|独立入口|本轮范围|
|---|---|---|---|
|基金单位净值|cn-research-collection/1.0|cn-data-adapters collect/normalize/replay|东方财富一个渠道；工作台与组合原生档案转换|
|宏观、价格或财务的显式观察表|cn-research-observations/1.0|python -m cn_data_adapters.tables normalize|本地CSV明确列映射和固定元数据；不猜单位、季度、累计或取得时点|
|规则/监管事件证据|cn-market-rules.rule-handoff/1.0及1.1|规则库已有common_interface|保持既有信封；没有另造可互换的监管事件契约|
|引擎输出归档|explicit-research-review/1.0|工作台research_review archive-index|嵌入输入/结果及版本摘要；不同结果并列保存|

```console
python -m cn_data_adapters.tables normalize --input examples/tables-teaching.json --out-dir reports/table-1
```

净值单位固定声明CNY/份；普通观察表保留所填单位，不把percent与decimal-ratio、元与亿元隐式混用。观察、发布、历史可得、原取得与重放时点分开。未知可得性不补成发布时间；同一冻结字节才要求摘要一致，线上刷新可能变。

通用表的原始CSV以UTF-8文本内嵌input.json保存，rawSourceSha256仅对应CSV文本字节，不是假称保存了源站原始HTTP字节。如需HTTP原件，用各源采集留档。文件摘要不是来源签名、权利授权或数据真实性认证。

独立合同校验：`cn-research-contracts validate-table --input 标准观察表.json`。从转换结果result.json提取snapshot对象作为标准表，不把整个报告当成表格式。规则信封另按原入口验证。没有宣称全部宏观/微观源已逐个迁移完成。
