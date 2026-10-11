# 组合研究：详细使用说明

当前安装与教学入口见[首页](README.md)，资料准备见[BEGINNER](BEGINNER.md)。历史下载说明见[版本记录](CHANGELOG.md)。以下保留具体命令、方法、样本和限制，历史案例按各自日期阅读。

## 完整分析例子（可选组件）

需要 **Python 3.10 或以上**。下载或克隆本仓库，在仓库目录打开终端。安装时需要联网获取 NumPy、pandas、SciPy、scikit-learn、statsmodels 及其依赖；下面的教学演示离线运行，不获取真实行情。

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[analysis]"
.\.venv\Scripts\python.exe -m portfolio_engine demo --fast --out reports/demo-01
```

打开 `reports/demo-01/report.html`。同一目录里还有完整 JSON、账本、模拟交易和输入记录。**再次运行时，把 `demo-01` 换成新名字；已有结果不会覆盖。**

已有 Python 环境时，也可使用：

```sh
python -m pip install ".[analysis]"
python -m portfolio_engine demo --fast --out reports/demo-02
```

`--fast` 是快速教学模式。自己的数据格式、错误处理和完整命令见[使用说明](docs/usage.md)。


## 实际结果示例

**回撤变小，也可能以更低收益为代价。**下面这份固定种子的历史教学报告中，等权组合年化收益为 6.29%、最大回撤为 9.41%；最小方差组合分别为 1.41% 和 4.87%。它展示配置取舍，不证明某个方案长期更好。

[![历史教学报告：配置收益与回撤取舍](docs/previews/allocation.png)](docs/report-previews.md)

截图来自 2026-10-09 实际生成并检查的合成数据报告。[预览与复现记录](docs/report-previews.md)保留了当时的代码版本、输入和限制；这不是市场绩效，也不是对新版本的视觉验收。

想看入金、解冻、延迟到账和预算无解时会怎样，在装好本仓之后运行：

```powershell
.\.venv\Scripts\python.exe examples/run_scenarios.py --out reports/scenarios-01
```

打开 `reports/scenarios-01/scenario-index.html`，可分别查看预期、实际和报告。[七组场景索引](examples/scenario-index.json)说明复用了哪些手算和反例。例如，入金 1000 后资产从 1000 变为 2000，投资收益仍为零；缺少费用或到账依据时，完整现金余额保留为未知。脚本和样例由源码及源包提供，运行模块由本仓安装包提供。


## 能做什么，暂时不能做什么

| 你要检查的问题 | 当前源码能做的事 | 需要保留的限制 |
|---|---|---|
| 配置是否值得调整 | 比较等权、最小方差、风险平价等方案的收益、回撤和费用 | 不保证更优，也不生成实际交易指令 |
| 回撤预算能否满足 | 模拟路径、筛选候选；滚动重新估计并在下一段数据检验 | 无解就报告无解，参考组合不冒充预算解；模拟误差不是投资有效认证 |
| 入金后是不是赚了更多 | 分开核对投入、损益、累计 TWR 和年化 XIRR | 观察估值与收益路径模拟的时点、求根方法不同，不能只看名称替换 |
| 钱什么时候够用 | 分开记录可用现金、冻结资金和条件变现款，计算首次缺口和最大缺口 | 不确认实际成交、到账、借款或未来收入，不给缺口概率 |
| 基金是否持有同一批资产 | 汇总披露支持的底层资产、发行人和未知部分 | 披露并非实时完整持仓，也不是基金综合评价 |
| 数据能不能直接用于收益分析 | 核对净值、分红拆分声明、币种、日期和缺失情况 | 原始价格、累计净值及不完整事件不能直接当复利总回报 |

真实成交、整数份额、最低佣金、基金确认、盘中 QDII 估值、税率日历和通胀／信用联合情景尚未完整适配。详细方法和支持范围见[设计与实现说明](docs/design-v0.4.md)、[现金需求说明](docs/cash-demand.md)和[数据接入指南](docs/data-bridge.md)。设计目标不等于全部已实现。


## 独立使用与其他仓库的关系

这是一个**独立 Python 计算引擎和 CLI**，命令入口为 `python -m portfolio_engine`，安装后也提供 `portfolio-engine`。本仓另提供 [Skill 调用指引](SKILL.md)，完整资源注册与 CLI 安装分别完成。

生成主报告不需要安装 research-workbench 或其他自家专业仓库；普通科学计算依赖按本仓声明安装。开发用的 `pytest`、`build` 属于 `dev` 可选依赖。这里没有 PDF 解析 extra：原页字段解析由对应专业工具负责，本引擎消费明确提供的 JSON／CSV 和披露记录。

research-workbench 可以调用本引擎，并继续负责资料组织、公司经营与估值判断、基金综合评价、解释和报告接续；能被工作台调用不等于本引擎依赖工作台运行。[两仓分工及旧调用兼容范围](docs/workbench-cashflow-integration.md)说明了已经搬迁和暂未搬迁的计算。当前定投与行业退出的后续迁移仍在契约盘点阶段，不能称已经完成。

需要联网取数时，必须明确使用 `collect --online`；演示和已有输入分析不会自动打开采集。取得响应不代表事件齐全、原文核验或历史可得时间已经确认。


## 验证、许可与来源

- 现有 206 项回归测试，以及单仓隔离安装、CLI 报告和七组教学场景已经验证。CI 检查可在 [Actions](https://github.com/KILING-TASI/portfolio-decision-engine/actions) 查看；首页文案改动的最新检查以对应 PR 为准。
- [独立安装与验证范围](docs/usage.md)、[场景输入与资源](examples/README.md)、[统计方法与反例](docs/statistical-validation-methods.md)分别记录通过范围。CLI 成功不代表真实资料、投资效果、自然语言发现或视觉验收通过。
- 有限真实响应只核对了两只基金各 42 条净值档案的字节记录；完整事件、历史可得和真实 M2 正向验证仍有缺口，详见[数据目录与来源差异](docs/data-bridge.md)。真实账户和原始材料不在公共包中。
- 原创代码及有权授权的原创说明采用 [MIT](LICENSE)。第三方代码、公告、研报、行情和字体继续适用各自权利；见[许可范围](docs/license-scope.md)、[第三方说明](THIRD_PARTY_NOTICES.md)和[使用边界](DISCLAIMER.md)。

开发者测试与构建：

```sh
python -m pip install ".[dev]"
python -m pytest -q
python -m build
```


## 输出目录参数

原生子命令统一支持 `--out-dir`，旧 `--out` 保留为兼容别名，两者只能指定一个。参数接受新目录，不是文件名；例如 `portfolio-decision-engine run convert-lookthrough --input holdings.json --out-dir reports/lookthrough-first`。结果JSON和来源底稿保存在该目录中；重复运行换新目录，或在仓库名入口加 `--auto-name`。


## 自然语言使用

向已注册本仓 Skill 的助手直接提问。助手整理输入、调用计算并先回答能确定的部分，再解释依据和缺口；无需安装工作台。新增指引自 v0.8.3 随包提供；更早的发行包保持原样。


## 验证范围

源码教学启动、软件环境查询和安装后教学入口分别验证；软件就绪不等于真实资料已取得。中文问答需要助手按本仓Skill准备已声明输入，没有宣称任意自然语言自动发现或全市场数据闭环。旧报告、历史tag与案例证据保留。


本轮新增因子横截面与研究试验留档。独立入口、底稿与限制见 [EXPANSION.md](EXPANSION.md)。


共同采集与观察表的单位、时间及版本范围见 [FORMAT_SCOPE.md](FORMAT_SCOPE.md)。宏观、微观和规则事件保留各自口径，不混作净值。


本轮更新：[定投与退出现金流](CASH_MIGRATION.md)，轻量计算不需要完整分析扩展。
