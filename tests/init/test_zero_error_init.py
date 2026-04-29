"""Tests for zero-error initial population (Murata 2017 §3, Issue #77).

`use_zero_error_init=True` で初期人口生成時に F-W 統計（family_type × sex
demographic pyramid）の誤差を 0 にする手続きを実装する。

論文 p.516:
> "Using the proposed generation method of an initial population with the above
> statistics, we can synthesize a population with no errors from the statistics
> F) to W). The errors in the statistics A) to C) about relations among family
> members should be minimized by an SA method."
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import numpy as np
import pytest

from synthpop_jp.config import ObjectiveConfig
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
from synthpop_jp.optimize.objective import ObjectiveState
from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.rng import SeedRegistry


class _Input(TypedDict):
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
def objective_input(sample_stats: InitStats) -> _Input:
    return _Input(
        age_diff_parent_child=load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv"),
        age_diff_couple=load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv"),
        demographic_by_age_sex=sample_stats.demographic_by_age_sex,
        demo_ft_role=sample_stats.demographic_by_family_type_role or [],
    )


class TestObjectiveConfigZeroErrorFlag:
    """ObjectiveConfig.use_zero_error_init."""

    def test_default_false(self) -> None:
        cfg = ObjectiveConfig()
        assert cfg.use_zero_error_init is False

    def test_can_enable(self) -> None:
        cfg = ObjectiveConfig(use_zero_error_init=True)
        assert cfg.use_zero_error_init is True


class TestGenerateInitialPopulationZeroError:
    """generate_initial_population(use_zero_error_init=True) の挙動."""

    def test_returns_population_arrays(self, sample_stats: InitStats) -> None:
        """zero_error mode で PopulationArrays を返す."""
        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(sample_stats, rng, use_zero_error_init=True)
        assert isinstance(arrays, PopulationArrays)
        assert arrays.n_persons > 0

    def test_default_keeps_existing_behavior(self, sample_stats: InitStats) -> None:
        """フラグ未指定では既存挙動と完全一致 (regression)."""
        rng_a = SeedRegistry(root=42).rng("init")
        rng_b = SeedRegistry(root=42).rng("init")
        arrays_a = generate_initial_population(sample_stats, rng_a)
        arrays_b = generate_initial_population(sample_stats, rng_b, use_zero_error_init=False)
        assert np.array_equal(arrays_a.age, arrays_b.age)
        assert np.array_equal(arrays_a.sex, arrays_b.sex)

    def test_zero_error_differs_from_default(self, sample_stats: InitStats) -> None:
        """zero_error mode は既定 (重み付きランダム) と異なる age 配列を返す."""
        rng_a = SeedRegistry(root=42).rng("init")
        rng_b = SeedRegistry(root=42).rng("init")
        arrays_default = generate_initial_population(sample_stats, rng_a)
        arrays_zero = generate_initial_population(sample_stats, rng_b, use_zero_error_init=True)
        assert not np.array_equal(arrays_default.age, arrays_zero.age), (
            "zero_error mode が既定と同じ age 配列を返している (差分が無い)"
        )

    def test_hard_constraints_satisfied(self, sample_stats: InitStats) -> None:
        """zero_error mode でも全 person のハード制約が満たされる."""
        from synthpop_jp.init.initial_population import ROLE_AGE_CONSTRAINTS

        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(sample_stats, rng, use_zero_error_init=True)

        for i in range(arrays.n_persons):
            role_id = int(arrays.role[i])
            age = int(arrays.age[i])
            role_name = arrays.role_reg.name_of(role_id)
            min_age, max_age = ROLE_AGE_CONSTRAINTS.get(role_name, (0, 120))
            assert min_age <= age <= max_age, (
                f"person {i} (role={role_name}, age={age}) がハード制約 "
                f"[{min_age}, {max_age}] を破っている"
            )


class TestZeroErrorInitFamilyTypePyramidL1:
    """zero_error mode で family_type × sex pyramid (F-W) の L1 誤差が下がる."""

    def test_extended_objective_l1_lower_with_zero_error(
        self, sample_stats: InitStats, objective_input: _Input
    ) -> None:
        """zero_error mode の方が family_type × sex pyramid の L1 が低い.

        sample_case では完全 0 化が達成できる前提（target が hard constraint と
        矛盾しない）。万一フォールバックが起きても、既存重み付きランダムよりは
        下がるはず。
        """
        # 既定モード（重み付きランダム）
        rng_default = SeedRegistry(root=42).rng("init")
        arrays_default = generate_initial_population(sample_stats, rng_default)

        # zero_error モード
        rng_zero = SeedRegistry(root=42).rng("init")
        arrays_zero = generate_initial_population(sample_stats, rng_zero, use_zero_error_init=True)

        # extended objective (use_family_type_pyramid=True) で L1 を測る
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

        # family_type × sex pyramid (stats[5..]) の L1 合計
        ft_l1_default = sum(s.l1_score() for s in obj_default.stats[5:])
        ft_l1_zero = sum(s.l1_score() for s in obj_zero.stats[5:])

        assert ft_l1_zero <= ft_l1_default, (
            f"zero_error mode が family_type pyramid の L1 を下げていない "
            f"(default={ft_l1_default}, zero={ft_l1_zero})"
        )


class TestDeterminism:
    """zero_error mode は同 seed で決定論的."""

    def test_same_seed_produces_same_arrays(self, sample_stats: InitStats) -> None:
        rng1 = SeedRegistry(root=42).rng("init")
        rng2 = SeedRegistry(root=42).rng("init")
        arrays1 = generate_initial_population(sample_stats, rng1, use_zero_error_init=True)
        arrays2 = generate_initial_population(sample_stats, rng2, use_zero_error_init=True)
        assert np.array_equal(arrays1.age, arrays2.age)
        assert np.array_equal(arrays1.sex, arrays2.sex)
        assert np.array_equal(arrays1.role, arrays2.role)
