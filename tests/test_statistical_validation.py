import numpy as np
import pytest

from portfolio_engine.bootstrap import quantile_interval
from portfolio_engine.risk import expected_shortfall
from portfolio_engine.statistical_cases import statistical_cases
from portfolio_engine.validation import InputError


def test_extreme_confidence_cannot_turn_worst_loss_into_zero():
    r = expected_shortfall([0] * 19 + [-.4], np.nextafter(1., 0.))
    assert r["es"] == pytest.approx(.4)
    assert r["tail_sample_status"] == "insufficient_data"
    with pytest.raises(InputError): expected_shortfall([[0, -.4]])


def test_order_bound_cannot_claim_unsupported_tail_coverage():
    # With 20 samples, P(all observations below the true p95) = .95**20 > .025.
    # A sample-max upper endpoint cannot support the requested two-sided 95% CI.
    assert .95**20 > .025
    with pytest.raises(InputError, match="finite two-sided"):
        quantile_interval(np.linspace(0, 1, 20))
    with pytest.raises(InputError): quantile_interval(np.r_[np.arange(100), np.nan])


def test_original_counterexamples_expose_model_and_selection_limits():
    r = statistical_cases()
    assert all(r["tail_mc"]["acceptance"].values())
    assert all(r["selection_isolation"]["acceptance"].values())
    audit = r["selection_isolation"]["local_selection_audit"]
    assert audit["generated_candidates_across_folds"] >= 2
    assert audit["candidate_block_evaluations"] == audit["generated_candidates_across_folds"] * 2
    assert audit["independent_research_trials"] is None
