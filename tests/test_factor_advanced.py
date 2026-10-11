# SPDX-License-Identifier: MIT
import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from portfolio_engine.factor_advanced import multi, budget
from portfolio_engine.attribution import factor_attribution

ROOT = Path(__file__).resolve().parents[1]


def spec(name):
    return json.loads((ROOT / 'examples/factor-review' / (name + '.json')).read_text(encoding='utf-8'))


def test_neutralized_orthogonal_scores_are_finite_and_declared():
    result = multi(spec('multi'))
    assert len(result['scores']) == 15
    assert all(np.isfinite(r['score']) for r in result['scores'])
    assert result['neutralize'] == 'industry-log-market-cap'
    assert result['orthogonalize'] is True


def test_rank_deficiency_blocks_instead_of_degraded_scores():
    draft = spec('multi')
    for row in draft['observations']: row['factors']['quality'] = row['factors']['value'] * 2
    result = multi(draft)
    assert result['scores'] is None
    assert '秩不足' in result['reason']


def test_missing_control_and_factor_coverage_visible():
    draft = spec('multi'); draft['observations'][0]['factors']['value'] = None
    draft['observations'][1]['industry'] = None
    result = multi(draft)
    assert result['observations'] == 13 and len(result['excluded']) == 2


def test_high_vif_is_diagnostic_with_full_rank():
    draft = spec('multi'); draft['neutralize'] = 'none'; draft['orthogonalize'] = False
    for i, row in enumerate(draft['observations']): row['factors']['quality'] = i + .1 * ((i * 7) % 5)
    result = multi(draft)
    assert result['status'] == 'degraded' and result['scores'] is not None
    assert max(result['vif'].values()) > 10


@pytest.mark.parametrize('kind', ['constant', 'sample', 'controls'])
def test_invalid_conditions_do_not_generate_composite(kind):
    draft = spec('multi')
    if kind == 'constant':
        for row in draft['observations']: row['factors']['value'] = 1
    elif kind == 'sample': draft['observations'] = draft['observations'][:6]
    else:
        for row in draft['observations']: row['marketCap'] = 100
    assert multi(draft)['scores'] is None


def test_controls_and_factors_available_before_snapshot():
    draft = spec('multi'); draft['observations'][0]['controlsEvidence']['availableAt'] = '2026-01-06T10:00:00+08:00'
    with pytest.raises(ValueError): multi(draft)


def budget_spec():
    draft = spec('budget'); draft['compute'] = True
    draft['account']['initialCash'] = 0; draft['account']['initialHoldings'] = {'teaching:A': 100}
    draft['account']['costBps'] = 0; draft['account']['periods'] = []
    start = datetime.fromisoformat('2026-01-01T10:00:00+08:00')
    for i in range(25):
        at = start + timedelta(days=i); end = at + timedelta(days=1)
        draft['account']['periods'].append({'startAt': at.isoformat(), 'endAt': end.isoformat(),
                                          'availableAt': end.isoformat(), 'source': '原创教学',
                                          'trades': [], 'assetReturns': {'teaching:A': [.01, -.02, .005][i % 3]}})
    draft['budgetParameters'] = {'budget': .25, 'horizon': 10, 'paths': 200, 'block_lengths': [2],
                                 'seed': 42, 'mc_tolerance': .2, 'max_paths': 200, 'strict': True, 'periods': 252}
    return draft


def test_budget_reuses_conditional_model_and_serializes():
    result = budget(budget_spec())
    json.dumps(result, allow_nan=False)
    assert result['status'] == 'conditional_model_result'
    assert result['budgetResult']['error_scope'].startswith('conditional Monte Carlo')
    assert result['bridge']['simulationCosts'] == 0


def test_budget_excessive_resource_request_rejected():
    draft = budget_spec(); draft['budgetParameters']['horizon'] = 100000
    with pytest.raises(ValueError): budget(draft)


def test_regression_existing_fields_preserved_with_explanation():
    rng = np.random.default_rng(42)
    factors = pd.DataFrame(rng.normal(size=(30, 2)), index=pd.date_range('2026-01-01', periods=30), columns=['a', 'b'])
    returns = factors['a'] * .2 + pd.Series(rng.normal(size=30) * .1, index=factors.index)
    result = factor_attribution(returns, factors)
    assert all(key in result for key in ('p_values', 't_values', 'confidence_intervals', 'coefficients'))
    assert 'future-profit' in result['statistical_scope']['p_values']
    assert result['statistical_scope']['sample_end'] == str(factors.index[-1])
    with pytest.raises(ValueError): factor_attribution(returns, factors, lags=True)
