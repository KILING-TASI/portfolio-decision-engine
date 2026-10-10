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
