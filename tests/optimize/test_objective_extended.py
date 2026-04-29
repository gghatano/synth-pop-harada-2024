"""Tests for extended objective with family_type × sex pyramid (Issue #71).

minimal 5 統計に加えて family_type 別 demographic pyramid を追加する拡張モード:
- `use_family_type_pyramid=True` で 5 + 2N 個の StatTable を構築
- 差分更新ロジックが family_type 別 pyramid も O(1) で更新
- AggregateStatL1Evaluator が新キーを出力

`docs/spec/spec.md` §11.3 / §11.4.1 (式(3)) に基づく段階的実装。
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
from synthpop_jp.optimize.objective import (
    ObjectiveState,
    build_objective_stats,
)
from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.rng import SeedRegistry


class ExtendedObjectiveInput(TypedDict):
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
def extended_input(sample_stats: InitStats) -> ExtendedObjectiveInput:
    return ExtendedObjectiveInput(
        age_diff_parent_child=load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv"),
        age_diff_couple=load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv"),
        demographic_by_age_sex=sample_stats.demographic_by_age_sex,
        demo_ft_role=sample_stats.demographic_by_family_type_role or [],
    )


class TestBuildObjectiveStatsExtended:
    """build_objective_stats の use_family_type_pyramid フラグ."""

    def test_default_returns_five_stats(
        self, sample_arrays: PopulationArrays, extended_input: ExtendedObjectiveInput
    ) -> None:
        """フラグ未指定では既存 5 統計のみ返す."""
        stats = build_objective_stats(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
        )
        assert len(stats) == 5

    def test_extended_returns_more_stats(
        self, sample_arrays: PopulationArrays, extended_input: ExtendedObjectiveInput
    ) -> None:
        """use_family_type_pyramid=True で 5 + 2N 個（N >= 1）."""
        stats = build_objective_stats(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
            demo_ft_role=extended_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        # 5 + (n_family_types * 2)
        n_ft = len(sample_arrays.family_reg.all_names())
        assert len(stats) == 5 + n_ft * 2

    def test_extended_each_pyramid_observed_sum_matches_population(
        self, sample_arrays: PopulationArrays, extended_input: ExtendedObjectiveInput
    ) -> None:
        """全 family_type × sex pyramid の observed 合計が人口に一致."""
        stats = build_objective_stats(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
            demo_ft_role=extended_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        n_ft = len(sample_arrays.family_reg.all_names())
        offset = 5
        ft_stats = stats[offset : offset + n_ft * 2]
        total_observed = sum(int(s.observed.sum()) for s in ft_stats)
        assert total_observed == sample_arrays.n_persons


class TestObjectiveStateExtended:
    """ObjectiveState の拡張モード."""

    def test_from_arrays_with_extended_flag(
        self, sample_arrays: PopulationArrays, extended_input: ExtendedObjectiveInput
    ) -> None:
        """from_arrays に use_family_type_pyramid=True を渡せて、attribute が立つ."""
        obj = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
            demo_ft_role=extended_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        assert obj.family_type_pyramid_offset == 5
        n_ft = len(sample_arrays.family_reg.all_names())
        assert len(obj.stats) == 5 + n_ft * 2

    def test_total_score_includes_extended_stats(
        self, sample_arrays: PopulationArrays, extended_input: ExtendedObjectiveInput
    ) -> None:
        """拡張モードの total_score は 拡張なしより大きい（追加統計の L1 が加算）."""
        obj_minimal = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
        )
        # 同じ arrays で再度（in-place 変更がないと仮定）
        obj_extended = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
            demo_ft_role=extended_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        # 5 統計部分の L1 は同じ。追加分は >= 0
        assert obj_extended.total_score >= obj_minimal.total_score

    def test_apply_change_keeps_score_consistent(
        self, sample_arrays: PopulationArrays, extended_input: ExtendedObjectiveInput
    ) -> None:
        """拡張モードで apply_change 後の total_score が再計算と一致 (差分更新の正しさ)."""
        obj = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
            demo_ft_role=extended_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        # 5 人について age を ±1 動かして差分更新後のスコアと再計算スコアが一致するか
        rng = SeedRegistry(root=999).rng("test")
        for _ in range(5):
            idx = int(rng.integers(0, sample_arrays.n_persons))
            old_age = int(sample_arrays.age[idx])
            new_age = max(18, min(80, old_age + int(rng.choice([-1, 1]))))
            if new_age == old_age:
                continue
            obj.apply_change(idx, new_age)

        # 再構築して比較
        obj_recomputed = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
            demo_ft_role=extended_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        assert abs(obj.total_score - obj_recomputed.total_score) < 1e-9

    def test_apply_change_updates_only_target_family_type_pyramid(
        self, sample_arrays: PopulationArrays, extended_input: ExtendedObjectiveInput
    ) -> None:
        """age-change で対象 person の (ft, sex) pyramid だけ変化、他 ft pyramid は不変."""
        obj = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=extended_input["age_diff_parent_child"],
            age_diff_couple=extended_input["age_diff_couple"],
            demographic_by_age_sex=extended_input["demographic_by_age_sex"],
            demo_ft_role=extended_input["demo_ft_role"],
            use_family_type_pyramid=True,
        )
        # snapshot of all extended stats observed arrays
        n_ft = len(sample_arrays.family_reg.all_names())
        offset = 5
        before = [obj.stats[offset + i].observed.copy() for i in range(n_ft * 2)]

        # 1 person を動かす
        idx = 0
        old_age = int(sample_arrays.age[idx])
        new_age = old_age + 1 if old_age < 80 else old_age - 1
        target_ft_id = int(sample_arrays.family_type[idx])
        target_sex_id = int(sample_arrays.sex[idx])
        target_pyramid_idx = target_ft_id * 2 + target_sex_id

        obj.apply_change(idx, new_age)

        for i in range(n_ft * 2):
            after = obj.stats[offset + i].observed
            if i == target_pyramid_idx:
                # 対象 pyramid は old_age で -1, new_age で +1 のはず
                assert not np.array_equal(after, before[i])
            else:
                assert np.array_equal(after, before[i]), (
                    f"family_type pyramid index {i} が変化（対象 {target_pyramid_idx} 以外なのに）"
                )
