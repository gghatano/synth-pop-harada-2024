"""Tests for cooling schedules (Issue #30).

TDD サイクル:
  Cycle 1: ExponentialCooling の温度減衰（T0, alpha の算出テスト、境界値）
  Cycle 2: Cooling Protocol 定義 + ExponentialCooling 実装確認
"""

from __future__ import annotations

import math

import pytest

from synthpop_jp.optimize.cooling import CoolingSchedule, ExponentialCooling


class TestExponentialCooling:
    """ExponentialCooling の単体テスト."""

    def test_initial_temperature_at_iter_zero(self) -> None:
        """iter=0 のとき T0 が返される."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        assert abs(cooling.get_temperature(0) - 100.0) < 1e-9

    def test_temperature_decreases_monotonically(self) -> None:
        """温度が単調に減少する."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        temps = [cooling.get_temperature(i) for i in range(100)]
        for i in range(len(temps) - 1):
            assert temps[i] > temps[i + 1], f"iter {i}: {temps[i]} <= {temps[i + 1]}"

    def test_temperature_formula(self) -> None:
        """温度が T0 * alpha^iter の式に従う."""
        t0 = 50.0
        alpha = 0.95
        cooling = ExponentialCooling(T0=t0, alpha=alpha)
        for iter_n in [0, 1, 5, 10, 50]:
            expected = t0 * (alpha**iter_n)
            actual = cooling.get_temperature(iter_n)
            assert abs(actual - expected) < 1e-9, (
                f"iter={iter_n}: expected {expected}, got {actual}"
            )

    def test_temperature_after_many_iters(self) -> None:
        """多反復後も温度が 0 以上であることを確認（アンダーフローなし）."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.999)
        temp = cooling.get_temperature(100_000)
        assert temp >= 0.0
        # 100 * 0.999^100000 ≈ 100 * e^(-100) ≈ 3.7e-42 → 0 に近いが非負
        assert temp < 1.0

    def test_alpha_one_constant_temperature(self) -> None:
        """alpha=1.0 のとき温度が一定（特殊ケース）."""
        cooling = ExponentialCooling(T0=42.0, alpha=1.0)
        for iter_n in [0, 1, 100, 1000]:
            assert abs(cooling.get_temperature(iter_n) - 42.0) < 1e-9

    def test_large_iter_boundary(self) -> None:
        """大きな iter 値でも正常動作する."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.9)
        # 10000 回目: 100 * 0.9^10000 はほぼ 0 だが ValueError が起きないこと
        temp = cooling.get_temperature(10_000)
        assert temp >= 0.0

    def test_invalid_t0_raises(self) -> None:
        """T0 <= 0 は ValueError."""
        with pytest.raises(ValueError, match="T0"):
            ExponentialCooling(T0=0.0, alpha=0.99)
        with pytest.raises(ValueError, match="T0"):
            ExponentialCooling(T0=-1.0, alpha=0.99)

    def test_invalid_alpha_raises(self) -> None:
        """alpha が (0, 1] の範囲外は ValueError."""
        with pytest.raises(ValueError, match="alpha"):
            ExponentialCooling(T0=100.0, alpha=0.0)
        with pytest.raises(ValueError, match="alpha"):
            ExponentialCooling(T0=100.0, alpha=1.001)
        with pytest.raises(ValueError, match="alpha"):
            ExponentialCooling(T0=100.0, alpha=-0.1)

    def test_negative_iter_raises(self) -> None:
        """負の iter は ValueError."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        with pytest.raises(ValueError, match="iter"):
            cooling.get_temperature(-1)


class TestCoolingScheduleProtocol:
    """CoolingSchedule Protocol が ExponentialCooling で満たされることを確認."""

    def test_exponential_is_cooling_schedule(self) -> None:
        """ExponentialCooling は CoolingSchedule プロトコルを満たす."""
        cooling: CoolingSchedule = ExponentialCooling(T0=100.0, alpha=0.99)
        # get_temperature メソッドが呼べること
        temp = cooling.get_temperature(0)
        assert isinstance(temp, float)
        assert temp > 0.0

    def test_protocol_duck_typing(self) -> None:
        """CoolingSchedule として扱える duck typing を確認."""

        class LinearCoolingStub:
            """テスト用スタブ: 線形冷却の最小実装."""

            def __init__(
                self,
                T0: float,  # noqa: N803
                min_T: float,  # noqa: N803
                max_iters: int,
            ) -> None:
                self._T0 = T0
                self._min_T = min_T
                self._max_iters = max_iters

            def get_temperature(self, iter: int) -> float:
                """線形冷却スケジュール."""
                if iter >= self._max_iters:
                    return self._min_T
                ratio = iter / self._max_iters
                return self._T0 * (1 - ratio) + self._min_T * ratio

        stub: CoolingSchedule = LinearCoolingStub(T0=100.0, min_T=1.0, max_iters=1000)
        temp_0 = stub.get_temperature(0)
        temp_500 = stub.get_temperature(500)
        assert temp_0 > temp_500

    def test_exponential_cooling_at_specific_steps(self) -> None:
        """具体的な冷却ステップの検証.

        T0=100, alpha=0.9 の場合:
          iter=0:  100.0
          iter=1:  90.0
          iter=10: 100 * 0.9^10 ≈ 34.87
        """
        cooling = ExponentialCooling(T0=100.0, alpha=0.9)
        assert abs(cooling.get_temperature(0) - 100.0) < 1e-9
        assert abs(cooling.get_temperature(1) - 90.0) < 1e-9
        expected_10 = 100.0 * (0.9**10)
        assert abs(cooling.get_temperature(10) - expected_10) < 1e-9

    def test_repr(self) -> None:
        """ExponentialCooling の repr / str が情報を含む."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        s = repr(cooling)
        assert "100" in s or "ExponentialCooling" in s

    def test_cooling_reaches_near_zero(self) -> None:
        """十分な反復後に温度が非常に小さくなる."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.5)
        # 0.5^100 ≈ 7.9e-31 → 十分小さい
        temp_at_100 = cooling.get_temperature(100)
        assert temp_at_100 < 1e-20

    def test_compare_two_alphas(self) -> None:
        """alpha が小さいほど早く冷える."""
        fast_cooling = ExponentialCooling(T0=100.0, alpha=0.9)
        slow_cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        iter_n = 100
        assert fast_cooling.get_temperature(iter_n) < slow_cooling.get_temperature(iter_n)

    def test_get_temperature_returns_float(self) -> None:
        """get_temperature の戻り値は float."""
        cooling = ExponentialCooling(T0=100.0, alpha=0.99)
        result = cooling.get_temperature(42)
        assert isinstance(result, float)
        assert math.isfinite(result)
