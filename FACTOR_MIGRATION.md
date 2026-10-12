# 独立因子仓与PDE兼容

因子生成、CNN、K线规则、面板与试验留档的维护入口为 [cn-factor-research](https://github.com/KILING-TASI/cn-factor-research)。数据采集留在数据仓，账户敞口、成本、现金占用与组合约束留在PDE。

PDE既有 `cnn/pattern` 命令继续可用：

- 已安装独立发行包v0.1.x时，委托它的CLI，并在终端提示实际提供者。
- 未安装，或安装版本不在已验证v0.1.x范围时，使用本仓冻结的v0.12数学实现，明确提示原因。
- 不自动安装、联网取数、扫描兄弟仓目录或读取作者缓存；基础PDE仍零必需第三方依赖。旧输入、报告与回执不改写。

使用新功能可直接安装独立仓自己的wheel，并调用 `cn-factor-research`。这不是PDE必需依赖；独立因子仓也不依赖PDE。PyTorch仍是训练/预测的可选组件。

程序化导入原 `portfolio_engine.cnn_engine/candle_patterns` 等模块继续使用冻结v0.12实现；命令行兼容入口可能委托独立包，调用时以终端提供者说明为准。冻结源文件摘要见FACTOR_FROZEN_V012.json。后续因子功能在独立仓实现，避免两边并行维护新算法。

旧 `factor panel/trials` 与成本、暴露、预算、现金入口保留；本轮不宣称独立仓包含组合可投性判断。模型摘要只认证文件一致性，不认证历史存在或真实A股效果。
