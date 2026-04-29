"""統計検定 (Issue #80).

Welch's t-test / Wilcoxon signed-rank / Holm-Bonferroni 補正を提供する。
``scipy.stats`` を内部で呼ぶ薄いラッパー + Holm の自前実装。

実装ノート
----------
- Welch's t-test は ``scipy.stats.ttest_ind(equal_var=False)`` を使う
- Wilcoxon signed-rank は ``scipy.stats.wilcoxon`` を使う（対応群のみ）
- Holm 補正は手実装（scipy には ``multipletests`` 経由で同等品があるが
  依存追加を避けるため自前で書く）

`docs/spec/spec.md` §15.5 が定める検定方法に対応。
"""

from __future__ import annotations

from scipy import stats as _scipy_stats


def welch_t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Welch's t-test (independent samples, unequal variance).

    Parameters
    ----------
    a, b : list[float]
        2 群のサンプル。長さは異なっても良い。

    Returns
    -------
    tuple[float, float]
        ``(t_statistic, p_value)``。p_value は両側検定。
    """
    result = _scipy_stats.ttest_ind(a, b, equal_var=False)  # pyright: ignore[reportUnknownMemberType]
    return float(result.statistic), float(result.pvalue)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]


def wilcoxon_signed_rank(a: list[float], b: list[float]) -> tuple[float, float]:
    """Wilcoxon signed-rank test (paired samples).

    Parameters
    ----------
    a, b : list[float]
        対応のある 2 群。長さは一致が必須。

    Returns
    -------
    tuple[float, float]
        ``(statistic, p_value)``。p_value は両側検定。

    Raises
    ------
    ValueError
        ``a`` と ``b`` の長さが異なる場合。
    """
    if len(a) != len(b):
        msg = f"Wilcoxon signed-rank は対応群のみ対応 (got len(a)={len(a)}, len(b)={len(b)})"
        raise ValueError(msg)
    result = _scipy_stats.wilcoxon(a, b)  # pyright: ignore[reportUnknownMemberType]
    return float(result.statistic), float(result.pvalue)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]


def holm_correction(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """Holm-Bonferroni step-down 法で多重比較補正を行う.

    手順:
    1. p_values を昇順に並べる（元のインデックスを保持）
    2. ``i`` 番目（1-indexed）の p_value を ``alpha / (m - i + 1)`` と比較
    3. 一度比較に失敗したら、それ以降は全て **棄却せず** とする
    4. 元の入力順序で結果を返す

    Parameters
    ----------
    p_values : list[float]
        各検定の p_value（同じ問題群の中で並列に得たもの）。
    alpha : float
        family-wise error rate（デフォルト 0.05）。

    Returns
    -------
    list[bool]
        各 p_value について「帰無仮説を棄却するか」を入力順で返す。
    """
    m = len(p_values)
    if m == 0:
        return []
    # (original_index, p_value) を p_value 昇順に
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    rejected_by_orig: dict[int, bool] = {i: False for i in range(m)}
    holding = False  # 一度棄却に失敗したら残りも自動的に棄却せず
    for rank, (orig_idx, p) in enumerate(indexed, start=1):
        if holding:
            rejected_by_orig[orig_idx] = False
            continue
        threshold = alpha / (m - rank + 1)
        if p < threshold:
            rejected_by_orig[orig_idx] = True
        else:
            rejected_by_orig[orig_idx] = False
            holding = True
    return [rejected_by_orig[i] for i in range(m)]
