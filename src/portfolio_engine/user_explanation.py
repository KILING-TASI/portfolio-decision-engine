"""Chinese report explanations; frozen machine fields remain unchanged."""
LIMITS={
'Declared valuation joined to mixed disclosure dates, not verified live full holdings or portfolio risk':'金额与不同披露期的持仓连接，不是已核验的实时全量持仓或组合风险。',
'Overlapping direct and fund exposure is aggregated once per distinct economic lot; shared issuer does not justify deleting legitimate holdings':'直持与基金间接敞口按不同经济持仓累计；同一发行人不能成为删除真实敞口的理由。',
'Issuer/industry mappings require their own evidence; missing mappings stay unknown':'发行人和行业映射需要各自依据；缺失映射继续保留未知。',
'Cash status and valuations are input declarations, not settlement authentication':'现金状态和估值来自输入声明，不代表资金到账已核验。',
'No real-return M2 evaluation or trade instructions':'此报告不含真实收益M2检验，也不提供交易指令。',
'Conditional date-level arithmetic, not an executable liquidation plan or probability forecast':'按声明条件和日期计算，不是可执行的变现方案或概率预测。',
'Unknown cash amounts, dates and planned settlements are unresolved, not zero; reported balances and gaps only include resolved events':'未知金额、日期和到账事项不填零；展示的余额与缺口只包含已明确事件。',
'Negative projected balance means unfunded need, not a loan or payment already executed':'条件余额为负表示资金尚未补足，不代表已经借款或支付。',
'Same-day receipts are assumed available for same-day expenses; intraday timing is not modeled':'假设同日收入可用于同日支出；日内先后时序尚未建模。',
'Calendar-day settlement and fee deduction at receipt are explicit input assumptions, not exchange/fund settlement validation':'自然日到账和到账时扣费是明确输入的假设，不是交易所或基金结算认证。',
'Root assets only; fund underlying assets and disclosed fund cash are not additional available account cash':'仅计算账户根持仓；基金底层资产与披露现金不能再加成账户可用现金。',
'No insurance, tax planning, real account verification or trading instructions':'不含保险、税务规划、真实账户核验或交易执行。',
}
def limit_text(value):return LIMITS.get(value,value)
