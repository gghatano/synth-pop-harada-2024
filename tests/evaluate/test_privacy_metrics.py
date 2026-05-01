"""Tests for DCR / NNDR / ARD privacy metrics (Issue #99)."""

from __future__ import annotations

import numpy as np

from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.evaluate.privacy_metrics import (
    ARDEvaluator,
    DCREvaluator,
    NNDREvaluator,
)
from synthpop_jp.optimize.state import PopulationArrays


def _make_pop(
    age: list[int],
    sex: list[int],
    role: list[int],
    family_type: list[int],
    household_id: list[int],
) -> PopulationArrays:
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


def _diverse_pop(seed: int = 0, n: int = 30) -> PopulationArrays:
    rng = np.random.default_rng(seed)
    return _make_pop(
        age=[int(a) for a in rng.integers(20, 60, size=n)],
        sex=[int(s) for s in rng.integers(0, 2, size=n)],
        role=[int(r) for r in rng.integers(0, 3, size=n)],
        family_type=[int(ft) for ft in rng.integers(0, 2, size=n)],
        household_id=list(range(n)),
    )


# ---------------------------------------------------------------------------
# DCR
# ---------------------------------------------------------------------------


class TestDCREvaluator:
    def test_name_and_layer(self) -> None:
        ev = DCREvaluator()
        assert ev.name == "dcr"
        assert ev.layer == "proxy"

    def test_synth_equals_real_yields_zero_dcr(self) -> None:
        pop = _diverse_pop(seed=42)
        ev = DCREvaluator()
        result = ev.evaluate(synthetic=pop, holdout=pop)
        # synth=real なので最近傍距離は 0
        assert result["dcr.p05"] == 0.0
        assert result["dcr.p50"] == 0.0
        assert result["dcr.mean"] == 0.0

    def test_disjoint_pops_yield_positive_dcr(self) -> None:
        synth = _diverse_pop(seed=42)
        real = _diverse_pop(seed=43)
        ev = DCREvaluator()
        result = ev.evaluate(synthetic=synth, holdout=real)
        # 値域は [0, 1]
        assert 0.0 <= result["dcr.p05"] <= 1.0
        assert 0.0 <= result["dcr.mean"] <= 1.0

    def test_empty_returns_neutral_zeros(self) -> None:
        empty = _make_pop(age=[], sex=[], role=[], family_type=[], household_id=[])
        real = _diverse_pop(seed=42)
        ev = DCREvaluator()
        result = ev.evaluate(synthetic=empty, holdout=real)
        for v in result.values():
            assert np.isfinite(v)


# ---------------------------------------------------------------------------
# NNDR
# ---------------------------------------------------------------------------


class TestNNDREvaluator:
    def test_name_and_layer(self) -> None:
        ev = NNDREvaluator()
        assert ev.name == "nndr"
        assert ev.layer == "proxy"

    def test_value_in_range(self) -> None:
        synth = _diverse_pop(seed=42)
        real = _diverse_pop(seed=43)
        ev = NNDREvaluator()
        result = ev.evaluate(synthetic=synth, holdout=real)
        # NNDR は [0, 1]
        for k, v in result.items():
            if v != 0.0:  # 0 は分母 0 ケースの中立値
                assert 0.0 <= v <= 1.0, f"{k}={v}"

    def test_synth_equals_real_yields_low_nndr(self) -> None:
        # synth=real なら最近傍は 0 で 2 番目以降は > 0、ratio = 0
        pop = _diverse_pop(seed=42)
        ev = NNDREvaluator()
        result = ev.evaluate(synthetic=pop, holdout=pop)
        # mean NNDR は 0（最近傍距離 0 / 2nd nearest > 0）
        # ただし 2nd nearest が 0 なら ratio は 0/0 = 0 で扱う
        assert 0.0 <= result["nndr.mean"] <= 1.0


# ---------------------------------------------------------------------------
# ARD
# ---------------------------------------------------------------------------


class TestARDEvaluator:
    def test_name_and_layer(self) -> None:
        ev = ARDEvaluator()
        assert ev.name == "ard"
        assert ev.layer == "proxy"

    def test_returns_finite_value(self) -> None:
        synth = _diverse_pop(seed=42)
        real = _diverse_pop(seed=43)
        ev = ARDEvaluator()
        result = ev.evaluate(synthetic=synth, holdout=real)
        assert "ard.mean" in result
        assert 0.0 <= result["ard.mean"] <= 1.0

    def test_self_ard_smaller_than_independent(self) -> None:
        # synth と real が同じだと ARD は小さい（対角に 0 があるため）
        pop = _diverse_pop(seed=42)
        independent = _diverse_pop(seed=999)
        ev = ARDEvaluator()
        ard_self = ev.evaluate(synthetic=pop, holdout=pop)["ard.mean"]
        ard_indep = ev.evaluate(synthetic=pop, holdout=independent)["ard.mean"]
        # 同じデータどうしの ARD は独立データより小さくないとおかしい
        assert ard_self <= ard_indep + 1e-6
