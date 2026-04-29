"""generate サブコマンドのテスト (Issue #30 Cycle 9, Issue #32 Cycle 9).

typer.testing.CliRunner を使って generate の動作を確認する。
- Cycle 9a: generate が exit 0 で完走すること
- Cycle 9b: 出力 CSV と metrics.json が生成されること
- Cycle 9c: --dry-run でファイルが生成されないこと
- Cycle 9d: --seed でシードが上書きされること
- Cycle 9e: metrics.json に best_score が含まれること
- Cycle 9f: annealing セクションなし config でもデフォルト値で動作すること
- Cycle 9g (Issue #32): --resume フラグで checkpoint から再開できること
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


@pytest.mark.slow
class TestGenerateResume:
    """generate の --resume フラグの統合テスト（Issue #32 Cycle 9）."""

    def _make_config_with_checkpoint(
        self,
        tmp_path: Path,
        checkpoint_dir: Path,
        max_iters: int = 100,
        checkpoint_every: int = 50,
    ) -> Path:
        """checkpoint 付きの設定 YAML を返す."""
        config_data: dict[str, object] = {
            "seed": 42,
            "input_dir": str(SAMPLE_CASE_DIR),
            "output_dir": str(tmp_path / "out"),
            "annealing": {
                "T0": 100.0,
                "alpha": 0.99,
                "max_iters": max_iters,
                "evals_per_agent": 0,
                "target_threshold": 0.0,
                "patience": 0,
                "trace_enabled": False,
                "checkpoint_every_n_iters": checkpoint_every,
                "checkpoint_dir": str(checkpoint_dir),
            },
        }
        config_path = tmp_path / "config_ckpt.yaml"
        config_path.write_text(yaml.dump(config_data))
        return config_path

    def test_resume_flag_exits_0(self, tmp_path: Path) -> None:
        """--resume フラグを渡しても exit 0 で完走すること."""
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()

        # phase 1: checkpoint を作成する
        config_p1 = self._make_config_with_checkpoint(
            tmp_path, checkpoint_dir, max_iters=100, checkpoint_every=100
        )
        result_p1 = runner.invoke(
            app, ["generate", "--config", str(config_p1), "--log-level", "ERROR"]
        )
        assert result_p1.exit_code == 0, result_p1.output + str(result_p1.exception or "")

        latest_ckpt = checkpoint_dir / "latest.pkl.gz"
        assert latest_ckpt.exists(), "checkpoint が生成されていない"

        # phase 2: --resume で再開
        config_p2 = self._make_config_with_checkpoint(
            tmp_path, checkpoint_dir, max_iters=200, checkpoint_every=0
        )
        result_p2 = runner.invoke(
            app,
            [
                "generate",
                "--config",
                str(config_p2),
                "--resume",
                str(latest_ckpt),
                "--log-level",
                "ERROR",
            ],
        )
        assert result_p2.exit_code == 0, result_p2.output + str(result_p2.exception or "")

    def test_resume_invalid_path_exits_1(self, tmp_path: Path) -> None:
        """存在しない checkpoint パスを --resume に渡すと exit 1 になること."""
        config_path = _make_config_yaml(tmp_path)
        nonexistent = tmp_path / "no_such_file.pkl.gz"

        result = runner.invoke(
            app,
            [
                "generate",
                "--config",
                str(config_path),
                "--resume",
                str(nonexistent),
                "--log-level",
                "ERROR",
            ],
        )
        assert result.exit_code == 1, f"exit code は 1 であるべき: got {result.exit_code}"


@pytest.mark.slow
class TestGenerateHybridTransition:
    """hybrid 遷移を選択した generate の統合テスト (Issue #67)."""

    def _make_hybrid_config(self, tmp_path: Path) -> Path:
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
                "transition_kind": "hybrid",
                "p_change": 0.7,
                "p_swap": 0.3,
            },
        }
        config_path = tmp_path / "config_hybrid.yaml"
        config_path.write_text(yaml.dump(config_data))
        return config_path

    def test_hybrid_generate_exits_0(self, tmp_path: Path) -> None:
        """hybrid 設定で generate が exit 0 で完走する."""
        config_path = self._make_hybrid_config(tmp_path)
        result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert result.exit_code == 0, result.output + str(result.exception or "")

    def test_hybrid_generate_creates_outputs(self, tmp_path: Path) -> None:
        """hybrid 設定で synthetic_persons.csv と metrics.json が生成される."""
        config_path = self._make_hybrid_config(tmp_path)
        result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "out" / "synthetic_persons.csv").exists()
        assert (tmp_path / "out" / "metrics.json").exists()

    def test_hybrid_linear_schedule_runs(self, tmp_path: Path) -> None:
        """linear schedule の hybrid config で generate が exit 0 で完走する (Issue #69)."""
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
                "transition_kind": "hybrid",
                "p_change_schedule": "linear",
                "p_change": 0.9,
                "p_change_end": 0.3,
            },
        }
        config_path = tmp_path / "config_hybrid_linear.yaml"
        config_path.write_text(yaml.dump(config_data))
        result = runner.invoke(app, ["generate", "--config", str(config_path)])
        assert result.exit_code == 0, result.output + str(result.exception or "")
        assert (tmp_path / "out" / "synthetic_persons.csv").exists()
