"""quickstart サブコマンドのテスト (Cycle 3-7).

typer.testing.CliRunner を使って quickstart の動作を確認する。
- Cycle 3: quickstart 骨格（input 読み込み → generate）
- Cycle 4: CSV 書き出し（household + person）
- Cycle 5: metrics.json 出力
- Cycle 6: --dry-run / --seed / --log-level フラグ
- Cycle 7: 決定性テスト（同 seed で 2 回実行して SHA256 一致）
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from synthpop_jp.cli import app

runner = CliRunner()

# sample_case の入力ディレクトリ（worktree 内）
SAMPLE_CASE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_case"
CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs"


def _make_config_yaml(tmp_path: Path, seed: int = 42) -> Path:
    """quickstart 用の設定 YAML をテンポラリに作る."""
    import yaml

    config_data = {
        "seed": seed,
        "input_dir": str(SAMPLE_CASE_DIR),
        "output_dir": str(tmp_path / "out"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


@pytest.mark.slow
class TestQuickstartIntegration:
    """quickstart の統合テスト（sample_case 使用）."""

    def test_quickstart_exits_0(self, tmp_path: Path) -> None:
        """quickstart が exit 0 で完走すること."""
        config_path = _make_config_yaml(tmp_path)

        result = runner.invoke(app, ["quickstart", "--config", str(config_path)])

        assert result.exit_code == 0, result.output + (result.stderr or "")

    def test_quickstart_creates_households_csv(self, tmp_path: Path) -> None:
        """synthetic_households.csv が生成されること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["quickstart", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        assert (output_dir / "synthetic_households.csv").exists()

    def test_quickstart_creates_persons_csv(self, tmp_path: Path) -> None:
        """synthetic_persons.csv が生成されること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["quickstart", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        assert (output_dir / "synthetic_persons.csv").exists()

    def test_quickstart_creates_metrics_json(self, tmp_path: Path) -> None:
        """metrics.json が生成されること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(app, ["quickstart", "--config", str(config_path)])

        assert result.exit_code == 0, result.output
        assert (output_dir / "metrics.json").exists()

    def test_households_csv_columns(self, tmp_path: Path) -> None:
        """synthetic_households.csv の列が仕様通りであること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        runner.invoke(app, ["quickstart", "--config", str(config_path)])

        with (output_dir / "synthetic_households.csv").open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == ["household_id", "family_type", "household_size"]
            rows = list(reader)

        assert len(rows) > 0

    def test_persons_csv_columns(self, tmp_path: Path) -> None:
        """synthetic_persons.csv の列が仕様通りであること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        runner.invoke(app, ["quickstart", "--config", str(config_path)])

        with (output_dir / "synthetic_persons.csv").open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == [
                "person_id",
                "household_id",
                "family_type",
                "role",
                "sex",
                "age",
            ]
            rows = list(reader)

        assert len(rows) > 0

    def test_households_csv_id_format(self, tmp_path: Path) -> None:
        """household_id が HH_000001 形式であること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        runner.invoke(app, ["quickstart", "--config", str(config_path)])

        with (output_dir / "synthetic_households.csv").open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) > 0
        first_id = rows[0]["household_id"]
        assert first_id.startswith("HH_")
        assert len(first_id) == 9, f"Expected HH_000001 format (9 chars), got: {first_id}"

    def test_persons_csv_id_format(self, tmp_path: Path) -> None:
        """person_id が P_000001 形式であること."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        runner.invoke(app, ["quickstart", "--config", str(config_path)])

        with (output_dir / "synthetic_persons.csv").open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) > 0
        first_id = rows[0]["person_id"]
        assert first_id.startswith("P_")
        assert len(first_id) == 8, f"Expected P_000001 format (8 chars), got: {first_id}"

    def test_metrics_json_has_required_keys(self, tmp_path: Path) -> None:
        """metrics.json が必要なキーを含むこと."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        runner.invoke(app, ["quickstart", "--config", str(config_path)])

        with (output_dir / "metrics.json").open(encoding="utf-8") as f:
            metrics = json.load(f)

        assert "total_households" in metrics
        assert "total_persons" in metrics
        assert "family_type_counts" in metrics
        assert "household_size_distribution" in metrics
        assert metrics["total_households"] > 0
        assert metrics["total_persons"] > 0

    def test_dry_run_creates_no_files(self, tmp_path: Path) -> None:
        """--dry-run ではファイルが生成されないこと."""
        config_path = _make_config_yaml(tmp_path)
        output_dir = tmp_path / "out"

        result = runner.invoke(
            app, ["quickstart", "--config", str(config_path), "--dry-run"]
        )

        assert result.exit_code == 0, result.output
        assert not (output_dir / "synthetic_households.csv").exists()
        assert not (output_dir / "synthetic_persons.csv").exists()
        assert not (output_dir / "metrics.json").exists()

    def test_seed_override(self, tmp_path: Path) -> None:
        """--seed で config の seed を上書きできること."""
        config_path = _make_config_yaml(tmp_path, seed=42)
        output_dir = tmp_path / "out"

        result = runner.invoke(
            app, ["quickstart", "--config", str(config_path), "--seed", "99"]
        )

        assert result.exit_code == 0, result.output
        assert (output_dir / "synthetic_households.csv").exists()

    def test_log_level_debug(self, tmp_path: Path) -> None:
        """--log-level DEBUG で正常終了すること."""
        config_path = _make_config_yaml(tmp_path)

        result = runner.invoke(
            app, ["quickstart", "--config", str(config_path), "--log-level", "DEBUG"]
        )

        assert result.exit_code == 0, result.output

    def test_determinism_same_seed_produces_same_output(self, tmp_path: Path) -> None:
        """同じ seed で 2 回実行すると出力ファイルの SHA256 が一致すること.

        Phase 1 Exit 条件の決定性テスト。
        """
        # 1 回目の実行
        config_path_1 = _make_config_yaml(tmp_path, seed=42)
        output_dir_1 = tmp_path / "out1"

        import yaml

        config_data_1 = {
            "seed": 42,
            "input_dir": str(SAMPLE_CASE_DIR),
            "output_dir": str(output_dir_1),
        }
        config_path_1.write_text(yaml.dump(config_data_1))

        result1 = runner.invoke(app, ["quickstart", "--config", str(config_path_1)])
        assert result1.exit_code == 0, result1.output

        # 2 回目の実行（別の出力ディレクトリ、同じ seed）
        config_path_2 = tmp_path / "config2.yaml"
        output_dir_2 = tmp_path / "out2"
        config_data_2 = {
            "seed": 42,
            "input_dir": str(SAMPLE_CASE_DIR),
            "output_dir": str(output_dir_2),
        }
        config_path_2.write_text(yaml.dump(config_data_2))

        result2 = runner.invoke(app, ["quickstart", "--config", str(config_path_2)])
        assert result2.exit_code == 0, result2.output

        # SHA256 比較
        for filename in ["synthetic_households.csv", "synthetic_persons.csv", "metrics.json"]:
            content1 = (output_dir_1 / filename).read_bytes()
            content2 = (output_dir_2 / filename).read_bytes()
            sha1 = hashlib.sha256(content1).hexdigest()
            sha2 = hashlib.sha256(content2).hexdigest()
            assert sha1 == sha2, (
                f"{filename}: SHA256 が一致しない\n  実行1: {sha1}\n  実行2: {sha2}"
            )

    def test_different_seed_produces_different_output(self, tmp_path: Path) -> None:
        """異なる seed で実行すると出力が異なること."""
        import yaml

        output_dir_1 = tmp_path / "out1"
        config_path_1 = tmp_path / "config1.yaml"
        config_path_1.write_text(
            yaml.dump(
                {
                    "seed": 42,
                    "input_dir": str(SAMPLE_CASE_DIR),
                    "output_dir": str(output_dir_1),
                }
            )
        )

        output_dir_2 = tmp_path / "out2"
        config_path_2 = tmp_path / "config2.yaml"
        config_path_2.write_text(
            yaml.dump(
                {
                    "seed": 99,
                    "input_dir": str(SAMPLE_CASE_DIR),
                    "output_dir": str(output_dir_2),
                }
            )
        )

        runner.invoke(app, ["quickstart", "--config", str(config_path_1)])
        runner.invoke(app, ["quickstart", "--config", str(config_path_2)])

        content1 = (output_dir_1 / "synthetic_persons.csv").read_bytes()
        content2 = (output_dir_2 / "synthetic_persons.csv").read_bytes()
        # seed が違えば少なくとも persons は異なるはず
        assert content1 != content2

    def test_nonexistent_config_exits_1(self, tmp_path: Path) -> None:
        """存在しない config ファイルで exit 1 になること."""
        result = runner.invoke(
            app,
            ["quickstart", "--config", str(tmp_path / "nonexistent.yaml")],
        )
        assert result.exit_code == 1


class TestQuickstartBaseConfig:
    """configs/base.yaml を使った quickstart テスト."""

    def test_base_yaml_exists(self) -> None:
        """configs/base.yaml が存在すること."""
        assert (CONFIGS_DIR / "base.yaml").exists(), "configs/base.yaml が見つかりません"

    def test_base_yaml_is_valid(self) -> None:
        """configs/base.yaml が有効な Settings として読み込めること."""
        from synthpop_jp.config import Settings

        settings = Settings.from_yaml(CONFIGS_DIR / "base.yaml")
        assert settings.seed >= 0
