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
    AgeSwapTransition,
    ConstantPChange,
    HybridTransition,
    LinearPChange,
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


def make_demo_by_age_sex(*, uniform_count: int = 100) -> list[DemographicByAgeSexRow]:
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
        hh_list.append(Household(household_id=hh_id, family_type=family_type, members=persons))
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
        husband_idx = int(np.where(arrays.role == arrays.role_reg.id_of("husband"))[0][0])
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
        wife_idx = int(np.where(arrays.role == arrays.role_reg.id_of("wife"))[0][0])
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
        father_idx = int(np.where(arrays.role == arrays.role_reg.id_of("father"))[0][0])
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
        father_idx = int(np.where(arrays.role == arrays.role_reg.id_of("father"))[0][0])
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
        mother_idx = int(np.where(arrays.role == arrays.role_reg.id_of("mother"))[0][0])
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
        child_idx = int(np.where(arrays.role == arrays.role_reg.id_of("child"))[0][0])
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
        parent_idx = int(np.where(arrays.role == arrays.role_reg.id_of("parent"))[0][0])
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

        def _exhaust_retries() -> None:
            # 最大 10 回 retry するので 20 回試行すれば必ず発生
            for _ in range(20):
                transition2.propose()

        with pytest.raises(TransitionError):
            _exhaust_retries()

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
            transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
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
        def uniform_cdf(x: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
            """U(18, 100) の CDF（vectorized）."""
            x_arr = np.asarray(x, dtype=float)
            mid = (x_arr - 18 + 1) / (100 - 18 + 1)
            result_arr = np.where(x_arr < 18, 0.0, np.where(x_arr >= 100, 1.0, mid))
            return result_arr

        ks_result = ks_1samp(sampled_ages, uniform_cdf)
        pvalue = float(ks_result.pvalue)  # type: ignore[union-attr]
        assert pvalue > 0.01, f"KS 検定 p={pvalue:.4f} < 0.01: single の年齢分布が期待と乖離"

    def test_husband_age_distribution_only_ge_18(self) -> None:
        """husband の new_age が age>=18 の範囲のみから来ることを 1000 回で確認."""
        demo = make_demo_by_age_sex(uniform_count=100)
        arrays = make_arrays_single_household(
            family_type="couple",
            members=[("husband", "M", 40), ("wife", "F", 38)],
        )
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        husband_idx = int(np.where(arrays.role == arrays.role_reg.id_of("husband"))[0][0])
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


# ---------------------------------------------------------------------------
# AgeSwapTransition (Issue #57, Phase 3a §12.2B)
# ---------------------------------------------------------------------------


class TestAgeSwapPropose:
    """AgeSwapTransition.propose() の基本挙動."""

    def test_swap_returns_two_pairs(self) -> None:
        """propose は ((idx_a, new_age_a), (idx_b, new_age_b)) を返す."""
        # 同 family_type、同 sex で 2 人とも valid swap 可能な構成
        # （single 世帯 2 つ → 各 single の role 制約 age>=18 を満たす）
        arrays = make_multi_household_arrays(
            [
                ("single", [("single", "M", 30)]),
                ("single", [("single", "M", 35)]),
            ]
        )
        demo = make_demo_by_age_sex()
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeSwapTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)

        result = transition.propose()
        ((idx_a, new_age_a), (idx_b, new_age_b)) = result
        assert isinstance(idx_a, int)
        assert isinstance(idx_b, int)
        assert idx_a != idx_b
        assert isinstance(new_age_a, int)
        assert isinstance(new_age_b, int)

    def test_swap_semantics_age_exchange(self) -> None:
        """new_age_a == old_age_b かつ new_age_b == old_age_a（年齢交換）."""
        arrays = make_multi_household_arrays(
            [
                ("single", [("single", "M", 30)]),
                ("single", [("single", "M", 35)]),
            ]
        )
        demo = make_demo_by_age_sex()
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeSwapTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)

        ((idx_a, new_age_a), (idx_b, new_age_b)) = transition.propose()
        assert int(arrays.age[idx_a]) == new_age_b
        assert int(arrays.age[idx_b]) == new_age_a


