import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from portfolio_engine.observed_review import review, strict_load

ROOT = Path(__file__).parents[1]
REFERENCE = json.loads((ROOT / "examples/observed-review-reference.json").read_text("utf8"))


def assert_legacy_result(actual, expected):
    actual, expected = dict(actual), dict(expected)
    a, b = actual.pop("xirrPct"), expected.pop("xirrPct")
    assert actual == expected
    assert type(a) is type(b)
    if a is not None:
        # The original math.exp/log1p algorithm varies by a few libm ULPs
        # across OSes; only this field gets a narrow, magnitude-aware bound.
        assert abs(a-b) <= 8 * max(math.ulp(a), math.ulp(b))


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["case"])
def test_full_original_observed_result_is_preserved(case):
    assert_legacy_result(review(case["input"])["result"], case["expected_result"])


@pytest.mark.parametrize("case", REFERENCE["failures"], ids=lambda c: c["case"])
def test_original_failures_are_preserved(case):
    with pytest.raises(ValueError) as error:
        review(case["input"])
    assert str(error.value) == case["expected_error"]


@pytest.mark.parametrize("key,value", [("schema", "v2"),
    ("requested_method_version", "observed-flow-link-and-native-xirr-v1"),
    ("fee_basis", "deduct-again"), ("frozen_basis", "available"),
    ("settlement_basis", "guaranteed"), ("valuation_timing", "before-return")])
def test_unknown_version_or_changed_model_does_not_silently_upgrade(key, value):
    spec = copy.deepcopy(REFERENCE["cases"][0]["input"])
    spec[key] = value
    with pytest.raises(ValueError):
        review(spec)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}'])
def test_ambiguous_or_nonfinite_json_rejected(raw):
    with pytest.raises(ValueError):
        strict_load(raw)


def command(source, out):
    bootstrap = "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('portfolio_engine.observed_review',run_name='__main__')"
    return [sys.executable, "-I", "-S", "-c", bootstrap, str(ROOT / "src"), str(source), "--out", str(out)]


def test_standard_library_only_cli_freezes_input_and_does_not_overwrite(tmp_path):
    source = ROOT / "examples/observed-review-demo.json"
    out = tmp_path / "observed"
    env = dict(os.environ, PYTHONIOENCODING="utf8")
    completed = subprocess.run(command(source, out), capture_output=True, env=env)
    assert completed.returncode == 0, completed.stderr.decode("utf8")
    result = json.loads(completed.stdout)
    assert_legacy_result(result["result"], REFERENCE["cases"][0]["expected_result"])
    assert (out / "source-input.json").read_bytes() == source.read_bytes()
    assert result["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = json.loads((out / "report-manifest.json").read_text("utf8"))
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == expected
    assert subprocess.run(command(source, out), capture_output=True, env=env).returncode == 2


def test_stdin_metadata_snapshot_and_failed_version(tmp_path):
    env = dict(os.environ, PYTHONIOENCODING="utf8")
    case = next(c for c in REFERENCE["cases"] if c["case"] == "metadata-preserved-input")
    raw = json.dumps(case["input"], ensure_ascii=False).encode("utf8")
    out = tmp_path / "stdin"
    result = subprocess.run(command("-", out), input=raw, capture_output=True, env=env)
    assert result.returncode == 0
    assert (out / "source-input.json").read_bytes() == raw
    assert_legacy_result(json.loads(result.stdout)["result"], case["expected_result"])
    spec = copy.deepcopy(case["input"])
    spec["requested_method_version"] = "unknown"
    blocked = tmp_path / "blocked"
    result = subprocess.run(command("-", blocked), input=json.dumps(spec).encode(), capture_output=True, env=env)
    assert result.returncode == 2 and not blocked.exists()
