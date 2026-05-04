"""Bitwise determinism check for paper_results runner (Issue #115).

spec §19.3: 同一 seed × 同一 config × `uv sync --frozen` 環境では best_score が
bitwise 一致する。`run_one` を 2 回呼んで dict / float レベルで完全一致するかを
極小 N で確認する（CI 上常時走らせる）。
"""

from __future__ import annotations

import pytest
from paper_results._shared.runner import run_one


@pytest.mark.parametrize("transition_kind", ["age_change", "age_swap", "hybrid"])
def test_run_one_is_bitwise_deterministic(transition_kind: str) -> None:
    """同じ seed で 2 回呼んで best_score / stat_l1 が完全一致."""
    a = run_one(
        seed=99,
        transition_kind=transition_kind,
        evals_per_agent=200,
        n_households=100,
    )
    b = run_one(
        seed=99,
        transition_kind=transition_kind,
        evals_per_agent=200,
        n_households=100,
    )

    assert a.best_score == b.best_score, (
        f"best_score diverged for {transition_kind}: a={a.best_score} b={b.best_score}"
    )
    assert a.stat_l1 == b.stat_l1, (
        f"stat_l1 diverged for {transition_kind}: a={a.stat_l1} b={b.stat_l1}"
    )


def test_run_one_differs_for_different_seeds() -> None:
    """別 seed では best_score がほぼ一致しないことを確認（決定論性が動的に効くか）."""
    a = run_one(seed=100, transition_kind="age_change", evals_per_agent=200, n_households=100)
    b = run_one(seed=200, transition_kind="age_change", evals_per_agent=200, n_households=100)

    # best_score 自体は同じになる可能性もある（収束してしまえば）が、stat_l1 内訳は
    # 経路に依存するので、どちらかが異なれば「決定論的だが seed に依存」と言える。
    assert a.best_score != b.best_score or a.stat_l1 != b.stat_l1
