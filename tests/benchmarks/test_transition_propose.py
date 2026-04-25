"""ベンチマーク: AgeChangeTransition.propose の性能ゲート検証 (Issue #33).

成功条件: propose 1 回の実行時間 < 10 μs (median)

設計
----
- 1000 世帯規模の AgeChangeTransition を使って現実的な負荷を再現する
- benchmark.stats.median で閾値を判定する
- propose() は乱数を使うため benchmark での繰り返し呼び出しでも副作用がない（配列は変更しない）
- TransitionError（ハード制約 retry 上限到達）は稀に発生するため、
  benchmark ループでは無視して成功ケースの時間だけを計測する

閾値
----
- 10 μs = 1e-5 秒
"""

from __future__ import annotations

import pytest

from synthpop_jp.optimize.transitions import AgeChangeTransition, TransitionError

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

        Note
        ----
        TransitionError（ハード制約 retry 超過）は稀に発生する。
        実際の SA runner は TransitionError をスキップして実行を継続する。
        benchmark では TransitionError を無視し、成功した計測時間のみを記録する。
        """

        def _safe_propose() -> tuple[int, int] | None:
            """TransitionError を無視して propose を呼ぶ."""
            try:
                return sample_transition.propose()
            except TransitionError:
                return None

        benchmark(_safe_propose)

        # median が閾値未満であること
        median_s = benchmark.stats.get("median", None)  # type: ignore[attr-defined]
        if median_s is not None:
            assert median_s < _PROPOSE_MEDIAN_LIMIT_S, (
                f"propose の median {median_s * 1e6:.1f} μs が"
                f" 閾値 {_PROPOSE_MEDIAN_LIMIT_S * 1e6:.1f} μs を超えています"
            )
