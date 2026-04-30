"""Tests for NarrowUtilityEvaluator (Issue #97).

3 つの固定タスク（family_type 分類 / household_size 回帰 / role 予測）の
TSTR / TRTS を計算する評価器のユニットテスト。
"""

from __future__ import annotations

import numpy as np
import pytest

from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.evaluate.utility.narrow import NarrowUtilityEvaluator
from synthpop_jp.optimize.state import PopulationArrays


def _make_pop(
    age: list[int],
    sex: list[int],
    role: list[int],
    family_type: list[int],
    household_id: list[int],
) -> PopulationArrays:
    """Tests 用に小さな PopulationArrays を組み立てる."""
    role_reg = RoleRegistry()
    sex_reg = SexRegistry()
    family_reg = FamilyTypeRegistry()
    for r in sorted(set(role)):
        role_reg.register(f"role_{r}")
    for s in sorted(set(sex)):
        sex_reg.register(f"sex_{s}")
    for f in sorted(set(family_type)):
        family_reg.register(f"ft_{f}")
    return PopulationArrays(
        age=np.array(age, dtype=np.int16),
        sex=np.array(sex, dtype=np.int8),
        role=np.array(role, dtype=np.int8),
        family_type=np.array(family_type, dtype=np.int8),
        household_id=np.array(household_id, dtype=np.int32),
        _role_reg=role_reg,
        _sex_reg=sex_reg,
        _family_reg=family_reg,
    )


def _diverse_pop(seed: int = 0, n_per_group: int = 10) -> PopulationArrays:
    """各 family_type / role / sex の組合せを十分網羅する人口を作る."""
    rng = np.random.default_rng(seed)
    ages: list[int] = []
    sexes: list[int] = []
    roles: list[int] = []
    fts: list[int] = []
    hids: list[int] = []
    hid = 0
    for ft in range(2):
        for role in range(2):
            for sex in range(2):
                for _ in range(n_per_group):
                    ages.append(int(rng.integers(20, 60)))
                    sexes.append(sex)
                    roles.append(role)
                    fts.append(ft)
                    hids.append(hid)
                    hid += 1
    return _make_pop(age=ages, sex=sexes, role=roles, family_type=fts, household_id=hids)


class TestNarrowUtilityEvaluatorBasics:
    def test_name(self) -> None:
        ev = NarrowUtilityEvaluator()
        assert ev.name == "narrow_utility"

    def test_returns_six_keys(self) -> None:
        ev = NarrowUtilityEvaluator(seed=0)
        pop = _diverse_pop(seed=42)
        result = ev.evaluate(synthetic=pop, holdout=pop)
        expected_keys = {
            "narrow_utility.task_a.tstr_macro_f1",
            "narrow_utility.task_a.trts_macro_f1",
            "narrow_utility.task_b.tstr_rmse",
            "narrow_utility.task_b.trts_rmse",
            "narrow_utility.task_c.tstr_macro_f1",
            "narrow_utility.task_c.trts_macro_f1",
        }
        assert expected_keys <= set(result.keys())

    def test_identical_pops_yield_meaningful_metrics(self) -> None:
        ev = NarrowUtilityEvaluator(seed=0)
        pop = _diverse_pop(seed=42)
        result = ev.evaluate(synthetic=pop, holdout=pop)
        # synth=real なので TSTR/TRTS は同じ
        assert result["narrow_utility.task_a.tstr_macro_f1"] == pytest.approx(
            result["narrow_utility.task_a.trts_macro_f1"], abs=1e-9
        )
        assert result["narrow_utility.task_b.tstr_rmse"] == pytest.approx(
            result["narrow_utility.task_b.trts_rmse"], abs=1e-9
        )
        # F1 は [0, 1]
        assert 0.0 <= result["narrow_utility.task_a.tstr_macro_f1"] <= 1.0
        assert 0.0 <= result["narrow_utility.task_c.tstr_macro_f1"] <= 1.0
        # RMSE は非負・有限
        rmse = result["narrow_utility.task_b.tstr_rmse"]
        assert rmse >= 0.0
        assert np.isfinite(rmse)


class TestNarrowUtilityDeterminism:
    def test_same_seed_same_result(self) -> None:
        pop = _diverse_pop(seed=42)
        ev1 = NarrowUtilityEvaluator(seed=7)
        ev2 = NarrowUtilityEvaluator(seed=7)
        r1 = ev1.evaluate(synthetic=pop, holdout=pop)
        r2 = ev2.evaluate(synthetic=pop, holdout=pop)
        for k in r1:
            assert r1[k] == pytest.approx(r2[k]), f"key {k}: {r1[k]} != {r2[k]}"


class TestNarrowUtilityEdgeCases:
    def test_empty_synthetic_returns_neutral_values(self) -> None:
        ev = NarrowUtilityEvaluator(seed=0)
        empty = _make_pop(age=[], sex=[], role=[], family_type=[], household_id=[])
        real = _diverse_pop(seed=42)
        result = ev.evaluate(synthetic=empty, holdout=real)
        # 空でも評価器は壊れない（NaN/Inf を返さず 0 などの中立値を入れる）
        for k, v in result.items():
            assert np.isfinite(v), f"{k}: {v} is not finite"

    def test_empty_holdout_returns_neutral_values(self) -> None:
        ev = NarrowUtilityEvaluator(seed=0)
        synth = _diverse_pop(seed=42)
        empty = _make_pop(age=[], sex=[], role=[], family_type=[], household_id=[])
        result = ev.evaluate(synthetic=synth, holdout=empty)
        for k, v in result.items():
            assert np.isfinite(v), f"{k}: {v} is not finite"


class TestNarrowUtilitySanity:
    """sample_case 相当の現実的なデータで sanity check."""

    def test_random_baseline_outperformed_in_task_a(self) -> None:
        """family_type 別に age が分離していれば task A の F1 は random（≈0.33）を上回る."""
        # 2 family_types で age 帯が完全分離 → 高 F1 期待
        n = 30
        ages = [25] * n + [60] * n  # ft=0 は若い、ft=1 は年配
        sexes = [0] * (2 * n)
        roles = [0] * (2 * n)
        fts = [0] * n + [1] * n
        hids = list(range(2 * n))
        pop = _make_pop(age=ages, sex=sexes, role=roles, family_type=fts, household_id=hids)
        ev = NarrowUtilityEvaluator(seed=0)
        result = ev.evaluate(synthetic=pop, holdout=pop)
        # 2 クラスで age が完全分離 → F1 は ~1.0
        assert result["narrow_utility.task_a.tstr_macro_f1"] >= 0.9
