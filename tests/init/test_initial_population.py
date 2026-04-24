"""Tests for initial_population.py — Steps 5〜6 and end-to-end.

TDD サイクル:
  Cycle 6: Step5 — sex assignment
  Cycle 7: Step6 — age assignment (hard constraints)
  Cycle 8: generate_initial_population() end-to-end (100 households, 1 sec)
  Cycle 9: Determinism and property tests
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from synthpop_jp.init.initial_population import (
    AgeAssignmentError,
    InitStats,
    assign_age,
    assign_sex,
    generate_initial_population,
)
from synthpop_jp.init.household_sampler import (
    HouseholdPlan,
    HouseholdRoleEntry,
    assign_children_counts,
    assign_household_counts,
    assign_household_sizes,
    expand_roles,
)
from synthpop_jp.io.loaders import (
    load_children_count_dist,
    load_demographic_by_age_sex,
    load_demographic_by_family_type_role,
    load_family_type_counts,
    load_family_type_mapping,
    load_household_size_by_family_type,
)
from synthpop_jp.io.schemas import (
    ChildrenCountDistRow,
    DemographicByAgeSexRow,
    DemographicByFamilyTypeRoleRow,
    FamilyTypeCountRow,
    HouseholdSizeByFamilyTypeRow,
)
from synthpop_jp.rng import SeedRegistry

# サンプルデータパス
_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "sample_case"
_CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rng() -> np.random.Generator:
    """固定 seed の乱数発生器."""
    reg = SeedRegistry(root=42)
    return reg.rng("init")


@pytest.fixture
def sample_stats() -> InitStats:
    """sample_case から読み込んだ統計データ."""
    return InitStats(
        family_type_counts=load_family_type_counts(_DATA_DIR / "family_type_counts.csv"),
        children_count_dist=load_children_count_dist(_DATA_DIR / "children_count_dist.csv"),
        demographic_by_age_sex=load_demographic_by_age_sex(_DATA_DIR / "demographic_by_age_sex.csv"),
        family_type_mapping=load_family_type_mapping(_CONFIGS_DIR / "family_type_mapping.yaml"),
        household_size_by_family_type=load_household_size_by_family_type(
            _DATA_DIR / "household_size_by_family_type.csv"
        ),
        demographic_by_family_type_role=load_demographic_by_family_type_role(
            _DATA_DIR / "demographic_by_family_type_role.csv"
        ),
    )


@pytest.fixture
def simple_demographic() -> list[DemographicByAgeSexRow]:
    """シンプルな人口ピラミッド（20〜60 歳均等）."""
    rows = []
    for age in range(20, 65, 5):
        rows.append(DemographicByAgeSexRow(age=age, sex="M", count=10))
        rows.append(DemographicByAgeSexRow(age=age, sex="F", count=10))
    return rows


@pytest.fixture
def simple_roles_couple() -> list[HouseholdRoleEntry]:
    """シンプルな couple 世帯 2 件のロール展開結果."""
    plans = [
        HouseholdPlan(family_type="couple", household_size=2, n_children=0),
        HouseholdPlan(family_type="couple", household_size=2, n_children=0),
    ]
    return [HouseholdRoleEntry(plan=p, roles=["husband", "wife"]) for p in plans]


# ---------------------------------------------------------------------------
# Cycle 6: Step5 — sex assignment
# ---------------------------------------------------------------------------


class TestAssignSex:
    """Cycle 6: assign_sex() のテスト."""

    def test_husband_gets_male(
        self, simple_roles_couple: list[HouseholdRoleEntry], rng: np.random.Generator
    ) -> None:
        """husband role には 'M' が割り当てられる."""
        result = assign_sex(simple_roles_couple, None, rng)
        for entry in result:
            for role, sex in zip(entry.roles, entry.sexes):
                if role == "husband":
                    assert sex == "M"

    def test_wife_gets_female(
        self, simple_roles_couple: list[HouseholdRoleEntry], rng: np.random.Generator
    ) -> None:
        """wife role には 'F' が割り当てられる."""
        result = assign_sex(simple_roles_couple, None, rng)
        for entry in result:
            for role, sex in zip(entry.roles, entry.sexes):
                if role == "wife":
                    assert sex == "F"

    def test_father_gets_male(self, rng: np.random.Generator) -> None:
        """father role には 'M' が割り当てられる."""
        plans = [HouseholdPlan(family_type="father_and_children", household_size=2, n_children=1)]
        entries = [HouseholdRoleEntry(plan=plans[0], roles=["father", "child"])]
        result = assign_sex(entries, None, rng)
        for entry in result:
            for role, sex in zip(entry.roles, entry.sexes):
                if role == "father":
                    assert sex == "M"

    def test_mother_gets_female(self, rng: np.random.Generator) -> None:
        """mother role には 'F' が割り当てられる."""
        plans = [HouseholdPlan(family_type="mother_and_children", household_size=2, n_children=1)]
        entries = [HouseholdRoleEntry(plan=plans[0], roles=["mother", "child"])]
        result = assign_sex(entries, None, rng)
        for entry in result:
            for role, sex in zip(entry.roles, entry.sexes):
                if role == "mother":
                    assert sex == "F"

    def test_sex_values_are_valid(
        self, simple_roles_couple: list[HouseholdRoleEntry], rng: np.random.Generator
    ) -> None:
        """全 sex 値が 'M' または 'F' のみ."""
        result = assign_sex(simple_roles_couple, None, rng)
        for entry in result:
            for sex in entry.sexes:
                assert sex in ("M", "F"), f"無効な sex 値: {sex}"


# ---------------------------------------------------------------------------
# Cycle 7: Step6 — age assignment
# ---------------------------------------------------------------------------


class TestAssignAge:
    """Cycle 7: assign_age() のテスト."""

    def test_child_gets_age_0_to_19(
        self, simple_demographic: list[DemographicByAgeSexRow], rng: np.random.Generator
    ) -> None:
        """child には 0〜19 歳 (あるいは利用可能な範囲の最小) が割り当てられる.

        child のハード制約は 0〜19 歳。ただし simple_demographic は 20〜60 のため
        child に割り当て可能な age がない。この場合は 20 歳以上から割り当てる
        (フォールバック)。このテストでは child に年齢が割り当てられることを確認する。
        """
        # child に割り当て可能な age を持つ demographic を使う
        demo = [
            DemographicByAgeSexRow(age=5, sex="M", count=10),
            DemographicByAgeSexRow(age=10, sex="M", count=10),
            DemographicByAgeSexRow(age=15, sex="M", count=10),
            DemographicByAgeSexRow(age=20, sex="M", count=10),
            DemographicByAgeSexRow(age=30, sex="F", count=10),
            DemographicByAgeSexRow(age=40, sex="F", count=10),
        ]
        plans = [HouseholdPlan(family_type="father_and_children", household_size=2, n_children=1)]
        role_entries = [HouseholdRoleEntry(plan=plans[0], roles=["father", "child"])]
        rng2 = SeedRegistry(root=42).rng("init")
        sex_entries = assign_sex(role_entries, None, rng2)
        aged = assign_age(sex_entries, demo, None, rng)
        for entry in aged:
            for role, age in zip(entry.roles, entry.ages):
                if role == "child":
                    assert age <= 19, f"child の年齢が 20 歳以上: {age}"

    def test_ages_are_non_negative(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """全 age 値が 0 以上."""
        hh_counts = assign_household_counts(sample_stats.family_type_counts)
        plans = assign_household_sizes(
            hh_counts, sample_stats.household_size_by_family_type
        )
        plans = assign_children_counts(
            plans, sample_stats.children_count_dist, sample_stats.family_type_mapping
        )
        role_entries = expand_roles(plans)
        rng2 = SeedRegistry(root=42).rng("init")
        sex_entries = assign_sex(
            role_entries, sample_stats.demographic_by_family_type_role, rng2
        )
        aged = assign_age(
            sex_entries,
            sample_stats.demographic_by_age_sex,
            sample_stats.demographic_by_family_type_role,
            rng,
        )
        for entry in aged:
            for age in entry.ages:
                assert age >= 0, f"age が負: {age}"

    def test_ages_at_most_120(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """全 age 値が 120 以下."""
        hh_counts = assign_household_counts(sample_stats.family_type_counts)
        plans = assign_household_sizes(
            hh_counts, sample_stats.household_size_by_family_type
        )
        plans = assign_children_counts(
            plans, sample_stats.children_count_dist, sample_stats.family_type_mapping
        )
        role_entries = expand_roles(plans)
        rng2 = SeedRegistry(root=42).rng("init")
        sex_entries = assign_sex(
            role_entries, sample_stats.demographic_by_family_type_role, rng2
        )
        aged = assign_age(
            sex_entries,
            sample_stats.demographic_by_age_sex,
            sample_stats.demographic_by_family_type_role,
            rng,
        )
        for entry in aged:
            for age in entry.ages:
                assert age <= 120, f"age が 120 超: {age}"


# ---------------------------------------------------------------------------
# Cycle 8: end-to-end
# ---------------------------------------------------------------------------


class TestGenerateInitialPopulation:
    """Cycle 8: generate_initial_population() の end-to-end テスト."""

    def test_family_type_counts_match_exactly(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """family_type 別世帯数が入力統計と完全一致する."""
        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()

        from collections import Counter
        actual_counts = Counter(hh.family_type for hh in households)
        for row in sample_stats.family_type_counts:
            assert actual_counts.get(row.family_type, 0) == row.count, (
                f"{row.family_type}: expected {row.count}, got {actual_counts.get(row.family_type, 0)}"
            )

    def test_household_size_distribution_matches_exactly(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """household_size 分布（family_type 毎）が入力統計と完全一致する."""
        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()

        if sample_stats.household_size_by_family_type is None:
            pytest.skip("household_size_by_family_type が None のためスキップ")

        from collections import Counter
        # family_type × household_size のクロス集計
        actual: dict[str, Counter[int]] = {}
        for hh in households:
            ft = hh.family_type
            sz = len(hh.members)
            if ft not in actual:
                actual[ft] = Counter()
            actual[ft][sz] += 1

        # CSV の分布と照合
        from collections import defaultdict
        expected: dict[str, dict[int, int]] = defaultdict(dict)
        for row in sample_stats.household_size_by_family_type:
            expected[row.family_type][row.household_size] = row.count

        for ft, size_counts in expected.items():
            for sz, cnt in size_counts.items():
                got = actual.get(ft, Counter()).get(sz, 0)
                assert got == cnt, (
                    f"{ft} size={sz}: expected {cnt}, got {got}"
                )

    def test_children_count_distribution_matches_exactly(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """children 数分布が入力統計と完全一致する（Largest Remainder 保証）."""
        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()

        with_children_fts = {
            ft
            for ft, grp in sample_stats.family_type_mapping.items()
            if grp == "with_children"
        }
        hh_with_children = [hh for hh in households if hh.family_type in with_children_fts]
        total = len(hh_with_children)

        if total == 0:
            return

        from collections import Counter
        # children 数 = child role を持つメンバー数
        actual_counts: Counter[int] = Counter()
        for hh in hh_with_children:
            n_children = sum(1 for m in hh.members if m.role == "child")
            actual_counts[n_children] += 1

        # expected を Largest Remainder で計算
        from synthpop_jp.init.household_sampler import largest_remainder

        group_rows = [
            r
            for r in sample_stats.children_count_dist
            if r.family_type_group == "with_children"
        ]
        rates = np.array([r.rate for r in group_rows])
        expected_counts = largest_remainder(rates, total)

        for i, row in enumerate(group_rows):
            got = actual_counts.get(row.n_children, 0)
            exp = int(expected_counts[i])
            assert got == exp, (
                f"n_children={row.n_children}: expected {exp}, got {got}"
            )

    def test_total_persons_equals_sum_of_household_sizes(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """総人数が全 household_size の合計に等しい."""
        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()
        total_persons = sum(len(hh.members) for hh in households)
        assert arrays.n_persons == total_persons

    def test_completes_within_one_second(
        self, sample_stats: InitStats
    ) -> None:
        """100 世帯の初期人口生成が 1 秒以内に完了する."""
        import time

        rng = SeedRegistry(root=42).rng("init")
        start = time.perf_counter()
        generate_initial_population(sample_stats, rng)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"生成時間 {elapsed:.3f}s が 1 秒を超えた"

    def test_no_invalid_sex_values(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """sex が 'M' または 'F' のみ."""
        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()
        for hh in households:
            for m in hh.members:
                assert m.sex in ("M", "F"), f"無効な sex: {m.sex}"

    def test_no_age_constraint_violations(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """role と age のハード制約を違反するレコード数が 0."""
        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()
        violations = []
        for hh in households:
            for m in hh.members:
                if m.role == "child" and m.age > 19:
                    violations.append(
                        f"HH {hh.household_id}: child age={m.age} > 19"
                    )
        assert len(violations) == 0, f"制約違反: {violations[:5]}"


# ---------------------------------------------------------------------------
# Cycle 9: Determinism and property tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Cycle 9: 決定性テスト."""

    def test_same_seed_produces_identical_households(
        self, sample_stats: InitStats
    ) -> None:
        """同じ seed で 2 回生成すると to_households() が完全一致する."""
        rng1 = SeedRegistry(root=42).rng("init")
        rng2 = SeedRegistry(root=42).rng("init")
        arrays1 = generate_initial_population(sample_stats, rng1)
        arrays2 = generate_initial_population(sample_stats, rng2)

        hh1 = arrays1.to_households()
        hh2 = arrays2.to_households()

        assert len(hh1) == len(hh2)
        for h1, h2 in zip(hh1, hh2):
            assert h1.household_id == h2.household_id
            assert h1.family_type == h2.family_type
            assert len(h1.members) == len(h2.members)
            for m1, m2 in zip(h1.members, h2.members):
                assert m1.age == m2.age
                assert m1.sex == m2.sex
                assert m1.role == m2.role

    def test_different_seeds_produce_different_ages(
        self, sample_stats: InitStats
    ) -> None:
        """異なる seed では（ほぼ確実に）異なる年齢分布になる."""
        rng1 = SeedRegistry(root=42).rng("init")
        rng2 = SeedRegistry(root=99).rng("init")
        arrays1 = generate_initial_population(sample_stats, rng1)
        arrays2 = generate_initial_population(sample_stats, rng2)
        # 全く同じになることはほぼない
        assert not np.array_equal(arrays1.age, arrays2.age), (
            "異なる seed で同一の age 配列が生成された（確率的に失敗するはずのテスト）"
        )

    def test_numpy_arrays_bitwise_equal_for_same_seed(
        self, sample_stats: InitStats
    ) -> None:
        """同じ seed で numpy 配列が bitwise 一致する."""
        rng1 = SeedRegistry(root=42).rng("init")
        rng2 = SeedRegistry(root=42).rng("init")
        arrays1 = generate_initial_population(sample_stats, rng1)
        arrays2 = generate_initial_population(sample_stats, rng2)

        assert np.array_equal(arrays1.age, arrays2.age)
        assert np.array_equal(arrays1.sex, arrays2.sex)
        assert np.array_equal(arrays1.role, arrays2.role)
        assert np.array_equal(arrays1.household_id, arrays2.household_id)
        assert np.array_equal(arrays1.family_type, arrays2.family_type)
