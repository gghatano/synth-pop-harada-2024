"""Tests for CAPEvaluator (Phase 3.5, Issue #65).

Generalized CAP / TCAP の baseline 評価器。

`docs/spec/metrics.md` §5.2 / Taub et al. (2018) に基づく。
quasi-identifier `Q` から sensitive attribute `S` を推定したときの一致確率を測る。
"""

from __future__ import annotations

import numpy as np

from synthpop_jp.domain.household import Household
from synthpop_jp.domain.person import Person
from synthpop_jp.domain.registry import FamilyTypeRegistry, RoleRegistry, SexRegistry
from synthpop_jp.evaluate.attribute_inference import CAPEvaluator
from synthpop_jp.optimize.state import PopulationArrays


def _build_arrays(persons: list[tuple[str, str, str, int]]) -> PopulationArrays:
    """テスト用 helper. ``persons = [(family_type, role, sex, age), ...]``.

    各 person は別世帯（household_id を 1 始まりで連番）。
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


def _empty_arrays() -> PopulationArrays:
    return PopulationArrays.empty(FamilyTypeRegistry(), RoleRegistry(), SexRegistry())


class TestCAPEvaluatorBasic:
    """CAPEvaluator の基本属性."""

    def test_name_is_cap(self) -> None:
        """name は 'cap'."""
        evaluator = CAPEvaluator()
        assert evaluator.name == "cap"

    def test_layer_is_attribute_inference(self) -> None:
        """layer は 'attribute_inference'."""
        evaluator = CAPEvaluator()
        assert evaluator.layer == "attribute_inference"

    def test_returns_required_keys(self) -> None:
        """evaluate は generalized / targeted / coverage を返す."""
        synthetic = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "husband", "M", 40),
            ]
        )
        holdout = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "husband", "M", 40),
            ]
        )
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, holdout)
        assert "cap.generalized" in result
        assert "cap.targeted" in result
        assert "cap.coverage" in result


class TestCAPEvaluatorMath:
    """CAP / TCAP の数学的正しさ."""

    def test_identical_populations_give_perfect_cap(self) -> None:
        """holdout = synthetic なら GCAP = TCAP = 1.0、coverage = 1.0."""
        persons = [
            ("single", "single", "M", 30),
            ("single", "single", "F", 25),
            ("couple", "husband", "M", 40),
            ("couple", "wife", "F", 38),
        ]
        synthetic = _build_arrays(persons)
        holdout = _build_arrays(persons)
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, holdout)
        # Q = (family_type, sex), S = age. 各 (ft, sex) に対し holdout の age が 1 つ
        # synthetic 内も同じ 1 つしかないので一致確率 = 1.0
        assert abs(result["cap.generalized"] - 1.0) < 1e-9
        assert abs(result["cap.targeted"] - 1.0) < 1e-9
        assert abs(result["cap.coverage"] - 1.0) < 1e-9

    def test_deterministic_mapping_gives_targeted_one(self) -> None:
        """Q から S が一意に決まれば TCAP = 1.0."""
        # Q = (single, M) → S=30 ばかり
        # Q = (couple, F) → S=40 ばかり
        synthetic = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("single", "single", "M", 30),
                ("couple", "wife", "F", 40),
                ("couple", "wife", "F", 40),
            ]
        )
        holdout = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "wife", "F", 40),
            ]
        )
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, holdout)
        assert abs(result["cap.targeted"] - 1.0) < 1e-9
        assert abs(result["cap.generalized"] - 1.0) < 1e-9
        assert abs(result["cap.coverage"] - 1.0) < 1e-9

    def test_uniform_sensitive_gives_low_cap(self) -> None:
        """Q を全員同じ、S を一様に異ならせると GCAP は低い."""
        # synthetic: Q=(single, M) で age が 4 種
        synthetic = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("single", "single", "M", 31),
                ("single", "single", "M", 32),
                ("single", "single", "M", 33),
            ]
        )
        # holdout: 同じ Q で age=30 のみ
        holdout = _build_arrays([("single", "single", "M", 30)])
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, holdout)
        # 同 Q 内で age=30 は 1/4 だけ → GCAP = 0.25
        assert abs(result["cap.generalized"] - 0.25) < 1e-9
        # TCAP: 最頻値が 30 とは限らない（全部 1 つずつなので最頻値は最初の 30）
        # 実装に依存するが、この場合 30 が最頻値になりうる→ 1.0、または別なら 0.0
        # ここでは曖昧さを避けるため検証スキップ
        assert abs(result["cap.coverage"] - 1.0) < 1e-9

    def test_coverage_when_holdout_q_missing_in_synthetic(self) -> None:
        """synthetic に無い Q が holdout にあると coverage < 1.0."""
        synthetic = _build_arrays([("single", "single", "M", 30)])
        # holdout に couple が含まれるが synthetic には無い
        holdout = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "wife", "F", 40),
            ]
        )
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, holdout)
        # coverage = 1/2
        assert abs(result["cap.coverage"] - 0.5) < 1e-9
        # 該当 person は CAP 計算の分母から除外されるので、carry-over は 1.0
        assert abs(result["cap.generalized"] - 1.0) < 1e-9
        assert abs(result["cap.targeted"] - 1.0) < 1e-9

    def test_per_family_type_breakdown(self) -> None:
        """per_family_type 分解キーが揃う."""
        synthetic = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "wife", "F", 40),
            ]
        )
        holdout = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "wife", "F", 40),
            ]
        )
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, holdout)
        assert "cap.per_family_type.generalized.single" in result
        assert "cap.per_family_type.generalized.couple" in result
        assert "cap.per_family_type.targeted.single" in result
        assert "cap.per_family_type.targeted.couple" in result
        # 同一なので各 1.0
        assert abs(result["cap.per_family_type.generalized.single"] - 1.0) < 1e-9
        assert abs(result["cap.per_family_type.targeted.couple"] - 1.0) < 1e-9


class TestCAPEvaluatorEdgeCases:
    """境界条件."""

    def test_empty_holdout_returns_zero(self) -> None:
        """holdout が空なら全メトリクス 0.0、例外なし."""
        synthetic = _build_arrays([("single", "single", "M", 30)])
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, _empty_arrays())
        assert abs(result["cap.generalized"] - 0.0) < 1e-9
        assert abs(result["cap.targeted"] - 0.0) < 1e-9
        assert abs(result["cap.coverage"] - 0.0) < 1e-9

    def test_empty_synthetic_returns_zero_coverage(self) -> None:
        """synthetic が空なら coverage = 0.0、CAP は 0.0（分母なし）."""
        holdout = _build_arrays([("single", "single", "M", 30)])
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(_empty_arrays(), holdout)
        assert abs(result["cap.coverage"] - 0.0) < 1e-9
        assert abs(result["cap.generalized"] - 0.0) < 1e-9
        assert abs(result["cap.targeted"] - 0.0) < 1e-9

    def test_finite_values(self) -> None:
        """全 fraction 値が有限."""
        synthetic = _build_arrays([("single", "single", "M", 30), ("couple", "wife", "F", 40)])
        holdout = _build_arrays([("single", "single", "M", 30), ("couple", "wife", "F", 41)])
        evaluator = CAPEvaluator()
        result = evaluator.evaluate(synthetic, holdout)
        for k, v in result.items():
            assert np.isfinite(v), f"{k} = {v} is not finite"


class TestCAPEvaluatorCustomQS:
    """quasi-identifier / sensitive を constructor で変更できる."""

    def test_custom_quasi_identifier_role_only(self) -> None:
        """Q = (role,) のみで CAP を計算できる."""
        synthetic = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "husband", "M", 40),
            ]
        )
        holdout = _build_arrays(
            [
                ("single", "single", "M", 30),
                ("couple", "husband", "M", 40),
            ]
        )
        evaluator = CAPEvaluator(quasi_identifiers=("role",), sensitive="age")
        result = evaluator.evaluate(synthetic, holdout)
        # 同一なので perfect CAP
        assert abs(result["cap.generalized"] - 1.0) < 1e-9
