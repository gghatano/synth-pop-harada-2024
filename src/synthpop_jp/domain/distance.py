r"""Distance functions for mixed-type data (Phase 4b, Issue #98).

数値属性（連続）とカテゴリ属性（離散）が混在するレコード集合の距離関数を提供する。
DCR / NNDR / ARD（Issue #99）の前提モジュール。

提供するもの
------------
- :func:`gower_distance`: 2 レコード間の Gower 距離（純関数）
- :func:`gower_distance_matrix`: N×M レコード対の距離行列を batch で計算

Gower 距離（Gower 1971）の定義
------------------------------

レコード ``i`` と ``j`` の距離:

.. math::

    d(i, j) = \\frac{1}{p} \\sum_k w_k \\, d_k(i, j)

- ``p``: 属性数
- ``w_k``: 属性 ``k`` の重み（既定 1.0）
- ``d_k(i, j)``:
    - 数値属性: ``|x_i - x_j| / range(x)``（range が 0 なら 0）
    - カテゴリ属性: ``0`` if ``x_i == x_j`` else ``1``

スコープ外
----------
- 重み付き Gower（``w_k != 1.0``）: 別 Issue
- chunk 化（メモリ最適化）: N=10,000 以上で必要なら別 Issue
- Mahalanobis や他の距離: 別 Issue
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import ArrayLike


def gower_distance(
    x: ArrayLike,
    y: ArrayLike,
    *,
    is_numeric: Sequence[bool],
    ranges: Sequence[float],
) -> float:
    """2 レコード間の Gower 距離を計算する.

    Parameters
    ----------
    x : ArrayLike, shape=(p,)
        1 レコードの属性値ベクトル。
    y : ArrayLike, shape=(p,)
        もう 1 レコードの属性値ベクトル。``x`` と同じ形状。
    is_numeric : Sequence[bool]
        各属性が数値（True）かカテゴリ（False）か。長さ ``p``。
    ranges : Sequence[float]
        数値属性の range（max - min）。``is_numeric`` が True の属性に対し
        昇順で並ぶ。長さは ``sum(is_numeric)`` でなくてはならない。

    Returns
    -------
    float
        Gower 距離（0.0〜1.0）。

    Notes
    -----
    range=0 の数値属性（全データが同値）はその属性の貢献を 0 として扱い、
    0 除算を避ける（Gower 1971 の慣習）。
    """
    xa = np.asarray(x, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    if xa.shape != ya.shape:
        msg = f"x.shape {xa.shape} != y.shape {ya.shape}"
        raise ValueError(msg)
    p = int(xa.shape[0])
    if p == 0:
        return 0.0
    if len(is_numeric) != p:
        msg = f"len(is_numeric) {len(is_numeric)} != p {p}"
        raise ValueError(msg)

    range_idx = 0
    total = 0.0
    for k in range(p):
        if is_numeric[k]:
            r = float(ranges[range_idx])
            range_idx += 1
            if r > 0.0:
                total += abs(float(xa[k]) - float(ya[k])) / r
            # else: 貢献 0
        else:
            total += 0.0 if xa[k] == ya[k] else 1.0
    return total / p


def _compute_ranges(x_full: np.ndarray, is_numeric: Sequence[bool]) -> list[float]:
    """数値属性ごとの range（max - min）を返す."""
    ranges: list[float] = []
    for k, num in enumerate(is_numeric):
        if num:
            col = x_full[:, k]
            ranges.append(float(col.max() - col.min()))
    return ranges


def gower_distance_matrix(
    x: ArrayLike,
    y: ArrayLike,
    *,
    is_numeric: Sequence[bool],
    ranges: Sequence[float] | None = None,
) -> np.ndarray:
    """N×M レコード対の Gower 距離行列を返す（batch 計算、vectorize）.

    Parameters
    ----------
    x : ArrayLike, shape=(N, p)
        参照レコード集合（行が N 件、列が属性 p 個）。
    y : ArrayLike, shape=(M, p)
        比較レコード集合。
    is_numeric : Sequence[bool]
        各属性が数値（True）かカテゴリ（False）か。
    ranges : Sequence[float] | None
        数値属性の range。``None`` のとき ``x ∪ y`` から自動計算する。
        外部から渡すと正規化基準を一貫させられる（DCR 等で必須）。

    Returns
    -------
    np.ndarray, shape=(N, M)
        距離行列。``x`` または ``y`` が空のときは shape=(0, M) または (N, 0)。
    """
    xa = np.asarray(x, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    if xa.ndim == 1:
        xa = xa.reshape(1, -1)
    if ya.ndim == 1:
        ya = ya.reshape(1, -1)

    n_x = int(xa.shape[0])
    n_y = int(ya.shape[0])
    p = (
        int(xa.shape[1])
        if xa.ndim == 2 and n_x > 0
        else (int(ya.shape[1]) if ya.ndim == 2 and n_y > 0 else 0)
    )
    if p == 0 or n_x == 0 or n_y == 0:
        return np.empty((n_x, n_y), dtype=np.float64)

    if len(is_numeric) != p:
        msg = f"len(is_numeric) {len(is_numeric)} != p {p}"
        raise ValueError(msg)

    is_num_arr = np.array(list(is_numeric), dtype=bool)
    if ranges is None:
        combined = np.vstack([xa, ya])
        rng_list = _compute_ranges(combined, is_numeric)
    else:
        rng_list = list(ranges)
    if len(rng_list) != int(is_num_arr.sum()):
        msg = f"len(ranges) {len(rng_list)} != number of numeric attrs {int(is_num_arr.sum())}"
        raise ValueError(msg)

    num_cols = np.where(is_num_arr)[0]
    cat_cols = np.where(~is_num_arr)[0]

    contributions = np.zeros((n_x, n_y), dtype=np.float64)

    for k_idx, col in enumerate(num_cols.tolist()):
        r = rng_list[k_idx]
        if r > 0.0:
            x_col = xa[:, col].reshape(n_x, 1)
            y_col = ya[:, col].reshape(1, n_y)
            contributions += np.abs(x_col - y_col) / r

    for col in cat_cols.tolist():
        x_col = xa[:, col].reshape(n_x, 1)
        y_col = ya[:, col].reshape(1, n_y)
        contributions += (x_col != y_col).astype(np.float64)

    return contributions / float(p)
