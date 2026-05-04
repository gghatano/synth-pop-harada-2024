"""best config selector のユニットテスト (Issue #119, Step 5).

``select_best(history, objective)`` は 4 種類の objective:

- ``"composite"``: ``best_score`` (SA の終了スコア合計、小さいほど良い)
- ``"statistical_fit"``: ``aggregate.l1.total`` 系の代理キー
- ``"utility"``: ``utility`` 系の代理キー
- ``"privacy"``: ``privacy`` 系の代理キー

を持ち、最小値を持つ TrialResult を返す。同点なら trial_id 最小を返す（決定性）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from synthpop_jp.config import AnnealingConfig, Settings
from synthpop_jp.improve.runner import TrialResult
from synthpop_jp.improve.selector import select_best


def _trial(
    trial_id: int,
    *,
    composite: float,
    statistical_fit: float = 0.0,
    utility: float = 0.0,
    privacy: float = 0.0,
) -> TrialResult:
    cfg = Settings(
        input_dir=Path("/tmp"),
        output_dir=Path("/tmp"),
        annealing=AnnealingConfig(),
    )
    return TrialResult(
        trial_id=trial_id,
        config=cfg,
        metrics={
            "best_score": composite,
            "statistical_fit": statistical_fit,
            "utility": utility,
            "privacy": privacy,
        },
    )


class TestSelectBestComposite:
    def test_returns_min_best_score(self) -> None:
        history = [_trial(1, composite=10.0), _trial(2, composite=5.0), _trial(3, composite=8.0)]
        best = select_best(history, "composite")
        assert best.trial_id == 2

    def test_tie_returns_smallest_trial_id(self) -> None:
        history = [_trial(2, composite=5.0), _trial(1, composite=5.0), _trial(3, composite=8.0)]
        best = select_best(history, "composite")
        assert best.trial_id == 1


class TestSelectBestPerObjective:
    @pytest.mark.parametrize(
        ("objective", "winner_id"),
        [
            ("statistical_fit", 1),
            ("utility", 2),
            ("privacy", 3),
        ],
    )
    def test_per_objective_selection(self, objective: str, winner_id: int) -> None:
        history = [
            _trial(1, composite=10.0, statistical_fit=0.1, utility=10.0, privacy=10.0),
            _trial(2, composite=10.0, statistical_fit=10.0, utility=0.1, privacy=10.0),
            _trial(3, composite=10.0, statistical_fit=10.0, utility=10.0, privacy=0.1),
        ]
        best = select_best(history, objective)  # type: ignore[arg-type]
        assert best.trial_id == winner_id


class TestSelectBestEmptyRaises:
    def test_empty_history_raises(self) -> None:
        with pytest.raises(ValueError, match="history"):
            select_best([], "composite")


class TestSelectBestMissingMetricFallback:
    """メトリクスが欠けている trial は +inf 扱い → 最後尾に."""

    def test_missing_metric_treated_as_inf(self) -> None:
        history = [
            TrialResult(
                trial_id=1,
                config=Settings(
                    input_dir=Path("/tmp"),
                    output_dir=Path("/tmp"),
                    annealing=AnnealingConfig(),
                ),
                metrics={"best_score": 5.0},
            ),
            TrialResult(
                trial_id=2,
                config=Settings(
                    input_dir=Path("/tmp"),
                    output_dir=Path("/tmp"),
                    annealing=AnnealingConfig(),
                ),
                metrics={},  # best_score なし → +inf
            ),
        ]
        best = select_best(history, "composite")
        assert best.trial_id == 1
