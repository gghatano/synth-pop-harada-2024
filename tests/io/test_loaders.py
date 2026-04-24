"""Tests for io/loaders.py — TDD Cycle 1〜9.

構成:
- Cycle 1: FamilyTypeCountRow スキーマ単体テスト
- Cycle 2: load_family_type_counts 正常 / 異常系
- Cycle 3: family_type_mapping YAML + load_family_type_mapping
- Cycle 4: load_children_count_dist 正常 / 重複 key
- Cycle 5: load_demographic_by_age_sex
- Cycle 6: load_age_diff_parent_child
- Cycle 7: load_age_diff_couple (couple_diff 符号規則)
- Cycle 8: 任意 2 種
- Cycle 9: generate_sample_case 往復テスト（bitwise 一致）
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from synthpop_jp.io.schemas import (
    AgeDiffCoupleRow,
    AgeDiffParentChildRow,
    ChildrenCountDistRow,
    DemographicByAgeSexRow,
    DemographicByFamilyTypeRoleRow,
    FamilyTypeCountRow,
    HouseholdSizeByFamilyTypeRow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORKTREE = Path(__file__).parent.parent.parent
DATA_SAMPLE = WORKTREE / "data" / "sample_case"
CONFIGS_DIR = WORKTREE / "configs"


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    """Serialize a list of dicts to CSV bytes."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Cycle 1: FamilyTypeCountRow schema unit tests
# ---------------------------------------------------------------------------


class TestFamilyTypeCountRowSchema:
    """FamilyTypeCountRow の pydantic バリデーション単体テスト."""

    def test_valid_row_accepted(self) -> None:
        row = FamilyTypeCountRow(family_type="single", count=10)
        assert row.family_type == "single"
        assert row.count == 10

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FamilyTypeCountRow(family_type="single", count=-1)

    def test_zero_count_accepted(self) -> None:
        row = FamilyTypeCountRow(family_type="couple", count=0)
        assert row.count == 0

    def test_missing_family_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FamilyTypeCountRow(count=5)  # type: ignore[call-arg]

    def test_missing_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FamilyTypeCountRow(family_type="single")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Cycle 2: load_family_type_counts — 正常 / 列欠落 / 型違い / 範囲外
# ---------------------------------------------------------------------------


class TestLoadFamilyTypeCounts:
    """load_family_type_counts の CSV ローダテスト."""

    def test_valid_csv_returns_list_of_rows(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import load_family_type_counts

        csv_file = tmp_path / "family_type_counts.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [
                    {"family_type": "single", "count": 10},
                    {"family_type": "couple", "count": 5},
                ]
            )
        )
        rows = load_family_type_counts(csv_file)
        assert len(rows) == 2
        assert rows[0].family_type == "single"
        assert rows[1].count == 5

    def test_missing_column_raises_with_row_number(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import CsvValidationError, load_family_type_counts

        csv_file = tmp_path / "family_type_counts.csv"
        # count 列が欠落
        csv_file.write_text("family_type\nsingle\n")
        with pytest.raises(CsvValidationError) as exc_info:
            load_family_type_counts(csv_file)
        assert "row" in str(exc_info.value).lower() or "行" in str(exc_info.value)

    def test_wrong_type_age_raises_with_row_number(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import CsvValidationError, load_family_type_counts

        csv_file = tmp_path / "family_type_counts.csv"
        csv_file.write_bytes(_csv_bytes([{"family_type": "single", "count": "abc"}]))
        with pytest.raises(CsvValidationError) as exc_info:
            load_family_type_counts(csv_file)
        assert "row" in str(exc_info.value).lower() or "行" in str(exc_info.value)

    def test_negative_count_raises_with_row_number(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import CsvValidationError, load_family_type_counts

        csv_file = tmp_path / "family_type_counts.csv"
        csv_file.write_bytes(_csv_bytes([{"family_type": "single", "count": -1}]))
        with pytest.raises(CsvValidationError) as exc_info:
            load_family_type_counts(csv_file)
        # 行番号 0 (0-indexed) が含まれること
        assert "0" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Cycle 3: family_type_mapping YAML + load_family_type_mapping
# ---------------------------------------------------------------------------


class TestFamilyTypeMapping:
    """configs/family_type_mapping.yaml の読み込みテスト."""

    def test_yaml_file_exists(self) -> None:
        yaml_path = CONFIGS_DIR / "family_type_mapping.yaml"
        assert yaml_path.exists(), f"{yaml_path} が存在しない"

    def test_load_returns_dict(self) -> None:
        from synthpop_jp.io.loaders import load_family_type_mapping

        mapping = load_family_type_mapping(CONFIGS_DIR / "family_type_mapping.yaml")
        assert isinstance(mapping, dict)
        assert len(mapping) > 0

    def test_all_9_family_types_present(self) -> None:
        from synthpop_jp.io.loaders import load_family_type_mapping

        mapping = load_family_type_mapping(CONFIGS_DIR / "family_type_mapping.yaml")
        expected = {
            "single",
            "couple",
            "couple_and_children",
            "father_and_children",
            "mother_and_children",
            "couple_and_parents",
            "couple_and_a_parent",
            "couple_children_and_parents",
            "couple_children_and_a_parent",
        }
        assert expected <= set(mapping.keys())

    def test_unknown_group_raises_on_validation(self, tmp_path: Path) -> None:
        """family_type_counts.csv に未登録グループが含まれる場合を検証."""
        from synthpop_jp.io.loaders import CsvValidationError, load_children_count_dist

        # children_count_dist は family_type_group を持つ CSV — 未登録 group をテスト
        mapping_path = CONFIGS_DIR / "family_type_mapping.yaml"
        csv_file = tmp_path / "children_count_dist.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [
                    {
                        "family_type_group": "UNKNOWN_GROUP",
                        "n_children": 1,
                        "rate": 0.5,
                    }
                ]
            )
        )
        with pytest.raises(CsvValidationError):
            load_children_count_dist(csv_file, mapping_path=mapping_path)


