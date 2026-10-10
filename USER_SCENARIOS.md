# 15类使用者：从问题到可复查结果

按任务选择工具，不按职业整体排除。下面是本轮可复查的使用路径，不能据此声称已有15类真实客户或机构生产认证。独立安装各所属仓库即可；跨仓组织需要用户明确提供输出，工作台不是所有专业工具的依赖。

|使用者|可做的研究|所属仓库|入口|关键边界|
|---|---|---|---|---|
|个人投资者|了解分派现金、基金重合和组合现金缺口|cn-reits-research / cn-fund-lookthrough / portfolio-decision-engine|distribution-plan / overlap问答 / cash-demand|不知道价格不算收益率，部分披露保留未知|
|量化小白|看懂相关、分层和试验选择|portfolio-decision-engine|factor_research panel / trials|恒定因子相关为null，泄漏时阻断|
|投资顾问|匿名研究组合和可用现金情景|portfolio-decision-engine / research-workbench|cash-demand / archive-index|不建立CRM或适当性审批记录|
|证券分析师|配对预测、首次实际、重述和公开问答|research-workbench / cn-financial-reconcile|forecast-actual / public-qa / 财报核对|口径不同、事后取得预测不算误差|
|财经媒体/事实核查者|引用计划、执行、持仓的有限证据|marketlens|citation_summary summary|计划不当执行，原句语义仍人工核实|
|风控/合规|复查分母、管理人范围、例外和资金缺口|cn-market-rules|fund-limits / redemption-liquidity|部分持仓线内也不能认证全机构合规|
|FOF经理/基金评价|看两期披露变化和重合|cn-fund-lookthrough|snapshot_review compare / 穿透|新增披露不推实际买卖，非股票未知|
|交易员/做市商|盘后检查条款、发行资金和公开证据|convertible-bond-engine / bjx-ipo-engine / marketlens|条款情景 / 多发行现金情景 / 核查摘要|不保证实时成交和资金到账|
|基金会计/运营|复查可供分配、净值渠道和原表金额|cn-reits-research / cn-data-adapters / cn-financial-reconcile|available / replay / 金额勾稽|不是净值生产、TA结算或支付认证|
|上市公司IR/董秘/战投|复查公开问答、假设和同行口径|research-workbench|public-qa / hypothesis-diff / 公司情景|前瞻表述和实际业绩分别记录|
|专业量化研究员|核因子时点、股票池和选型记录|portfolio-decision-engine|factor_research panel / trials|保留失败，不把尝试数变独立试验数|
|基金经理PM|比较资金、宏观和REIT经营情景|portfolio-decision-engine / macro-dashboard-engine / cn-reits-research|现金 / 宏观报告 / value|模型现金闭合不证明现实偿债安全|
|审计师/财务核数|逐项复查金额、单位和版本|cn-financial-reconcile / cn-reits-research|财报核对 / available|算术通过不出审计意见|
|学者/金融教学|复现经营权DCF、IC和反例|cn-reits-research / portfolio-decision-engine|demo / factor_research panel|合成样本不代表真实市场表现|
|Agent开发者|独立安装、校验格式、重放和绑定报告|cn-research-contracts / cn-data-adapters / research-workbench|validate / replay / archive-index|成功退出0、阻断2，摘要不是认证|

## 最短复现与验收

各仓 README 的 demo 是最短流程。新增模块说明在 EXPANSION.md；REITs 在 PUBLIC_CASES.md、METHODS.md；格式和采集在 BEGINNER.md。选择公开资料或明确教学输入→核身份/截止/单位→运行新目录→读结论、金额与缺口→展开依据→按摘要复查保存文件。每次参数变化保存新输入版本，不修改历史报告。

教学问答、税款、限额、因子输入中的数值和摘要是原创示意，不是原文认证。公开REIT案例仅核两个公告的限定事实，不冒充完整真实产品估值。真实数据取得、完整账户、全部现金流、权限及产品特殊规则仍需各自核验。

## 共同阅读口径

未知不是零。权重说明分母：基金净资产、股票资产、账户总值不可互换。敞口指已知资料支持的暴露，不是全部真实资产；若给定完整同币种账户基数，可将比例乘基数换成金额，但未知资产不归一。最大回撤是历史从高点跌下来的幅度，不是未来损失上限。折现值依赖未来现金和折现率；分派率、IRR和净值是三种不同口径。IC衡量因子与随后收益的相关，ICIR不是策略收益或准确率。每项结果均应保留来源、资料时点、参数与方法版本。
