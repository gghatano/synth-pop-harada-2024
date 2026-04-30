"""Tests for 9 family_types coverage (Issue #95).

sample_case が 9 family_types すべてを含むことを前提に、
- 初期生成で 9 family_types すべてが少なくとも 1 件現れる
- ``use_zero_error_init=True`` で family_type × sex pyramid (F-W) の L1
  が 9 family_types ごとに 0 または小さい値になる

を保証する。data 自体は既に 9 種を含むため、ここでは検証テスト追加が主作業
（#95 の本質）。
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import numpy as np
import pytest

from synthpop_jp.init.initial_population import InitStats, generate_initial_population
from synthpop_jp.io.loaders import (
    load_age_diff_couple,
    load_age_diff_parent_child,
    load_children_count_dist,
    load_demographic_by_age_sex,
    load_demographic_by_family_type_role,
    load_family_type_counts,
    load_family_type_mapping,
    load_household_size_by_family_type,
)
from synthpop_jp.io.schemas import (
    AgeDiffCoupleRow,
    AgeDiffParentChildRow,
    DemographicByAgeSexRow,
    DemographicByFamilyTypeRoleRow,
)
from synthpop_jp.optimize.objective import ObjectiveState, family_type_pyramid_index
from synthpop_jp.rng import SeedRegistry


class _ObjInput(TypedDict):
    age_diff_parent_child: list[AgeDiffParentChildRow]
    age_diff_couple: list[AgeDiffCoupleRow]
    demographic_by_age_sex: list[DemographicByAgeSexRow]
    demo_ft_role: list[DemographicByFamilyTypeRoleRow]


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("pyproject.toml not found")


_REPO_ROOT = _find_repo_root()
_DATA_DIR = _REPO_ROOT / "data" / "sample_case"
_CONFIGS_DIR = _REPO_ROOT / "configs"


# Murata 2017 / spec §8.1 で定義された 9 family_types。
_NINE_FAMILY_TYPES: tuple[str, ...] = (
    "single",
    "couple",
    "couple_and_children",
    "father_and_children",
    "mother_and_children",
    "couple_and_parents",
    "couple_and_a_parent",
    "couple_children_and_parents",
    "couple_children_and_a_parent",
)


@pytest.fixture
def sample_stats() -> InitStats:
    return InitStats(
        family_type_counts=load_family_type_counts(_DATA_DIR / "family_type_counts.csv"),
        children_count_dist=load_children_count_dist(_DATA_DIR / "children_count_dist.csv"),
        demographic_by_age_sex=load_demographic_by_age_sex(
            _DATA_DIR / "demographic_by_age_sex.csv"
        ),
        family_type_mapping=load_family_type_mapping(_CONFIGS_DIR / "family_type_mapping.yaml"),
        household_size_by_family_type=load_household_size_by_family_type(
            _DATA_DIR / "household_size_by_family_type.csv"
        ),
        demographic_by_family_type_role=load_demographic_by_family_type_role(
            _DATA_DIR / "demographic_by_family_type_role.csv"
        ),
    )


@pytest.fixture
def objective_input(sample_stats: InitStats) -> _ObjInput:
    return _ObjInput(
        age_diff_parent_child=load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv"),
        age_diff_couple=load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv"),
        demographic_by_age_sex=sample_stats.demographic_by_age_sex,
        demo_ft_role=sample_stats.demographic_by_family_type_role or [],
    )


class TestSampleCaseCoversNineFamilyTypes:
    """sample_case が 9 family_types すべてを最低 1 件ずつ含むことを保証する."""

    def test_family_type_counts_csv_has_nine_types(self, sample_stats: InitStats) -> None:
        """family_type_counts.csv に 9 種すべてが ≥1 件で存在."""
        actual = {row.family_type: row.count for row in sample_stats.family_type_counts}
        for ft in _NINE_FAMILY_TYPES:
            assert ft in actual, f"sample_case に family_type={ft!r} が無い"
            assert actual[ft] >= 1, f"family_type={ft!r} の count が 1 未満"

    def test_demographic_ft_role_csv_has_nine_types(self, sample_stats: InitStats) -> None:
        """demographic_by_family_type_role.csv に 9 種すべての row がある."""
        ft_set = {row.family_type for row in sample_stats.demographic_by_family_type_role or []}
        for ft in _NINE_FAMILY_TYPES:
            assert ft in ft_set, f"demographic_by_family_type_role に {ft!r} の row が無い"

    def test_household_size_csv_has_nine_types(self, sample_stats: InitStats) -> None:
        """household_size_by_family_type.csv に 9 種すべての row がある."""
        ft_set = {row.family_type for row in sample_stats.household_size_by_family_type or []}
        for ft in _NINE_FAMILY_TYPES:
            assert ft in ft_set, f"household_size_by_family_type に {ft!r} の row が無い"


class TestInitialPopulationCoversNineFamilyTypes:
    """初期生成結果に 9 family_types すべてが 1 件以上含まれる."""

    def test_all_nine_family_types_appear_in_default(self, sample_stats: InitStats) -> None:
        """既定モード（重み付きランダム）で 9 種すべてが生成される."""
        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(sample_stats, rng)

        present_ids = set(np.unique(arrays.family_type).tolist())
        present_names = {arrays.family_reg.name_of(int(i)) for i in present_ids}
        for ft in _NINE_FAMILY_TYPES:
            assert ft in present_names, f"既定モードで family_type={ft!r} が生成されていない"

    def test_all_nine_family_types_appear_in_zero_error(self, sample_stats: InitStats) -> None:
        """zero_error_init モードで 9 種すべてが生成される."""
        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(sample_stats, rng, use_zero_error_init=True)

        present_ids = set(np.unique(arrays.family_type).tolist())
        present_names = {arrays.family_reg.name_of(int(i)) for i in present_ids}
        for ft in _NINE_FAMILY_TYPES:
            assert ft in present_names, f"zero_error モードで family_type={ft!r} が生成されていない"


class TestFwL1PerFamilyTypeWithZeroError:
    """zero_error_init で各 family_type の F-W (family_type × sex pyramid) L1 が低い."""

    def test_per_family_type_l1_is_zero_or_low_with_zero_error(
        self, sample_stats: InitStats, objective_input: _ObjInput
    ) -> None:
        """zero_error_init=True で 9 family_types ごとに F-W L1 が default より下がる.

        sample_case の target は household_size_by_family_type と
        demographic_by_family_type_role の人数集計が完全に一致するとは
        限らない（実集計 CSV はラウンドや欠損を含む）。よって完全な 0 化は
        保証せず、「少なくとも default より同等以下」を保証する。
        達成できない family_type が出た場合は ``problem_fts`` に集約して
        report で扱う（テストは「全 family_type が default 以下」で pass）。
        """
        # default mode
        rng_default = SeedRegistry(root=42).rng("init")
        arrays_default = generate_initial_population(sample_stats, rng_default)

        # zero_error mode
        rng_zero = SeedRegistry(root=42).rng("init")
        arrays_zero = generate_initial_population(sample_stats, rng_zero, use_zero_error_init=True)

        # extended objective を組む
        obj_default = ObjectiveState.from_arrays(
            arrays=arrays_default,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        obj_zero = ObjectiveState.from_arrays(
            arrays=arrays_zero,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )

        offset = obj_zero.family_type_pyramid_offset
        assert offset is not None, "family_type_pyramid_offset が None"
        n_sex = 2

        per_ft_default: dict[str, float] = {}
        per_ft_zero: dict[str, float] = {}
        for ft_name in _NINE_FAMILY_TYPES:
            ft_id = arrays_zero.family_reg.id_of(ft_name)
            l1_default = 0.0
            l1_zero = 0.0
            for sex_id in range(n_sex):
                idx = family_type_pyramid_index(offset, ft_id, sex_id, n_sex=n_sex)
                l1_default += obj_default.stats[idx].l1_score()
                l1_zero += obj_zero.stats[idx].l1_score()
            per_ft_default[ft_name] = l1_default
            per_ft_zero[ft_name] = l1_zero

        # zero_error が default を上回る family_type は許容しない
        regressions = [ft for ft in _NINE_FAMILY_TYPES if per_ft_zero[ft] > per_ft_default[ft]]
        assert not regressions, (
            f"zero_error_init で L1 が悪化した family_type: {regressions}\n"
            f"default={per_ft_default}\nzero={per_ft_zero}"
        )
