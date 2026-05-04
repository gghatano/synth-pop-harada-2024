"""決定性テスト (Issue #119, Step 6).

同一 ``base_settings`` × 同一 ``strategy_name`` × 同一 ``seed`` で
``run_improve_loop`` を 2 回呼ぶと、``best_config.yaml`` が **bitwise 一致**
する（spec §19.3、SeedRegistry 経由の bitwise 再現）。

検証は 3 戦略すべてで行う:

- ``random_search``: 戦略内部 RNG が再現される
- ``rule_based``: 純粋関数（決定論的）
- ``pareto``: ジッタ用 RNG が再現される
"""

from __future__ import annotations

from pathlib import Path

import pytest

from synthpop_jp.config import AnnealingConfig, Settings
from synthpop_jp.improve.runner import run_improve_loop

SAMPLE_CASE = Path(__file__).resolve().parents[2] / "data" / "sample_case"


def _smoke_settings(out_dir: Path) -> Settings:
    return Settings(
        seed=42,
        input_dir=SAMPLE_CASE,
        output_dir=out_dir,
        annealing=AnnealingConfig(
            T0=10.0,
            alpha=0.99,
            evals_per_agent=2,
            max_iters=200,
            transition_kind="age-change",
            checkpoint_every_n_iters=0,
            trace_enabled=False,
            log_every_n_iters=10000,
        ),
    )


@pytest.mark.slow
@pytest.mark.parametrize("strategy_name", ["random_search", "rule_based", "pareto"])
def test_best_config_yaml_bitwise_identical(tmp_path: Path, strategy_name: str) -> None:
    """同一 seed × 同一戦略 × 同一 base_settings で 2 回呼ぶと best_config.yaml が一致."""
    settings_a = _smoke_settings(tmp_path / "run_a")
    settings_b = _smoke_settings(tmp_path / "run_b")

    result_a = run_improve_loop(
        settings_a,
        strategy_name=strategy_name,  # type: ignore[arg-type]
        n_trials=2,
        seed=99,
        output_root=tmp_path / "out_a",
    )
    result_b = run_improve_loop(
        settings_b,
        strategy_name=strategy_name,  # type: ignore[arg-type]
        n_trials=2,
        seed=99,
        output_root=tmp_path / "out_b",
    )

    yaml_a = (result_a.output_dir / "best_config.yaml").read_bytes()
    yaml_b = (result_b.output_dir / "best_config.yaml").read_bytes()
    assert yaml_a == yaml_b, "best_config.yaml が bitwise 一致しません"


@pytest.mark.slow
def test_history_metrics_identical(tmp_path: Path) -> None:
    """history の各 trial のメトリクスも 2 回実行で一致する."""
    settings_a = _smoke_settings(tmp_path / "run_a")
    settings_b = _smoke_settings(tmp_path / "run_b")

    result_a = run_improve_loop(
        settings_a,
        strategy_name="random_search",
        n_trials=2,
        seed=7,
        output_root=tmp_path / "out_a",
    )
    result_b = run_improve_loop(
        settings_b,
        strategy_name="random_search",
        n_trials=2,
        seed=7,
        output_root=tmp_path / "out_b",
    )

    assert len(result_a.history) == len(result_b.history)
    for tr_a, tr_b in zip(result_a.history, result_b.history, strict=True):
        assert tr_a.metrics == tr_b.metrics
        # output_dir は tmp_path 起因で異なるため比較から外し、annealing 部分のみで照合
        ann_a = tr_a.config.annealing.model_dump(mode="json")
        ann_b = tr_b.config.annealing.model_dump(mode="json")
        assert ann_a == ann_b
        assert tr_a.config.seed == tr_b.config.seed
