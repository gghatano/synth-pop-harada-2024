"""Tests for Gower distance (Issue #98).

Gower 距離（Gower 1971）は数値属性とカテゴリ属性が混在する dataset で
レコード間距離を測る指標。本テストは手計算 fixture と既知の境界条件で
数値一致を保証する。
"""

from __future__ import annotations

import numpy as np
import pytest

from synthpop_jp.domain.distance import (
    gower_distance,
    gower_distance_matrix,
)


class TestGowerDistanceSinglePair:
    def test_identical_records_yield_zero(self) -> None:
        x = np.array([10.0, 0, 1])
        y = np.array([10.0, 0, 1])
        is_numeric = [True, False, False]
        ranges = [100.0]
        assert gower_distance(x, y, is_numeric=is_numeric, ranges=ranges) == pytest.approx(0.0)

    def test_numeric_only_l1_normalized(self) -> None:
        # 1 attribute, numeric: |10 - 30| / 100 = 0.2
        x = np.array([10.0])
        y = np.array([30.0])
        assert gower_distance(x, y, is_numeric=[True], ranges=[100.0]) == pytest.approx(0.2)

    def test_categorical_only_hamming(self) -> None:
        # 2 categorical: x=[0,1], y=[0,2] → 1 mismatch / 2 = 0.5
        x = np.array([0, 1])
        y = np.array([0, 2])
        assert gower_distance(x, y, is_numeric=[False, False], ranges=[]) == pytest.approx(0.5)

    def test_mixed_handworked(self) -> None:
        # 3 attributes:
        #   age: 20 vs 40, range=80 → |20-40|/80 = 0.25
        #   sex: 0 vs 0 → 0
        #   role: 1 vs 2 → 1
        # mean = (0.25 + 0 + 1) / 3 ≈ 0.4167
        x = np.array([20.0, 0, 1])
        y = np.array([40.0, 0, 2])
        is_numeric = [True, False, False]
        ranges = [80.0]
        expected = (0.25 + 0.0 + 1.0) / 3.0
        assert gower_distance(x, y, is_numeric=is_numeric, ranges=ranges) == pytest.approx(expected)

    def test_symmetry(self) -> None:
        x = np.array([10.0, 1, 2])
        y = np.array([30.0, 0, 2])
        is_numeric = [True, False, False]
        ranges = [100.0]
        d_xy = gower_distance(x, y, is_numeric=is_numeric, ranges=ranges)
        d_yx = gower_distance(y, x, is_numeric=is_numeric, ranges=ranges)
        assert d_xy == pytest.approx(d_yx)

    def test_zero_range_does_not_raise(self) -> None:
        # range=0（全部同値の数値属性）でも 0 除算しない
        x = np.array([10.0])
        y = np.array([10.0])
        d = gower_distance(x, y, is_numeric=[True], ranges=[0.0])
        assert d == pytest.approx(0.0)


class TestGowerDistanceMatrix:
    def test_self_matrix_has_zero_diagonal(self) -> None:
        x = np.array([[10.0, 0, 1], [20.0, 1, 2], [30.0, 0, 1]])
        is_numeric = [True, False, False]
        m = gower_distance_matrix(x, x, is_numeric=is_numeric)
        assert m.shape == (3, 3)
        for i in range(3):
            assert m[i, i] == pytest.approx(0.0)

    def test_matches_pairwise_calls(self) -> None:
        rng = np.random.default_rng(42)
        x = np.column_stack(
            [
                rng.uniform(0, 100, size=10),
                rng.integers(0, 3, size=10),
                rng.integers(0, 5, size=10),
            ]
        ).astype(np.float64)
        y = np.column_stack(
            [
                rng.uniform(0, 100, size=8),
                rng.integers(0, 3, size=8),
                rng.integers(0, 5, size=8),
            ]
        ).astype(np.float64)
        is_numeric = [True, False, False]
        # range は x∪y から計算（None 指定）
        m = gower_distance_matrix(x, y, is_numeric=is_numeric)
        assert m.shape == (10, 8)

        # 同じ range で gower_distance を 1 ペアずつ計算しても一致
        combined = np.vstack([x, y])
        ranges_each = [float(combined[:, 0].max() - combined[:, 0].min())]
        for i in range(10):
            for j in range(8):
                pair_d = gower_distance(x[i], y[j], is_numeric=is_numeric, ranges=ranges_each)
                assert m[i, j] == pytest.approx(pair_d, abs=1e-9), (
                    f"mismatch at ({i}, {j}): matrix={m[i, j]}, pair={pair_d}"
                )

    def test_matrix_symmetric_when_x_eq_y(self) -> None:
        rng = np.random.default_rng(7)
        x = np.column_stack([rng.uniform(0, 10, size=5), rng.integers(0, 3, size=5)]).astype(
            np.float64
        )
        is_numeric = [True, False]
        m = gower_distance_matrix(x, x, is_numeric=is_numeric)
        for i in range(5):
            for j in range(5):
                assert m[i, j] == pytest.approx(m[j, i], abs=1e-9)

    def test_empty_inputs_return_empty_matrix(self) -> None:
        x = np.empty((0, 2), dtype=np.float64)
        y = np.array([[1.0, 0]])
        is_numeric = [True, False]
        m = gower_distance_matrix(x, y, is_numeric=is_numeric)
        assert m.shape == (0, 1)

        m2 = gower_distance_matrix(y, x, is_numeric=is_numeric)
        assert m2.shape == (1, 0)

    def test_explicit_ranges_override_calculated(self) -> None:
        x = np.array([[10.0, 0], [20.0, 1]])
        y = np.array([[10.0, 0]])
        is_numeric = [True, False]
        # ranges を 100 と指定 → numeric の正規化が変わる
        m = gower_distance_matrix(x, y, is_numeric=is_numeric, ranges=[100.0])
        # m[0, 0]: x[0]=y[0] → 0
        # m[1, 0]: numeric: |20-10|/100=0.1, categorical: 1-0=1 → (0.1+1)/2=0.55
        assert m[0, 0] == pytest.approx(0.0)
        assert m[1, 0] == pytest.approx(0.55)
