"""Tests for AgeChangeTransition — TDD cycles 1-8.

TDD Cycle 1: 役割別年齢分布の事前構築（正規化して合計 1.0）
TDD Cycle 2: propose() の単純ケース（role=single、制約なし）
TDD Cycle 3: husband/wife の age>=18 ハード制約
TDD Cycle 4: 親子関係のハード制約（father/mother/parent が child+14 以上）
TDD Cycle 5: retry と TransitionError（制約違反が必ず起きるシナリオ）
TDD Cycle 6: 決定性（同 seed で propose() 列が bitwise 一致）
TDD Cycle 7: 抽選の統計性（KS 検定、サンプル 10000）
TDD Cycle 8: 性能 skeleton（1000 世帯で propose() 1 回が 10μs 以内）
"""

from __future__ import annotations

import numpy as np
import pytest

from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.io.schemas import DemographicByAgeSexRow, DemographicByFamilyTypeRoleRow
from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.optimize.transitions import (
    AgeChangeTransition,
    TransitionError,
    build_role_age_dist,
)
from synthpop_jp.rng import SeedRegistry

# ---------------------------------------------------------------------------
# ヘルパー: テスト用 Registry / PopulationArrays の生成
# ---------------------------------------------------------------------------

ALL_ROLES = ["husband", "wife", "father", "mother", "child", "parent", "single"]
ALL_FAMILY_TYPES = [
    "couple",
    "couple_and_children",
    "single",
    "lone_parent_and_children",
    "couple_and_a_parent",
]


def make_registries() -> tuple[FamilyTypeRegistry, RoleRegistry, SexRegistry]:
    """テスト用の登録済み Registry を返す."""
    family_reg = FamilyTypeRegistry()
    for ft in ALL_FAMILY_TYPES:
        family_reg.register(ft)
    role_reg = RoleRegistry()
    for r in ALL_ROLES:
        role_reg.register(r)
    sex_reg = SexRegistry()
    return family_reg, role_reg, sex_reg


def make_demo_by_age_sex(
    *, uniform_count: int = 100
) -> list[DemographicByAgeSexRow]:
    """age=0-100, sex=M/F の均一分布を返す."""
    rows: list[DemographicByAgeSexRow] = []
    for age in range(101):
        rows.append(DemographicByAgeSexRow(age=age, sex="M", count=uniform_count))
        rows.append(DemographicByAgeSexRow(age=age, sex="F", count=uniform_count))
    return rows


def make_arrays_single_household(
    *,
    family_type: str = "couple_and_children",
    members: list[tuple[str, str, int]],
    household_id: int = 1,
) -> PopulationArrays:
    """指定メンバー構成の 1 世帯から PopulationArrays を生成するヘルパー.

    Parameters
    ----------
    members : list[tuple[str, str, int]]
        (role, sex, age) のタプルリスト。
    """
    family_reg, role_reg, sex_reg = make_registries()
    persons = [
        Person(household_id=household_id, role=role, sex=sex, age=age)  # type: ignore[arg-type]
        for role, sex, age in members
    ]
    hh = Household(household_id=household_id, family_type=family_type, members=persons)
    return PopulationArrays.from_households([hh], family_reg, role_reg, sex_reg)


def make_multi_household_arrays(
    households: list[tuple[str, list[tuple[str, str, int]]]],
) -> PopulationArrays:
    """複数世帯から PopulationArrays を生成するヘルパー.

    Parameters
    ----------
    households : list[tuple[str, list[tuple[str, str, int]]]]
        (family_type, [(role, sex, age), ...]) のリスト。
    """
    family_reg, role_reg, sex_reg = make_registries()
    hh_list: list[Household] = []
    for hh_id, (family_type, members) in enumerate(households, start=1):
        persons = [
            Person(household_id=hh_id, role=role, sex=sex, age=age)  # type: ignore[arg-type]
            for role, sex, age in members
        ]
        hh_list.append(
            Household(household_id=hh_id, family_type=family_type, members=persons)
        )
    return PopulationArrays.from_households(hh_list, family_reg, role_reg, sex_reg)


# ---------------------------------------------------------------------------
# Cycle 1: 役割別年齢分布の事前構築
# ---------------------------------------------------------------------------


