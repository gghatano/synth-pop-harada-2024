"""統計検定 (Issue #80) + bootstrap CI (Issue #81).

Welch's t-test / Wilcoxon signed-rank / Holm-Bonferroni 補正 + percentile
法 bootstrap CI を提供する。``scipy.stats`` を内部で呼ぶ薄いラッパー + 自前実装。

実装ノート
----------
- Welch's t-test は ``scipy.stats.ttest_ind(equal_var=False)`` を使う
- Wilcoxon signed-rank は ``scipy.stats.wilcoxon`` を使う（対応群のみ）
- Holm 補正は手実装（scipy には ``multipletests`` 経由で同等品があるが
  依存追加を避けるため自前で書く）
- bootstrap CI は ``numpy.random.Generator`` で復元抽出 + percentile 法

`docs/spec/spec.md` §15.5 が定める検定方法 + bootstrap CI に対応。
"""

from __future__ import annotations

import statistics
from collections.abc import Callable

import numpy as np
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


def bootstrap_ci(
    values: list[float],
    n_bootstrap: int = 2000,
    confidence: float = 0.95,
    rng: np.random.Generator | None = None,
    statistic: Callable[[list[float]], float] = statistics.mean,
) -> tuple[float, float]:
    """Percentile 法 bootstrap CI を返す (spec §15.5、Issue #81).

    手順:
    1. ``values`` から復元抽出で ``n_bootstrap`` 個の resample を作る
    2. 各 resample に ``statistic`` を適用して bootstrap 分布を得る
    3. 分布の ``(1-c)/2`` と ``1-(1-c)/2`` quantile を返す

    Parameters
    ----------
    values : list[float]
        標本（空でないこと）。
    n_bootstrap : int
        リサンプル数。spec §15.5 のデフォルトは 2000。
    confidence : float
        信頼度（0 < c < 1）。デフォルト 0.95（95% CI）。
    rng : np.random.Generator | None
        乱数発生器。``None`` のとき ``np.random.default_rng()`` を使う
        （非決定論）。実験では固定 seed の Generator を渡すこと。
    statistic : Callable[[list[float]], float]
        ブートストラップ対象の統計量。デフォルトは平均。

    Returns
    -------
    tuple[float, float]
        ``(ci_low, ci_high)``。

    Raises
    ------
    ValueError
        ``values`` が空、``n_bootstrap`` <= 0、``confidence`` ∉ (0, 1) のとき。
    """
    if not values:
        msg = "bootstrap_ci: values が空です"
        raise ValueError(msg)
    if n_bootstrap <= 0:
        msg = f"n_bootstrap は 1 以上 (got {n_bootstrap})"
        raise ValueError(msg)
    if not (0.0 < confidence < 1.0):
        msg = f"confidence は (0, 1) の範囲 (got {confidence})"
        raise ValueError(msg)

    if rng is None:
        rng = np.random.default_rng()

    arr = np.asarray(values, dtype=np.float64)
    n = arr.size
    boot_stats = np.empty(n_bootstrap, dtype=np.float64)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sample = arr[idx]
        boot_stats[i] = statistic(sample.tolist())
    alpha = 1.0 - confidence
    low_q = alpha / 2.0
    high_q = 1.0 - alpha / 2.0
    ci_low = float(np.quantile(boot_stats, low_q))
    ci_high = float(np.quantile(boot_stats, high_q))
    return ci_low, ci_high
