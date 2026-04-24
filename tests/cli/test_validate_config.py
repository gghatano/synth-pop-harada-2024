"""validate-config サブコマンドのテスト (Cycle 2).

typer.testing.CliRunner を使って、validate-config の動作を確認する。
"""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from synthpop_jp.cli import app

runner = CliRunner()


def _write_valid_config(path: Path) -> None:
    """有効な設定 YAML を書き出すヘルパー."""
    data = {
        "seed": 42,
        "input_dir": "data/sample_case",
        "output_dir": "outputs/quickstart",
    }
    path.write_text(yaml.dump(data))


def _write_invalid_config(path: Path) -> None:
    """不正な設定 YAML（seed が文字列）を書き出すヘルパー."""
    data = {
        "seed": "not_an_int",
        "input_dir": "data/sample_case",
        "output_dir": "outputs/quickstart",
    }
    path.write_text(yaml.dump(data))


class TestValidateConfig:
    """validate-config サブコマンドのテスト."""

    def test_valid_config_exits_0(self, tmp_path: Path) -> None:
        """有効な config で exit 0 になること."""
        config_path = tmp_path / "config.yaml"
        _write_valid_config(config_path)

        result = runner.invoke(app, ["validate-config", str(config_path)])

        assert result.exit_code == 0, result.output

    def test_valid_config_shows_success_message(self, tmp_path: Path) -> None:
        """有効な config で成功メッセージが表示されること."""
        config_path = tmp_path / "config.yaml"
        _write_valid_config(config_path)

        result = runner.invoke(app, ["validate-config", str(config_path)])

        assert "Config is valid" in result.output

    def test_invalid_config_exits_1(self, tmp_path: Path) -> None:
        """型が不正な config で exit 1 になること."""
        config_path = tmp_path / "config.yaml"
        _write_invalid_config(config_path)

        result = runner.invoke(app, ["validate-config", str(config_path)])

        assert result.exit_code == 1

    def test_invalid_config_shows_error_message(self, tmp_path: Path) -> None:
        """型が不正な config でエラーメッセージが表示されること."""
        config_path = tmp_path / "config.yaml"
        _write_invalid_config(config_path)

        result = runner.invoke(app, ["validate-config", str(config_path)])

        # ValidationError の内容が出力に含まれること
        assert "seed" in result.output or "validation" in result.output.lower()

    def test_nonexistent_path_exits_1(self, tmp_path: Path) -> None:
        """存在しないパスで exit 1 になること."""
        result = runner.invoke(app, ["validate-config", str(tmp_path / "nonexistent.yaml")])

        assert result.exit_code == 1

    def test_extra_field_invalid(self, tmp_path: Path) -> None:
        """未定義キーを含む config で exit 1 になること."""
        config_path = tmp_path / "config.yaml"
        data = {
            "seed": 42,
            "input_dir": "data/sample_case",
            "output_dir": "outputs/quickstart",
            "unknown_key": "bad",
        }
        config_path.write_text(yaml.dump(data))

        result = runner.invoke(app, ["validate-config", str(config_path)])

        assert result.exit_code == 1
