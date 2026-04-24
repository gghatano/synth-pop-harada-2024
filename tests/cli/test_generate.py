"""generate サブコマンドのテスト (Issue #30 Cycle 9).

typer.testing.CliRunner を使って generate の動作を確認する。
- Cycle 9a: generate が exit 0 で完走すること
- Cycle 9b: 出力 CSV と metrics.json が生成されること
- Cycle 9c: --dry-run でファイルが生成されないこと
- Cycle 9d: --seed でシードが上書きされること
- Cycle 9e: metrics.json に best_score が含まれること
- Cycle 9f: annealing セクションなし config でもデフォルト値で動作すること
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
CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs"


def _make_config_yaml(
    tmp_path: Path,
    seed: int = 42,
    include_annealing: bool = True,
    evals_per_agent: int = 10,
) -> Path:
    """generate 用の設定 YAML を tmp_path に作る.

    evals_per_agent を小さくしてテスト実行を高速化する。
    """
    config_data: dict[str, object] = {
        "seed": seed,
        "input_dir": str(SAMPLE_CASE_DIR),
        "output_dir": str(tmp_path / "out"),
    }
    if include_annealing:
        config_data["annealing"] = {
            "T0": 100.0,
            "alpha": 0.99,
            "max_iters": 100000,
            "evals_per_agent": evals_per_agent,
            "target_threshold": 0.0,
            "patience": 0,
        }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


@pytest.mark.slow
class TestGenerateIntegration:
    """generate の統合テスト（sample_case 使用）."""

    def test_generate_exits_0(self, tmp_path: Path) -> None:
        """generate が exit 0 で完走すること."""
        config_path = _make_config_yaml(tmp_path)

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output + str(result.exception or "")

    def test_generate_creates_households_csv(self, tmp_path: Path) -> None:
        """synthetic_households.csv が生成されること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        assert (output_dir / "synthetic_households.csv").exists()

    def test_generate_creates_persons_csv(self, tmp_path: Path) -> None:
        """synthetic_persons.csv が生成されること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        assert (output_dir / "synthetic_persons.csv").exists()

    def test_generate_creates_metrics_json(self, tmp_path: Path) -> None:
        """metrics.json が生成されること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        assert (output_dir / "metrics.json").exists()

    def test_generate_metrics_json_has_best_score(self, tmp_path: Path) -> None:
        """metrics.json に best_score が含まれること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        metrics_path = output_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        assert "best_score" in metrics, f"metrics.json に best_score がない: {metrics}"
        assert isinstance(metrics["best_score"], (int, float))

    def test_generate_metrics_json_has_initial_score(self, tmp_path: Path) -> None:
        """metrics.json に initial_score が含まれること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
        assert "initial_score" in metrics, f"metrics.json に initial_score がない: {metrics}"

    def test_generate_dry_run_no_files(self, tmp_path: Path) -> None:
        """--dry-run でファイルが生成されないこと."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path), "--dry-run"])

        assert result.exit_code == 0, result.output
        assert not (output_dir / "synthetic_households.csv").exists()
        assert not (output_dir / "synthetic_persons.csv").exists()
        assert not (output_dir / "metrics.json").exists()

    def test_generate_seed_override(self, tmp_path: Path) -> None:
        """--seed でシードが上書きされて正常動作すること."""
        config_path = _make_config_yaml(tmp_path)

        result = runner.invoke(app, ["generate", "--config", str(config_path), "--seed", "99"])

        assert result.exit_code == 0, result.output

    def test_generate_without_annealing_section_uses_defaults(self, tmp_path: Path) -> None:
        """annealing セクションがない config でもデフォルト値で動作すること.

        Settings モデルの ``annealing`` フィールドにデフォルト値があるため、
        YAML に ``annealing`` を書かなくても動く。
        """
        config_path = _make_config_yaml(tmp_path, include_annealing=False)

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        # デフォルト evals_per_agent=1000 はテスト実行が長いので exit 0 だけ確認
        # 実際の CI は slow マーカーを付けてスキップ可能にする
        assert result.exit_code == 0, result.output

    def test_generate_persons_csv_has_correct_columns(self, tmp_path: Path) -> None:
        """synthetic_persons.csv のカラムが正しいこと."""
        import csv

        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        with (output_dir / "synthetic_persons.csv").open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        assert fieldnames is not None
        assert "person_id" in fieldnames
        assert "household_id" in fieldnames
        assert "role" in fieldnames
        assert "sex" in fieldnames
        assert "age" in fieldnames

    def test_generate_households_csv_has_correct_columns(self, tmp_path: Path) -> None:
        """synthetic_households.csv のカラムが正しいこと."""
        import csv

        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["generate", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        with (output_dir / "synthetic_households.csv").open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        assert fieldnames is not None
        assert "household_id" in fieldnames
        assert "family_type" in fieldnames
