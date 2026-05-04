"""ParetoStrategy のユニットテスト (Issue #119, Step 4).

ParetoStrategy は spec §14.4 に従い:

1. 内部に candidate pool（``RandomSearchStrategy`` 相当）から各 trial の候補 config を作る
2. history（過去 trial の結果）を 3 目的（``statistical_fit`` / ``utility`` / ``privacy``）の点群に
   写像し non-dominated set を求める
3. 次の trial では non-dominated 点に **近い** config を返す（最初の trial や history が
   フロンティアを構成しないときは pool からランダムに取る）

最小実装の方針:
- 履歴から「最も最近の non-dominated trial」を取り、その config を中心にして
  同 transition_kind を保持しつつ p_change / evals_per_agent / alpha に小さな
  ジッタを乗せた config を返す（"perturb the non-dominated"）。
- 履歴が空 / フロンティアが空のときは RandomSearchStrategy と同じくランダムサンプル
  を返す。
"""

from __future__ import annotations

from pathlib import Path

from synthpop_jp.config import AnnealingConfig, Settings
from synthpop_jp.improve.runner import TrialResult
from synthpop_jp.improve.strategy import ImproveStrategy, ParetoStrategy


def _base_settings(tmp_path: Path) -> Settings:
    return Settings(
        seed=42,
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "out",
        annealing=AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            evals_per_agent=100,
            transition_kind="age-change",
            p_change=0.5,
            p_swap=0.5,
            checkpoint_every_n_iters=0,
            trace_enabled=False,
        ),
    )


def _make_trial(
    base: Settings,
    *,
    trial_id: int,
    statistical_fit: float,
    utility: float,
    privacy: float,
    p_change: float = 0.5,
    evals_per_agent: int = 100,
    alpha: float = 0.99,
    transition_kind: str = "age-change",
) -> TrialResult:
    cfg = base.model_copy(
        update={
            "annealing": base.annealing.model_copy(
                update={
                    "p_change": p_change,
                    "p_swap": 1.0 - p_change,
                    "evals_per_agent": evals_per_agent,
                    "alpha": alpha,
                    "transition_kind": transition_kind,
                },
            ),
        },
    )
    return TrialResult(
        trial_id=trial_id,
        config=cfg,
        metrics={
            "statistical_fit": statistical_fit,
            "utility": utility,
            "privacy": privacy,
        },
    )


class TestParetoProtocol:
    def test_implements_protocol(self, tmp_path: Path) -> None:
        s = ParetoStrategy(_base_settings(tmp_path), seed=0)
        assert isinstance(s, ImproveStrategy)


class TestParetoEmptyHistory:
    """history が空のときは RandomSearch 相当で param_ranges 内をサンプル."""

    def test_empty_history_returns_valid_config(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        s = ParetoStrategy(base, seed=42)
        result = s.next_config([])
        # 最低限 valid な Settings であること
        assert 0.0 <= result.annealing.p_change <= 1.0
        assert result.annealing.evals_per_agent >= 1
        assert 0.0 < result.annealing.alpha <= 1.0


class TestParetoFollowsFrontier:
    """history に non-dominated trial があると、その近傍に config を返す."""

    def test_returns_config_near_non_dominated(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        s = ParetoStrategy(base, seed=2026)

        # trial 1: 全成分で良い → non-dominated
        # trial 2: 全成分で悪い → dominated
        history = [
            _make_trial(
                base,
                trial_id=1,
                statistical_fit=0.1,
                utility=0.1,
                privacy=0.1,
                p_change=0.3,
                evals_per_agent=50,
                alpha=0.995,
                transition_kind="hybrid",
            ),
            _make_trial(
                base,
                trial_id=2,
                statistical_fit=10.0,
                utility=10.0,
                privacy=10.0,
                p_change=0.9,
                evals_per_agent=200,
                alpha=0.95,
                transition_kind="age-swap",
            ),
        ]
        result = s.next_config(history)

        # non-dominated trial 1 の transition_kind を継承
        assert result.annealing.transition_kind == "hybrid"
        # p_change / alpha は trial 1 の近傍にジッタが乗る
        # 非常に厳密でない検証: trial 1 から trial 2 までの距離より小さい
        assert abs(result.annealing.p_change - 0.3) < 0.5
        assert abs(result.annealing.alpha - 0.995) < 0.05


class TestParetoDeterminism:
    """同一 seed × 同一 history で 2 回呼ぶと同じ Settings を返す."""

    def test_same_seed_same_result(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        s1 = ParetoStrategy(base, seed=7)
        s2 = ParetoStrategy(base, seed=7)
        history = [
            _make_trial(
                base,
                trial_id=1,
                statistical_fit=1.0,
                utility=1.0,
                privacy=1.0,
            ),
        ]
        r1 = s1.next_config(history).model_dump(mode="json")
        r2 = s2.next_config(history).model_dump(mode="json")
        assert r1 == r2

    def test_repeat_calls_advance_rng(self, tmp_path: Path) -> None:
        """2 回連続で next_config を呼ぶと 2 つ目は別の Settings."""
        base = _base_settings(tmp_path)
        s = ParetoStrategy(base, seed=1)
        history: list[TrialResult] = []
        cfg1 = s.next_config(history).model_dump(mode="json")
        cfg2 = s.next_config(history).model_dump(mode="json")
        assert cfg1 != cfg2
