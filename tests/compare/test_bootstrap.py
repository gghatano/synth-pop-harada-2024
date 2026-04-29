"""Tests for bootstrap CI (Issue #81)."""

from __future__ import annotations

import numpy as np
import pytest

from synthpop_jp.compare.stats import bootstrap_ci


class TestBootstrapCI:
    """Percentile bootstrap CI."""

    def test_deterministic_with_fixed_seed(self) -> None:
        """同じ seed で同じ CI を返す（決定論）."""
        values: list[float] = [float(x) for x in range(1, 101)]
        rng1 = np.random.default_rng(seed=42)
        rng2 = np.random.default_rng(seed=42)
        ci1 = bootstrap_ci(values, n_bootstrap=200, rng=rng1)
        ci2 = bootstrap_ci(values, n_bootstrap=200, rng=rng2)
        assert ci1 == ci2

    def test_ci_contains_population_mean_for_normal(self) -> None:
        """N=200 のガウス標本で 95% CI が真の平均を高確率で含む."""
        rng = np.random.default_rng(seed=42)
        values = rng.normal(loc=10.0, scale=1.0, size=200).tolist()
        ci_rng = np.random.default_rng(seed=99)
        ci_low, ci_high = bootstrap_ci(values, n_bootstrap=2000, rng=ci_rng)
        assert ci_low < 10.0 < ci_high

    def test_ci_high_greater_than_low(self) -> None:
        """ci_high > ci_low が常に成立."""
        values: list[float] = [float(x) for x in range(1, 51)]
        rng = np.random.default_rng(seed=42)
        ci_low, ci_high = bootstrap_ci(values, n_bootstrap=200, rng=rng)
        assert ci_low <= ci_high

    def test_n_bootstrap_zero_raises(self) -> None:
        """n_bootstrap が 0 以下なら ValueError."""
        with pytest.raises(ValueError):
            bootstrap_ci([1.0, 2.0, 3.0], n_bootstrap=0)

    def test_invalid_confidence_raises(self) -> None:
        """confidence が (0, 1) 外なら ValueError."""
        with pytest.raises(ValueError):
            bootstrap_ci([1.0, 2.0, 3.0], n_bootstrap=10, confidence=1.5)
        with pytest.raises(ValueError):
            bootstrap_ci([1.0, 2.0, 3.0], n_bootstrap=10, confidence=-0.1)

    def test_empty_values_raises(self) -> None:
        """空サンプルは ValueError."""
        with pytest.raises(ValueError):
            bootstrap_ci([], n_bootstrap=10)
