"""Tests for household_sampler.py — Steps 1〜4 of §10.1.

TDD サイクル:
  Cycle 1: FamilyTypeTemplate 定義 (family_types.py)
  Cycle 2: Step1 — household counts
  Cycle 3: Step2 — household sizes (Largest Remainder)
  Cycle 4: Step3 — children counts (Largest Remainder)
  Cycle 5: Step4 — role expansion
"""

from __future__ import annotations

import pytest

from synthpop_jp.domain.family_types import (
    FAMILY_TEMPLATES,
    FamilyTypeTemplate,
    register_family_type,
)
from synthpop_jp.io.schemas import (
    ChildrenCountDistRow,
    FamilyTypeCountRow,
    HouseholdSizeByFamilyTypeRow,
)
from synthpop_jp.init.household_sampler import (
    HouseholdPlan,
    assign_children_counts,
    assign_household_counts,
    assign_household_sizes,
    expand_roles,
    largest_remainder,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_ft_counts() -> list[FamilyTypeCountRow]:
    """9 種 family_type の世帯数（合計 100）."""
    return [
        FamilyTypeCountRow(family_type="single", count=20),
        FamilyTypeCountRow(family_type="couple", count=24),
        FamilyTypeCountRow(family_type="couple_and_children", count=30),
        FamilyTypeCountRow(family_type="father_and_children", count=3),
        FamilyTypeCountRow(family_type="mother_and_children", count=10),
        FamilyTypeCountRow(family_type="couple_and_parents", count=2),
        FamilyTypeCountRow(family_type="couple_and_a_parent", count=8),
        FamilyTypeCountRow(family_type="couple_children_and_parents", count=1),
        FamilyTypeCountRow(family_type="couple_children_and_a_parent", count=2),
    ]


@pytest.fixture
def sample_children_dist() -> list[ChildrenCountDistRow]:
    """with_children グループの children 数分布."""
    return [
        ChildrenCountDistRow(family_type_group="with_children", n_children=1, rate=0.5521436260921879),
        ChildrenCountDistRow(family_type_group="with_children", n_children=2, rate=0.08511306995409623),
        ChildrenCountDistRow(family_type_group="with_children", n_children=3, rate=0.3390559721921986),
        ChildrenCountDistRow(family_type_group="with_children", n_children=4, rate=0.023687331761517265),
        ChildrenCountDistRow(family_type_group="without_children", n_children=0, rate=1.0),
        ChildrenCountDistRow(family_type_group="single", n_children=0, rate=1.0),
    ]


@pytest.fixture
def sample_family_type_mapping() -> dict[str, str]:
    return {
        "single": "single",
        "couple": "without_children",
        "couple_and_children": "with_children",
        "father_and_children": "with_children",
        "mother_and_children": "with_children",
        "couple_and_parents": "without_children",
        "couple_and_a_parent": "without_children",
        "couple_children_and_parents": "with_children",
        "couple_children_and_a_parent": "with_children",
    }


@pytest.fixture
def sample_hh_sizes() -> list[HouseholdSizeByFamilyTypeRow]:
    return [
        HouseholdSizeByFamilyTypeRow(family_type="single", household_size=1, count=20),
        HouseholdSizeByFamilyTypeRow(family_type="couple", household_size=2, count=20),
        HouseholdSizeByFamilyTypeRow(family_type="couple_and_children", household_size=3, count=10),
        HouseholdSizeByFamilyTypeRow(family_type="couple_and_children", household_size=4, count=2),
        HouseholdSizeByFamilyTypeRow(family_type="couple_and_children", household_size=5, count=8),
        HouseholdSizeByFamilyTypeRow(family_type="father_and_children", household_size=2, count=12),
        HouseholdSizeByFamilyTypeRow(family_type="father_and_children", household_size=3, count=1),
        HouseholdSizeByFamilyTypeRow(family_type="father_and_children", household_size=4, count=7),
        HouseholdSizeByFamilyTypeRow(family_type="mother_and_children", household_size=2, count=4),
        HouseholdSizeByFamilyTypeRow(family_type="mother_and_children", household_size=3, count=16),
        HouseholdSizeByFamilyTypeRow(family_type="mother_and_children", household_size=4, count=0),
        HouseholdSizeByFamilyTypeRow(family_type="couple_and_parents", household_size=3, count=8),
        HouseholdSizeByFamilyTypeRow(family_type="couple_and_parents", household_size=4, count=12),
        HouseholdSizeByFamilyTypeRow(family_type="couple_and_a_parent", household_size=3, count=20),
        HouseholdSizeByFamilyTypeRow(family_type="couple_children_and_parents", household_size=4, count=2),
        HouseholdSizeByFamilyTypeRow(family_type="couple_children_and_parents", household_size=5, count=18),
        HouseholdSizeByFamilyTypeRow(family_type="couple_children_and_parents", household_size=6, count=0),
        HouseholdSizeByFamilyTypeRow(family_type="couple_children_and_a_parent", household_size=4, count=5),
        HouseholdSizeByFamilyTypeRow(family_type="couple_children_and_a_parent", household_size=5, count=15),
    ]


# ---------------------------------------------------------------------------
# Cycle 1: FamilyTypeTemplate 定義
# ---------------------------------------------------------------------------


class TestFamilyTypeTemplate:
    """Cycle 1: FAMILY_TEMPLATES と register_family_type() のテスト."""

    def test_all_nine_family_types_defined(self) -> None:
        """9 種の family_type テンプレがすべて存在する."""
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
        assert set(FAMILY_TEMPLATES.keys()) == expected

    def test_template_has_required_fields(self) -> None:
        """各テンプレが roles, base_size, has_children を持つ."""
        for name, tmpl in FAMILY_TEMPLATES.items():
            assert isinstance(tmpl, FamilyTypeTemplate), f"{name} は FamilyTypeTemplate でない"
            assert len(tmpl.roles) >= 1, f"{name} の roles が空"
            assert tmpl.base_size >= 1, f"{name} の base_size が 0 以下"
            assert isinstance(tmpl.has_children, bool), f"{name} の has_children が bool でない"

    def test_has_children_flag_is_correct(self) -> None:
        """has_children フラグが正しく設定されている."""
        with_children = {
            "couple_and_children",
            "father_and_children",
            "mother_and_children",
            "couple_children_and_parents",
            "couple_children_and_a_parent",
        }
        without_children = {
            "single",
            "couple",
            "couple_and_parents",
            "couple_and_a_parent",
        }
        for name in with_children:
            assert FAMILY_TEMPLATES[name].has_children, f"{name} は has_children=True のはず"
        for name in without_children:
            assert not FAMILY_TEMPLATES[name].has_children, f"{name} は has_children=False のはず"

    def test_single_has_one_role(self) -> None:
        """single の roles は ['single'] 1 つ."""
        tmpl = FAMILY_TEMPLATES["single"]
        assert tmpl.roles == ["single"]
        assert tmpl.base_size == 1

    def test_couple_has_husband_and_wife(self) -> None:
        """couple の roles は husband と wife を含む."""
        tmpl = FAMILY_TEMPLATES["couple"]
        assert "husband" in tmpl.roles
        assert "wife" in tmpl.roles

    def test_register_family_type_adds_new_template(self) -> None:
        """register_family_type() で新しいテンプレを追加できる."""
        custom = FamilyTypeTemplate(
            roles=["custom_role"],
            base_size=1,
            has_children=False,
        )
        register_family_type("custom_test_type", custom)
        assert "custom_test_type" in FAMILY_TEMPLATES
        assert FAMILY_TEMPLATES["custom_test_type"] is custom
        # クリーンアップ
        del FAMILY_TEMPLATES["custom_test_type"]

    def test_base_size_matches_non_child_roles(self) -> None:
        """base_size は child を除いた roles の数と一致する."""
        for name, tmpl in FAMILY_TEMPLATES.items():
            non_child_count = sum(1 for r in tmpl.roles if r != "child")
            assert tmpl.base_size == non_child_count, (
                f"{name}: base_size={tmpl.base_size}, non_child_roles={non_child_count}"
            )


# ---------------------------------------------------------------------------
# Cycle 2: Step1 — household counts
# ---------------------------------------------------------------------------


class TestAssignHouseholdCounts:
    """Cycle 2: assign_household_counts() のテスト."""

    def test_counts_match_input_exactly(self, sample_ft_counts: list[FamilyTypeCountRow]) -> None:
        """family_type 別世帯数が入力統計と完全一致する."""
        result = assign_household_counts(sample_ft_counts)
        for row in sample_ft_counts:
            assert result[row.family_type] == row.count, (
                f"{row.family_type}: expected {row.count}, got {result.get(row.family_type)}"
            )

    def test_total_count_preserved(self, sample_ft_counts: list[FamilyTypeCountRow]) -> None:
        """合計世帯数が保存される."""
        result = assign_household_counts(sample_ft_counts)
        assert sum(result.values()) == sum(r.count for r in sample_ft_counts)

    def test_zero_count_included(self) -> None:
        """count=0 の family_type も結果に含まれる."""
        rows = [
            FamilyTypeCountRow(family_type="single", count=10),
            FamilyTypeCountRow(family_type="couple", count=0),
        ]
        result = assign_household_counts(rows)
        assert result["couple"] == 0


# ---------------------------------------------------------------------------
# Cycle 3: largest_remainder and Step2 — household sizes
# ---------------------------------------------------------------------------


class TestLargestRemainder:
    """largest_remainder() 関数のテスト."""

    def test_sum_equals_total(self) -> None:
        """割付結果の合計が total に等しい."""
        import numpy as np

        rates = np.array([0.5, 0.3, 0.2])
        result = largest_remainder(rates, 10)
        assert result.sum() == 10

    def test_proportional_allocation(self) -> None:
        """完全に割り切れる場合は比例割付になる."""
        import numpy as np

        rates = np.array([0.5, 0.3, 0.2])
        result = largest_remainder(rates, 10)
        assert result[0] == 5
        assert result[1] == 3
        assert result[2] == 2

    def test_remainder_goes_to_largest_fraction(self) -> None:
        """余りは小数部が最大のものに割り当てられる."""
        import numpy as np

        # 1/3 ずつ 3 分割 → 合計 3, floor=[0,0,0], remainder=[0.33,0.33,0.33]
        # 最初の 3 つに +1 されるので all 1
        rates = np.array([1 / 3, 1 / 3, 1 / 3])
        result = largest_remainder(rates, 3)
        assert result.sum() == 3
        assert all(result == 1)

    def test_total_zero_returns_zeros(self) -> None:
        """total=0 のとき全 0 を返す."""
        import numpy as np

        rates = np.array([0.5, 0.5])
        result = largest_remainder(rates, 0)
        assert result.sum() == 0


class TestAssignHouseholdSizes:
    """Cycle 3: assign_household_sizes() のテスト."""

    def test_size_distribution_matches_csv_exactly(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
    ) -> None:
        """household_size_by_family_type.csv があるとき、分布が完全一致する."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)

        # couple_and_children: total 30 世帯, size 3=10, 4=2, 5=8 → 比率 10:2:8
        cac_plans = [p for p in plans if p.family_type == "couple_and_children"]
        sizes = [p.household_size for p in cac_plans]
        assert sizes.count(3) == 10
        assert sizes.count(4) == 2
        assert sizes.count(5) == 8

    def test_total_households_preserved(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
    ) -> None:
        """世帯数の合計が保存される."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)
        assert len(plans) == sum(r.count for r in sample_ft_counts)

    def test_fallback_to_base_size_when_no_csv(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
    ) -> None:
        """household_size_by_family_type.csv がないとき、base_size が使われる."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, None)
        for p in plans:
            tmpl = FAMILY_TEMPLATES[p.family_type]
            assert p.household_size >= tmpl.base_size


# ---------------------------------------------------------------------------
# Cycle 4: Step3 — children counts
# ---------------------------------------------------------------------------


class TestAssignChildrenCounts:
    """Cycle 4: assign_children_counts() のテスト."""

    def test_children_count_distribution_matches_exactly(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
        sample_children_dist: list[ChildrenCountDistRow],
        sample_family_type_mapping: dict[str, str],
    ) -> None:
        """children 数分布が入力統計と完全一致する（Largest Remainder 保証）."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)
        plans_with_children = assign_children_counts(
            plans, sample_children_dist, sample_family_type_mapping
        )

        # with_children グループに属する全世帯の children 数を集計
        with_children_fts = {
            ft for ft, grp in sample_family_type_mapping.items() if grp == "with_children"
        }
        hh_with_children = [p for p in plans_with_children if p.family_type in with_children_fts]
        total = len(hh_with_children)

        if total == 0:
            return

        # 実際の分布
        from collections import Counter
        actual_counts = Counter(p.n_children for p in hh_with_children)

        # Largest Remainder で期待される分布を計算
        import numpy as np

        group_rows = [r for r in sample_children_dist if r.family_type_group == "with_children"]
        rates = np.array([r.rate for r in group_rows])
        expected_counts = largest_remainder(rates, total)

        for i, row in enumerate(group_rows):
            assert actual_counts.get(row.n_children, 0) == expected_counts[i], (
                f"n_children={row.n_children}: expected {expected_counts[i]}, "
                f"got {actual_counts.get(row.n_children, 0)}"
            )

    def test_no_children_for_without_children_types(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
        sample_children_dist: list[ChildrenCountDistRow],
        sample_family_type_mapping: dict[str, str],
    ) -> None:
        """without_children の世帯に children が割り当てられない."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)
        plans_with_children = assign_children_counts(
            plans, sample_children_dist, sample_family_type_mapping
        )
        without_children_fts = {
            ft for ft, grp in sample_family_type_mapping.items() if grp != "with_children"
        }
        for p in plans_with_children:
            if p.family_type in without_children_fts:
                assert p.n_children == 0, (
                    f"{p.family_type} は without_children なのに n_children={p.n_children}"
                )


# ---------------------------------------------------------------------------
# Cycle 5: Step4 — role expansion
# ---------------------------------------------------------------------------


class TestExpandRoles:
    """Cycle 5: expand_roles() のテスト."""

    def test_single_household_has_one_single_role(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
        sample_children_dist: list[ChildrenCountDistRow],
        sample_family_type_mapping: dict[str, str],
    ) -> None:
        """single 世帯には 'single' role が 1 つ."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)
        plans = assign_children_counts(plans, sample_children_dist, sample_family_type_mapping)
        expanded = expand_roles(plans)
        for entry in expanded:
            if entry.plan.family_type == "single":
                assert entry.roles == ["single"]

    def test_couple_household_has_husband_and_wife(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
        sample_children_dist: list[ChildrenCountDistRow],
        sample_family_type_mapping: dict[str, str],
    ) -> None:
        """couple 世帯には husband と wife が 1 つずつ."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)
        plans = assign_children_counts(plans, sample_children_dist, sample_family_type_mapping)
        expanded = expand_roles(plans)
        for entry in expanded:
            if entry.plan.family_type == "couple":
                assert entry.roles.count("husband") == 1
                assert entry.roles.count("wife") == 1

    def test_couple_and_children_has_correct_child_count(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
        sample_children_dist: list[ChildrenCountDistRow],
        sample_family_type_mapping: dict[str, str],
    ) -> None:
        """couple_and_children 世帯の child role 数が n_children と一致する."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)
        plans = assign_children_counts(plans, sample_children_dist, sample_family_type_mapping)
        expanded = expand_roles(plans)
        for entry in expanded:
            if entry.plan.family_type == "couple_and_children":
                assert entry.roles.count("child") == entry.plan.n_children

    def test_total_roles_equals_person_count(
        self,
        sample_ft_counts: list[FamilyTypeCountRow],
        sample_hh_sizes: list[HouseholdSizeByFamilyTypeRow],
        sample_children_dist: list[ChildrenCountDistRow],
        sample_family_type_mapping: dict[str, str],
    ) -> None:
        """全世帯の roles 総数が household_size と一致する."""
        hh_counts = assign_household_counts(sample_ft_counts)
        plans = assign_household_sizes(hh_counts, sample_hh_sizes)
        plans = assign_children_counts(plans, sample_children_dist, sample_family_type_mapping)
        expanded = expand_roles(plans)
        for entry in expanded:
            assert len(entry.roles) == entry.plan.household_size, (
                f"family_type={entry.plan.family_type}: "
                f"roles={entry.roles}, size={entry.plan.household_size}"
            )