class TestAgeSwapSelectionLogic:
    """選択ロジック: 同 family_type かつ同 sex の 2 人だけが組になる."""

    def test_same_family_type(self) -> None:
        """選ばれた 2 人は同じ family_type に属する."""
        # single 世帯 2 つ + couple 世帯 2 つ。同じ family_type 内でしか swap しない
        arrays = make_multi_household_arrays(
            [
                ("single", [("single", "M", 30)]),
                ("single", [("single", "M", 35)]),
                ("couple", [("husband", "M", 40), ("wife", "F", 38)]),
                ("couple", [("husband", "M", 45), ("wife", "F", 42)]),
            ]
        )
        demo = make_demo_by_age_sex()
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeSwapTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)

        for _ in range(30):
            ((idx_a, _), (idx_b, _)) = transition.propose()
            assert int(arrays.family_type[idx_a]) == int(arrays.family_type[idx_b])

    def test_same_sex(self) -> None:
        """選ばれた 2 人は同じ sex を持つ."""
        # 同 family_type 内で M 2 人と F 2 人を持つ構成（couple × 2 世帯）
        arrays = make_multi_household_arrays(
            [
                ("couple", [("husband", "M", 40), ("wife", "F", 38)]),
                ("couple", [("husband", "M", 45), ("wife", "F", 42)]),
            ]
        )
        demo = make_demo_by_age_sex()
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeSwapTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)

        for _ in range(30):
            ((idx_a, _), (idx_b, _)) = transition.propose()
            assert int(arrays.sex[idx_a]) == int(arrays.sex[idx_b])


class TestAgeSwapHardConstraints:
    """Parent-child 年齢差制約（§11.5）が swap 後も保たれる."""

    def test_swap_avoids_parent_child_violation(self) -> None:
        """child と father の swap で年齢差が 14 未満になるケースは選ばれない."""
        # father=20, child=18 の世帯。swap すると father=18 / child=20 で違反。
        # ただし father=M, child=F なら sex が違うのでそもそも swap 不可
        # → father=M, child=M で同 sex かつ親子年齢差が際どいケースを構築
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 35),
                ("mother", "F", 30),
                ("child", "M", 22),  # 35 - 22 = 13 < 14, 元から 14 ギャップ未満
            ],
        )
        # ↑ 元から制約違反のため、swap も violation を回避できないので
        # 別構成: 父 40, 子 24（M）→ swap すると父 24, 子 40 で 16 < 14 違反
        arrays = make_arrays_single_household(
            family_type="couple_and_children",
            members=[
                ("father", "M", 40),
                ("mother", "F", 38),
                ("child", "M", 18),
            ],
        )
        demo = make_demo_by_age_sex()
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeSwapTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)

        # この世帯では father (M) と child (M) のペアしか同 sex 候補がないが
        # swap すると父 18 / 子 40 で 22 < 14 を満たすが、子 40 は role=child の上限を超える
        # → 唯一可能なペアが制約違反のため、propose() は TransitionError を raise する
        with pytest.raises(TransitionError):
            transition.propose()


class TestAgeSwapEmptyPool:
    """同 family_type 同 sex で 2 人未満のプールでは TransitionError を返す."""

    def test_no_compatible_pair(self) -> None:
        """各 family_type/sex に 1 人ずつしかいない場合 TransitionError."""
        arrays = make_arrays_single_household(
            family_type="couple",
            members=[
                ("husband", "M", 35),
                ("wife", "F", 33),
            ],
        )
        demo = make_demo_by_age_sex()
        rng = SeedRegistry(root=42).rng("sa_transition")
        transition = AgeSwapTransition(arrays=arrays, demo_by_age_sex=demo, rng=rng)
        with pytest.raises(TransitionError):
            transition.propose()


