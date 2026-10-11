# 定投与退出现金流迁移

本轮本地迁移计算，尚未发布。定投的日期顺延、分红权益、再投、费用、账本、XIRR，以及退出情景的现金流归类、完整性检查和非传统现金流阻断，由组合引擎负责。工作台保留原调用名、报告和判断，计算改为明确选择独立包；缺包或接口缺失时明确失败，不回退重复算法。

两项均使用标准库，基础安装不要求 numpy/pandas/scipy。输入结构、单位、原字段、错误及数值保持旧口径；迁移不增加实际成交、到账、税负或交易日历认证。

```console
python -m portfolio_engine scheduled-cash --input examples/scheduled-cash-demo.json --out-dir reports/scheduled
python -m portfolio_engine exit-cash --input examples/exit-cash-demo.json --out-dir reports/exit
```

例子是原创教学现金流。每次另存新目录，旧报告保持冻结。工作台需要安装含这两个接口的新本地 wheel，或设置 RESEARCH_WORKBENCH_PORTFOLIO_DIR 为明确可信的项目目录；旧公开发行尚不含本轮接口。
