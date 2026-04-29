"""Tests for compare.stats — 統計検定 (Issue #80).

Welch's t-test / Wilcoxon signed-rank / Holm 補正を scipy.stats と比較して
動作を保証する。
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as scipy_stats

from synthpop_jp.compare.stats import (
    holm_correction,
    welch_t_test,
    wilcoxon_signed_rank,
)


class TestWelchTTest:
    """Welch's t-test が scipy と一致."""

    def test_known_values(self) -> None:
        """既知の 2 群で scipy.stats.ttest_ind(equal_var=False) と一致."""
        rng = np.random.default_rng(seed=42)
        a = rng.normal(loc=10.0, scale=1.0, size=20).tolist()
        b = rng.normal(loc=11.0, scale=1.5, size=25).tolist()
        my_t, my_p = welch_t_test(a, b)
        sp = scipy_stats.ttest_ind(a, b, equal_var=False)  # pyright: ignore[reportUnknownMemberType]
        assert abs(my_t - float(sp.statistic)) < 1e-9  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
        assert abs(my_p - float(sp.pvalue)) < 1e-9  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]

    def test_identical_samples_give_zero_t(self) -> None:
        """同じ平均なら t 値が 0 に近い、p 値は大きい."""
        a = [10.0, 11.0, 9.0, 10.5, 9.5]
        b = [10.0, 11.0, 9.0, 10.5, 9.5]
        t, p = welch_t_test(a, b)
        assert abs(t) < 1e-9
        assert p > 0.99


class TestWilcoxonSignedRank:
    """Wilcoxon signed-rank が scipy と一致."""

    def test_known_values(self) -> None:
        """対応のある 2 群で scipy.stats.wilcoxon と一致."""
        rng = np.random.default_rng(seed=42)
        a = rng.normal(loc=10.0, scale=1.0, size=15).tolist()
        b = rng.normal(loc=11.0, scale=1.0, size=15).tolist()
        my_w, my_p = wilcoxon_signed_rank(a, b)
        sp = scipy_stats.wilcoxon(a, b)  # pyright: ignore[reportUnknownMemberType]
        assert abs(my_w - float(sp.statistic)) < 1e-9  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
        assert abs(my_p - float(sp.pvalue)) < 1e-9  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]

    def test_unequal_length_raises(self) -> None:
        """異なる長さなら ValueError (対応群でない)."""
        with pytest.raises(ValueError):
            wilcoxon_signed_rank([1.0, 2.0], [1.0, 2.0, 3.0])


class TestHolmCorrection:
    """Holm-Bonferroni 補正の正しさ."""

    def test_known_holm_example(self) -> None:
        """Holm の手順を手計算で追える例."""
        # m = 4, alpha = 0.05
        # sorted p: 0.01, 0.02, 0.03, 0.04
        # threshold: 0.05/4 = 0.0125, 0.05/3 = 0.0167, 0.05/2 = 0.025, 0.05/1 = 0.05
        # 0.01 < 0.0125 ✓ → 棄却
        # 0.02 < 0.0167 ✗ → 棄却せず、それ以降も自動的に保留
        rejected = holm_correction([0.01, 0.02, 0.03, 0.04], alpha=0.05)
        assert rejected == [True, False, False, False]

    def test_all_significant(self) -> None:
        """全て有意な場合は全 True."""
        rejected = holm_correction([0.001, 0.002, 0.003], alpha=0.05)
        assert rejected == [True, True, True]

    def test_none_significant(self) -> None:
        """全て有意でない場合は全 False."""
        rejected = holm_correction([0.5, 0.6, 0.7], alpha=0.05)
        assert rejected == [False, False, False]

    def test_preserves_input_order(self) -> None:
        """入力順序を保ったまま結果を返す (sort で並び替えない)."""
        # input: [0.04, 0.01, 0.03, 0.02]
        # sort後: [0.01, 0.02, 0.03, 0.04] → [True, False, False, False]
        # 元の順 [0.04, 0.01, 0.03, 0.02] → [False, True, False, False]
        rejected = holm_correction([0.04, 0.01, 0.03, 0.02], alpha=0.05)
        assert rejected == [False, True, False, False]
