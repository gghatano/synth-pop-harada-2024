"""許容幅テストのスケルトン（Phase 2 で実装予定）.

決定性テスト（bitwise 一致）とは別に、SA の収束後スコアが
初期スコアに対して一定割合（例: ±1%）以内に収まることを検証します。

Phase 2 の SA 実装が完了したら、このファイルのスキップを解除して
テスト本体を記述してください。

Notes
-----
- 決定性テストとは分離して管理します（``test_determinism.py`` を参照）。
- ``hypothesis`` の seed はここでは扱いません（テスト側の乱数は別系統）。
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="phase 2 で実装予定: SA MVP 完成後にスキップを解除する")
class TestApproximateConvergence:
    """SA 実行後のスコアが許容幅 (±1%) に収まることを検証する.

    Phase 2 の Exit 条件:
      - seed=42 で evals_per_agent=1000 を実行したとき、
        best_score が初期スコアの 30% 以下になること。

    参考: action-plan.md §3.4 Phase 2 Exit 条件
    """

    def test_best_score_below_threshold(self) -> None:
        """SA 後の best_score が初期スコアの 30% 以下であることを確認する.

        TODO (Phase 2): SA runner が実装されたら、以下の疑似コードを実装する::

            from synthpop_jp.rng import SeedRegistry
            from synthpop_jp.optimize.runner import run_sa

            reg = SeedRegistry(root=42)
            result = run_sa(reg=reg, evals_per_agent=1000, ...)
            assert result.best_score <= result.initial_score * 0.30
        """
        raise NotImplementedError("Phase 2 で実装する")

    def test_score_within_tolerance_across_seeds(self) -> None:
        """複数の seed で best_score が ±1% 以内のばらつきであることを確認する.

        TODO (Phase 2): 複数 seed でのスコアばらつきを許容幅テストで保護する。
        """
        raise NotImplementedError("Phase 2 で実装する")
