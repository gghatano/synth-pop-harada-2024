"""Tests for strict_extended objective mode (Murata 2017 式(3) 準拠, Issue #76).

`exclude_male_female_pyramid=True` で D (male pyramid), E (female pyramid) を
目的関数から除外し、A + B + C + family_type×sex pyramid のみで SA を回す
モードを追加する。

論文 §3 / 式(3): "We do not employ the statistics D) and E) in our previous
method but employ finer demographic pyramids by sex and family type"
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import numpy as np
import pytest
from pydantic import ValidationError

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
def rng() -> np.random.Generator:
    return SeedRegistry(root=42).rng("init")


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
def sample_arrays(sample_stats: InitStats, rng: np.random.Generator) -> PopulationArrays:
    return generate_initial_population(sample_stats, rng)


@pytest.fixture
def objective_input(sample_stats: InitStats) -> _Input:
    return _Input(
        age_diff_parent_child=load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv"),
        age_diff_couple=load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv"),
        demographic_by_age_sex=sample_stats.demographic_by_age_sex,
        demo_ft_role=sample_stats.demographic_by_family_type_role or [],
    )


class TestObjectiveConfigValidator:
    """exclude_male_female_pyramid と use_family_type_pyramid の組合せ検証."""

    def test_default_both_false_is_valid(self) -> None:
        """default は両方 False で valid."""
        cfg = ObjectiveConfig()
        assert cfg.use_family_type_pyramid is False
        assert cfg.exclude_male_female_pyramid is False

    def test_extended_only_is_valid(self) -> None:
        """use_family_type_pyramid=True、exclude=False は valid (PR #72 の研究拡張モード)."""
        cfg = ObjectiveConfig(use_family_type_pyramid=True, exclude_male_female_pyramid=False)
        assert cfg.use_family_type_pyramid is True
        assert cfg.exclude_male_female_pyramid is False

    def test_strict_extended_is_valid(self) -> None:
        """use_family_type_pyramid=True、exclude=True は valid (Murata 式(3) 準拠)."""
        cfg = ObjectiveConfig(use_family_type_pyramid=True, exclude_male_female_pyramid=True)
        assert cfg.use_family_type_pyramid is True
        assert cfg.exclude_male_female_pyramid is True

    def test_exclude_without_family_type_pyramid_rejected(self) -> None:
        """exclude=True で use_family_type_pyramid=False は ValidationError."""
        with pytest.raises(ValidationError):
            ObjectiveConfig(use_family_type_pyramid=False, exclude_male_female_pyramid=True)


class TestObjectiveStateStrictExtended:
    """ObjectiveState が exclude_male_female_pyramid を反映する."""

    def test_total_score_excludes_male_female_pyramid(
        self, sample_arrays: PopulationArrays, objective_input: _Input
    ) -> None:
        """exclude=True の total_score は extended モードより低い (D, E が抜けるため)."""
        obj_extended = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=False,
        )
        obj_strict = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=True,
        )
        # D + E の L1 が引かれるので strict は extended 以下
        assert obj_strict.total_score <= obj_extended.total_score
        # 厳密には D, E の L1 分だけ違う
        d_l1 = obj_extended.stats[3].l1_score()
        e_l1 = obj_extended.stats[4].l1_score()
        assert abs(obj_extended.total_score - obj_strict.total_score - (d_l1 + e_l1)) < 1e-9

    def test_apply_change_does_not_update_excluded_stats(
        self, sample_arrays: PopulationArrays, objective_input: _Input
    ) -> None:
        """strict モードで age を動かしても D (stats[3]) / E (stats[4]) の observed 不変."""
        obj = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=True,
        )
        before_d = obj.stats[3].observed.copy()
        before_e = obj.stats[4].observed.copy()

        # 5 人 age を動かす
        rng = SeedRegistry(root=999).rng("test")
        for _ in range(5):
            idx = int(rng.integers(0, sample_arrays.n_persons))
            old_age = int(sample_arrays.age[idx])
            new_age = max(18, min(80, old_age + int(rng.choice([-1, 1]))))
            if new_age != old_age:
                obj.apply_change(idx, new_age)

        # stats[3] / stats[4] は不変
        assert np.array_equal(before_d, obj.stats[3].observed), (
            "exclude モードで D (male pyramid) が変化した"
        )
        assert np.array_equal(before_e, obj.stats[4].observed), (
            "exclude モードで E (female pyramid) が変化した"
        )

    def test_diff_update_consistent_with_recompute(
        self, sample_arrays: PopulationArrays, objective_input: _Input
    ) -> None:
        """strict モードでも差分更新と再計算が一致."""
        obj = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=True,
        )
        rng = SeedRegistry(root=999).rng("test")
        for _ in range(5):
            idx = int(rng.integers(0, sample_arrays.n_persons))
            old_age = int(sample_arrays.age[idx])
            new_age = max(18, min(80, old_age + int(rng.choice([-1, 1]))))
            if new_age != old_age:
                obj.apply_change(idx, new_age)

        obj_recomputed = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=True,
        )
        assert abs(obj.total_score - obj_recomputed.total_score) < 1e-9


class TestAggregateStatL1EvaluatorStrictExtended:
    """AggregateStatL1Evaluator が exclude モードで pyramid_male/female を出力しない."""

    def test_strict_mode_omits_pyramid_male_female_keys(
        self, sample_arrays: PopulationArrays, objective_input: _Input
    ) -> None:
        from synthpop_jp.evaluate.aggregate_metrics import AggregateStatL1Evaluator

        evaluator = AggregateStatL1Evaluator(
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=True,
        )
        result = evaluator.evaluate(sample_arrays)
        assert "aggregate.l1.pyramid_male" not in result
        assert "aggregate.l1.pyramid_female" not in result
        # A, B, C は残る
        assert "aggregate.l1.father_child_age_diff" in result
        assert "aggregate.l1.mother_child_age_diff" in result
        assert "aggregate.l1.couple_age_diff" in result
        # family_type pyramid は残る
        assert any(k.startswith("aggregate.l1.pyramid_per_family_type.") for k in result)
        # total は残る
        assert "aggregate.l1.total" in result

    def test_extended_mode_keeps_pyramid_male_female_keys(
        self, sample_arrays: PopulationArrays, objective_input: _Input
    ) -> None:
        """exclude=False (現状の研究拡張モード) では pyramid_male/female が残る (regression)."""
        from synthpop_jp.evaluate.aggregate_metrics import AggregateStatL1Evaluator

        evaluator = AggregateStatL1Evaluator(
            age_diff_parent_child=objective_input["age_diff_parent_child"],
            age_diff_couple=objective_input["age_diff_couple"],
            demographic_by_age_sex=objective_input["demographic_by_age_sex"],
            demo_ft_role=objective_input["demo_ft_role"],
            use_family_type_pyramid=True,
            exclude_male_female_pyramid=False,
        )
        result = evaluator.evaluate(sample_arrays)
        assert "aggregate.l1.pyramid_male" in result
        assert "aggregate.l1.pyramid_female" in result
