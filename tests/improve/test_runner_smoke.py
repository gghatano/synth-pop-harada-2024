"""multi-trial runner の end-to-end スモークテスト (Issue #119, Step 5).

trials=2 / sample_case の極小設定で ``run_improve_loop`` が完走し、想定の
出力ファイルが揃うことを確認する。

実行時間の目安: 30 秒以内（CI で常時 green を維持するため evals_per_agent
を 5 に抑える）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synthpop_jp.config import AnnealingConfig, Settings
from synthpop_jp.improve.runner import run_improve_loop

SAMPLE_CASE = Path(__file__).resolve().parents[2] / "data" / "sample_case"


def _smoke_settings(tmp_path: Path) -> Settings:
    """sample_case を入力に、ごく小さな evals_per_agent で SA を回す Settings."""
    return Settings(
        seed=42,
        input_dir=SAMPLE_CASE,
        output_dir=tmp_path / "out",
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
class TestRunImproveLoopSmoke:
    """run_improve_loop が end-to-end で完走するか確認."""

    def test_runs_two_trials(self, tmp_path: Path) -> None:
        settings = _smoke_settings(tmp_path)
        result = run_improve_loop(
            settings,
            strategy_name="random_search",
            n_trials=2,
            seed=0,
            output_root=tmp_path / "improve",
        )
        assert len(result.history) == 2
        assert result.best.trial_id in {1, 2}
        assert result.output_dir.exists()

    def test_each_trial_has_synthetic_persons_csv(self, tmp_path: Path) -> None:
        settings = _smoke_settings(tmp_path)
        result = run_improve_loop(
            settings,
            strategy_name="random_search",
            n_trials=2,
            seed=0,
            output_root=tmp_path / "improve",
        )
        for tr in result.history:
            assert tr.output_dir is not None
            persons_csv = tr.output_dir / "synthetic_persons.csv"
            assert persons_csv.exists(), f"trial {tr.trial_id}: {persons_csv} missing"
            metrics_json = tr.output_dir / "metrics.json"
            assert metrics_json.exists()

    def test_best_config_yaml_exists(self, tmp_path: Path) -> None:
        settings = _smoke_settings(tmp_path)
        result = run_improve_loop(
            settings,
            strategy_name="random_search",
            n_trials=2,
            seed=0,
            output_root=tmp_path / "improve",
        )
        best_yaml = result.output_dir / "best_config.yaml"
        assert best_yaml.exists()
        assert best_yaml.read_text(encoding="utf-8")

    def test_summary_md_exists_and_human_readable(self, tmp_path: Path) -> None:
        settings = _smoke_settings(tmp_path)
        result = run_improve_loop(
            settings,
            strategy_name="random_search",
            n_trials=2,
            seed=0,
            output_root=tmp_path / "improve",
        )
        summary = result.output_dir / "summary.md"
        assert summary.exists()
        text = summary.read_text(encoding="utf-8")
        # 「best」「trial」「best_score」のいずれかが含まれることを確認
        assert "best" in text.lower() or "ベスト" in text

    def test_pareto_front_md_only_for_pareto_strategy(self, tmp_path: Path) -> None:
        # random_search では pareto_front.md は無い
        settings = _smoke_settings(tmp_path)
        result_rs = run_improve_loop(
            settings,
            strategy_name="random_search",
            n_trials=2,
            seed=0,
            output_root=tmp_path / "rs",
        )
        assert not (result_rs.output_dir / "pareto_front.md").exists()

        # pareto では pareto_front.md が出力される
        settings2 = _smoke_settings(tmp_path / "pp")
        result_p = run_improve_loop(
            settings2,
            strategy_name="pareto",
            n_trials=2,
            seed=0,
            output_root=tmp_path / "pa",
        )
        assert (result_p.output_dir / "pareto_front.md").exists()

    def test_metrics_json_contains_objectives(self, tmp_path: Path) -> None:
        settings = _smoke_settings(tmp_path)
        result = run_improve_loop(
            settings,
            strategy_name="random_search",
            n_trials=2,
            seed=0,
            output_root=tmp_path / "improve",
        )
        first = result.history[0]
        assert first.output_dir is not None
        metrics = json.loads(
            (first.output_dir / "metrics.json").read_text(encoding="utf-8"),
        )
        # 必須キー: best_score / statistical_fit / utility / privacy（後 3 つは proxy 値）
        for key in ("best_score", "statistical_fit", "utility", "privacy"):
            assert key in metrics, f"missing key: {key}"