# ---------------------------------------------------------------------------
# Cycle 4: ChildrenCountDistRow + load_children_count_dist
# ---------------------------------------------------------------------------


class TestChildrenCountDistRowSchema:
    def test_valid_row(self) -> None:
        row = ChildrenCountDistRow(family_type_group="with_children", n_children=2, rate=0.3)
        assert row.rate == pytest.approx(0.3)

    def test_negative_n_children_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChildrenCountDistRow(family_type_group="with_children", n_children=-1, rate=0.3)

    def test_rate_above_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChildrenCountDistRow(family_type_group="with_children", n_children=1, rate=1.5)

    def test_negative_rate_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChildrenCountDistRow(family_type_group="with_children", n_children=1, rate=-0.1)


class TestLoadChildrenCountDist:
    def test_valid_csv(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import load_children_count_dist

        mapping_path = CONFIGS_DIR / "family_type_mapping.yaml"
        csv_file = tmp_path / "children_count_dist.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [
                    {"family_type_group": "with_children", "n_children": 1, "rate": 0.5},
                    {"family_type_group": "with_children", "n_children": 2, "rate": 0.5},
                ]
            )
        )
        rows = load_children_count_dist(csv_file, mapping_path=mapping_path)
        assert len(rows) == 2

    def test_duplicate_key_raises(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import CsvValidationError, load_children_count_dist

        mapping_path = CONFIGS_DIR / "family_type_mapping.yaml"
        csv_file = tmp_path / "children_count_dist.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [
                    {"family_type_group": "with_children", "n_children": 1, "rate": 0.5},
                    {"family_type_group": "with_children", "n_children": 1, "rate": 0.3},
                ]
            )
        )
        with pytest.raises(CsvValidationError):
            load_children_count_dist(csv_file, mapping_path=mapping_path)


# ---------------------------------------------------------------------------
# Cycle 5: DemographicByAgeSexRow + load_demographic_by_age_sex
# ---------------------------------------------------------------------------


class TestDemographicByAgeSexRowSchema:
    def test_valid_male_row(self) -> None:
        row = DemographicByAgeSexRow(age=30, sex="M", count=100)
        assert row.sex == "M"

    def test_invalid_sex_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DemographicByAgeSexRow(age=30, sex="X", count=100)

    def test_negative_age_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DemographicByAgeSexRow(age=-1, sex="M", count=100)

    def test_age_above_120_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DemographicByAgeSexRow(age=121, sex="M", count=100)