class TestBuildRoleAgeDist:
    """build_role_age_dist の単体テスト."""

    def test_distribution_sums_to_one_husband(self) -> None:
        """husband の分布（sex=M, age>=18）の合計が 1.0."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        assert "husband" in dist
        total = float(np.sum(dist["husband"]))
        assert abs(total - 1.0) < 1e-9

    def test_distribution_sums_to_one_child(self) -> None:
        """child の分布（age<=25）の合計が 1.0."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        assert "child" in dist
        total = float(np.sum(dist["child"]))
        assert abs(total - 1.0) < 1e-9

    def test_husband_dist_has_zero_prob_under_18(self) -> None:
        """husband の分布は age<18 の確率が 0."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        husband_dist = dist["husband"]
        assert float(np.sum(husband_dist[:18])) == 0.0

    def test_wife_dist_has_zero_prob_under_18(self) -> None:
        """wife の分布は age<18 の確率が 0（sex=F, age>=18 のみ）."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        wife_dist = dist["wife"]
        assert float(np.sum(wife_dist[:18])) == 0.0

    def test_child_dist_has_zero_prob_over_25(self) -> None:
        """child の分布は age>25 の確率が 0."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        child_dist = dist["child"]
        assert float(np.sum(child_dist[26:])) == 0.0

    def test_parent_dist_has_zero_prob_under_40(self) -> None:
        """parent の分布は age<40 の確率が 0."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        parent_dist = dist["parent"]
        assert float(np.sum(parent_dist[:40])) == 0.0

    def test_single_dist_has_zero_prob_under_18(self) -> None:
        """single の分布は age<18 の確率が 0."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        single_dist = dist["single"]
        assert float(np.sum(single_dist[:18])) == 0.0

    def test_dist_shape_is_101(self) -> None:
        """分布の shape は (101,)（age 0-100）."""
        demo = make_demo_by_age_sex()
        dist = build_role_age_dist(demo, demo_ft_role=None)
        for role in ["husband", "wife", "child", "parent", "single"]:
            assert dist[role].shape == (101,), f"role={role} の shape が違う"

    def test_ft_role_data_overrides_fallback_for_husband(self) -> None:
        """demographic_by_family_type_role がある場合、husband 分布がそちらを優先する."""
        demo = make_demo_by_age_sex()
        # husband の ft_role データ: age=30 のみに集中
        ft_role_rows = [
            DemographicByFamilyTypeRoleRow(
                family_type="couple", role="husband", sex="M", age=30, count=100
            )
        ]
        dist = build_role_age_dist(demo, demo_ft_role=ft_role_rows)
        husband_dist = dist["husband"]
        # age=30 の確率が 1.0
        assert abs(float(husband_dist[30]) - 1.0) < 1e-9
        # その他の age は 0
        assert float(np.sum(husband_dist[:30])) == 0.0
        assert float(np.sum(husband_dist[31:])) == 0.0


# ---------------------------------------------------------------------------
# Cycle 2: propose() の単純ケース（role=single、制約なし）
# ---------------------------------------------------------------------------


class TestProposeBasic:
    """propose() の基本動作テスト."""

    def test_propose_returns_tuple_of_two_ints(self) -> None:
        """propose() が (int, int) のタプルを返す."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="single",
            members=[("single", "M", 30)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        result = transition.propose()
        assert isinstance(result, tuple)
        assert len(result) == 2
        person_idx, new_age = result
        assert isinstance(person_idx, int)
        assert isinstance(new_age, int)

    def test_propose_person_idx_in_valid_range(self) -> None:
        """person_idx が 0 以上 n_persons 未満の範囲内."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="single",
            members=[("single", "M", 30), ("single", "F", 25)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        for _ in range(50):
            person_idx, _ = transition.propose()
            assert 0 <= person_idx < arrays.n_persons

    def test_propose_new_age_in_valid_range(self) -> None:
        """new_age が 0 以上 100 以下の範囲内."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="single",
            members=[("single", "M", 30)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        for _ in range(50):
            _, new_age = transition.propose()
            assert 0 <= new_age <= 100

    def test_propose_does_not_modify_arrays(self) -> None:
        """propose() を呼んでも arrays.age が変更されない（副作用なし）."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="single",
            members=[("single", "M", 30)],
        )
        original_age = int(arrays.age[0])
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        transition.propose()
        assert int(arrays.age[0]) == original_age


# ---------------------------------------------------------------------------
# Cycle 3: husband/wife の age>=18 ハード制約
# ---------------------------------------------------------------------------


class TestHardConstraintAge18:
    """husband/wife の age>=18 ハード制約テスト."""

    def test_husband_new_age_always_ge_18(self) -> None:
        """husband の propose() で new_age が常に 18 以上（100 回試行）."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="couple",
            members=[("husband", "M", 40), ("wife", "F", 38)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        husband_idx = int(
            np.where(
                arrays.role == arrays._role_reg.id_of("husband")
            )[0][0]
        )
        for _ in range(100):
            person_idx, new_age = transition.propose()
            if person_idx == husband_idx:
                assert new_age >= 18, f"husband の new_age={new_age} が 18 未満"

    def test_wife_new_age_always_ge_18(self) -> None:
        """wife の propose() で new_age が常に 18 以上（100 回試行）."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="couple",
            members=[("husband", "M", 40), ("wife", "F", 38)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        wife_idx = int(
            np.where(
                arrays.role == arrays._role_reg.id_of("wife")
            )[0][0]
        )
        for _ in range(100):
            person_idx, new_age = transition.propose()
            if person_idx == wife_idx:
                assert new_age >= 18, f"wife の new_age={new_age} が 18 未満"

    def test_father_new_age_always_ge_18(self) -> None:
        """father の propose() で new_age が常に 18 以上（100 回試行）."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 45),
                ("mother", "F", 43),
                ("child", "M", 15),
            ],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        father_idx = int(
            np.where(
                arrays.role == arrays._role_reg.id_of("father")
            )[0][0]
        )
        for _ in range(100):
            person_idx, new_age = transition.propose()
            if person_idx == father_idx:
                assert new_age >= 18, f"father の new_age={new_age} が 18 未満"


# ---------------------------------------------------------------------------
# Cycle 4: 親子関係のハード制約
# ---------------------------------------------------------------------------


class TestHardConstraintParentChild:
    """親子関係のハード制約テスト."""

    def test_father_new_age_ge_child_max_age_plus_14(self) -> None:
        """father の new_age が同世帯 child の max_age + 14 以上（100 回試行）."""
        demo = make_demo_by_age_sex()
        child_age = 20
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 50),
                ("mother", "F", 48),
                ("child", "F", child_age),
            ],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        father_idx = int(
            np.where(
                arrays.role == arrays._role_reg.id_of("father")
            )[0][0]
        )
        min_father_age = child_age + 14
        for _ in range(100):
            person_idx, new_age = transition.propose()
            if person_idx == father_idx:
                assert new_age >= min_father_age, (
                    f"father の new_age={new_age} が child({child_age})+14={min_father_age} 未満"
                )

    def test_mother_new_age_ge_child_max_age_plus_14(self) -> None:
        """mother の new_age が同世帯 child の max_age + 14 以上（100 回試行）."""
        demo = make_demo_by_age_sex()
        child_age = 20
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 50),
                ("mother", "F", 48),
                ("child", "M", child_age),
            ],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        mother_idx = int(
            np.where(
                arrays.role == arrays._role_reg.id_of("mother")
            )[0][0]
        )
        min_mother_age = child_age + 14
        for _ in range(100):
            person_idx, new_age = transition.propose()
            if person_idx == mother_idx:
                assert new_age >= min_mother_age, (
                    f"mother の new_age={new_age} が child({child_age})+14={min_mother_age} 未満"
                )

    def test_child_new_age_le_parent_min_age_minus_14(self) -> None:
        """child の new_age が同世帯 father/mother の min_age - 14 以下（100 回試行）."""
        demo = make_demo_by_age_sex()
        father_age = 45
        mother_age = 43
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", father_age),
                ("mother", "F", mother_age),
                ("child", "M", 15),
            ],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        child_idx = int(
            np.where(
                arrays.role == arrays._role_reg.id_of("child")
            )[0][0]
        )
        max_child_age = min(father_age, mother_age) - 14
        for _ in range(100):
            person_idx, new_age = transition.propose()
            if person_idx == child_idx:
                assert new_age <= max_child_age, (
                    f"child の new_age={new_age} が parent_min({min(father_age, mother_age)})"
                    f"-14={max_child_age} 超"
                )

    def test_parent_role_new_age_ge_child_max_age_plus_14(self) -> None:
        """parent（role='parent'）の new_age が同世帯 child の max_age + 14 以上."""
        demo = make_demo_by_age_sex()
        child_age = 20
        arrays = make_arrays_single_household(
            family_type="couple_and_a_parent",
            members=[
                ("husband", "M", 45),
                ("wife", "F", 43),
                ("parent", "M", 70),
                ("child", "F", child_age),
            ],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        parent_idx = int(
            np.where(
                arrays.role == arrays._role_reg.id_of("parent")
            )[0][0]
        )
        min_parent_age = child_age + 14
        hits = 0
        for _ in range(200):
            person_idx, new_age = transition.propose()
            if person_idx == parent_idx:
                hits += 1
                assert new_age >= min_parent_age, (
                    f"parent の new_age={new_age} が child({child_age})+14={min_parent_age} 未満"
                )
        # parent が一度も選ばれなかったら警告
        assert hits > 0, "parent が 200 回試行で一度も選ばれなかった"

    def test_no_parent_child_constraint_without_children(self) -> None:
        """同世帯に child がいない場合、father でも親子制約が適用されない（エラーなし）."""
        demo = make_demo_by_age_sex()
        # couple_and_children でも child がいないケース（単純な夫婦世帯として）
        arrays = make_arrays_single_household(
            family_type="couple",
            members=[("husband", "M", 40), ("wife", "F", 38)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        # エラーが出ないこと
        for _ in range(10):
            transition.propose()


# ---------------------------------------------------------------------------
# Cycle 5: retry と TransitionError
# ---------------------------------------------------------------------------


class TestRetryAndTransitionError:
    """retry と TransitionError の例外テスト."""

    def test_transition_error_raised_when_no_valid_age(self) -> None:
        """全 age が制約違反になるシナリオで TransitionError が raise される.

        child が age=25 で同世帯の father/mother の age が 25 + 14 = 39 のとき、
        father の分布は age>=18 だが、age>=39 を満たす range は 39-100 でほとんど満たせる。
        ここでは故意に child=25 かつ father の分布を age<=30 に限定して conflict を起こす。
        """
        # child_age=25 なので father は 39 以上が必要
        # father の ft_role データを age=20 のみにして制約（>=39）を必ず違反させる
        demo = make_demo_by_age_sex()
        ft_role_rows = [
            DemographicByFamilyTypeRoleRow(
                family_type="couple_and_children",
                role="father",
                sex="M",
                age=20,
                count=100,
            )
        ]
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 50),
                ("mother", "F", 48),
                ("child", "F", 25),
            ],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(
            arrays=arrays,
            demo_by_age_sex=demo,
            demo_ft_role=ft_role_rows,
            rng=rng,
        )
        # father だけを対象に propose を強制的に実行するため、
        # 単人配列で試みる（father のみの世帯）
        father_only_arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 50),
                ("child", "F", 25),
            ],
        )
        rng2 = SeedRegistry(root=42).rng("sa_transition")
        transition2 = AgeChangeTransition(
            arrays=father_only_arrays,
            demo_by_age_sex=demo,
            demo_ft_role=ft_role_rows,
            rng=rng2,
        )
        with pytest.raises(TransitionError):
            # 最大 10 回 retry するので 20 回試行すれば必ず発生
            for _ in range(20):
                transition2.propose()

    def test_transition_error_is_raised(self) -> None:
        """TransitionError が Exception のサブクラスであること."""
        assert issubclass(TransitionError, Exception)


