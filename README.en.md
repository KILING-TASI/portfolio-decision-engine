# Portfolio scenario and factor research

Review portfolio scenarios, cash needs, point-in-time factor panels and experiment histories. Full historical analysis uses optional analysis dependencies; base installation remains lightweight.

[中文说明](README.md) · [Release v0.13.1](https://github.com/KILING-TASI/portfolio-decision-engine/releases/tag/v0.13.1) · [Skill instructions](SKILL.md) · [Input preparation](BEGINNER.md)

Current release: **regular release**. Python **3.10+**. Base runtime dependencies: none. Optional extras: `analysis`. See [USAGE.md](USAGE.md) for scope.

## First run

Download the [complete source ZIP](https://github.com/KILING-TASI/portfolio-decision-engine/releases/download/v0.13.1/portfolio-decision-engine-v0.13.1-source.zip), extract it and enter the directory containing `try_demo.py`:

```console
python try_demo.py --no-open --out-dir reports/first-demo
```

Alternatively, clone `https://github.com/KILING-TASI/portfolio-decision-engine.git`, run `cd portfolio-decision-engine`, then execute the command above. Open the report at the path printed by the command. Teaching data is synthetic; use a new output directory and keep prior reports.

## CLI and Skill

From the source directory:

```console
python -m pip install .
portfolio-decision-engine --help
```

Repository and distribution: `portfolio-decision-engine`. Primary CLI: `portfolio-decision-engine`. Skill name in SKILL.md: `portfolio-decision-engine`. Installing the CLI does not register the Skill; configure the complete resources in an assistant that supports local Skills. Build or optional dependencies may require network access during installation.

## Scope and rights

Read the [Chinese capability boundaries](README.md#能力与边界) and [detailed commands](USAGE.md). Each tool can run independently; cross-tool calls need explicit configuration. Successful execution does not authenticate source documents, fill missing data or establish investment validity. No trade execution or guaranteed returns.

Original code uses MIT. Third-party code and documents/data retain their own licenses and rights. Default-branch documentation edits do not rewrite released archives or frozen results.

[Changes](CHANGELOG.md) · [Third-party rights](THIRD_PARTY_NOTICES.md) · [Contribution](CONTRIBUTING.md) · [Security](SECURITY.md)

Factor review: `portfolio-decision-engine factor exposure --input examples/factor-review/exposure.json --out-dir reports/factor-exposure`. Base factor, exposure, cost and cash checks use the standard library; multi-factor modeling and budget computation require the optional analysis extra. Research spreads are separate from account returns, and missing coverage stays unknown. See [input contracts and limits](FACTOR_REVIEW.md).

## Optional CNN research

Install `.[cnn]` for the original CPU OHLCV Conv1d regression module. Validation and evidence bridging use the standard library. See [CNN contracts and examples (Chinese)](CNN_RESEARCH.md). Scores are not probabilities. Retrospective models do not certify historical availability or A-share performance.

Explicit candle rules and gross-outcome studies use `pattern identify/study` without optional dependencies. `cnn compare` compares OHLCV, train-calibrated rules and causal geometry augmentation on the same frozen test samples. See [pattern contracts](PATTERN_RESEARCH.md).

Factor generation and CNN research now have an independent home: [cn-factor-research](https://github.com/KILING-TASI/factor-research). Existing CNN/pattern entries delegate to installed v0.1.x/v0.2.x or retain the frozen v0.12 fallback. No mandatory sibling dependency or automatic install.
