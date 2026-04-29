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

from synthpop_jp.init.household_sampler import (
    HouseholdPlan,
    HouseholdRoleEntry,
    assign_children_counts,
    assign_household_counts,
    assign_household_sizes,
    expand_roles,
)
from synthpop_jp.init.initial_population import (
    InitStats,
    assign_age,
    assign_sex,
    generate_initial_population,
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
    DemographicByAgeSexRow,
    DemographicByFamilyTypeRoleRow,
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
def simple_demographic() -> list[DemographicByAgeSexRow]:
    """シンプルな人口ピラミッド（20〜60 歳均等）."""
    rows: list[DemographicByAgeSexRow] = []
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
            for role, sex in zip(entry.roles, entry.sexes, strict=True):
                if role == "husband":
                    assert sex == "M"

    def test_wife_gets_female(
        self, simple_roles_couple: list[HouseholdRoleEntry], rng: np.random.Generator
    ) -> None:
        """wife role には 'F' が割り当てられる."""
        result = assign_sex(simple_roles_couple, None, rng)
        for entry in result:
            for role, sex in zip(entry.roles, entry.sexes, strict=True):
                if role == "wife":
                    assert sex == "F"

    def test_father_gets_male(self, rng: np.random.Generator) -> None:
        """father role には 'M' が割り当てられる."""
        plans = [HouseholdPlan(family_type="father_and_children", household_size=2, n_children=1)]
        entries = [HouseholdRoleEntry(plan=plans[0], roles=["father", "child"])]
        result = assign_sex(entries, None, rng)
        for entry in result:
            for role, sex in zip(entry.roles, entry.sexes, strict=True):
                if role == "father":
                    assert sex == "M"

    def test_mother_gets_female(self, rng: np.random.Generator) -> None:
        """mother role には 'F' が割り当てられる."""
        plans = [HouseholdPlan(family_type="mother_and_children", household_size=2, n_children=1)]
        entries = [HouseholdRoleEntry(plan=plans[0], roles=["mother", "child"])]
        result = assign_sex(entries, None, rng)
        for entry in result:
            for role, sex in zip(entry.roles, entry.sexes, strict=True):
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
            for role, age in zip(entry.roles, entry.ages, strict=True):
                if role == "child":
                    assert age <= 19, f"child の年齢が 20 歳以上: {age}"

    def test_ages_are_non_negative(self, sample_stats: InitStats, rng: np.random.Generator) -> None:
        """全 age 値が 0 以上."""
        hh_counts = assign_household_counts(sample_stats.family_type_counts)
        plans = assign_household_sizes(hh_counts, sample_stats.household_size_by_family_type)
        plans = assign_children_counts(
            plans, sample_stats.children_count_dist, sample_stats.family_type_mapping
        )
        role_entries = expand_roles(plans)
        rng2 = SeedRegistry(root=42).rng("init")
        sex_entries = assign_sex(role_entries, sample_stats.demographic_by_family_type_role, rng2)
        aged = assign_age(
            sex_entries,
            sample_stats.demographic_by_age_sex,
            sample_stats.demographic_by_family_type_role,
            rng,
        )
        for entry in aged:
            for age in entry.ages:
                assert age >= 0, f"age が負: {age}"

    def test_ages_at_most_120(self, sample_stats: InitStats, rng: np.random.Generator) -> None:
        """全 age 値が 120 以下."""
        hh_counts = assign_household_counts(sample_stats.family_type_counts)
        plans = assign_household_sizes(hh_counts, sample_stats.household_size_by_family_type)
        plans = assign_children_counts(
            plans, sample_stats.children_count_dist, sample_stats.family_type_mapping
        )
        role_entries = expand_roles(plans)
        rng2 = SeedRegistry(root=42).rng("init")
        sex_entries = assign_sex(role_entries, sample_stats.demographic_by_family_type_role, rng2)
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
            got = actual_counts.get(row.family_type, 0)
            assert got == row.count, f"{row.family_type}: expected {row.count}, got {got}"

    def test_household_size_distribution_matches_exactly(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """household_size 分布（family_type 毎）が Largest Remainder 割付と一致する.

        household_size_by_family_type.csv の counts は比率を表すサンプル。
        実際の割付は family_type_counts に従った世帯数を CSV の比率で配分し、
        Largest Remainder で整数化する。この割付結果が生成結果と一致することを確認する。
        """
        from collections import Counter, defaultdict

        from synthpop_jp.init.household_sampler import largest_remainder

        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()

        if sample_stats.household_size_by_family_type is None:
            pytest.skip("household_size_by_family_type が None のためスキップ")

        # family_type × household_size のクロス集計
        actual: dict[str, Counter[int]] = {}
        for hh in households:
            ft = hh.family_type
            sz = len(hh.members)
            if ft not in actual:
                actual[ft] = Counter()
            actual[ft][sz] += 1

        # CSV の比率から Largest Remainder で期待される割付を計算
        ft_size_csv: dict[str, dict[int, int]] = defaultdict(dict)
        for row in sample_stats.household_size_by_family_type:
            ft_size_csv[row.family_type][row.household_size] = row.count

        ft_total = {row.family_type: row.count for row in sample_stats.family_type_counts}

        for ft, size_map in ft_size_csv.items():
            total = ft_total.get(ft, 0)
            if total == 0:
                continue
            sizes = sorted(size_map.keys())
            raw = np.array([size_map[s] for s in sizes], dtype=float)
            raw_sum = raw.sum()
            if raw_sum == 0:
                continue
            rates = raw / raw_sum
            expected_alloc = largest_remainder(rates, total)

            for sz, exp_cnt in zip(sizes, expected_alloc, strict=True):
                got = actual.get(ft, Counter()).get(sz, 0)
                assert got == int(exp_cnt), f"{ft} size={sz}: expected {exp_cnt}, got {got}"

    def test_children_count_distribution_matches_exactly(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """children 数が household_size から正しく導出される.

        household_size_by_family_type.csv がある場合（モード A）:
            n_children = household_size - base_size で決定論的に導出される。
            生成結果の child role 数が household_size の想定と一致することを確認する。

        household_size_by_family_type.csv がない場合（モード B）:
            children_count_dist.csv の分布から Largest Remainder で割り付けられる。
            このテストケースでは CSV ありのため、モード A の挙動を確認する。
        """

        from synthpop_jp.domain.family_types import FAMILY_TEMPLATES

        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()

        with_children_fts = {
            ft for ft, grp in sample_stats.family_type_mapping.items() if grp == "with_children"
        }

        for hh in households:
            if hh.family_type not in with_children_fts:
                continue
            tmpl = FAMILY_TEMPLATES.get(hh.family_type)
            if tmpl is None:
                continue
            n_children_actual = sum(1 for m in hh.members if m.role == "child")
            expected_n_children = len(hh.members) - tmpl.base_size
            assert n_children_actual == expected_n_children, (
                f"{hh.family_type}: members={len(hh.members)}, "
                f"base_size={tmpl.base_size}, "
                f"expected n_children={expected_n_children}, "
                f"actual child count={n_children_actual}"
            )

    def test_children_count_distribution_exact_match_mode_b(self, sample_stats: InitStats) -> None:
        """household_size CSV なし（モード B）: children 数分布が Largest Remainder と完全一致."""
        from collections import Counter

        from synthpop_jp.init.household_sampler import largest_remainder

        # household_size_by_family_type なしの統計
        stats_no_size = InitStats(
            family_type_counts=sample_stats.family_type_counts,
            children_count_dist=sample_stats.children_count_dist,
            demographic_by_age_sex=sample_stats.demographic_by_age_sex,
            family_type_mapping=sample_stats.family_type_mapping,
            household_size_by_family_type=None,  # CSV なし → モード B
            demographic_by_family_type_role=sample_stats.demographic_by_family_type_role,
        )

        rng2 = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(stats_no_size, rng2)
        households = arrays.to_households()

        with_children_fts = {
            ft for ft, grp in sample_stats.family_type_mapping.items() if grp == "with_children"
        }
        hh_with_children = [hh for hh in households if hh.family_type in with_children_fts]
        total = len(hh_with_children)

        if total == 0:
            return

        actual_counts: Counter[int] = Counter()
        for hh in hh_with_children:
            n_children = sum(1 for m in hh.members if m.role == "child")
            actual_counts[n_children] += 1

        group_rows = [
            r for r in sample_stats.children_count_dist if r.family_type_group == "with_children"
        ]
        rates = np.array([r.rate for r in group_rows])
        expected_counts = largest_remainder(rates, total)

        for i, row in enumerate(group_rows):
            got = actual_counts.get(row.n_children, 0)
            exp = int(expected_counts[i])
            assert got == exp, f"n_children={row.n_children}: expected {exp}, got {got}"

    def test_total_persons_equals_sum_of_household_sizes(
        self, sample_stats: InitStats, rng: np.random.Generator
    ) -> None:
        """総人数が全 household_size の合計に等しい."""
        arrays = generate_initial_population(sample_stats, rng)
        households = arrays.to_households()
        total_persons = sum(len(hh.members) for hh in households)
        assert arrays.n_persons == total_persons

    def test_completes_within_one_second(self, sample_stats: InitStats) -> None:
        """100 世帯の初期人口生成が 1 秒以内に完了する."""
        import time

        rng = SeedRegistry(root=42).rng("init")
        start = time.perf_counter()
        generate_initial_population(sample_stats, rng)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"生成時間 {elapsed:.3f}s が 1 秒を超えた"

    def test_no_invalid_sex_values(self, sample_stats: InitStats, rng: np.random.Generator) -> None:
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
        violations: list[str] = []
        for hh in households:
            for m in hh.members:
                if m.role == "child" and m.age > 19:
                    violations.append(f"HH {hh.household_id}: child age={m.age} > 19")
        assert len(violations) == 0, f"制約違反: {violations[:5]}"


# ---------------------------------------------------------------------------
# Cycle 9: Determinism and property tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Cycle 9: 決定性テスト."""

    def test_same_seed_produces_identical_households(self, sample_stats: InitStats) -> None:
        """同じ seed で 2 回生成すると to_households() が完全一致する."""
        rng1 = SeedRegistry(root=42).rng("init")
        rng2 = SeedRegistry(root=42).rng("init")
        arrays1 = generate_initial_population(sample_stats, rng1)
        arrays2 = generate_initial_population(sample_stats, rng2)

        hh1 = arrays1.to_households()
        hh2 = arrays2.to_households()

        assert len(hh1) == len(hh2)
        for h1, h2 in zip(hh1, hh2, strict=True):
            assert h1.household_id == h2.household_id
            assert h1.family_type == h2.family_type
            assert len(h1.members) == len(h2.members)
            for m1, m2 in zip(h1.members, h2.members, strict=True):
                assert m1.age == m2.age
                assert m1.sex == m2.sex
                assert m1.role == m2.role

    def test_different_seeds_produce_different_ages(self, sample_stats: InitStats) -> None:
        """異なる seed では（ほぼ確実に）異なる年齢分布になる."""
        rng1 = SeedRegistry(root=42).rng("init")
        rng2 = SeedRegistry(root=99).rng("init")
        arrays1 = generate_initial_population(sample_stats, rng1)
        arrays2 = generate_initial_population(sample_stats, rng2)
        # 全く同じになることはほぼない
        assert not np.array_equal(arrays1.age, arrays2.age), (
            "異なる seed で同一の age 配列が生成された（確率的に失敗するはずのテスト）"
        )

    def test_numpy_arrays_bitwise_equal_for_same_seed(self, sample_stats: InitStats) -> None:
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


# ---------------------------------------------------------------------------
# Issue #75: ft × role × sex 別 age プールが実際に活用されている保証
# ---------------------------------------------------------------------------


class TestFamilyTypeRoleSexAgePool:
    """``demographic_by_family_type_role`` が assign_age で実際に効いているか.

    このクラスは Issue #75 で追加した保証テスト。実装は既に存在するが、
    ft × role × sex 別プールがフォールバック経路に落ちずに使われていることを
    保証するためのカバレッジを追加する。
    """

    def test_ft_role_sex_pool_drives_age_when_present(self, sample_stats: InitStats) -> None:
        """demo_ft_role を渡すと、対応する family_type の age 分布が target に近い.

        極端な demo_ft_role を作って (couple, husband, M) の age を全部 30 にし、
        生成人口でその組合せの person 全員が age=30 になることを確認する。
        フォールバック (demographic_by_age_sex) なら一様分布 20-60 になるはずなので
        100% 30 は ft × role × sex 別プールが使われた証左になる。
        """
        # couple 世帯 5 件のみの最小 stats
        from synthpop_jp.io.schemas import (
            ChildrenCountDistRow,
            FamilyTypeCountRow,
            HouseholdSizeByFamilyTypeRow,
        )

        ft_counts = [FamilyTypeCountRow(family_type="couple", count=5)]
        children_dist = [
            ChildrenCountDistRow(family_type_group="with_children", n_children=0, rate=1.0)
        ]
        # demographic_by_age_sex は均等 20-60 を全 sex で
        demo_age_sex: list[DemographicByAgeSexRow] = []
        for age in range(20, 65, 5):
            demo_age_sex.append(DemographicByAgeSexRow(age=age, sex="M", count=10))
            demo_age_sex.append(DemographicByAgeSexRow(age=age, sex="F", count=10))
        # ft_role: couple husband M は age=30 のみ、couple wife F は age=28 のみ
        demo_ft_role = [
            DemographicByFamilyTypeRoleRow(
                family_type="couple", role="husband", sex="M", age=30, count=100
            ),
            DemographicByFamilyTypeRoleRow(
                family_type="couple", role="wife", sex="F", age=28, count=100
            ),
        ]
        size_dist = [HouseholdSizeByFamilyTypeRow(family_type="couple", household_size=2, count=5)]
        stats = InitStats(
            family_type_counts=ft_counts,
            children_count_dist=children_dist,
            demographic_by_age_sex=demo_age_sex,
            family_type_mapping=sample_stats.family_type_mapping,
            household_size_by_family_type=size_dist,
            demographic_by_family_type_role=demo_ft_role,
        )

        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(stats, rng)

        # couple_husband (M) は全員 age=30、couple_wife (F) は全員 age=28
        husband_id = arrays.role_reg.id_of("husband")
        wife_id = arrays.role_reg.id_of("wife")
        m_id = arrays.sex_reg.id_of("M")
        f_id = arrays.sex_reg.id_of("F")

        husband_mask = (arrays.role == husband_id) & (arrays.sex == m_id)
        wife_mask = (arrays.role == wife_id) & (arrays.sex == f_id)

        husband_ages = arrays.age[husband_mask]
        wife_ages = arrays.age[wife_mask]

        assert len(husband_ages) == 5, "husband が 5 人いるはず"
        assert len(wife_ages) == 5, "wife が 5 人いるはず"
        assert all(int(a) == 30 for a in husband_ages), (
            f"全 husband の age が 30 のはず: {husband_ages.tolist()}"
        )
        assert all(int(a) == 28 for a in wife_ages), (
            f"全 wife の age が 28 のはず: {wife_ages.tolist()}"
        )

    def test_falls_back_when_ft_role_sex_pool_missing(self, sample_stats: InitStats) -> None:
        """demo_ft_role に該当 (ft, role, sex) が無いとき、demographic_by_age_sex に
        フォールバックしてハード制約を満たす age が選ばれる."""
        from synthpop_jp.io.schemas import (
            ChildrenCountDistRow,
            FamilyTypeCountRow,
            HouseholdSizeByFamilyTypeRow,
        )

        ft_counts = [FamilyTypeCountRow(family_type="couple", count=3)]
        children_dist = [
            ChildrenCountDistRow(family_type_group="with_children", n_children=0, rate=1.0)
        ]
        demo_age_sex: list[DemographicByAgeSexRow] = []
        for age in range(20, 65, 5):
            demo_age_sex.append(DemographicByAgeSexRow(age=age, sex="M", count=10))
            demo_age_sex.append(DemographicByAgeSexRow(age=age, sex="F", count=10))
        # demo_ft_role には couple は無い (single だけ) → フォールバックが発動するはず
        demo_ft_role = [
            DemographicByFamilyTypeRoleRow(
                family_type="single", role="single", sex="M", age=40, count=100
            ),
        ]
        size_dist = [HouseholdSizeByFamilyTypeRow(family_type="couple", household_size=2, count=3)]
        stats = InitStats(
            family_type_counts=ft_counts,
            children_count_dist=children_dist,
            demographic_by_age_sex=demo_age_sex,
            family_type_mapping=sample_stats.family_type_mapping,
            household_size_by_family_type=size_dist,
            demographic_by_family_type_role=demo_ft_role,
        )

        rng = SeedRegistry(root=42).rng("init")
        arrays = generate_initial_population(stats, rng)

        # couple は demo_ft_role に無いのでフォールバック → age は 20-60 の範囲
        # ハード制約 (husband/wife は >= 18) も満たす
        husband_id = arrays.role_reg.id_of("husband")
        m_id = arrays.sex_reg.id_of("M")
        husband_mask = (arrays.role == husband_id) & (arrays.sex == m_id)
        husband_ages = arrays.age[husband_mask]

        assert len(husband_ages) == 3
        for age in husband_ages:
            assert 18 <= int(age) <= 100, f"フォールバック後の age が範囲外: {age}"

    def test_extended_objective_score_differs_with_ft_role_sex_pool(
        self, sample_stats: InitStats
    ) -> None:
        """demo_ft_role を渡したかどうかで extended objective の初期スコアが変わる.

        想定: ft × role × sex 別プールが使われていれば年齢分布が変化し、
        family_type pyramid を含む extended objective のスコアも変わる
        （改善方向とは限らない、後述の regression note 参照）。

        Regression note (Issue #75 plan):
            sample_case では demo_ft_role 使用時のスコアが **悪化** することが
            観測された (with=822 > without=799 at seed=42)。理由は
            demographic_by_family_type_role の age 粒度が荒く、家族類型の
            age 分布を狭く固定してしまうため、フォールバック (sex 別の幅広い
            分布) よりも family_type pyramid target との合致が下がる。
            これは「品質は実装と暗黙の仕様の組合せに依存する」典型例として
            handoff doc / extended-summary に記録。
        """
        from synthpop_jp.io.loaders import load_age_diff_couple, load_age_diff_parent_child
        from synthpop_jp.optimize.objective import ObjectiveState

        age_diff_pc = load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv")
        age_diff_cp = load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv")

        # WITH demo_ft_role
        rng_with = SeedRegistry(root=42).rng("init")
        arrays_with = generate_initial_population(sample_stats, rng_with)
        obj_with = ObjectiveState.from_arrays(
            arrays=arrays_with,
            age_diff_parent_child=age_diff_pc,
            age_diff_couple=age_diff_cp,
            demographic_by_age_sex=sample_stats.demographic_by_age_sex,
            demo_ft_role=sample_stats.demographic_by_family_type_role,
            use_family_type_pyramid=True,
        )

        # WITHOUT demo_ft_role (fallback to age_sex only)
        stats_without = InitStats(
            family_type_counts=sample_stats.family_type_counts,
            children_count_dist=sample_stats.children_count_dist,
            demographic_by_age_sex=sample_stats.demographic_by_age_sex,
            family_type_mapping=sample_stats.family_type_mapping,
            household_size_by_family_type=sample_stats.household_size_by_family_type,
            demographic_by_family_type_role=None,
        )
        rng_without = SeedRegistry(root=42).rng("init")
        arrays_without = generate_initial_population(stats_without, rng_without)
        obj_without = ObjectiveState.from_arrays(
            arrays=arrays_without,
            age_diff_parent_child=age_diff_pc,
            age_diff_couple=age_diff_cp,
            demographic_by_age_sex=sample_stats.demographic_by_age_sex,
            demo_ft_role=sample_stats.demographic_by_family_type_role,
            use_family_type_pyramid=True,
        )

        # 「使われている」事実の保証: スコアが変わる
        assert obj_with.total_score != obj_without.total_score, (
            "demo_ft_role の渡し有無で初期スコアが変わるはず "
            f"(with={obj_with.total_score}, without={obj_without.total_score})"
        )
