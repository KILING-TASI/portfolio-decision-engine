# 参考来源与许可

v0.6 的数据契约、净值分红/拆分再投、报告留档、未知仓位递归穿透和失败处理参考了用户维护的 [research-workbench](https://github.com/KILING-TASI/research-workbench)，评审提交为 `051846168d7590991c75afc001abb97a89b1d3ed`。

相关实现按本引擎接口重新整理，没有将研究工作台整个脚本树作为依赖。特别参考 fund_series_tools.py、research_extensions.py、start.py、verify_collection_report.py、market_collect.py、portable_collect.py、etf_closing_premium.py 与 observation_calendar.py。为保留相关参考和适配的授权说明，附上游许可。上游数据、公告和外部组件继续适用各自条件，MIT 不授予其再分发权。本仓库原创代码及有权授权的原创说明采用根 MIT；第三方材料继续按其原许可和权利范围处理。

## research-workbench MIT

新增cn-fund-lookthrough输入适配参考该用户仓库提交`72bf3651269ef156f3f002641b224a968adbb3e0`的公开输入契约；教学夹具由examples/demo.json改编。该仓库同样使用下列MIT与2026 research-workbench contributors署名。保留上游数据许可边界，未复制其计算核心作为依赖。

MIT License

Copyright (c) 2026 research-workbench contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 工作台兼容参考

限定买入持有契约参考 research-workbench 提交 051846168d7590991c75afc001abb97a89b1d3ed 的 portfolio_stress.py。参考 JSON 由其纯数学 portfolio_path 函数生成；未复制整套报告或修改工作台。固定摘要及范围见 docs/workbench-contracts.md。该参考不作为本仓库整体 MIT 重新授权的第三方代码。

## 科学计算依赖（单独安装，未嵌入本项目 wheel）

| 依赖 | 主项目许可 | 本次核对版本 | 保留文本 |
|---|---|---|---|
| NumPy | BSD-3-Clause；附带组件还有其他许可 | 2.5.3 | licenses/dependencies/numpy/ |
| pandas | BSD-3-Clause | 3.0.6 | licenses/dependencies/pandas/ |
| SciPy | BSD-3-Clause；发行物包含单独组件许可及例外 | 1.18.1 | licenses/dependencies/scipy/ |
| scikit-learn | BSD-3-Clause | 1.9.1 | licenses/dependencies/scikit-learn/ |
| statsmodels | BSD-3-Clause | 0.15.0 | licenses/dependencies/statsmodels/ |

上述主许可不是对所有捆绑组件的统一授权。目录保留已安装发行物提供的原始文本，包括附带组件、版权和例外，不删改或重新署名。licenses/dependency-license-snapshot.json 记录文本对应版本；安装版本可能变化，使用或再分发依赖须核对实际发行物的许可证。NumPy、SciPy 的二进制组件不随本项目 wheel 打包。其他传递依赖由包管理器单独安装并自带许可，本清单不冒称已审核所有未来依赖组合。

research-workbench 与 cn-fund-lookthrough 的原始 MIT 文本分别保存于 licenses/，版权署名按实际文件保留；教学夹具与受参考影响的适配保留来源说明。skfolio、Riskfolio、arch、PortfolioAttribution 等属于选型或论文/算法参考，未作为复制实现或依赖收录；不能将参考阅读误写成代码移植。

根 MIT 不授权天天基金/东方财富、腾讯等外部接口响应、公告、研报、行情、商标、字体或第三方资料。有限真实取数档案留在忽略的本地 reports/，不进入 Git、源码包或 wheel。教学预览仅含原创人工序列和生成结果，实际浏览器截图不附浏览器/系统字体文件；输入来源占位链接不是取得真实数据授权的证明。完整范围和未明事项见 docs/license-scope.md。
