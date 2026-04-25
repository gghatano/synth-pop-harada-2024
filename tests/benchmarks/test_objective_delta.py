"""ベンチマーク: ObjectiveState.propose_change の性能ゲート検証 (Issue #33).

成功条件: propose_change 1 回の実行時間 < 100 μs (median)

設計
----
- 1000 世帯規模の ObjectiveState を使って現実的な負荷を再現する
- benchmark.stats.median で閾値を判定する
- benchmark 自体は pytest-benchmark で計測し、結果は docs/reports/phase-02-benchmarks.md に記録する

閾値
----
- 100 μs = 1e-4 秒
"""

from __future__ import annotations

import pytest

from synthpop_jp.optimize.objective import ObjectiveState

# 閾値定数（秒単位）
_PROPOSE_CHANGE_MEDIAN_LIMIT_S: float = 1e-4  # 100 μs


@pytest.mark.benchmark
class TestObjectiveProposeDelta:
    """ObjectiveState.propose_change の性能テスト."""

    def test_propose_change_under_100us(
        self,
        benchmark: pytest.FixtureRequest,
        sample_objective: ObjectiveState,
    ) -> None:
        """propose_change 1 回が 100 μs 以内であること.

        1000 世帯（約 2660 人）規模の ObjectiveState に対して、
        最初の person（index=0）の age を ±1 した propose_change を計測する。
        """
        # 計測対象: person 0 の age を +1 した場合のスコア差分
        current_age = int(sample_objective.arrays.age[0])
        new_age = current_age + 1 if current_age < 100 else current_age - 1

        result = benchmark(sample_objective.propose_change, 0, new_age)

        # 返り値は float（スコア差分）
        assert isinstance(result, float)

        # median が閾値未満であること
        median_s = benchmark.stats.get("median", None)  # type: ignore[attr-defined]
        if median_s is not None:
            assert median_s < _PROPOSE_CHANGE_MEDIAN_LIMIT_S, (
                f"propose_change の median {median_s * 1e6:.1f} μs が"
                f" 閾値 {_PROPOSE_CHANGE_MEDIAN_LIMIT_S * 1e6:.1f} μs を超えています"
            )

    def test_propose_change_no_side_effect_during_bench(
        self,
        benchmark: pytest.FixtureRequest,
        sample_objective: ObjectiveState,
    ) -> None:
        """ベンチマーク実行中も total_score が変化しないこと（副作用なし検証）."""
        before_score = sample_objective.total_score
        current_age = int(sample_objective.arrays.age[0])
        new_age = current_age + 1 if current_age < 100 else current_age - 1

        benchmark(sample_objective.propose_change, 0, new_age)

        # benchmark が繰り返し呼び出しても total_score は変わらない
        assert abs(sample_objective.total_score - before_score) < 1e-9, (
            f"propose_change がベンチマーク中に副作用を起こした: "
            f"before={before_score}, after={sample_objective.total_score}"
        )
