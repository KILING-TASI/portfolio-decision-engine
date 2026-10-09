"""Generate public teaching excerpts from freshly computed reports; no external data."""
import argparse
from datetime import datetime
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo


def run(*args):
    subprocess.run([sys.executable, "-m", "portfolio_engine", *args], check=True)


def excerpt(document, titles):
    sections = re.findall(r"<section[^>]*>.*?</section>", document, re.S)
    selected = []
    for title in titles:
        matches = [s for s in sections if "<h2>" + title + "</h2>" in s]
        if len(matches) != 1:
            raise ValueError("Expected exactly one report section: " + title)
        selected.append(matches[0])
    return "\n".join(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="New directory, never overwritten")
    parser.add_argument("--browser", help="Optional Chrome/Edge executable for genuine headless screenshots")
    args = parser.parse_args()
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    run("demo", "--fast", "--seed", "42", "--out", str(root / "demo"))
    run("m2-demo", "--fast", "--out", str(root / "m2"))
    for name in ["demo", "m2"]:
        run("verify", str(root / name))
    preview = root / "preview"
    preview.mkdir()
    demo = json.loads((root / "demo/report.json").read_text(encoding="utf-8"))
    m2 = json.loads((root / "m2/m2-evaluation.json").read_text(encoding="utf-8"))
    version = demo["engine_version"]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    generated = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    cases = [
        ("allocation", "配置的收益与回撤取舍", "demo/report.html", ["冻结权重后的留出区间比较", "相对基准的收益与风险取舍"], "v0.7.0 已发布能力；单次留出比较，不是完整 M2 滚动验证。"),
        ("m2-windows", "M2：先训练与筛选，再测试", "m2/m2-report.html", ["每个窗口实际执行什么", "窗口记录"], "待审 PR #2 能力；fast 演示仅 100 条模拟路径，未做多重选择校正，不是实盘验证。"),
        ("lookthrough", "穿透中的已知与未知", "demo/report.html", ["披露持仓穿透"], "教学披露快照；未知部分不当作零风险，不据此推算全组合风险或交易。"),
    ]
    records = []
    for name, title, source, sections, limitation in cases:
        document = (root / source).read_text(encoding="utf-8")
        body = excerpt(document, sections)
        style = re.search(r"<style>(.*?)</style>", document, re.S).group(1)
        html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · 教学预览</title><style>{style}
main{{max-width:1200px}}.stamp{{background:#fff2d6;padding:14px;border-radius:8px}}.provenance{{font-size:13px;overflow-wrap:anywhere}}section{{margin:14px 0;padding:20px}}h1{{font-size:28px}}.table table{{font-size:13px}}.table td,.table th{{padding:8px 5px}}</style><main>
<h1>{title}</h1><p class="stamp"><strong>合成教学数据 · 不是市场绩效</strong><br>引擎 v{escape(version)} · 生成日期 {escape(generated[:10])}（北京时间） · 固定种子 42</p>
<p>{escape(limitation)}</p>{body}
<p class="provenance">实际生成报告的节选，未修改计算结果。来源：{source}；代码提交：{commit[:12]}。<a href="https://github.com/KILING-TASI/portfolio-decision-engine/blob/feat/workbench-history-contract/docs/report-previews.md">样本、生成步骤与完整报告说明</a>。截图仅展示这一教学节选。</p></main></html>'''
        target = preview / (name + ".html")
        target.write_text(html, encoding="utf-8")
        records.append({"case": name, "source_report": source, "source_sha256": sha256((root / source).read_bytes()).hexdigest(), "excerpt_sha256": sha256(target.read_bytes()).hexdigest(), "sections": sections})
    manifest = {"schema": "teaching-report-preview-v1", "engine_version": version, "code_commit": commit, "generated_at": generated, "data_kind": "synthetic_teaching_not_market_performance", "seed": 42, "screenshots": "separate_browser_render_required", "cases": records, "input_archives": {name: {k: v for k, v in json.loads((root / name / "report-manifest.json").read_text(encoding="utf-8"))["files"].items() if k.startswith("inputs/") or k.startswith("source-")} for name in ["demo", "m2"]}, "m2_test_periods": [{k: f[k] for k in ["fit_end", "calibration_end", "test_start", "test_end"]} for f in m2["folds"]]}
    (preview / "preview-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.browser:
        for name, height in [("allocation", 1150), ("m2-windows", 950), ("lookthrough", 900)]:
            subprocess.run([str(Path(args.browser).resolve()), "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check", "--user-data-dir=" + str(root / ("browser-" + name)), "--screenshot=" + str(preview / (name + ".png")), "--window-size=1400," + str(height), (preview / (name + ".html")).as_uri()], capture_output=True, timeout=40, check=True)
            if not (preview / (name + ".png")).is_file():
                raise RuntimeError("Browser did not create screenshot: " + name)
        manifest["screenshots"] = {name + ".png": sha256((preview / (name + ".png")).read_bytes()).hexdigest() for name, *_ in cases}
        manifest["renderer"] = "Actual Chrome/Edge headless render; visual inspection is a separate step"
        (preview / "preview-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Teaching HTML previews:", preview)


if __name__ == "__main__":
    main()
