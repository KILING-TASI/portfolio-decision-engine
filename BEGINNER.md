# 从自己的问题开始

教学入口只验证软件能运行，不代表已经分析你的标的。先用已有资料回答能确定的部分：金额表说明钱放在哪里；披露持仓说明已知重合；公告和报表字段需区分期间、单位及版本。

## 首次试用

完整源码解压后，需要 Python。Windows 可运行 Start-Demo.cmd；也可在源码目录执行 `python try_demo.py`。Linux/macOS 可执行 `sh Start-Demo.sh`，自动打开浏览器依系统能力而定。运行前可用 `python try_demo.py --check`。不联网、不自动安装组件，新输出目录保留旧报告。不能把教学数值替代真实资料。

## 准备资料确认卡

先确认：你问什么；标的身份；研究截止日；来源及资料日期；金额还是份额；币种与单位；权重相对什么。已有会话信息无需重复追问。日期和单位无法确定时只做不依赖它们的解释，不补造。

## 看懂结果与失败

报告生成、输入通过、计算完成和来源核验分别判断。未知比例不是错误率，也不代表未知部分没有风险；说明它可能影响哪个问题。缺来源时提供原表或原文，缺组件时按README按需安装，输出已存在时换新目录。完整技术错误和原始警告留底稿，正文解释影响与下一步。

## 更新与追问

先明确沿用资料还是取得新资料。保存输入、参数和结果，另存新情景；不覆盖历史冻结结果。只有明确登记的资料才能复用，不能默选最新文件。受控取数和专题能力按各自README提供，不把本指南当作任意数据的自动采集器。

基础安装只需本仓；轻量 account-exposure、cash-demand、convert-lookthrough、verify、light-demo 无科学计算依赖。完整收益、回归、M1–M7与优化安装 `python -m pip install ".[analysis]"`。安装普通 wheel 后要完整分析，可指定该 wheel 文件路径并加 `[analysis]`。

## 标准基金净值资料入口

python -m portfolio_engine.nav_collection demo --out-dir 新目录

python -m portfolio_engine.nav_collection collect --request 请求.json --online --out-dir 新目录

python -m portfolio_engine.nav_collection normalize --request 请求.json --input 原生档案.json --out-dir 新目录

python -m portfolio_engine.nav_collection replay --input 标准快照.json --raw response.txt --out-dir 新目录

标准请求显式声明id、source= eastmoney-fund-nav、fundCode（六位字符串）、start/end/asOf、currency=CNY、frequency=daily、fields=[unit_nav,distribution_text]。净值不等于总回报，原始事件文本未认证。旧入口保留；新资料采用cn-research-collection/1.0。首次演示是原创合成响应，不是实际基金。

格式实现和采集器固定随包提供，不要求安装作者其他仓库。转换工作台旧档案时原始响应可能缺失，明确保留缺口；重放必须提供与原记录一致的原始响应，原取得时间不改为今天。详见新数据适配仓cn-data-adapters，原报告不自动重算。


本轮新增因子横截面与研究试验留档。独立入口、底稿与限制见 [EXPANSION.md](EXPANSION.md)。


共同采集与观察表的单位、时间及版本范围见 [FORMAT_SCOPE.md](FORMAT_SCOPE.md)。宏观、微观和规则事件保留各自口径，不混作净值。
