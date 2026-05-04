"""Pareto frontier 抽出のユニットテスト (Issue #119, Step 3).

``extract_non_dominated(points)`` は M 次元スコア空間で **小さいほど良い** 前提の
non-dominated set を返す。改善ループでは

- statistical_fit（小さいほど良い、例: aggregate L1）
- utility（小さいほど良い、TSTR と RTRT の差など）
- privacy（小さいほど良い、CAP / unique 率の代理）

の 3 目的で使う。
"""

from __future__ import annotations

import pytest

from synthpop_jp.improve.pareto import extract_non_dominated, is_dominated


class TestIsDominated:
    """``is_dominated(a, b)``: 全成分で b <= a で 1 つ以上厳密に <。"""

    def test_strictly_dominated(self) -> None:
        assert is_dominated((1.0, 1.0), (0.5, 0.5)) is True

    def test_not_dominated_when_equal(self) -> None:
        assert is_dominated((1.0, 1.0), (1.0, 1.0)) is False

    def test_not_dominated_when_one_better_one_worse(self) -> None:
        assert is_dominated((1.0, 0.5), (0.5, 1.0)) is False

    def test_dominated_when_one_strict_others_equal(self) -> None:
        assert is_dominated((1.0, 1.0), (1.0, 0.5)) is True


class TestExtractNonDominated:
    """``extract_non_dominated(points)``: 非劣点のインデックスを返す."""

    def test_empty_input(self) -> None:
        assert extract_non_dominated([]) == []

    def test_single_point(self) -> None:
        assert extract_non_dominated([(1.0, 2.0, 3.0)]) == [0]

    def test_2d_simple_frontier(self) -> None:
        # (1, 5) は (5, 1) に支配されず、(3, 3) は (1, 5) や (5, 1) に支配されない。
        # (2, 4) は (1, 5) に支配されない（first 2 < 1 は false なので OK）。
        # 実際、(2, 4) は (1, 5) と互いに非劣（2 > 1 だが 4 < 5）。
        # → 全 4 点とも非劣集合に入る
        points = [(1.0, 5.0), (5.0, 1.0), (3.0, 3.0), (2.0, 4.0)]
        result = extract_non_dominated(points)
        assert sorted(result) == [0, 1, 2, 3]

    def test_2d_dominated_point_removed(self) -> None:
        # (10, 10) は他の全点に支配される
        points = [(1.0, 5.0), (5.0, 1.0), (3.0, 3.0), (10.0, 10.0)]
        result = extract_non_dominated(points)
        assert sorted(result) == [0, 1, 2]

    def test_3d_simple_frontier(self) -> None:
        # (1, 1, 1) は他全てに勝つ → 単独フロンティア
        points = [(1.0, 1.0, 1.0), (2.0, 2.0, 2.0), (3.0, 3.0, 3.0)]
        result = extract_non_dominated(points)
        assert result == [0]

    def test_3d_multiple_frontier(self) -> None:
        # 各成分で別々に小さい点 → 全てフロンティア
        points = [(0.0, 5.0, 5.0), (5.0, 0.0, 5.0), (5.0, 5.0, 0.0)]
        result = extract_non_dominated(points)
        assert sorted(result) == [0, 1, 2]

    def test_returns_indices_in_input_order(self) -> None:
        """出力は入力順のインデックス（決定性）."""
        points = [(2.0, 2.0), (1.0, 5.0), (5.0, 1.0)]
        result = extract_non_dominated(points)
        # 全点非劣 → [0, 1, 2] in 入力順
        assert result == [0, 1, 2]

    def test_inconsistent_dimension_raises(self) -> None:
        with pytest.raises(ValueError, match="dimension"):
            extract_non_dominated([(1.0, 2.0), (3.0, 4.0, 5.0)])

    def test_duplicates_kept(self) -> None:
        """完全同一点はどちらも非劣（is_dominated == False で互いに）."""
        points = [(1.0, 1.0), (1.0, 1.0), (5.0, 5.0)]
        result = extract_non_dominated(points)
        # (5, 5) は (1, 1) に支配される
        assert sorted(result) == [0, 1]
