"""Pareto frontier extraction (Issue #119, Step 3).

改善ループは「statistical_fit × utility × privacy」の 3 目的で各 trial を比較し、
non-dominated set（パレートフロンティア）を抽出する。

すべての目的は **小さいほど良い** 前提（minimization）。``points`` の各要素は
M 次元タプル（``(stat, util, priv)`` など）。``extract_non_dominated`` は
非劣点の **入力順インデックス** のリストを返す（決定性のため）。

設計
----
- ``is_dominated(a, b)``: ``b`` が ``a`` を支配するか（全成分で b <= a かつ 1 つ
  以上で b < a）
- ``extract_non_dominated(points)``: 他の点に支配されない点のインデックス集合
- 計算量は O(N²)。N <= 30 程度を想定するため十分。
"""

from __future__ import annotations

from collections.abc import Sequence


def is_dominated(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    """``b`` が ``a`` を支配するなら True.

    支配の定義（最小化）:
    - 全成分で ``b[i] <= a[i]``
    - かつ 1 つ以上の成分で ``b[i] < a[i]``

    Parameters
    ----------
    a : tuple[float, ...]
        被支配候補。
    b : tuple[float, ...]
        支配候補。

    Returns
    -------
    bool
        b が a を厳密に支配するなら True。

    Raises
    ------
    ValueError
        a と b の次元が異なる場合。
    """
    if len(a) != len(b):
        msg = f"次元が異なります: len(a)={len(a)}, len(b)={len(b)}"
        raise ValueError(msg)
    all_le = all(bi <= ai for ai, bi in zip(a, b, strict=True))
    any_lt = any(bi < ai for ai, bi in zip(a, b, strict=True))
    return all_le and any_lt


def extract_non_dominated(points: Sequence[tuple[float, ...]]) -> list[int]:
    """非劣点（パレートフロンティア）のインデックスを返す.

    すべての目的は **小さいほど良い** 前提。返値は **入力順のインデックス**。

    Parameters
    ----------
    points : Sequence[tuple[float, ...]]
        各 trial のスコアタプル（同じ次元で揃っていること）。

    Returns
    -------
    list[int]
        非劣点のインデックスを入力順で並べたリスト。

    Raises
    ------
    ValueError
        ``points`` の中に次元が異なる要素がある場合。
    """
    if not points:
        return []

    # 次元一貫性チェック
    dim = len(points[0])
    for i, p in enumerate(points):
        if len(p) != dim:
            msg = (
                f"points の dimension が一致しません: points[0] dim={dim}, points[{i}] dim={len(p)}"
            )
            raise ValueError(msg)

    n = len(points)
    result: list[int] = []
    for i in range(n):
        a = points[i]
        dominated = False
        for j in range(n):
            if i == j:
                continue
            b = points[j]
            if is_dominated(a, b):
                dominated = True
                break
        if not dominated:
            result.append(i)
    return result


__all__ = ["extract_non_dominated", "is_dominated"]
