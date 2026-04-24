"""Settings モデルのテスト (Cycle 1).

pydantic の Settings モデルが正しくバリデーションを行うことを確認する。
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from synthpop_jp.config import Settings


class TestSettings:
    """Settings モデルの基本バリデーションテスト."""

    def test_valid_settings_from_dict(self, tmp_path: Path) -> None:
        """必須フィールドをすべて指定すると Settings が作れること."""
        s = Settings(seed=42, input_dir=tmp_path, output_dir=tmp_path / "out")
        assert s.seed == 42
        assert s.input_dir == tmp_path
        assert s.output_dir == tmp_path / "out"

    def test_default_seed(self, tmp_path: Path) -> None:
        """seed のデフォルト値は 42 であること."""
        s = Settings(input_dir=tmp_path, output_dir=tmp_path / "out")
        assert s.seed == 42

    def test_input_dir_as_string(self, tmp_path: Path) -> None:
        """input_dir に文字列を渡しても Path に変換されること."""
        s = Settings(seed=1, input_dir=str(tmp_path), output_dir=str(tmp_path / "out"))
        assert isinstance(s.input_dir, Path)

    def test_extra_field_forbidden(self, tmp_path: Path) -> None:
        """未定義キーを渡すと ValidationError が発生すること."""
        with pytest.raises(ValidationError):
            Settings(
                seed=42,
                input_dir=tmp_path,
                output_dir=tmp_path / "out",
                unknown_field="bad",  # type: ignore[call-arg]
            )

    def test_seed_must_be_int(self, tmp_path: Path) -> None:
        """seed に非整数型を渡すと ValidationError が発生すること."""
        with pytest.raises(ValidationError):
            Settings(seed="not_int", input_dir=tmp_path, output_dir=tmp_path / "out")  # type: ignore[arg-type]

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """YAML ファイルから Settings を読み込めること."""
        import yaml

        config_path = tmp_path / "config.yaml"
        config_data = {
            "seed": 99,
            "input_dir": str(tmp_path),
            "output_dir": str(tmp_path / "out"),
        }
        config_path.write_text(yaml.dump(config_data))

        s = Settings.from_yaml(config_path)
        assert s.seed == 99
