"""Cooling schedules for Simulated Annealing (Issue #30).

冷却スケジュールは SA の温度管理を担う。
``CoolingSchedule`` Protocol を実装することで、将来の LinearCooling など
を追加しやすくする設計にしている。

現在の実装:
- ``ExponentialCooling``: T(iter) = T0 * alpha^iter の指数冷却
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CoolingSchedule(Protocol):
    """冷却スケジュールの Protocol 定義.

    SA runner は温度取得に ``get_temperature(iter)`` だけを使う。
    この Protocol を満たすクラスを任意に差し替えられる。

    Examples
    --------
    >>> cooling: CoolingSchedule = ExponentialCooling(T0=100.0, alpha=0.99)
    >>> cooling.get_temperature(0)
    100.0
    """

    def get_temperature(self, iter: int) -> float:
        """反復 ``iter`` での温度を返す.

        Parameters
        ----------
        iter : int
            現在の反復回数（0-indexed）。非負整数。

        Returns
        -------
        float
            現在の温度 T > 0。
        """
        ...


class ExponentialCooling:
    """指数冷却スケジュール.

    T(iter) = T0 * alpha^iter

    最もシンプルかつ広く使われる冷却方式。
    alpha が 1.0 に近いほど緩やかに冷える。

    Parameters
    ----------
    T0 : float
        初期温度（> 0）。
    alpha : float
        冷却率（0 < alpha <= 1.0）。1.0 のとき温度は一定。

    Raises
    ------
    ValueError
        T0 <= 0 または alpha が (0, 1] の範囲外のとき。

    Examples
    --------
    >>> cooling = ExponentialCooling(T0=100.0, alpha=0.9)
    >>> cooling.get_temperature(0)
    100.0
    >>> cooling.get_temperature(1)
    90.0
    """

    def __init__(self, T0: float, alpha: float) -> None:  # noqa: N803
        if T0 <= 0.0:
            msg = f"T0 は正の実数でなければなりません（T0={T0}）"
            raise ValueError(msg)
        if alpha <= 0.0 or alpha > 1.0:
            msg = f"alpha は (0, 1] の範囲でなければなりません（alpha={alpha}）"
            raise ValueError(msg)
        self._T0 = float(T0)
        self._alpha = float(alpha)

    def get_temperature(self, iter: int) -> float:
        """反復 ``iter`` での温度を返す.

        T(iter) = T0 * alpha^iter

        Parameters
        ----------
        iter : int
            現在の反復回数（0-indexed）。非負整数。

        Returns
        -------
        float
            現在の温度 T >= 0。

        Raises
        ------
        ValueError
            iter < 0 のとき。
        """
        if iter < 0:
            msg = f"iter は非負整数でなければなりません（iter={iter}）"
            raise ValueError(msg)
        return self._T0 * (self._alpha**iter)

    def __repr__(self) -> str:
        """デバッグ用の文字列表現."""
        return f"ExponentialCooling(T0={self._T0}, alpha={self._alpha})"
