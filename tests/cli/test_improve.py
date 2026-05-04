"""improve サブコマンドの CLI テスト (Issue #119, Step 7).

`synthpop-jp improve --strategy NAME --trials N --seed S --output-dir PATH` が
end-to-end で完走し、best_config.yaml / summary.md が出力されることを確認。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from synthpop_jp.cli import app

runner = CliRunner()

SAMPLE_CASE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_case"
CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs"


def _make_config_yaml(tmp_path: Path) -> Path:
    """improve 用の極小 config を作る."""
    config_data: dict[str, object] = {
        "seed": 42,
        "input_dir": str(SAMPLE_CASE_DIR),
        "output_dir": str(tmp_path / "out"),
        "annealing": {
            "T0": 10.0,
            "alpha": 0.99,
            "max_iters": 200,
            "evals_per_agent": 2,
            "trace_enabled": False,
            "checkpoint_every_n_iters": 0,
            "log_every_n_iters": 10000,
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


@pytest.mark.slow
class TestImproveCli:
    """improve サブコマンドの統合テスト."""

    def test_improve_runs_successfully(self, tmp_path: Path) -> None:
        config_path = _make_config_yaml(tmp_path)
        result = runner.invoke(
            app,
            [
                "improve",
                "--config",
                str(config_path),
                "--strategy",
                "rule_based",
                "--trials",
                "2",
                "--seed",
                "0",
                "--output-dir",
                str(tmp_path / "improve_out"),
            ],
        )
        assert result.exit_code == 0, result.output + str(result.exception or "")

    def test_improve_creates_best_config_yaml(self, tmp_path: Path) -> None:
        config_path = _make_config_yaml(tmp_path)
        out_root = tmp_path / "improve_out"
        result = runner.invoke(
            app,
            [
                "improve",
                "--config",
                str(config_path),
                "--strategy",
                "random_search",
                "--trials",
                "2",
                "--seed",
                "0",
                "--output-dir",
                str(out_root),
            ],
        )
        assert result.exit_code == 0, result.output
        # 出力構造: out_root / random_search_seed0 / best_config.yaml
        run_dir = out_root / "random_search_seed0"
        assert (run_dir / "best_config.yaml").exists()
        assert (run_dir / "summary.md").exists()

    def test_improve_unknown_strategy_fails(self, tmp_path: Path) -> None:
        config_path = _make_config_yaml(tmp_path)
        result = runner.invoke(
            app,
            [
                "improve",
                "--config",
                str(config_path),
                "--strategy",
                "bogus_name",
                "--trials",
                "2",
                "--seed",
                "0",
                "--output-dir",
                str(tmp_path / "out"),
            ],
        )
        assert result.exit_code != 0

    def test_improve_pareto_strategy_writes_pareto_front(self, tmp_path: Path) -> None:
        config_path = _make_config_yaml(tmp_path)
        out_root = tmp_path / "improve_out"
        result = runner.invoke(
            app,
            [
                "improve",
                "--config",
                str(config_path),
                "--strategy",
                "pareto",
                "--trials",
                "2",
                "--seed",
                "0",
                "--output-dir",
                str(out_root),
            ],
        )
        assert result.exit_code == 0, result.output
        run_dir = out_root / "pareto_seed0"
        assert (run_dir / "pareto_front.md").exists()
