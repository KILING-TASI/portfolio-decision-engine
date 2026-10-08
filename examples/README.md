# 合成示例

所有收益、因子、账户和订单均为固定种子生成的人工示例，不能当市场业绩。

```sh
python -m portfolio_engine run --returns examples/returns.csv --config examples/config.json --out reports/example
```

配置中的 factor_csv 与 orders_csv 相对本目录解析。更改资产顺序时同步更改各数组。真实输入不要保存到本目录或提交 Git。
