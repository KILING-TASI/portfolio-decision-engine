# 定投与退出现金流迁移

v0.9.4提供独立迁移计算。定投的日期顺延、分红权益、再投、费用、账本、XIRR，以及退出情景的现金流归类、完整性检查和非传统现金流阻断，由组合引擎负责。工作台保留原调用名、报告和判断，计算改为明确选择独立包；缺包或接口缺失时明确失败，不回退重复算法。

两项均使用标准库，基础安装不要求 numpy/pandas/scipy。输入结构、单位、原字段、错误及数值保持旧口径；迁移不增加实际成交、到账、税负或交易日历认证。

```console
python -m portfolio_engine scheduled-cash --input examples/scheduled-cash-demo.json --out-dir reports/scheduled
python -m portfolio_engine exit-cash --input examples/exit-cash-demo.json --out-dir reports/exit
```

例子是原创教学现金流。每次另存新目录，旧报告保持冻结。工作台需要安装含这两个接口的v0.9.4或兼容新版wheel，或设置 RESEARCH_WORKBENCH_PORTFOLIO_DIR 为明确可信的项目目录；v0.9.3及更早公开发行不含本轮接口。

104项旧输入与完整结果留作迁移核对。现金金额、费用、日期、缺失状态和错误逐项精确比较；仅XIRR在不同平台的浮点求根尾数允许1e-10百分点绝对或1e-13相对差异，计算算法未因测试精度范围改变。
