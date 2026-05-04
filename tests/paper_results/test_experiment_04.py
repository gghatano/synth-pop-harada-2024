"""Tests for paper_results/experiment-04 (Issue #121, Step 3).

experiment-04 は **rule_based 固定** で 5 seeds × n_trials=5 の improve loop を
回し、`expected/trial_metrics.csv`（25 行）と `expected/variance_summary.csv`
（指標ごとの mean / std / CV / bootstrap CI）を出力する。

ここでは:

1. ファイル配置の前提（run.py / INPUT.md / config.yaml / expected/*.csv）
2. expected CSV の列構造
3. variance_summary.csv に bootstrap_ci_low / bootstrap_ci_high が含まれる
4. main 関数が callable
を smoke で確認する。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP04_DIR = REPO_ROOT / "paper_results" / "experiment-04-multi-trial-variance"
RUN_PY = EXP04_DIR / "run.py"


def _load_run_module() -> object:
    spec = importlib.util.spec_from_file_location("paper_results_exp04_run", RUN_PY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.slow
class TestExperiment04Layout:
    """ファイル配置の前提."""

    def test_run_py_exists(self) -> None:
        assert RUN_PY.exists(), f"{RUN_PY} が無い。Issue #121 Step 3 で作成する。"

    def test_input_md_exists(self) -> None:
        assert (EXP04_DIR / "INPUT.md").exists()

    def test_config_yaml_exists(self) -> None:
        assert (EXP04_DIR / "config.yaml").exists()

    def test_expected_dir_has_csvs(self) -> None:
        for name in ("trial_metrics.csv", "variance_summary.csv"):
            assert (EXP04_DIR / "expected" / name).exists(), (
                f"{name} が expected/ に無い。--write-expected で生成する必要がある。"
            )


@pytest.mark.slow
class TestExperiment04ExpectedSchema:
    """expected CSV の列構造."""

    def test_trial_metrics_columns(self) -> None:
        df = pd.read_csv(EXP04_DIR / "expected" / "trial_metrics.csv")
        for col in (
            "seed",
            "trial_id",
            "best_score",
            "statistical_fit",
            "utility_proxy",
            "privacy_proxy",
        ):
            assert col in df.columns, f"missing column in trial_metrics.csv: {col}"
        # 5 seeds × 5 trials = 25 行
        assert len(df) == 25

    def test_variance_summary_columns(self) -> None:
        df = pd.read_csv(EXP04_DIR / "expected" / "variance_summary.csv")
        for col in (
            "metric",
            "seed_mean",
            "seed_std",
            "seed_cv",
            "bootstrap_ci_low",
            "bootstrap_ci_high",
        ):
            assert col in df.columns, f"missing column in variance_summary.csv: {col}"
        # 4 指標（best_score / statistical_fit / utility_proxy / privacy_proxy）
        assert len(df) == 4
        metrics = set(df["metric"].unique())
        assert metrics == {
            "best_score",
            "statistical_fit",
            "utility_proxy",
            "privacy_proxy",
        }


@pytest.mark.slow
class TestExperiment04Cli:
    """run.py の CLI が callable."""

    def test_main_function_callable(self) -> None:
        m = _load_run_module()
        assert hasattr(m, "main")
        assert callable(m.main)  # type: ignore[attr-defined]
