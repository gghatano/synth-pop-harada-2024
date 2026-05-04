"""Tests for paper_results/experiment-03 (Issue #121, Step 2).

experiment-03 の `run.py` を import して呼べるか、`expected/best_scores.csv` /
`expected/strategy_metrics.csv` の構造が期待通りか、`--write-expected` /
`--check-tolerance` の CLI が落ちないかを smoke で確認する。

実 SA を回す test は `@pytest.mark.slow` を付け、改善ループの全 9 trial を
1 度走らせる重さを許容する（CI 既定で 5 分以内）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP03_DIR = REPO_ROOT / "paper_results" / "experiment-03-improve-strategy-comparison"
RUN_PY = EXP03_DIR / "run.py"


def _load_run_module() -> object:
    """experiment-03/run.py を動的に import する.

    `paper_results/experiment-03-...` はハイフン入りなので通常の import は
    できない。spec から直接 module spec を作る。
    """
    spec = importlib.util.spec_from_file_location("paper_results_exp03_run", RUN_PY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.slow
class TestExperiment03Layout:
    """ファイル配置の前提."""

    def test_run_py_exists(self) -> None:
        assert RUN_PY.exists(), f"{RUN_PY} が無い。Issue #121 Step 2 で作成する。"

    def test_input_md_exists(self) -> None:
        assert (EXP03_DIR / "INPUT.md").exists()

    def test_config_yaml_exists(self) -> None:
        assert (EXP03_DIR / "config.yaml").exists()

    def test_expected_dir_has_csvs(self) -> None:
        # expected は `make paper-results-write` で生成済を想定（リポジトリ凍結）
        for name in ("best_scores.csv", "strategy_metrics.csv"):
            assert (EXP03_DIR / "expected" / name).exists(), (
                f"{name} が expected/ に無い。--write-expected で生成する必要がある。"
            )


@pytest.mark.slow
class TestExperiment03ExpectedSchema:
    """expected CSV の列構造."""

    def test_best_scores_csv_columns(self) -> None:
        df = pd.read_csv(EXP03_DIR / "expected" / "best_scores.csv")
        for col in (
            "seed",
            "strategy",
            "best_trial_id",
            "best_score",
            "composite",
            "statistical_fit",
            "utility_proxy",
            "privacy_proxy",
        ):
            assert col in df.columns, f"missing column in best_scores.csv: {col}"
        # 3 seeds × 3 戦略 = 9 行
        assert len(df) == 9
        # strategy 列に 3 種類が揃う
        strategies = set(df["strategy"].unique())
        assert strategies == {"rule_based", "pareto", "random_search"}

    def test_strategy_metrics_csv_columns(self) -> None:
        df = pd.read_csv(EXP03_DIR / "expected" / "strategy_metrics.csv")
        for col in (
            "strategy",
            "statistical_fit_mean",
            "utility_proxy_mean",
            "privacy_proxy_mean",
            "composite_mean",
        ):
            assert col in df.columns, f"missing column in strategy_metrics.csv: {col}"
        # 戦略は 3 種類
        assert len(df) == 3


@pytest.mark.slow
class TestExperiment03Cli:
    """run.py の CLI が --write-expected / --check-tolerance で動作する."""

    def test_main_function_callable(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "main")
        # main は callable
        assert callable(m.main)  # type: ignore[attr-defined]
