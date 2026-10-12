# CNN 因子研究

本页记录PDE冻结v0.12研究实现。后续因子增量以独立 [cn-factor-research](https://github.com/KILING-TASI/cn-factor-research) 为维护入口，旧命令兼容见 [迁移说明](FACTOR_MIGRATION.md)。
CNN 把过去一段价格与成交量记录变成一个得分，再交给 PDE 检查。这里实现的是原创的一维 OHLCV 回归网络：两层卷积、平均池化、一个回归输出。它没有复制论文的二维K线图片模型，也没有认证真实A股预测效果。

得分是声明期限内简单总收益的回归估计，可以为负，也可能低于 -100%；这说明模型估计有误，不应把输出强行裁成概率。模型本身不决定买入，不计算账户收益。

## 单独安装与最短流程

Python 3.10+。基础 PDE 无必需第三方依赖；`cnn validate`、冻结文件核对和 `cnn bridge` 只需标准库。训练、滚动验证、预测单独安装 `[cnn]`，不需要其他仓库、工作台或作者缓存。

在本仓完整源码目录：

```text
python -m pip install ".[cnn]"
portfolio-decision-engine cnn validate --input examples/cnn-teaching/train.json --out-dir reports/cnn-check
portfolio-decision-engine cnn train --input examples/cnn-teaching/train.json --out-dir reports/cnn-train
portfolio-decision-engine cnn walk-forward --input examples/cnn-teaching/train.json --out-dir reports/cnn-rolling
```

CPU 安装可先按 [PyTorch 官方安装说明](https://pytorch.org/get-started/locally/) 选择对应平台；本模块只在 CPU 计算，不要求显卡。已有 wheel 时执行 `python -m pip install "路径/portfolio_decision_engine-0.12.0-py3-none-any.whl[cnn]"`。安装依赖需要网络，运行不联网。所有命令也可写为 `python -m portfolio_engine cnn ...`。

示例是本仓原创的四只虚构证券、64个合成样本；记录日不代表中国交易日。`make_example.py` 仅说明示例来源，生成器拒绝覆盖已有示例。示例好成绩不代表实盘效果。

每次输出新目录，内含 `input.json`、`result.json`、`report.html`、`receipt.json`。旧结果不覆盖。命令提示读取、计算、保存阶段；异常返回2，说明缺失条件。模型嵌入 `result.json`，保存 JSON 数组权重、结构版本、训练参数、数据摘要、样本ID、逐轮训练/验证损失、选择轮数与清洗记录；不加载 pickle 或任意模型代码。

## 输入逐项核对

完整字段示例见 [train.json](examples/cnn-teaching/train.json)。`schemaVersion=cnn-factor/1`；必须声明研究/数据版本、`dataKind`（`synthetic-teaching` 或 `declared-history`）、含时区 `asOf`、当期股票池定义/版本、价格口径、标签定义、`volumeBasis=shares`、`returnUnit=decimal-simple-total-return`。

`lookbackRecords` 是4至256条有序记录，不冒称交易日数；`horizonRecords` 是1至256条声明期限记录，需要外部日历与标签依据，不自动推断。样本数1至5000；训练/验证/测试清洗后各至少3条。`parameters` 固定 `epochs`（1至200）、`seed`、`learningRate`（大于0、不超过0.1）。不要在查看测试结果后反复修改参数却称其为独立测试。

每个样本包含唯一 `id`、`security`、`signalAt`、`universeAvailableAt`、`membershipAtSignal`、`adjustmentEvidence`、`history`、训练用 `label`。

- 当期股票池须在信号前可得；不确认的成员列为排除，不能用今天的存活股票补历史。
- 复权证据含 `source`、含时区 `availableAt`，不得晚于信号。不能用事后后复权系数解释历史信号。
- 历史记录恰为声明窗口数，每条含 `at`、`availableAt`、`open/high/low/close`、`volumeShares`、`source`；价格为正，成交量非负，OHLC边界成立。记录时间递增且 `at <= availableAt <= signalAt`。缺数据不能填零，缺日期不自动填充。
- 标签含 `returnStartAt`、`returnEndAt`、`availableAt`、`forwardReturn`、`horizonRecords`、`source`；信号不晚于区间起点，结束晚于起点，标签在结束后、复查截止前可得。简单总收益不得小于 -100%。

价格四通道除以本样本第一条收盘价再减1，成交量通道取 `log1p(股数)`。通道均值、尺度与标签均值/尺度只用训练集拟合，并随模型保存；验证和测试不得重拟合。训练标签没有变化时阻断。

数据仓现有行情归档若只有原始成交量、未认证单位、取得日而无历史公开时点，就还不满足此契约；本模块不会代填股数或历史时间。价格口径、公司行动、退市覆盖和交易日历仍需独立证据。`declared-history` 仅表示用户提供历史底稿，不表示系统已认证。

## 滚动验证与模型可得性

`train` 的 `split` 包含 `trainStart/trainEnd/validationStart/validationEnd/testStart/testEnd`，区间按时间严格分开。训练标签可得时点触及验证开始、验证标签触及测试开始的样本，均清洗并记录。可选 `parameters.embargoSeconds` 在阶段边界前增加0至366天的隔离缓冲，默认0秒，不自动宣称完成CPCV。模型只按验证损失选择轮数，冻结后才算测试指标。`walk-forward` 使用1至12个 `folds`，测试区间有序、不重叠；每个窗口重新拟合。后面的训练窗口可以使用先前已可得的标签。滚动样本×轮数×窗口数上限100万。

测试报告并列提供只用训练标签均值预测的基线，误差改善可以为负，不能看过测试后重选。测试报告给出均方误差、逐信号时点的横截面 rank IC 与样本数。每时点不足3个、得分或标签无差异时相关系数未知；均值只对可计算时点取平均，不输出胜率、收益曲线、显著性或可信概率。

**事后训练不证明模型当时存在。** 训练和滚动结果标为回顾性模拟，模型保存实际 `createdAt`，模拟 cutoff 单独保存且 `historicalAvailabilityCertified=false`。`bridge` 拒绝把模拟结果导入普通历史可得面板。模型摘要只认证文件一致，不认证历史存在、来源版权或输入真实性。

未来调用用 `predict`：输入 `mode=prediction`，删除每条 `label`，声明实际计划使用的信号时点；历史行情仍必须已可得。用本次计算时间与模型实际创建时间检查，晚于声明信号则拒绝，不能用事后预测填旧信号。模型仅接受相同数据性质、股票池与标签/价格/成交量口径。

```text
portfolio-decision-engine cnn predict --input prediction.json --out-dir reports/cnn-predict --artifact-dir reports/cnn-train --receipt-sha256 回执摘要 --model-fingerprint 模型摘要
```

回执摘要为 `review_io.digest(receipt.json对象)`，模型摘要为训练 `result.json` 的 `model.fingerprint`。可用标准库读取，不能拿文件SHA替代规范对象摘要：

```text
python -c "from portfolio_engine.review_io import read,digest; print(digest(read('reports/cnn-train/receipt.json'))); print(read('reports/cnn-train/result.json')['model']['fingerprint'])"
```

加载时要求外部明确摘要，核对回执、原输入、结果、报告和固定结构权重；不信任文件里自己声称的摘要。预测结果包含 `scoreComputedAt`，这是可得时点的一项声明，不能拿模型创建时间替代。

## 接入 PDE

实际预测冻结后，等待标签可得，再用 `cnn bridge` 绑定，输入包括 `asOf`、`groups`（2至10）、与模型一致的 `labelDefinition/returnUnit/horizonRecords/priceBasis`，以及 `labels` 列表。每条必须包含与得分一致的 `id/security/signalAt`、`returnStartAt/returnEndAt/availableAt/forwardReturn/horizonRecords/source`。股票池成员和可得时间沿用冻结预测，不可在绑定时重写。

```text
portfolio-decision-engine cnn bridge --input measured-labels.json --out-dir reports/cnn-panel --artifact-dir reports/cnn-predict --receipt-sha256 预测回执摘要
```

结果同时保留 `panelInput` 和 `panelReview`。将 `panelInput` 单独保存为新 JSON，可以继续 `factor panel`，并结合因子身份、行业/市值暴露、成交成本与现金条件审查；这不意味着CNN有可投性。训练目录不能代替预测目录，合成模型不能改标签为真实市场认证。

训练结果的参数、样本、失败日志应加入研究人员自己的试验台账；模块无法知道仓库外失败过多少次，也不自动给 DSR、Reality Check 或策略概率。

## 兼容与范围

PDE v0.11.0 新增可选入口，v0.10.0 的基础因子与旧 panel/trials 口径保留。模型契约和结构分别带版本，不承诺任意第三方权重兼容。同平台同版本同输入使用CPU固定种子；[PyTorch 官方复现说明](https://docs.pytorch.org/docs/stable/notes/randomness.html)明确跨版本、平台不保证一致。原始代码 MIT，PyTorch 与其传递依赖保留各自许可，数据和研报不随代码许可证转移权利。

## 参考步骤的取舍

[用户提供的元宝步骤解析](https://yb.tencent.com/s/0Oav33vCGBm0)在2026-10-12逐项阅读（八步、三个常见坑、消融讨论）。采纳价量窗口、时间切分、训练期标准化、信号/交易分离与基线核对；该分享为AI整理，不作为收益数字、网络参数或原始研究结论的认证依据。二维因子图片、像素K线和一维卷积是不同输入方案，CNN不必转成二维图。

当前标签仅支持明确的小数简单总收益，不含基准超额或横截面分类；固定期限得分可作横截面相关核对，但不能冒称已实现相对排名损失、PBO、CPCV、消融平台、自动行业中性化或实盘回测。这些方法需要不同契约和完整试验资料，不能套用分享中的百分比。

## 本轮验收记录

2026-10-12：完整组件回归301项及138个子用例通过，CNN专项21项通过；仅安装本仓wheel的基础/CNN两种环境通过，旧基础因子7动作通过。运行时禁用网络，工作目录与用户目录为空，不依赖其他仓库；先从官方源安装依赖，安装过程本身不属于离线运行验收。

[教学性能记录](examples/cnn-teaching/acceptance-record.json)保留平台、Python、CPU、PyTorch版本、输入文件摘要、规模、种子和命令耗时；各命令只测一次，包含进程启动/导入/报告写入，不包含依赖安装，不能当压力上限或真实市场效果。单独验收脚本在 `tests/cnn_cold_acceptance.py`，可用新输出目录复跑。浏览器检查确认首屏范围、教学性质与展开留档；合成数据之外的历史效果尚未验收。
