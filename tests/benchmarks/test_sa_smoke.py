"""ベンチマーク: SA smoke テスト — CI 用軽量版 (Issue #33).

成功条件: 1000 世帯 × 1 万反復が 5 秒以内

設計
----
- CI（GitHub Actions Ubuntu）での実行を前提とした軽量版
- フル 20 万反復は CI では遅いため 1 万反復に縮小
- 閾値も CI 環境を考慮して 5 秒に設定
- ``make bench`` では本格版（test_sa_end_to_end.py）が実行される

閾値
----
- 5 秒 = 5.0 秒（CI 環境でも余裕を持つ値）
"""

from __future__ import annotations

import copy

import pytest

from synthpop_jp.optimize.annealing import SAResult, SARunner

from .conftest import SASetup

# 閾値定数（秒単位）
_SA_SMOKE_MEDIAN_LIMIT_S: float = 5.0  # 5 秒


@pytest.mark.benchmark
class TestSASmoke:
    """SA smoke テスト（1 万反復 × CI 用）."""

    def test_sa_1000_households_10000_iters_under_5s(
        self,
        benchmark: pytest.FixtureRequest,
        sample_setup_smoke: SASetup,
    ) -> None:
        """1000 世帯 × 1 万反復が 5 秒以内に完走すること.

        CI 上での性能ゲート。フルベンチは test_sa_end_to_end.py を参照。
        """

        def _run_smoke() -> SAResult:
            """smoke 用 SA 実行（smoke 専用の独立した state）."""
            arrays_copy = copy.deepcopy(sample_setup_smoke.arrays)
            objective_copy = copy.deepcopy(sample_setup_smoke.objective)
            rng_copy = copy.deepcopy(sample_setup_smoke.runner._rng)
            runner_copy = SARunner(rng=rng_copy)
            return runner_copy.run(
                arrays=arrays_copy,
                objective=objective_copy,
                transition=sample_setup_smoke.transition,
                cooling=sample_setup_smoke.cooling,
                config=sample_setup_smoke.config,
                progress_enabled=False,
            )

        result: SAResult = benchmark.pedantic(
            _run_smoke,
            iterations=1,
            rounds=1,
            warmup_rounds=0,
        )

        # 返り値が SAResult であること
        assert isinstance(result, SAResult)
        assert result.final_state.iter == 10_000, (
            f"iter が期待値 10000 と一致しない: {result.final_state.iter}"
        )

        # median が閾値未満であること
        median_s = benchmark.stats.get("median", None)  # type: ignore[attr-defined]
        if median_s is not None:
            assert median_s < _SA_SMOKE_MEDIAN_LIMIT_S, (
                f"SA smoke の median {median_s:.2f} 秒が"
                f" 閾値 {_SA_SMOKE_MEDIAN_LIMIT_S} 秒を超えています"
            )
