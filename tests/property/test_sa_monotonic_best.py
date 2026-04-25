"""Property test: SARunner の best_score は単調非増加 — Issue #34.

SA の設計上、best_score は「これまでに発見した最良スコア」であり、
一度改善されたら悪化することはない。
この単調非増加性（monotonic non-increasing）を hypothesis で検証する。

なぜ単調性が重要か
-------------------
best_score が増加するということは、「より悪い解を best とみなした」ことを意味する。
これは SA の実装バグのサインであり、最適化の方向が狂う。
scores リストは best_score の更新履歴を保持する（SAResult.scores）ため、
この順序が単調非増加であることをテストする。
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from synthpop_jp.config import AnnealingConfig
from synthpop_jp.optimize.annealing import SAResult, SARunner
from synthpop_jp.optimize.cooling import ExponentialCooling
from synthpop_jp.optimize.transitions import AgeChangeTransition
from synthpop_jp.rng import SeedRegistry

from .conftest import InitStats, ObjectiveInput, fresh_objective

# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    n_iters=st.integers(min_value=50, max_value=300),
)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_best_score_monotonic_non_increasing(
    seed: int,
    n_iters: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """SARunner.run の SAResult.scores が単調非増加であることを検証する.

    SAResult.scores は best_score が更新されるたびに追記されるリストであり、
    初期スコアから始まって改善のみが記録される。
    したがって隣接要素の差分 (scores[i+1] - scores[i]) は常に <= 0 のはずである。

    検証手順:
    1. 任意の seed と n_iters で SARunner.run を実行する
    2. result.scores の隣接差分を計算する
    3. すべての差分が <= 0 であることを確認する
    """
    obj = fresh_objective(sample_stats, objective_input)
    arrays = obj.arrays
    demo_rows = objective_input.demographic_by_age_sex

    rng_transition = SeedRegistry(root=seed).rng("sa_transition")
    rng_runner = SeedRegistry(root=seed).rng("sa_runner")

    transition = AgeChangeTransition(
        arrays=arrays,
        demo_by_age_sex=demo_rows,
        rng=rng_transition,
    )

    config = AnnealingConfig(
        T0=100.0,
        alpha=0.99,
        max_iters=n_iters,
        evals_per_agent=0,
        trace_enabled=False,
        checkpoint_every_n_iters=0,
        checkpoint_dir=None,
    )
    cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
    runner = SARunner(rng=rng_runner)

    result: SAResult = runner.run(
        arrays=arrays,
        objective=obj,
        transition=transition,
        cooling=cooling,
        config=config,
        progress_enabled=False,
    )

    scores = result.scores
    assert len(scores) >= 1, "scores リストが空である（初期スコアが含まれていない）"

    # 隣接差分がすべて <= 0 であることを確認する
    for i in range(len(scores) - 1):
        diff = scores[i + 1] - scores[i]
        assert diff <= 0.0, (
            f"best_score が増加している: "
            f"scores[{i}]={scores[i]:.6f} -> scores[{i + 1}]={scores[i + 1]:.6f}, "
            f"diff={diff:.6f}, seed={seed}, n_iters={n_iters}"
        )


@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    n_iters=st.integers(min_value=50, max_value=200),
)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_best_score_never_exceeds_initial_score(
    seed: int,
    n_iters: int,
    sample_stats: InitStats,
    objective_input: ObjectiveInput,
) -> None:
    """SA 実行後の best_score が初期スコアを超えないことを検証する.

    best_score は初期スコアからのみ改善方向に進む。
    initial_score 以上（=悪化）になることはない。
    """
    obj = fresh_objective(sample_stats, objective_input)
    initial_score = obj.total_score
    arrays = obj.arrays
    demo_rows = objective_input.demographic_by_age_sex

    rng_transition = SeedRegistry(root=seed).rng("sa_transition")
    rng_runner = SeedRegistry(root=seed).rng("sa_runner")

    transition = AgeChangeTransition(
        arrays=arrays,
        demo_by_age_sex=demo_rows,
        rng=rng_transition,
    )

    config = AnnealingConfig(
        T0=100.0,
        alpha=0.99,
        max_iters=n_iters,
        evals_per_agent=0,
        trace_enabled=False,
        checkpoint_every_n_iters=0,
        checkpoint_dir=None,
    )
    cooling = ExponentialCooling(T0=config.T0, alpha=config.alpha)
    runner = SARunner(rng=rng_runner)

    result: SAResult = runner.run(
        arrays=arrays,
        objective=obj,
        transition=transition,
        cooling=cooling,
        config=config,
        progress_enabled=False,
    )

    final_best_score = result.final_state.best_score

    assert final_best_score <= initial_score + 1e-9, (
        f"best_score ({final_best_score:.6f}) が初期スコア ({initial_score:.6f}) を超えた: "
        f"seed={seed}, n_iters={n_iters}"
    )
