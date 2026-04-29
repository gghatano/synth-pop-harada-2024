"""Tests for RareCellEvaluator (Phase 3.5, Issue #61).

(family_type, age) cell の脅威度メトリクス:
- cell size < 5 の割合
- cell size == 1（unique）の割合
- per-family_type 分解

`docs/spec/metrics.md` §6 に基づく実装。
"""

from __future__ import annotations

import numpy as np

from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.evaluate.rare_cell_metrics import RareCellEvaluator
from synthpop_jp.optimize.state import PopulationArrays


def _build_arrays(persons: list[tuple[str, str, str, int]]) -> PopulationArrays:
    """テスト用 helper. ``persons = [(family_type, role, sex, age), ...]``.

    各 person は別世帯（household_id を 1 始まりで連番）。家族構造は
    rare cell では使われない（family_type と age が重要）ため、role / sex は
    ダミーでも OK。
    """
    family_reg = FamilyTypeRegistry()
    role_reg = RoleRegistry()
    sex_reg = SexRegistry()
    seen_ft: set[str] = set()
    seen_role: set[str] = set()
    for ft, role, _sex, _age in persons:
        if ft not in seen_ft:
            family_reg.register(ft)
            seen_ft.add(ft)
        if role not in seen_role:
            role_reg.register(role)
            seen_role.add(role)
    households = [
        Household(
            household_id=i + 1,
            family_type=ft,
            members=[
                Person(household_id=i + 1, role=role, sex=sex, age=age)  # type: ignore[arg-type]
            ],
        )
        for i, (ft, role, sex, age) in enumerate(persons)
    ]
    return PopulationArrays.from_households(households, family_reg, role_reg, sex_reg)


class TestRareCellEvaluatorBasic:
    """RareCellEvaluator の基本挙動."""

    def test_name_is_rare_cell(self) -> None:
        """name は 'rare_cell'."""
        evaluator = RareCellEvaluator()
        assert evaluator.name == "rare_cell"

    def test_returns_required_keys(self) -> None:
        """evaluate は最低 4 共通キー + per_family_type 2 キー × N を返す."""
        arrays = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("single", "single", "F", 28),
                ("couple", "husband", "M", 40),
                ("couple", "wife", "F", 38),
            ]
        )
        evaluator = RareCellEvaluator()
        result = evaluator.evaluate(arrays)
        assert "rare_cell.total_cells" in result
        assert "rare_cell.fraction_below_5" in result
        assert "rare_cell.fraction_unique" in result
        # per_family_type 分解（cells_below_5 と fraction_unique）
        assert "rare_cell.per_family_type.fraction_below_5.single" in result
        assert "rare_cell.per_family_type.fraction_below_5.couple" in result
        assert "rare_cell.per_family_type.fraction_unique.single" in result
        assert "rare_cell.per_family_type.fraction_unique.couple" in result


class TestRareCellEvaluatorMath:
    """cell カウントの数学的正しさ."""

    def test_all_unique_returns_fraction_unique_one(self) -> None:
        """全 cell が unique（count == 1）なら fraction_unique = 1.0."""
        arrays = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("single", "single", "M", 31),
                ("single", "single", "M", 32),
                ("single", "single", "M", 33),
            ]
        )
        evaluator = RareCellEvaluator()
        result = evaluator.evaluate(arrays)
        assert abs(result["rare_cell.fraction_unique"] - 1.0) < 1e-9
        assert abs(result["rare_cell.fraction_below_5"] - 1.0) < 1e-9
        assert int(result["rare_cell.total_cells"]) == 4

    def test_single_cell_with_many_returns_zero_unique(self) -> None:
        """全員同じ cell なら fraction_unique = 0、total_cells = 1."""
        # 5 人とも (single, age=30) → 1 cell, count=5
        arrays = _build_arrays([("single", "single", "M", 30) for _ in range(5)])
        evaluator = RareCellEvaluator()
        result = evaluator.evaluate(arrays)
        assert abs(result["rare_cell.fraction_unique"] - 0.0) < 1e-9
        assert abs(result["rare_cell.fraction_below_5"] - 0.0) < 1e-9
        assert int(result["rare_cell.total_cells"]) == 1

    def test_mixed_cells_compute_correctly(self) -> None:
        """混在ケース: 2 unique cells + 1 cell-of-5 → fraction = 2/3."""
        # cell A: (single, 30) × 5 (= cell of 5, NOT < 5)
        # cell B: (single, 31) × 1 (unique, < 5)
        # cell C: (couple, 40) × 1 (unique, < 5)
        persons = [("single", "single", "M", 30) for _ in range(5)]
        persons.append(("single", "single", "M", 31))
        persons.append(("couple", "husband", "M", 40))
        arrays = _build_arrays(persons)
        evaluator = RareCellEvaluator()
        result = evaluator.evaluate(arrays)
        # 3 cells total
        assert int(result["rare_cell.total_cells"]) == 3
        # 2 cells が < 5: fraction = 2/3
        assert abs(result["rare_cell.fraction_below_5"] - (2.0 / 3.0)) < 1e-9
        # 2 cells が unique: fraction = 2/3
        assert abs(result["rare_cell.fraction_unique"] - (2.0 / 3.0)) < 1e-9

    def test_per_family_type_breakdown(self) -> None:
        """per family_type 分解: single は全 unique、couple は全 same-cell."""
        persons = [
            ("single", "single", "M", 30),
            ("single", "single", "M", 31),
            ("single", "single", "M", 32),
            # couple 5 名: 全員 (couple, age=40) → 1 cell of 5
            ("couple", "husband", "M", 40),
            ("couple", "husband", "M", 40),
            ("couple", "husband", "M", 40),
            ("couple", "husband", "M", 40),
            ("couple", "husband", "M", 40),
        ]
        arrays = _build_arrays(persons)
        evaluator = RareCellEvaluator()
        result = evaluator.evaluate(arrays)
        # single: 3 unique cells / 3 = 1.0
        assert abs(result["rare_cell.per_family_type.fraction_unique.single"] - 1.0) < 1e-9
        assert abs(result["rare_cell.per_family_type.fraction_below_5.single"] - 1.0) < 1e-9
        # couple: 1 cell, count=5, NOT < 5 → 0.0
        assert abs(result["rare_cell.per_family_type.fraction_unique.couple"] - 0.0) < 1e-9
        assert abs(result["rare_cell.per_family_type.fraction_below_5.couple"] - 0.0) < 1e-9


class TestRareCellEvaluatorEdgeCases:
    """境界条件."""

    def test_empty_population_returns_zero_fractions(self) -> None:
        """空人口でも 0 除算せず、全 fraction = 0、total_cells = 0."""
        family_reg = FamilyTypeRegistry()
        role_reg = RoleRegistry()
        sex_reg = SexRegistry()
        empty = PopulationArrays.empty(family_reg, role_reg, sex_reg)
        evaluator = RareCellEvaluator()
        result = evaluator.evaluate(empty)
        assert int(result["rare_cell.total_cells"]) == 0
        assert abs(result["rare_cell.fraction_below_5"] - 0.0) < 1e-9
        assert abs(result["rare_cell.fraction_unique"] - 0.0) < 1e-9

    def test_finite_values(self) -> None:
        """全 fraction 値が有限（NaN / inf でない）."""
        arrays = _build_arrays([("single", "single", "M", 30), ("single", "single", "M", 31)])
        evaluator = RareCellEvaluator()
        result = evaluator.evaluate(arrays)
        for k, v in result.items():
            assert np.isfinite(v), f"{k} = {v} is not finite"