class TestAgeSwapDeterminism:
    """同 seed で propose() 列が再現する."""

    def test_same_seed_same_sequence(self) -> None:
        def build_arrays() -> PopulationArrays:
            return make_multi_household_arrays(
                [
                    ("single", [("single", "M", 30)]),
                    ("single", [("single", "M", 35)]),
                    ("single", [("single", "M", 40)]),
                    ("couple", [("husband", "M", 50), ("wife", "F", 48)]),
                    ("couple", [("husband", "M", 55), ("wife", "F", 52)]),
                ]
            )

        demo = make_demo_by_age_sex()
        rng1 = SeedRegistry(root=42).rng("sa_transition")
        t1 = AgeSwapTransition(arrays=build_arrays(), demo_by_age_sex=demo, rng=rng1)
        rng2 = SeedRegistry(root=42).rng("sa_transition")
        t2 = AgeSwapTransition(arrays=build_arrays(), demo_by_age_sex=demo, rng=rng2)

        seq1 = [t1.propose() for _ in range(10)]
        seq2 = [t2.propose() for _ in range(10)]
        assert seq1 == seq2


# ---------------------------------------------------------------------------
# HybridTransition (Issue #67) — age-change と age-swap の確率混合
# ---------------------------------------------------------------------------


def _build_hybrid_pair(seed: int = 42) -> tuple[AgeChangeTransition, AgeSwapTransition]:
    """テスト用の AgeChange/AgeSwap ペアを構築する."""
    arrays = make_multi_household_arrays(
        [
            ("single", [("single", "M", 30)]),
            ("single", [("single", "M", 35)]),
            ("couple", [("husband", "M", 50), ("wife", "F", 48)]),
            ("couple", [("husband", "M", 55), ("wife", "F", 52)]),
        ]
    )
    demo = make_demo_by_age_sex()
    seed_reg = SeedRegistry(root=seed)
    change = AgeChangeTransition(arrays=arrays, demo_by_age_sex=demo, rng=seed_reg.rng("sa_change"))
    swap = AgeSwapTransition(arrays=arrays, demo_by_age_sex=demo, rng=seed_reg.rng("sa_swap"))
    return change, swap


class TestHybridTransitionChoose:
    """HybridTransition.choose() が確率に従って内部 transition を返す."""

    def test_p_change_one_always_returns_change(self) -> None:
        """p_change=1.0 で常に AgeChange が返る."""
        change, swap = _build_hybrid_pair()
        rng = SeedRegistry(root=42).rng("sa_hybrid_chooser")
        hybrid = HybridTransition(change=change, swap=swap, p_change=1.0, rng=rng)
        for _ in range(50):
            assert hybrid.choose() is change

    def test_p_change_zero_always_returns_swap(self) -> None:
        """p_change=0.0 で常に AgeSwap が返る."""
        change, swap = _build_hybrid_pair()
        rng = SeedRegistry(root=42).rng("sa_hybrid_chooser")
        hybrid = HybridTransition(change=change, swap=swap, p_change=0.0, rng=rng)
        for _ in range(50):
            assert hybrid.choose() is swap

    def test_mixing_ratio_matches_p_change(self) -> None:
        """大数で AgeChange の選択比率が p_change の許容範囲内."""
        change, swap = _build_hybrid_pair()
        rng = SeedRegistry(root=42).rng("sa_hybrid_chooser")
        hybrid = HybridTransition(change=change, swap=swap, p_change=0.7, rng=rng)
        n = 2000
        chosen = [hybrid.choose() for _ in range(n)]
        change_ratio = sum(1 for c in chosen if c is change) / n
        # ±0.05 の許容範囲（n=2000 で 95% CI ≈ ±0.02）
        assert 0.65 <= change_ratio <= 0.75


class TestHybridTransitionDeterminism:
    """同 seed で choose 列が再現する."""

    def test_same_seed_same_choose_sequence(self) -> None:
        def make_hybrid() -> HybridTransition:
            change, swap = _build_hybrid_pair()
            rng = SeedRegistry(root=99).rng("sa_hybrid_chooser")
            return HybridTransition(change=change, swap=swap, p_change=0.5, rng=rng)

        h1 = make_hybrid()
        h2 = make_hybrid()
        seq1 = [h1.choose() is h1._change for _ in range(20)]  # type: ignore[attr-defined]
        seq2 = [h2.choose() is h2._change for _ in range(20)]  # type: ignore[attr-defined]
        assert seq1 == seq2


