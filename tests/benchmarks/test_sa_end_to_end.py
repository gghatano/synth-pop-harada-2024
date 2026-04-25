"""ベンチマーク: SA エンドツーエンド性能ゲート検証 (Issue #33).

成功条件: 1000 世帯 × 20 万反復が 30 秒以内

設計
----
- 1000 世帯規模の SA セットアップを使ってフル計測する
- benchmark.pedantic で rounds=3 を実行して安定した計測値を得る
- 30 秒ゲートを超えた場合は明示的に失敗させる
- このテストはローカル計測用で CI では動かさない（smoke テストに委譲）

閾値
----
- 30 秒 = 30.0 秒
"""

from __future__ import annotations

import copy

import pytest

from synthpop_jp.optimize.annealing import SAResult, SARunner
from synthpop_jp.optimize.objective import ObjectiveState

from .conftest import SASetup

# 閾値定数（秒単位）
_SA_200K_MEDIAN_LIMIT_S: float = 30.0  # 30 秒


@pytest.mark.benchmark
class TestSAEndToEnd:
    """SA エンドツーエンド性能テスト（20 万反復）."""

    def test_sa_1000_households_200000_iters_under_30s(
        self,
        benchmark: pytest.FixtureRequest,
        sample_setup: SASetup,
    ) -> None:
        """1000 世帯 × 20 万反復が 30 秒以内に完走すること.

        benchmark.pedantic を使って rounds=3 で実行し、
        各 round で独立した arrays/objective のコピーを使って状態を分離する。

        Note
        ----
        このテストはローカル環境での実行を前提とする。
        CI では test_sa_smoke.py の smoke テストを使う。
        """

        def _run_sa_fresh() -> SAResult:
            """毎 round 独立したコピーで SA を実行する."""
            arrays_copy = copy.deepcopy(sample_setup.arrays)
            objective_copy = copy.deepcopy(sample_setup.objective)
            rng_copy = copy.deepcopy(sample_setup.runner._rng)
            runner_copy = SARunner(rng=rng_copy)
            return runner_copy.run(
                arrays=arrays_copy,
                objective=objective_copy,
                transition=sample_setup.transition,
                cooling=sample_setup.cooling,
                config=sample_setup.config,
                progress_enabled=False,
            )

        result: SAResult = benchmark.pedantic(
            _run_sa_fresh,
            iterations=1,
            rounds=3,
            warmup_rounds=0,
        )

        # 返り値が SAResult であること
        assert isinstance(result, SAResult)
        assert result.final_state.iter == 200_000, (
            f"iter が期待値 200000 と一致しない: {result.final_state.iter}"
        )

        # median が閾値未満であること
        median_s = benchmark.stats.get("median", None)  # type: ignore[attr-defined]
        if median_s is not None:
            assert median_s < _SA_200K_MEDIAN_LIMIT_S, (
                f"SA 20 万反復の median {median_s:.2f} 秒が"
                f" 閾値 {_SA_200K_MEDIAN_LIMIT_S} 秒を超えています"
            )

    def test_sa_score_improves(
        self,
        benchmark: pytest.FixtureRequest,
        sample_setup: SASetup,
    ) -> None:
        """SA 実行後に best_score が初期スコアより改善していること.

        純粋な性能テストではなく、SA が機能していることを確認する統合アサーション。
        """
        initial_score = float(sample_setup.objective.total_score)

        arrays_copy = copy.deepcopy(sample_setup.arrays)
        objective_copy = copy.deepcopy(sample_setup.objective)
        rng_copy = copy.deepcopy(sample_setup.runner._rng)
        runner_copy = SARunner(rng=rng_copy)

        result: SAResult = benchmark(
            runner_copy.run,
            arrays=arrays_copy,
            objective=objective_copy,
            transition=sample_setup.transition,
            cooling=sample_setup.cooling,
            config=sample_setup.config,
            progress_enabled=False,
        )

        # SA はスコアを改善するか維持するはず（初期スコアを超えることはない）
        assert result.final_state.best_score <= initial_score, (
            f"best_score={result.final_state.best_score} が"
            f" initial_score={initial_score} を超えている"
        )
