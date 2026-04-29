"""Settings モデルのテスト (Cycle 1).

pydantic の Settings モデルが正しくバリデーションを行うことを確認する。
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from synthpop_jp.config import AnnealingConfig, Settings


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
        """input_dir に文字列を渡しても Path に変換されること（pydantic の coercion）."""
        # pydantic v2 は str -> Path の coercion をサポートする。
        # model_validate を経由すれば str でも受け付ける。
        s = Settings.model_validate(
            {"seed": 1, "input_dir": str(tmp_path), "output_dir": str(tmp_path / "out")}
        )
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


class TestAnnealingConfigHybrid:
    """hybrid 遷移の確率パラメータ validator (Issue #67)."""

    def test_hybrid_with_default_probabilities_is_valid(self) -> None:
        """hybrid + default p_change/p_swap (0.7+0.3) は valid."""
        cfg = AnnealingConfig(transition_kind="hybrid")
        assert cfg.p_change == 0.7
        assert cfg.p_swap == 0.3

    def test_hybrid_explicit_valid_split(self) -> None:
        """hybrid + 任意の和=1.0 ペアは valid."""
        cfg = AnnealingConfig(transition_kind="hybrid", p_change=0.4, p_swap=0.6)
        assert cfg.p_change == 0.4
        assert cfg.p_swap == 0.6

    def test_hybrid_with_sum_not_one_rejected(self) -> None:
        """hybrid + p_change + p_swap != 1.0 は ValidationError."""
        with pytest.raises(ValidationError):
            AnnealingConfig(transition_kind="hybrid", p_change=0.5, p_swap=0.6)

    def test_hybrid_with_negative_p_change_rejected(self) -> None:
        """負の p_change は ValidationError."""
        with pytest.raises(ValidationError):
            AnnealingConfig(transition_kind="hybrid", p_change=-0.1, p_swap=1.1)

    def test_non_hybrid_keeps_default_probabilities(self) -> None:
        """age-change/age-swap では p_change/p_swap の default が残っても valid."""
        cfg = AnnealingConfig(transition_kind="age-change")
        assert cfg.transition_kind == "age-change"
        assert cfg.p_change == 0.7
        assert cfg.p_swap == 0.3

    def test_non_hybrid_skips_validation(self) -> None:
        """age-change で p_change + p_swap != 1.0 でも validator は通る."""
        cfg = AnnealingConfig(transition_kind="age-change", p_change=0.1, p_swap=0.1)
        assert cfg.transition_kind == "age-change"
