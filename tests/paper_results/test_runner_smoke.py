"""Smoke + determinism tests for paper_results._shared.runner (Issue #115 Step 2).

`runner.run_one(seed, transition_kind, evals_per_agent, n_households)` を
極小 N（200 世帯）で 1 回呼び出し、戻り値が dict で best_score / stat_l1 を
含むことを確認する。さらに同じ seed で 2 回呼んで bitwise 一致を確認する
（決定論性、spec §19.3）。
"""

from __future__ import annotations

import pytest
from paper_results._shared.runner import RunResult, run_one


@pytest.mark.parametrize("transition_kind", ["age_change", "age_swap"])
def test_runner_smoke_returns_run_result(transition_kind: str) -> None:
    """極小 N で 1 回回せて RunResult が返る."""
    result = run_one(
        seed=1,
        transition_kind=transition_kind,
        evals_per_agent=200,
        n_households=200,
    )

    assert isinstance(result, RunResult)
    assert result.seed == 1
    assert result.transition_kind == transition_kind
    assert result.best_score >= 0.0
    assert result.elapsed_seconds >= 0.0
    # 21 統計（A,B,C + 9 ft × 2 sex）の L1 を含む
    assert isinstance(result.stat_l1, dict)
    assert len(result.stat_l1) >= 3


def test_runner_is_deterministic_for_same_seed() -> None:
    """同じ seed × 同じ config で 2 回呼ぶと bitwise 一致 (spec §19.3)."""
    a = run_one(seed=42, transition_kind="age_change", evals_per_agent=200, n_households=200)
    b = run_one(seed=42, transition_kind="age_change", evals_per_agent=200, n_households=200)

    assert a.best_score == b.best_score
    assert a.stat_l1 == b.stat_l1


def test_runner_supports_hybrid() -> None:
    """hybrid 遷移も runner から呼べる."""
    result = run_one(
        seed=3,
        transition_kind="hybrid",
        evals_per_agent=200,
        n_households=200,
    )

    assert result.transition_kind == "hybrid"
    assert result.best_score >= 0.0