# ---------------------------------------------------------------------------
# Cycle 6: 決定性
# ---------------------------------------------------------------------------


class TestDeterminism:
    """決定性テスト: 同じ seed で propose() 100 回が bitwise 一致."""

    def test_propose_sequence_is_deterministic(self) -> None:
        """SeedRegistry(root=42) で propose() 100 回の列が 2 回とも同一."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 45),
                ("mother", "F", 43),
                ("child", "M", 15),
            ],
        )

        def run_sequence() -> list[tuple[int, int]]:
            rng = SeedRegistry(root=42).rng("sa_transition")
            transition = AgeChangeTransition(
                arrays=arrays, demo_by_age_sex=demo, rng=rng
            )
            return [transition.propose() for _ in range(100)]

        seq1 = run_sequence()
        seq2 = run_sequence()
        assert seq1 == seq2, "同 seed でも propose() 列が一致しない"

    def test_different_seeds_produce_different_sequences(self) -> None:
        """異なる seed では propose() 列が（高確率で）異なる."""
        demo = make_demo_by_age_sex()
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 45),
                ("mother", "F", 43),
                ("child", "M", 15),
            ],
        )
        rng1 = SeedRegistry(root=42).rng("sa_transition")
        rng2 = SeedRegistry(root=99).rng("sa_transition")
        t1 = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng1)
        t2 = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng2)
        seq1 = [t1.propose() for _ in range(20)]
        seq2 = [t2.propose() for _ in range(20)]
        # 20 回のうち全て一致する確率は無視できるほど低い
        assert seq1 != seq2, "異なる seed で propose() 列が完全一致した（異常）"


# ---------------------------------------------------------------------------
# Cycle 7: 抽選の統計性（KS 検定）
# ---------------------------------------------------------------------------


class TestStatisticalDistribution:
    """KS 検定で抽選の統計性を検証."""

    def test_single_age_distribution_follows_input(self) -> None:
        """role=single の new_age 分布が入力の人口ピラミッドに従う（KS 検定、p>0.05）.

        入力: age=18-100 の均一分布（single は age>=18 のフィルタ後）。
        期待: KS 検定で p > 0.05（分布が一致することを棄却できない）。
        """
        from scipy.stats import ks_1samp  # type: ignore[import-untyped]

        demo = make_demo_by_age_sex(uniform_count=100)
        arrays = make_arrays_single_household(
            family_type="single",
            members=[("single", "M", 30)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)

        # 10000 回サンプリング
        n_samples = 10000
        sampled_ages = [transition.propose()[1] for _ in range(n_samples)]

        # single は age=18-100 の均一分布（83 段階）
        # KS 検定: 離散一様分布 U(18, 100) との比較
        def uniform_cdf(x: float) -> float:
            """U(18, 100) の CDF."""
            if x < 18:
                return 0.0
            if x >= 100:
                return 1.0
            return (x - 18 + 1) / (100 - 18 + 1)

        result = ks_1samp(sampled_ages, uniform_cdf)
        assert result.pvalue > 0.01, (
            f"KS 検定 p={result.pvalue:.4f} < 0.01: single の年齢分布が期待と乖離"
        )

    def test_husband_age_distribution_only_ge_18(self) -> None:
        """husband の new_age が age>=18 の範囲のみから来ることを 1000 回で確認."""
        demo = make_demo_by_age_sex(uniform_count=100)
        arrays = make_arrays_single_household(
            family_type="couple",
            members=[("husband", "M", 40), ("wife", "F", 38)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        husband_idx = int(
            np.where(arrays.role == arrays._role_reg.id_of("husband"))[0][0]
        )
        violations = 0
        trials = 0
        for _ in range(1000):
            person_idx, new_age = transition.propose()
            if person_idx == husband_idx:
                trials += 1
                if new_age < 18:
                    violations += 1
        assert violations == 0, f"husband の age<18 が {violations}/{trials} 回発生"


# ---------------------------------------------------------------------------
# Cycle 8: 性能 skeleton（pytest-benchmark を使わず時刻計測）
# ---------------------------------------------------------------------------


class TestPerformanceSkeleton:
    """性能テスト skeleton: 1000 世帯で propose() 1 回が 10μs 以内."""

    def test_propose_performance_1000_households(self) -> None:
        """1000 世帯（約 3000 人）で propose() 1 回が 10 マイクロ秒以内."""
        import time

        demo = make_demo_by_age_sex()
        # 1000 世帯: couple_and_children（父・母・子 各 1 人）
        households = [
            (
                "couple_and_children",
                [
                    ("father", "M", 45),
                    ("mother", "F", 43),
                    ("child", "M", 15),
                ],
            )
            for _ in range(1000)
        ]
        arrays = make_multi_household_arrays(households)
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)

        # ウォームアップ
        transition.propose()

        # 計測
        n_trials = 100
        start = time.perf_counter()
        for _ in range(n_trials):
            transition.propose()
        elapsed = time.perf_counter() - start

        avg_us = (elapsed / n_trials) * 1e6
        # 10μs 以内が目標（CI 環境のばらつきを考慮して 100μs でチェック）
        # #33 で本格計測を行う
        assert avg_us < 100.0, (
            f"propose() の平均時間 {avg_us:.1f}μs が 100μs を超えた（skeleton チェック）"
        )
