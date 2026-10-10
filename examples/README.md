# 合成示例

所有收益、因子、账户和订单均为固定种子生成的人工示例，不能当市场业绩。

```sh
python -m portfolio_engine run --returns examples/returns.csv --config examples/config.json --out reports/example
```

配置中的 factor_csv 与 orders_csv 相对本目录解析。更改资产顺序时同步更改各数组。真实输入不要保存到本目录或提交 Git。

v0.6 的 bundle.json 是同一合成收益转换的总回报指数，用于验证准备与报告流程：

```sh
python -m portfolio_engine prepare --input examples/bundle.json --out reports/prepared-example
python -m portfolio_engine run --returns reports/prepared-example/returns.csv --config reports/prepared-example/config.json --out reports/prepared-analysis
python -m portfolio_engine verify reports/prepared-analysis
```

premium.json 和 lookthrough.json 也是教学输入。collection-request.json 是在线请求格式示例，无教学行情附带；运行 collect 须显式 --online，不代表来源当前可用。

待审cn-lookthrough-demo.json改编自cn-fund-lookthrough固定版本的教学输入，不是真实披露。运行`convert-lookthrough --input examples/cn-lookthrough-demo.json --out reports/cn-converted`可生成显式原生输入；出处与许可见THIRD_PARTY_NOTICES.md。

workbench-buy-hold.json 是人工总回报指数示例；reference 文件来自固定工作台计算函数的同输入对照，仅用于限定兼容验收。见 [契约说明](../docs/workbench-contracts.md)。

account-exposure-demo.json 为人工账户与披露；account-exposure-limited-real.json 仅复用已有真实基金身份/取数范围元信息，金额是教学值、无底层披露及真实净值数值。见[账户敞口口径](../docs/account-exposure.md)。

cash-demand-demo.json 为原创人工现金需求情景，金额、收入、支出、解冻与到账条件均为教学假设。见[现金需求口径](../docs/cash-demand.md)。


`workbench-observed-cashflow.json` 为流前/流后估值的合成教学输入；`workbench-observed-reference.json` 冻结四组同输入工作台结果与源码摘要，不是真实账户。兼容范围见 [现金联调契约](../docs/workbench-cashflow-integration.md)。


`observed-review-demo.json` 为专用旧观察方法迁移输入，`observed-review-reference.json` 绑定原工作台源码与15完整结果/11失败案例；全部为教学资料，非真实账户。新方法与原生回测XIRR及PR8窄桥分别版本化，详见 [工作台现金迁移说明](../docs/workbench-cashflow-integration.md)。


`data-reuse-teaching.json`/`data-reuse-reference.json` 是既有基金净值+分红拆分局部复用对照，非真实取得数据。`data-record-candidate-nav.json` 仅可选候选旁挂，完整保留原payload；未知时点/原件/单位/版本不补齐，不作为生产统一schema。详见 [数据接入指南](../docs/data-bridge.md)。