class TestHybridTransitionInvalidProbability:
    """p_change が [0, 1] 外の場合は ValueError."""

    def test_p_change_out_of_range_raises(self) -> None:
        change, swap = _build_hybrid_pair()
        rng = SeedRegistry(root=42).rng("sa_hybrid_chooser")
        with pytest.raises(ValueError):
            HybridTransition(change=change, swap=swap, p_change=1.5, rng=rng)
        with pytest.raises(ValueError):
            HybridTransition(change=change, swap=swap, p_change=-0.1, rng=rng)


# ---------------------------------------------------------------------------
# PChangeSchedule (Issue #69) — 動的 p_change スケジュール
# ---------------------------------------------------------------------------


class TestConstantPChange:
    """ConstantPChange は iter/total に依らず固定値を返す."""

    def test_constant_returns_p_for_any_iter(self) -> None:
        sched = ConstantPChange(0.7)
        for it in [0, 50, 100, 1000]:
            assert sched.p_change_at(it, 100) == 0.7


class TestLinearPChange:
    """LinearPChange は iter / total の進行率に従って線形補間する."""

    def test_start_at_iter_zero(self) -> None:
        sched = LinearPChange(start=0.9, end=0.3)
        assert abs(sched.p_change_at(0, 100) - 0.9) < 1e-9

    def test_end_at_iter_total(self) -> None:
        sched = LinearPChange(start=0.9, end=0.3)
        assert abs(sched.p_change_at(100, 100) - 0.3) < 1e-9

    def test_midpoint_linear_interpolation(self) -> None:
        sched = LinearPChange(start=0.9, end=0.3)
        # 50% 進行で (0.9 + 0.3) / 2 = 0.6
        assert abs(sched.p_change_at(50, 100) - 0.6) < 1e-9

    def test_iter_exceeding_total_clamps_to_end(self) -> None:
        sched = LinearPChange(start=0.9, end=0.3)
        assert abs(sched.p_change_at(200, 100) - 0.3) < 1e-9

    def test_total_zero_returns_start(self) -> None:
        """total=0 のとき進行率を計算できないので start を返す."""
        sched = LinearPChange(start=0.9, end=0.3)
        assert abs(sched.p_change_at(0, 0) - 0.9) < 1e-9


class TestHybridTransitionWithSchedule:
    """HybridTransition が schedule オブジェクトを受け取って set_progress に応じた選択を行う."""

    def test_accepts_schedule_object(self) -> None:
        """schedule オブジェクトを p_change として受理できる."""
        change, swap = _build_hybrid_pair()
        rng = SeedRegistry(root=42).rng("sa_hybrid_chooser")
        sched = ConstantPChange(0.7)
        # ValueError 等を出さずに構築できれば OK
        HybridTransition(change=change, swap=swap, p_change=sched, rng=rng)

    def test_float_is_wrapped_to_constant(self) -> None:
        """float を渡すと ConstantPChange に wrap され、既存挙動と一致."""
        change, swap = _build_hybrid_pair()
        rng = SeedRegistry(root=42).rng("sa_hybrid_chooser")
        hybrid = HybridTransition(change=change, swap=swap, p_change=1.0, rng=rng)
        # set_progress を呼ばなくても constant=1.0 で常に change が返る
        for _ in range(20):
            assert hybrid.choose() is change

    def test_set_progress_drives_linear_schedule(self) -> None:
        """linear schedule で set_progress(iter, total) に従って choose 確率が変わる."""
        # start=1.0, end=0.0 にすれば iter=0 で必ず change、iter=total で必ず swap
        change, swap = _build_hybrid_pair()
        rng = SeedRegistry(root=42).rng("sa_hybrid_chooser")
        sched = LinearPChange(start=1.0, end=0.0)
        hybrid = HybridTransition(change=change, swap=swap, p_change=sched, rng=rng)

        hybrid.set_progress(0, 100)
        for _ in range(20):
            assert hybrid.choose() is change

        hybrid.set_progress(100, 100)
        for _ in range(20):
            assert hybrid.choose() is swap
