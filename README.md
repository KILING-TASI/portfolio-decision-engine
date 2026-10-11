# 组合研究

比较配置、回撤、费用和现金需求，生成可核对的报告与账本。

[![原创代码 MIT](https://img.shields.io/badge/原创代码-MIT-green)](LICENSE) · [当前发行版 v0.9.4](https://github.com/KILING-TASI/portfolio-decision-engine/releases/tag/v0.9.4) · [运行检查](https://github.com/KILING-TASI/portfolio-decision-engine/actions)

## 能解决什么问题

**我的钱集中在哪？几笔申购会不会撞上同一段资金占用？**

独立维护组合和现金情景；披露持仓可以从基金穿透工具导入，也可提供明确底稿。

## 快速开始

从[发行页](https://github.com/KILING-TASI/portfolio-decision-engine/releases/tag/v0.9.4)下载完整源码并解压，需要 Python 3.10 或以上。在源码目录执行：

```text
python try_demo.py --no-open --out-dir reports/first-demo
```

按提示打开新生成的 HTML。Windows 也可双击 `Start-Demo.cmd`，Linux/macOS 可用 `sh Start-Demo.sh`。教学使用原创模拟资料，不自动取真实数据；重复运行使用新目录，历史结果保留。

[查看已保存的报告示例](docs/previews/lookthrough.html)。HTML请随完整源码下载后打开；示例按自身生成日期和口径阅读。

![已保存的报告示例](docs/previews/allocation.png)

图片是历史示例，不能推定全部新报告已完成视觉验收。

## 使用自己的资料

先按[资料准备](BEGINNER.md)填写输入，再看[详细命令与方法](USAGE.md)。需要安装CLI时，在自己的Python环境运行：

```text
python -m pip install .
portfolio-decision-engine --help
```

仓库、Python发行包、安装命令及Skill注册名均为 `portfolio-decision-engine`。CLI安装和Skill注册是两个步骤：自然语言调用按[SKILL.md](SKILL.md)配置，保留完整资源；不必安装全部仓库。安装普通构建依赖可能联网，教学流程不需要作者缓存。

## 结果范围

轻量金额入口无需科学计算包；完整风险、回归与优化按需安装 .[analysis]。不承诺更优配置或真实成交。

报告中的来源、日期、假设和未知事项需一起阅读。程序运行成功不等于来源已经认证、资料完整或投资判断有效。原创代码采用MIT，第三方代码、公告、研报和数据仍按各自权利范围处理。

## 文档与维护

- [详细命令与方法](USAGE.md)
- [资料准备与排错](BEGINNER.md)
- [Skill调用指引](SKILL.md)
- [版本记录](CHANGELOG.md)
- [许可与第三方范围](THIRD_PARTY_NOTICES.md)
- [审计范围](AUDIT_SCOPE.md)
- [扩展专题](EXPANSION.md)

[贡献说明](CONTRIBUTING.md) · [安全反馈](SECURITY.md) · [更新与清理](LIFECYCLE.md) · [English](README.en.md)

[按问题选择其他工具](https://github.com/KILING-TASI/research-workbench/blob/main/references/tool-navigation.md)。共12个活跃仓，另有1个供旧记录复查的[历史契约仓](https://github.com/KILING-TASI/cn-research-contracts)。各仓分别发布；main的后续文档整理不改写旧发行包和冻结结果。

## v0.9.4 本轮补强

定投与退出现金流独立入口，保留原结果语义并补104项迁移核对。具体参数与边界见[使用说明](USAGE.md)。
