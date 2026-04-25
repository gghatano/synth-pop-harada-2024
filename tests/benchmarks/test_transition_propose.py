"""ベンチマーク: AgeChangeTransition.propose の性能ゲート検証 (Issue #33).

成功条件: propose 1 回の実行時間 < 10 μs (median)

設計
----
- 1000 世帯規模の AgeChangeTransition を使って現実的な負荷を再現する
- benchmark.stats.median で閾値を判定する
- propose() は乱数を使うため benchmark での繰り返し呼び出しでも副作用がない（配列は変更しない）

閾値
----
- 10 μs = 1e-5 秒
"""

from __future__ import annotations

import pytest

from synthpop_jp.optimize.transitions import AgeChangeTransition

# 閾値定数（秒単位）
_PROPOSE_MEDIAN_LIMIT_S: float = 1e-5  # 10 μs


@pytest.mark.benchmark
class TestAgeChangeTransitionPropose:
    """AgeChangeTransition.propose の性能テスト."""

    def test_age_change_propose_under_10us(
        self,
        benchmark: pytest.FixtureRequest,
        sample_transition: AgeChangeTransition,
    ) -> None:
        """propose 1 回が 10 μs 以内であること.

        1000 世帯（約 2660 人）規模の AgeChangeTransition に対して、
        ランダムな person 選択と新年齢サンプリングを計測する。
        """
        result = benchmark(sample_transition.propose)

        # 返り値は (person_idx, new_age) のタプル
        assert isinstance(result, tuple)
        assert len(result) == 2

        person_idx, new_age = result
        assert isinstance(person_idx, int)
        assert isinstance(new_age, int)
        assert 0 <= new_age <= 100

        # median が閾値未満であること
        median_s = benchmark.stats.get("median", None)  # type: ignore[attr-defined]
        if median_s is not None:
            assert median_s < _PROPOSE_MEDIAN_LIMIT_S, (
                f"propose の median {median_s * 1e6:.1f} μs が"
                f" 閾値 {_PROPOSE_MEDIAN_LIMIT_S * 1e6:.1f} μs を超えています"
            )

    def test_propose_returns_valid_person_idx(
        self,
        benchmark: pytest.FixtureRequest,
        sample_transition: AgeChangeTransition,
    ) -> None:
        """propose が常に有効な person_idx を返すこと."""
        n_persons = sample_transition._arrays.n_persons

        result = benchmark(sample_transition.propose)
        person_idx, _ = result

        assert 0 <= person_idx < n_persons, (
            f"person_idx={person_idx} が範囲 [0, {n_persons}) 外"
        )
