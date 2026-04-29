"""Tests for AggregateStatL1Evaluator (Phase 3.5, Issue #59).

統計別 L1 誤差レポータの単体テスト。Phase 2 の ObjectiveState.stats と同型の
5 統計に対し、L1 誤差を統計別 + 合計で返すことを検証する。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from synthpop_jp.evaluate.aggregate_metrics import AggregateStatL1Evaluator
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
from synthpop_jp.optimize.objective import ObjectiveState
from synthpop_jp.optimize.state import PopulationArrays
from synthpop_jp.rng import SeedRegistry


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("pyproject.toml not found")


_DATA_DIR = _find_repo_root() / "data" / "sample_case"
_CONFIGS_DIR = _find_repo_root() / "configs"


@pytest.fixture
def sample_arrays() -> PopulationArrays:
    """sample_case から生成した初期人口."""
    stats = InitStats(
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
    rng = SeedRegistry(root=42).rng("init")
    return generate_initial_population(stats, rng)


@pytest.fixture
def evaluator() -> AggregateStatL1Evaluator:
    """sample_case の入力 CSV から構築した evaluator."""
    return AggregateStatL1Evaluator(
        age_diff_parent_child=load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv"),
        age_diff_couple=load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv"),
        demographic_by_age_sex=load_demographic_by_age_sex(
            _DATA_DIR / "demographic_by_age_sex.csv"
        ),
    )


class TestAggregateStatL1Evaluator:
    """AggregateStatL1Evaluator は domain/protocols.py::Evaluator Protocol を実装する."""

    def test_name_is_aggregate(self, evaluator: AggregateStatL1Evaluator) -> None:
        """`name` 属性は metrics.json でのキー prefix として 'aggregate'."""
        assert evaluator.name == "aggregate"

    def test_evaluate_returns_six_keys(
        self, evaluator: AggregateStatL1Evaluator, sample_arrays: PopulationArrays
    ) -> None:
        """5 統計分の L1 + total = 6 キー."""
        result = evaluator.evaluate(sample_arrays)
        expected_keys = {
            "aggregate.l1.father_child_age_diff",
            "aggregate.l1.mother_child_age_diff",
            "aggregate.l1.couple_age_diff",
            "aggregate.l1.pyramid_male",
            "aggregate.l1.pyramid_female",
            "aggregate.l1.total",
        }
        assert set(result.keys()) == expected_keys

    def test_total_equals_sum_of_individual(
        self, evaluator: AggregateStatL1Evaluator, sample_arrays: PopulationArrays
    ) -> None:
        """total は個別 5 統計 L1 の合計に一致."""
        result = evaluator.evaluate(sample_arrays)
        individual_sum = (
            result["aggregate.l1.father_child_age_diff"]
            + result["aggregate.l1.mother_child_age_diff"]
            + result["aggregate.l1.couple_age_diff"]
            + result["aggregate.l1.pyramid_male"]
            + result["aggregate.l1.pyramid_female"]
        )
        assert abs(result["aggregate.l1.total"] - individual_sum) < 1e-9

    def test_all_values_nonnegative(
        self, evaluator: AggregateStatL1Evaluator, sample_arrays: PopulationArrays
    ) -> None:
        """L1 誤差はすべて非負."""
        result = evaluator.evaluate(sample_arrays)
        for k, v in result.items():
            assert v >= 0.0, f"{k} = {v} should be >= 0"
            assert np.isfinite(v), f"{k} = {v} should be finite"

    def test_total_matches_objective_state_score(self, sample_arrays: PopulationArrays) -> None:
        """total は ObjectiveState.total_score と一致する（同 inputs / 同 arrays）."""
        age_diff_parent_child = load_age_diff_parent_child(_DATA_DIR / "age_diff_parent_child.csv")
        age_diff_couple = load_age_diff_couple(_DATA_DIR / "age_diff_couple.csv")
        demographic_by_age_sex = load_demographic_by_age_sex(
            _DATA_DIR / "demographic_by_age_sex.csv"
        )
        evaluator = AggregateStatL1Evaluator(
            age_diff_parent_child=age_diff_parent_child,
            age_diff_couple=age_diff_couple,
            demographic_by_age_sex=demographic_by_age_sex,
        )
        objective = ObjectiveState.from_arrays(
            arrays=sample_arrays,
            age_diff_parent_child=age_diff_parent_child,
            age_diff_couple=age_diff_couple,
            demographic_by_age_sex=demographic_by_age_sex,
        )
        result = evaluator.evaluate(sample_arrays)
        assert abs(result["aggregate.l1.total"] - objective.total_score) < 1e-6