class TestLoadDemographicByAgeSex:
    def test_valid_csv(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import load_demographic_by_age_sex

        csv_file = tmp_path / "demographic_by_age_sex.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [
                    {"age": 30, "sex": "M", "count": 100},
                    {"age": 30, "sex": "F", "count": 95},
                ]
            )
        )
        rows = load_demographic_by_age_sex(csv_file)
        assert len(rows) == 2

    def test_invalid_sex_raises(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import CsvValidationError, load_demographic_by_age_sex

        csv_file = tmp_path / "demographic_by_age_sex.csv"
        csv_file.write_bytes(_csv_bytes([{"age": 30, "sex": "X", "count": 100}]))
        with pytest.raises(CsvValidationError):
            load_demographic_by_age_sex(csv_file)


# ---------------------------------------------------------------------------
# Cycle 6: AgeDiffParentChildRow + load_age_diff_parent_child
# ---------------------------------------------------------------------------


class TestAgeDiffParentChildRowSchema:
    def test_valid_row(self) -> None:
        row = AgeDiffParentChildRow(role="father", diff_min=20, diff_max=30, count=50)
        assert row.diff_min == 20

    def test_diff_min_ge_diff_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgeDiffParentChildRow(role="father", diff_min=30, diff_max=20, count=50)

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgeDiffParentChildRow(role="husband", diff_min=20, diff_max=30, count=50)


class TestLoadAgeDiffParentChild:
    def test_valid_csv(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import load_age_diff_parent_child

        csv_file = tmp_path / "age_diff_parent_child.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [
                    {"role": "father", "diff_min": 20, "diff_max": 30, "count": 50},
                    {"role": "mother", "diff_min": 18, "diff_max": 28, "count": 45},
                ]
            )
        )
        rows = load_age_diff_parent_child(csv_file)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# Cycle 7: AgeDiffCoupleRow + load_age_diff_couple (couple_diff 符号規則)
# ---------------------------------------------------------------------------


class TestAgeDiffCoupleRowSchema:
    def test_valid_row_positive_diff(self) -> None:
        """husband が年上（couple_diff > 0）は正常."""
        row = AgeDiffCoupleRow(diff_min=0, diff_max=5, count=30)
        assert row.diff_min == 0

    def test_valid_row_negative_diff(self) -> None:
        """妻が年上（couple_diff < 0）も正常."""
        row = AgeDiffCoupleRow(diff_min=-5, diff_max=0, count=20)
        assert row.diff_min == -5

    def test_diff_min_ge_diff_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgeDiffCoupleRow(diff_min=5, diff_max=0, count=10)


class TestLoadAgeDiffCouple:
    def test_valid_csv(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import load_age_diff_couple

        csv_file = tmp_path / "age_diff_couple.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [
                    {"diff_min": -5, "diff_max": 0, "count": 20},
                    {"diff_min": 0, "diff_max": 5, "count": 30},
                ]
            )
        )
        rows = load_age_diff_couple(csv_file)
        assert len(rows) == 2

    def test_couple_diff_sign_convention_documented(self) -> None:
        """couple_diff = husband_age - wife_age が data_contract.md に明文化されていること."""
        contract_path = WORKTREE / "docs" / "spec" / "data_contract.md"
        text = contract_path.read_text(encoding="utf-8")
        assert "husband_age - wife_age" in text, (
            "data_contract.md に couple_diff の符号規則が記述されていない"
        )


# ---------------------------------------------------------------------------
# Cycle 8: 任意 2 種
# ---------------------------------------------------------------------------


class TestDemographicByFamilyTypeRoleRowSchema:
    def test_valid_row(self) -> None:
        row = DemographicByFamilyTypeRoleRow(
            family_type="couple", role="husband", sex="M", age=40, count=10
        )
        assert row.age == 40

    def test_invalid_sex_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DemographicByFamilyTypeRoleRow(
                family_type="couple", role="husband", sex="Z", age=40, count=10
            )


class TestHouseholdSizeByFamilyTypeRowSchema:
    def test_valid_row(self) -> None:
        row = HouseholdSizeByFamilyTypeRow(family_type="couple", household_size=2, count=50)
        assert row.household_size == 2

    def test_zero_household_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HouseholdSizeByFamilyTypeRow(family_type="couple", household_size=0, count=50)


