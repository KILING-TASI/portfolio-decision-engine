# 参考来源与许可

v0.6 的数据契约、净值分红/拆分再投、报告留档、未知仓位递归穿透和失败处理参考了用户维护的 [research-workbench](https://github.com/KILING-TASI/research-workbench)，评审提交为 `051846168d7590991c75afc001abb97a89b1d3ed`。

相关实现按本引擎接口重新整理，没有将研究工作台整个脚本树作为依赖。特别参考 fund_series_tools.py、research_extensions.py、start.py、verify_collection_report.py、market_collect.py、portable_collect.py、etf_closing_premium.py 与 observation_calendar.py。为保留相关参考和适配的授权说明，附上游许可。上游数据、公告和外部组件继续适用各自条件，MIT 不授予其再分发权。本引擎其他部分尚未选择许可证。

## research-workbench MIT

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
