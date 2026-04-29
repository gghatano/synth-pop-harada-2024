"""Tests for the ``evaluate`` CLI subcommand (Phase 3.5, Issue #59).

generate → evaluate を tmp_path 上で順番実行し、metrics.json に
``aggregate.l1.*`` キーが追記されることを検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from synthpop_jp.cli import app

runner = CliRunner()

SAMPLE_CASE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_case"


def _make_config_yaml(tmp_path: Path) -> Path:
    """generate + evaluate 共通の小さい config を作る."""
    config_data: dict[str, object] = {
        "seed": 42,
        "input_dir": str(SAMPLE_CASE_DIR),
        "output_dir": str(tmp_path / "out"),
        "annealing": {
            "T0": 100.0,
            "alpha": 0.99,
            "max_iters": 200,
            "evals_per_agent": 0,
            "target_threshold": 0.0,
            "patience": 0,
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


@pytest.mark.slow
class TestEvaluateIntegration:
    """end-to-end: generate → evaluate を順番に実行する."""

    def test_evaluate_appends_aggregate_keys(self, tmp_path: Path) -> None:
        """evaluate 後の metrics.json に aggregate.l1.* キーが含まれる."""
        config_path = _make_config_yaml(tmp_path)
        gen_result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert gen_result.exit_code == 0, gen_result.output

        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 0, eval_result.output

        metrics_path = tmp_path / "out" / "metrics.json"
        assert metrics_path.exists()
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

        # aggregate.l1.* が 5 stat + total = 6 キー含まれる
        assert "aggregate.l1.father_child_age_diff" in metrics
        assert "aggregate.l1.mother_child_age_diff" in metrics
        assert "aggregate.l1.couple_age_diff" in metrics
        assert "aggregate.l1.pyramid_male" in metrics
        assert "aggregate.l1.pyramid_female" in metrics
        assert "aggregate.l1.total" in metrics

        # 既存 generate キーが保持される
        assert "total_households" in metrics
        assert "best_score" in metrics

    def test_evaluate_aggregate_total_matches_best_score(self, tmp_path: Path) -> None:
        """evaluate の aggregate.l1.total は generate の best_score と一致."""
        config_path = _make_config_yaml(tmp_path)
        runner.invoke(app, ["generate", "--config", str(config_path)])
        runner.invoke(app, ["evaluate", "--config", str(config_path)])

        metrics_path = tmp_path / "out" / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        # best_score は generate が書いた値、aggregate.l1.total は evaluate が計算
        # 同じ最終人口に対する L1 なので一致する
        assert abs(metrics["aggregate.l1.total"] - metrics["best_score"]) < 1e-3

    def test_evaluate_fails_without_synthetic_csv(self, tmp_path: Path) -> None:
        """generate を先に実行していない場合は exit code 1."""
        config_path = _make_config_yaml(tmp_path)
        # generate せずに evaluate
        eval_result = runner.invoke(app, ["evaluate", "--config", str(config_path)])
        assert eval_result.exit_code == 1
        assert "synthetic_persons.csv" in eval_result.output
