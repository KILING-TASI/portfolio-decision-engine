# 实际教学报告预览

三个 PNG 是本机 Chrome 对实际生成的 HTML 节选进行无头渲染，已逐张检查文字、数值和表格完整性；没有使用生成式图片或修改计算数值。生成时间为 2026-10-09（北京时间），引擎包版本 v0.7.0，计算代码固定在提交 `0a370ad4b6d6`（完整提交见清单）。这包含待审代码，不能以包版本号宣称已经发行。

| 案例 | 实际截图 | 可离线打开 HTML | 用途及边界 |
|---|---|---|---|
| 配置取舍 | [配置截图](previews/allocation.png) | [配置节选](previews/allocation.html) | 等权留出年化收益 6.29%、回撤 9.41%；最小方差 1.41%、4.87%，是收益换取回撤改善，不证明优势 |
| M2 训练/测试 | [窗口截图](previews/m2-windows.png) | [窗口节选](previews/m2-windows.html) | 三个前置估计/校验截止与下一段测试；本例没有独立验证集，校验使用估计数据；仅100条路径，待审 #2 |
| 未知穿透 | [穿透截图](previews/lookthrough.png) | [穿透节选](previews/lookthrough.html) | 已知86%、未知14%，缺失不能作为零风险；使用教学披露，不是实时持仓或全组合风险 |

输入均由仓库 `make_demo` 用种子42生成，不是行情、个人账户或商业导出。收益样本是2014—2025人工收益；日期相似不代表市场历史。[生成代码](../examples/generate_report_previews.py)调用现有 demo 和 m2-demo，再选取真实报告章节。来源报告、输入字节及截图的摘要见 [预览清单](previews/preview-manifest.json)；摘要验证完整性，不认证真实来源。

## 最短 demo 与完整复现

普通配置 demo 在公开 v0.7.0 可运行。M2 及生成三个预览须使用包含 PR #1 → #2 → #3 的待审分支。

```sh
python -m pip install -e .
python -m portfolio_engine demo --fast --out reports/my-demo
```

打开 `reports/my-demo/report.html`；目录必须新建且此前不存在。它还输出 report.json、ledger.csv、transactions.csv、输入快照及 report-manifest.json。

待审分支复现三个节选（不需要浏览器即可生成 HTML）：

```sh
python examples/generate_report_previews.py --out reports/my-previews
```

会运行并核验两份报告，生成 `reports/my-previews/demo/report.html`、`m2/m2-report.html` 和 `preview/` 下三个 HTML。输出目录不覆盖。获取真实截图时，给同一命令附加 `--browser`，其值为本机 Chrome 或 Edge 可执行文件的绝对路径；脚本不会安装浏览器，不会产生AI图片，也不将截图存在等同视觉检查。

本次实际使用 Chrome 的1400像素宽视口，配置1150、M2 950、穿透900像素高；已检查 M2 包含期末现金列、无截断。图片呈现系统字体但不附字体文件、浏览器代码或依赖库。HTML保留结果旁边的模型限制和版本状态。

需要先整理资料或判断组合研究问题，可回到工作台[日常问题入口](https://github.com/KILING-TASI/research-workbench/blob/main/references/practical-entry.md)。该入口不改变两个仓库的职责或宣称全面替代。

有限真实基金净值仅完成取数及缺事件信息的拒绝验收；未通过总回报准备，未开展正向真实 M2 表现验证。本次公开预览不包含这些外部净值或其原始响应。