class TestLoadOptionalCsvFiles:
    def test_load_demographic_by_family_type_role(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import load_demographic_by_family_type_role

        csv_file = tmp_path / "demographic_by_family_type_role.csv"
        csv_file.write_bytes(
            _csv_bytes(
                [{"family_type": "couple", "role": "husband", "sex": "M", "age": 40, "count": 10}]
            )
        )
        rows = load_demographic_by_family_type_role(csv_file)
        assert len(rows) == 1

    def test_load_household_size_by_family_type(self, tmp_path: Path) -> None:
        from synthpop_jp.io.loaders import load_household_size_by_family_type

        csv_file = tmp_path / "household_size_by_family_type.csv"
        csv_file.write_bytes(
            _csv_bytes([{"family_type": "couple", "household_size": 2, "count": 50}])
        )
        rows = load_household_size_by_family_type(csv_file)
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Cycle 9: sample_case 往復テスト — 生成 CSV をローダで読み戻す
# ---------------------------------------------------------------------------


class TestSampleCaseRoundTrip:
    """data/sample_case/*.csv をローダで往復ロードできることを確認."""

    @pytest.mark.skipif(not DATA_SAMPLE.exists(), reason="data/sample_case が未生成")
    def test_round_trip_family_type_counts(self) -> None:
        from synthpop_jp.io.loaders import load_family_type_counts

        rows = load_family_type_counts(DATA_SAMPLE / "family_type_counts.csv")
        assert len(rows) > 0

    @pytest.mark.skipif(not DATA_SAMPLE.exists(), reason="data/sample_case が未生成")
    def test_round_trip_children_count_dist(self) -> None:
        from synthpop_jp.io.loaders import load_children_count_dist

        rows = load_children_count_dist(
            DATA_SAMPLE / "children_count_dist.csv",
            mapping_path=CONFIGS_DIR / "family_type_mapping.yaml",
        )
        assert len(rows) > 0

    @pytest.mark.skipif(not DATA_SAMPLE.exists(), reason="data/sample_case が未生成")
    def test_round_trip_demographic_by_age_sex(self) -> None:
        from synthpop_jp.io.loaders import load_demographic_by_age_sex

        rows = load_demographic_by_age_sex(DATA_SAMPLE / "demographic_by_age_sex.csv")
        assert len(rows) > 0

    @pytest.mark.skipif(not DATA_SAMPLE.exists(), reason="data/sample_case が未生成")
    def test_round_trip_age_diff_parent_child(self) -> None:
        from synthpop_jp.io.loaders import load_age_diff_parent_child

        rows = load_age_diff_parent_child(DATA_SAMPLE / "age_diff_parent_child.csv")
        assert len(rows) > 0

    @pytest.mark.skipif(not DATA_SAMPLE.exists(), reason="data/sample_case が未生成")
    def test_round_trip_age_diff_couple(self) -> None:
        from synthpop_jp.io.loaders import load_age_diff_couple

        rows = load_age_diff_couple(DATA_SAMPLE / "age_diff_couple.csv")
        assert len(rows) > 0

    def test_generate_sample_case_bitwise_identical(self, tmp_path: Path) -> None:
        """generate_sample_case.py を 2 回実行して CSV が bitwise 一致することを確認."""
        script = WORKTREE / "scripts" / "generate_sample_case.py"
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        out1.mkdir()
        out2.mkdir()

        result1 = subprocess.run(
            [sys.executable, str(script), "--output-dir", str(out1)],
            capture_output=True,
            text=True,
        )
        assert result1.returncode == 0, f"1回目失敗: {result1.stderr}"

        result2 = subprocess.run(
            [sys.executable, str(script), "--output-dir", str(out2)],
            capture_output=True,
            text=True,
        )
        assert result2.returncode == 0, f"2回目失敗: {result2.stderr}"

        for csv_file in out1.glob("*.csv"):
            file2 = out2 / csv_file.name
            assert file2.exists(), f"{csv_file.name} が2回目に存在しない"
            assert csv_file.read_bytes() == file2.read_bytes(), (
                f"{csv_file.name} の内容が一致しない（seed 固定が機能していない可能性）"
            )
