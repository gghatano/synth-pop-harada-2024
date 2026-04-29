"""Tests for the ``compare`` CLI subcommand (Phase 3b, Issue #80)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from synthpop_jp.cli import app

runner = CliRunner()
SAMPLE_CASE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_case"


def _make_config_yaml(tmp_path: Path, name: str, seed: int, alpha: float = 0.99) -> Path:
    """compare 比較用の小さな config を作る."""
    config_data: dict[str, object] = {
        "seed": seed,
        "input_dir": str(SAMPLE_CASE_DIR),
        "output_dir": str(tmp_path / name / "out"),
        "annealing": {
            "T0": 100.0,
            "alpha": alpha,
            "max_iters": 200,
            "evals_per_agent": 0,
            "target_threshold": 0.0,
            "patience": 0,
        },
    }
    config_path = tmp_path / f"{name}.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


@pytest.mark.slow
class TestCompareIntegration:
    """end-to-end: 2 config × 2 seeds で compare が完走する."""

    def test_compare_exits_0_with_outputs(self, tmp_path: Path) -> None:
        """2 config × 2 seeds で exit 0、compare.json + compare.md が生成される."""
        cfg_a = _make_config_yaml(tmp_path, "config_a", seed=42, alpha=0.99)
        cfg_b = _make_config_yaml(tmp_path, "config_b", seed=42, alpha=0.95)
        out_dir = tmp_path / "compare_out"

        result = runner.invoke(
            app,
            [
                "compare",
                "--configs",
                str(cfg_a),
                "--configs",
                str(cfg_b),
                "--n-seeds",
                "2",
                "--output-dir",
                str(out_dir),
                "--metrics",
                "aggregate.l1.total",
            ],
        )
        assert result.exit_code == 0, result.output + str(result.exception or "")
        assert (out_dir / "compare.json").exists()
        assert (out_dir / "compare.md").exists()

    def test_compare_json_structure(self, tmp_path: Path) -> None:
        """compare.json に configs / n_seeds / metrics / holm_corrected キーが含まれる."""
        cfg_a = _make_config_yaml(tmp_path, "config_a", seed=42)
        cfg_b = _make_config_yaml(tmp_path, "config_b", seed=42, alpha=0.95)
        out_dir = tmp_path / "compare_out"
        runner.invoke(
            app,
            [
                "compare",
                "-c",
                str(cfg_a),
                "-c",
                str(cfg_b),
                "--n-seeds",
                "2",
                "--output-dir",
                str(out_dir),
                "--metrics",
                "aggregate.l1.total",
            ],
        )
        payload = json.loads((out_dir / "compare.json").read_text(encoding="utf-8"))
        assert "configs" in payload
        assert "n_seeds" in payload
        assert "metrics" in payload
        assert "aggregate.l1.total" in payload["metrics"]
        assert "tests" in payload["metrics"]["aggregate.l1.total"]
        assert "holm_corrected" in payload

    def test_compare_with_single_config_fails(self, tmp_path: Path) -> None:
        """1 config だけでは exit 1."""
        cfg_a = _make_config_yaml(tmp_path, "config_a", seed=42)
        out_dir = tmp_path / "compare_out"
        result = runner.invoke(
            app,
            [
                "compare",
                "-c",
                str(cfg_a),
                "--n-seeds",
                "2",
                "--output-dir",
                str(out_dir),
            ],
        )
        assert result.exit_code == 1
        assert "2 個以上" in result.output

    def test_compare_with_invalid_n_seeds(self, tmp_path: Path) -> None:
        """n_seeds が範囲外で exit 1."""
        cfg_a = _make_config_yaml(tmp_path, "config_a", seed=42)
        cfg_b = _make_config_yaml(tmp_path, "config_b", seed=42, alpha=0.95)
        out_dir = tmp_path / "compare_out"
        result = runner.invoke(
            app,
            [
                "compare",
                "-c",
                str(cfg_a),
                "-c",
                str(cfg_b),
                "--n-seeds",
                "100",
                "--output-dir",
                str(out_dir),
            ],
        )
        assert result.exit_code == 1
        assert "1〜30" in result.output
