"""Tests for paper_results._shared.improve_runner (Issue #121, Step 1).

`improve_runner.run_improve_for_paper_results(...)` は ``configs/improve_quick.yaml``
を base settings とした最小 improve loop を ``synthpop_jp.improve.runner.run_improve_loop``
経由で実行し、各 trial の 3 目的 metrics を pandas.DataFrame にまとめて返す。

ここでは以下を確認する:

1. configs/improve_quick.yaml が存在し、Settings として読める
2. run_improve_for_paper_results が n_trials=2 / strategy="rule_based" / seed=1 で
   完走し、DataFrame に必要列を含む
3. 同一引数で 2 回呼ぶと best_score 列が bitwise 一致する（決定論性）
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from synthpop_jp.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
QUICK_CONFIG = REPO_ROOT / "configs" / "improve_quick.yaml"


@pytest.mark.slow
class TestImproveQuickConfig:
    """``configs/improve_quick.yaml`` がロード可能なこと."""

    def test_quick_yaml_exists(self) -> None:
        assert QUICK_CONFIG.exists(), (
            f"{QUICK_CONFIG} が存在しません。Issue #121 Step 1 で追加する必要があります。"
        )

    def test_quick_yaml_loads_as_settings(self) -> None:
        settings = Settings.from_yaml(QUICK_CONFIG)
        # 軽量設定: evals_per_agent <= 200、max_iters <= 50000
        assert settings.annealing.evals_per_agent <= 200
        assert settings.annealing.max_iters <= 50_000


@pytest.mark.slow
class TestRunImproveForPaperResults:
    """``run_improve_for_paper_results`` のスモーク + 決定性."""

    def test_returns_dataframe_with_required_columns(self, tmp_path: Path) -> None:
        from paper_results._shared.improve_runner import run_improve_for_paper_results

        df = run_improve_for_paper_results(
            base_config_path=QUICK_CONFIG,
            strategy_name="rule_based",
            n_trials=2,
            seed=1,
            output_root=tmp_path / "improve",
        )
        assert isinstance(df, pd.DataFrame)
        # 必須列
        for col in (
            "seed",
            "strategy",
            "trial_id",
            "best_score",
            "statistical_fit",
            "utility_proxy",
            "privacy_proxy",
            "composite",
        ):
            assert col in df.columns, f"missing column: {col}"
        # n_trials=2 で 2 行
        assert len(df) == 2
        # seed / strategy が固定値で揃う
        assert (df["seed"] == 1).all()
        assert (df["strategy"] == "rule_based").all()

    def test_deterministic_for_same_seed_and_strategy(self, tmp_path: Path) -> None:
        from paper_results._shared.improve_runner import run_improve_for_paper_results

        df_a = run_improve_for_paper_results(
            base_config_path=QUICK_CONFIG,
            strategy_name="rule_based",
            n_trials=2,
            seed=1,
            output_root=tmp_path / "a",
        )
        df_b = run_improve_for_paper_results(
            base_config_path=QUICK_CONFIG,
            strategy_name="rule_based",
            n_trials=2,
            seed=1,
            output_root=tmp_path / "b",
        )
        # 決定論性: best_score が bitwise 一致 (spec §19.3)
        assert list(df_a["best_score"]) == list(df_b["best_score"])
        assert list(df_a["statistical_fit"]) == list(df_b["statistical_fit"])

    def test_supports_pareto_and_random_search(self, tmp_path: Path) -> None:
        from paper_results._shared.improve_runner import run_improve_for_paper_results

        for strat in ("pareto", "random_search"):
            df = run_improve_for_paper_results(
                base_config_path=QUICK_CONFIG,
                strategy_name=strat,  # type: ignore[arg-type]
                n_trials=2,
                seed=2,
                output_root=tmp_path / strat,
            )
            assert len(df) == 2
            assert (df["strategy"] == strat).all()
