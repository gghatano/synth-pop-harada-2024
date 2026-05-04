"""RandomSearchStrategy のユニットテスト (Issue #119, Step 1).

`RandomSearchStrategy` は改善ループの「ベースライン下限」として、
``param_ranges`` で指定された範囲から各 trial 用の config を一様サンプリングする。

検証内容:
- Protocol（``ImproveStrategy``）に適合する
- 同一 seed × 同一 base_settings × 同一 param_ranges で 2 回 next_config を呼ぶと
  生成される Settings 列が決定論的に一致する
- サンプリングされた値は param_ranges 内に収まる
- transition_kind が候補リストの 1 つから選ばれる
"""

from __future__ import annotations

from pathlib import Path

import pytest

from synthpop_jp.config import AnnealingConfig, Settings
from synthpop_jp.improve.strategy import (
    DEFAULT_PARAM_RANGES,
    DEFAULT_TRANSITION_CHOICES,
    ImproveStrategy,
    RandomSearchStrategy,
)


def _base_settings(tmp_path: Path) -> Settings:
    """テスト用の最小 Settings を返す."""
    return Settings(
        seed=42,
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "out",
        annealing=AnnealingConfig(
            T0=100.0,
            alpha=0.99,
            evals_per_agent=10,
            transition_kind="age-change",
            p_change=0.7,
            p_swap=0.3,
            checkpoint_every_n_iters=0,
            trace_enabled=False,
        ),
    )


class TestRandomSearchProtocol:
    """RandomSearchStrategy は ImproveStrategy Protocol に適合する."""

    def test_implements_protocol(self, tmp_path: Path) -> None:
        strategy = RandomSearchStrategy(_base_settings(tmp_path), seed=0)
        assert isinstance(strategy, ImproveStrategy)


class TestRandomSearchDeterminism:
    """同一 seed × 同一入力で 2 回呼ぶと bitwise 一致する."""

    def test_same_seed_same_sequence(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        s1 = RandomSearchStrategy(base, seed=123)
        s2 = RandomSearchStrategy(base, seed=123)

        seq1 = [s1.next_config([]).model_dump(mode="json") for _ in range(5)]
        seq2 = [s2.next_config([]).model_dump(mode="json") for _ in range(5)]

        assert seq1 == seq2

    def test_different_seed_different_sequence(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        s1 = RandomSearchStrategy(base, seed=1)
        s2 = RandomSearchStrategy(base, seed=2)

        seq1 = [s1.next_config([]).model_dump(mode="json") for _ in range(5)]
        seq2 = [s2.next_config([]).model_dump(mode="json") for _ in range(5)]

        # 2 つの seed で全 5 trial が完全一致するのは事実上ありえない
        assert seq1 != seq2


class TestRandomSearchRanges:
    """サンプリングされたパラメータは param_ranges に収まる."""

    def test_p_change_in_range(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        ranges = {
            "p_change": (0.2, 0.8),
            "evals_per_agent": (5, 15),
            "alpha": (0.99, 0.999),
        }
        strategy = RandomSearchStrategy(base, seed=7, param_ranges=ranges)

        for _ in range(20):
            cfg = strategy.next_config([])
            ann = cfg.annealing
            # transition_kind が hybrid のとき constant schedule で p_change + p_swap == 1.0 が必須
            assert 0.2 <= ann.p_change <= 0.8
            assert 5 <= ann.evals_per_agent <= 15
            assert 0.99 <= ann.alpha <= 0.999

    def test_transition_kind_from_choices(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        strategy = RandomSearchStrategy(base, seed=2026)

        seen: set[str] = set()
        for _ in range(50):
            cfg = strategy.next_config([])
            seen.add(cfg.annealing.transition_kind)

        # 50 trials で必ず 1 つ以上の候補からサンプルする
        assert seen.issubset(set(DEFAULT_TRANSITION_CHOICES))
        assert seen  # 空でない

    def test_default_param_ranges_exposed(self) -> None:
        """DEFAULT_PARAM_RANGES が p_change / evals_per_agent / alpha を含む."""
        for key in ("p_change", "evals_per_agent", "alpha"):
            assert key in DEFAULT_PARAM_RANGES


class TestRandomSearchHybridConsistency:
    """transition_kind == "hybrid" のとき p_change + p_swap == 1.0 を保つ."""

    def test_hybrid_p_swap_complementary(self, tmp_path: Path) -> None:
        base = _base_settings(tmp_path)
        # transition_choices を hybrid だけに絞ってチェック
        strategy = RandomSearchStrategy(
            base,
            seed=0,
            transition_choices=("hybrid",),
        )
        for _ in range(10):
            cfg = strategy.next_config([])
            ann = cfg.annealing
            assert ann.transition_kind == "hybrid"
            # constant schedule のときは p_change + p_swap == 1.0
            if ann.p_change_schedule == "constant":
                assert pytest.approx(ann.p_change + ann.p_swap, abs=1e-6) == 1.0
