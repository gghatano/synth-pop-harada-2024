"""Tests for BroadUtilityEvaluator (Issue #96).

`docs/spec/spec.md` §13.2 / `docs/spec/metrics.md` §3 に基づく broad utility
評価器のユニットテスト。手計算 fixture と独立性 / 完全従属 ケースで数値を
確認する。
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.evaluate.utility.broad import (
    BroadUtilityEvaluator,
    _correlation_ratio,
    _cramers_v,
    _pair_joint_tv,
    _univariate_tv,
)
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
    # 出てくる id を全部登録（観測されない id でも問題ない）
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


# ---------------------------------------------------------------------------
# 純関数: TV / Cramér's V / Correlation Ratio
# ---------------------------------------------------------------------------


class TestUnivariateTV:
    def test_identical_distributions_yield_zero(self) -> None:
        a = np.array([1, 2, 3, 1, 2, 3], dtype=np.int64)
        b = np.array([1, 2, 3, 1, 2, 3], dtype=np.int64)
        assert _univariate_tv(a, b) == pytest.approx(0.0)

    def test_disjoint_supports_yield_one(self) -> None:
        a = np.array([1, 1, 1], dtype=np.int64)
        b = np.array([2, 2, 2], dtype=np.int64)
        # P(a=1)=1, Q(a=2)=1 → TV = 0.5 * (1 + 1) = 1.0
        assert _univariate_tv(a, b) == pytest.approx(1.0)

    def test_handworked_case(self) -> None:
        # synth: {10:2, 20:2} → {10:0.5, 20:0.5}
        # real: {10:1, 20:1, 30:1, 40:1} → {10:0.25, 20:0.25, 30:0.25, 40:0.25}
        # TV = 0.5 * (|0.5-0.25| + |0.5-0.25| + |0-0.25| + |0-0.25|) = 0.5
        a = np.array([10, 20, 10, 20], dtype=np.int64)
        b = np.array([10, 20, 30, 40], dtype=np.int64)
        assert _univariate_tv(a, b) == pytest.approx(0.5)


class TestPairJointTV:
    def test_identical_pairs_yield_zero(self) -> None:
        ax = np.array([1, 2, 3], dtype=np.int64)
        ay = np.array([10, 20, 30], dtype=np.int64)
        bx = ax.copy()
        by = ay.copy()
        assert _pair_joint_tv(ax, ay, bx, by) == pytest.approx(0.0)

    def test_handworked_case(self) -> None:
        # synth pairs: {(1,10):2, (2,20):2} → {(1,10):0.5, (2,20):0.5}
        # real pairs:  {(1,10):1, (2,20):1, (3,30):1, (4,40):1} → 各 0.25
        # TV = 0.5 * (|0.5-0.25| + |0.5-0.25| + |0-0.25| + |0-0.25|) = 0.5
        ax = np.array([1, 2, 1, 2], dtype=np.int64)
        ay = np.array([10, 20, 10, 20], dtype=np.int64)
        bx = np.array([1, 2, 3, 4], dtype=np.int64)
        by = np.array([10, 20, 30, 40], dtype=np.int64)
        assert _pair_joint_tv(ax, ay, bx, by) == pytest.approx(0.5)


class TestCramersV:
    def test_perfect_dependence(self) -> None:
        # x=y → V = 1.0
        x = np.array([0, 0, 1, 1, 2, 2], dtype=np.int64)
        y = np.array([0, 0, 1, 1, 2, 2], dtype=np.int64)
        assert _cramers_v(x, y) == pytest.approx(1.0, abs=1e-9)

    def test_independence_close_to_zero(self) -> None:
        # x と y が独立: 一様な分布 → chi2 が小さく V もほぼ 0
        x = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int64)
        y = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=np.int64)
        assert _cramers_v(x, y) == pytest.approx(0.0, abs=1e-9)

    def test_constant_input_returns_zero(self) -> None:
        # x が定数なら V は定義されないので 0 を返す
        x = np.array([5, 5, 5, 5], dtype=np.int64)
        y = np.array([0, 1, 0, 1], dtype=np.int64)
        assert _cramers_v(x, y) == pytest.approx(0.0)


class TestCorrelationRatio:
    def test_constant_groups_yield_zero(self) -> None:
        # cat: [0,0,1,1], num: [10,10,10,10] → group means 等しい → eta=0
        num = np.array([10, 10, 10, 10], dtype=np.float64)
        cat = np.array([0, 0, 1, 1], dtype=np.int64)
        assert _correlation_ratio(num, cat) == pytest.approx(0.0)

    def test_perfect_separation_yields_one(self) -> None:
        # cat=0 → num=10, cat=1 → num=20 で群内分散 0 → eta=1
        num = np.array([10.0, 10.0, 20.0, 20.0], dtype=np.float64)
        cat = np.array([0, 0, 1, 1], dtype=np.int64)
        assert _correlation_ratio(num, cat) == pytest.approx(1.0)

    def test_handworked_case(self) -> None:
        # cat: [0,0,1,1], num: [10,12,18,20]
        # group_mean(0) = 11, group_mean(1) = 19, total_mean = 15
        # SS_between = 2*(11-15)^2 + 2*(19-15)^2 = 32 + 32 = 64
        # SS_total = (10-15)^2+(12-15)^2+(18-15)^2+(20-15)^2 = 25+9+9+25 = 68
        # eta^2 = 64 / 68 ≈ 0.9412
        # eta = sqrt(64/68) ≈ 0.9701
        num = np.array([10.0, 12.0, 18.0, 20.0], dtype=np.float64)
        cat = np.array([0, 0, 1, 1], dtype=np.int64)
        assert _correlation_ratio(num, cat) == pytest.approx(math.sqrt(64.0 / 68.0))


# ---------------------------------------------------------------------------
# BroadUtilityEvaluator
# ---------------------------------------------------------------------------


class TestBroadUtilityEvaluator:
    def test_evaluator_name(self) -> None:
        ev = BroadUtilityEvaluator()
        assert ev.name == "broad_utility"

    def test_identical_pops_yield_zero_metrics(self) -> None:
        ev = BroadUtilityEvaluator()
        pop = _make_pop(
            age=[10, 20, 10, 20],
            sex=[0, 0, 1, 1],
            role=[0, 0, 1, 1],
            family_type=[0, 0, 1, 1],
            household_id=[0, 0, 1, 1],
        )
        result = ev.evaluate(synthetic=pop, holdout=pop)
        # 単変量 TV / L1 はすべて 0
        for attr in ("age", "sex", "role", "family_type"):
            assert result[f"broad_utility.tv.{attr}"] == pytest.approx(0.0)
            assert result[f"broad_utility.l1.{attr}"] == pytest.approx(0.0)
        # ペア TV すべて 0
        attrs = ("age", "sex", "role", "family_type")
        for i in range(len(attrs)):
            for j in range(i + 1, len(attrs)):
                key = f"broad_utility.pair_tv.{attrs[i]}__{attrs[j]}"
                assert result[key] == pytest.approx(0.0)
        # 相関 Frobenius / max-abs は 0
        assert result["broad_utility.correlation_frobenius_diff"] == pytest.approx(0.0)
        assert result["broad_utility.correlation_max_abs_diff"] == pytest.approx(0.0)
        # 集約
        assert result["broad_utility.sum_pair_tv"] == pytest.approx(0.0)

    def test_age_distribution_diff(self) -> None:
        ev = BroadUtilityEvaluator()
        synth = _make_pop(
            age=[10, 20, 10, 20],
            sex=[0, 0, 1, 1],
            role=[0, 0, 1, 1],
            family_type=[0, 0, 1, 1],
            household_id=[0, 0, 1, 1],
        )
        real = _make_pop(
            age=[10, 20, 30, 40],
            sex=[0, 0, 1, 1],
            role=[0, 0, 1, 1],
            family_type=[0, 0, 1, 1],
            household_id=[0, 0, 1, 1],
        )
        result = ev.evaluate(synthetic=synth, holdout=real)
        # age 単変量 TV = 0.5, L1 = 1.0
        assert result["broad_utility.tv.age"] == pytest.approx(0.5)
        assert result["broad_utility.l1.age"] == pytest.approx(1.0)
        # sex / role / family_type は同分布なので 0
        assert result["broad_utility.tv.sex"] == pytest.approx(0.0)
        assert result["broad_utility.tv.role"] == pytest.approx(0.0)
        assert result["broad_utility.tv.family_type"] == pytest.approx(0.0)
        # pair TV: age を含むペアは差分あり
        assert result["broad_utility.pair_tv.age__sex"] > 0.0
        assert result["broad_utility.pair_tv.age__role"] > 0.0
        assert result["broad_utility.pair_tv.age__family_type"] > 0.0
        # sex × role など age を含まないペアは差分 0
        assert result["broad_utility.pair_tv.sex__role"] == pytest.approx(0.0)

    def test_keys_present_for_all_pairs(self) -> None:
        ev = BroadUtilityEvaluator()
        pop = _make_pop(
            age=[10, 20, 30, 40],
            sex=[0, 0, 1, 1],
            role=[0, 0, 1, 1],
            family_type=[0, 0, 1, 1],
            household_id=[0, 0, 1, 1],
        )
        result = ev.evaluate(synthetic=pop, holdout=pop)
        attrs = ("age", "sex", "role", "family_type")
        for attr in attrs:
            assert f"broad_utility.tv.{attr}" in result
            assert f"broad_utility.l1.{attr}" in result
        for i in range(len(attrs)):
            for j in range(i + 1, len(attrs)):
                assert f"broad_utility.pair_tv.{attrs[i]}__{attrs[j]}" in result
        assert "broad_utility.correlation_frobenius_diff" in result
        assert "broad_utility.correlation_max_abs_diff" in result
        assert "broad_utility.sum_pair_tv" in result

    def test_empty_populations_yield_zeros(self) -> None:
        ev = BroadUtilityEvaluator()
        empty = _make_pop(age=[], sex=[], role=[], family_type=[], household_id=[])
        result = ev.evaluate(synthetic=empty, holdout=empty)
        # 空でも 0 除算しない
        for k, v in result.items():
            assert v == pytest.approx(0.0), f"{k}: {v}"
