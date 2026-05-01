"""Broad utility evaluator (Phase 4a, Issue #96).

合成データと参照（"real"）データの **全体としての一致度** を 3 つの指標で測る。

提供するもの
------------
- :class:`BroadUtilityEvaluator`: synth と real の 2 入力で broad utility を計算する評価器

出力キー命名規則
----------------
- ``broad_utility.tv.<attr>``: 単変量 Total Variation distance（0〜1）
- ``broad_utility.l1.<attr>``: 単変量 L1 距離（= 2 × TV）
- ``broad_utility.pair_tv.<a>__<b>``: 属性ペアの joint TV（pair は alphabetical 順）
- ``broad_utility.sum_pair_tv``: 全 pair_tv の合計（属性ペア間の相関歪みのスカラ要約）
- ``broad_utility.correlation_frobenius_diff``: 混合型相関行列の Frobenius norm 差
- ``broad_utility.correlation_max_abs_diff``: 混合型相関行列の max-abs 差

仕様参照
--------
- ``docs/spec/spec.md`` §13.2 / ``docs/spec/metrics.md`` §3
- 混合型相関は dython.associations 準拠（Cramér's V / Correlation Ratio）。
  本実装は外部依存 ``dython`` を導入せず ``scipy.stats`` で計算する。

スコープ外
----------
- Theil's U (asymmetric なため Frobenius と整合しない、別 Issue)
- Pearson 相関（age 以外の連続変数が無い前提）
- ``household_id`` を解析対象に含めない（unique 値が多すぎる）
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import numpy as np
from scipy.stats import (
    chi2_contingency,  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
)

if TYPE_CHECKING:
    from synthpop_jp.optimize.state import PopulationArrays


_DEFAULT_ATTRIBUTES: tuple[str, ...] = ("age", "sex", "role", "family_type")
_NUMERIC_ATTRIBUTES: frozenset[str] = frozenset({"age"})


def _column(pop: PopulationArrays, name: str) -> np.ndarray:
    """``PopulationArrays`` から属性列を取り出す."""
    if name == "age":
        return np.asarray(pop.age, dtype=np.int64)
    if name == "sex":
        return np.asarray(pop.sex, dtype=np.int64)
    if name == "role":
        return np.asarray(pop.role, dtype=np.int64)
    if name == "family_type":
        return np.asarray(pop.family_type, dtype=np.int64)
    if name == "household_id":
        return np.asarray(pop.household_id, dtype=np.int64)
    msg = f"Unknown attribute: {name!r}"
    raise ValueError(msg)


def _categorical_dist(values: np.ndarray) -> dict[int, float]:
    """1D 配列を ``{value: probability}`` 形式の正規化分布に変換."""
    n = int(values.shape[0])
    if n == 0:
        return {}
    unique, counts = np.unique(values, return_counts=True)
    return {int(v): float(c) / n for v, c in zip(unique.tolist(), counts.tolist(), strict=True)}


def _tv_from_dicts(p: dict[int, float], q: dict[int, float]) -> float:
    """2 つの離散分布の Total Variation 距離を計算（共通サポート上の和）."""
    keys = set(p.keys()) | set(q.keys())
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def _univariate_tv(synth: np.ndarray, real: np.ndarray) -> float:
    """同一属性の synth/real 配列から TV 距離を計算する（純関数）.

    どちらか一方が空のときは 0.0 を返す（評価不能 → 中立値）。
    """
    if synth.shape[0] == 0 or real.shape[0] == 0:
        return 0.0
    return _tv_from_dicts(_categorical_dist(synth), _categorical_dist(real))


def _pair_dist(x: np.ndarray, y: np.ndarray) -> dict[tuple[int, int], float]:
    """2 つの 1D 配列から joint 分布を計算する."""
    n = int(x.shape[0])
    if n == 0:
        return {}
    pairs = list(zip(x.tolist(), y.tolist(), strict=True))
    counts: dict[tuple[int, int], int] = {}
    for a, b in pairs:
        key = (int(a), int(b))
        counts[key] = counts.get(key, 0) + 1
    return {k: v / n for k, v in counts.items()}


def _pair_joint_tv(
    synth_x: np.ndarray, synth_y: np.ndarray, real_x: np.ndarray, real_y: np.ndarray
) -> float:
    """2 つの属性 (x, y) の joint TV 距離を計算する（純関数）."""
    if synth_x.shape[0] == 0 or real_x.shape[0] == 0:
        return 0.0
    p = _pair_dist(synth_x, synth_y)
    q = _pair_dist(real_x, real_y)
    keys = set(p.keys()) | set(q.keys())
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def _cramers_v(x: np.ndarray, y: np.ndarray) -> float:
    """Cramér's V を計算（カテゴリ × カテゴリ、bias 補正なし）.

    定義: V = sqrt(chi2 / (n * min(r-1, c-1)))
    片方の配列が定数（unique 値が 1）のときは 0 を返す（独立とみなす）。
    """
    n = int(x.shape[0])
    if n == 0:
        return 0.0
    ux = np.unique(x)
    uy = np.unique(y)
    if ux.shape[0] < 2 or uy.shape[0] < 2:
        return 0.0
    # contingency table
    table = np.zeros((ux.shape[0], uy.shape[0]), dtype=np.int64)
    x_idx = {int(v): i for i, v in enumerate(ux.tolist())}
    y_idx = {int(v): j for j, v in enumerate(uy.tolist())}
    for xi, yi in zip(x.tolist(), y.tolist(), strict=True):
        table[x_idx[int(xi)], y_idx[int(yi)]] += 1
    chi2_stat, _, _, _ = chi2_contingency(table, correction=False)
    chi2_val = float(chi2_stat)  # type: ignore[arg-type]
    denom = float(n) * float(min(ux.shape[0] - 1, uy.shape[0] - 1))
    if denom <= 0.0:
        return 0.0
    v_squared = chi2_val / denom
    if v_squared < 0.0:
        v_squared = 0.0
    if v_squared > 1.0:
        v_squared = 1.0
    return float(np.sqrt(v_squared))


def _correlation_ratio(num: np.ndarray, cat: np.ndarray) -> float:
    """Correlation Ratio (eta) を計算する（連続 × カテゴリ）.

    定義: eta = sqrt(SS_between / SS_total)。
    SS_total が 0（全データが同値）のときは 0 を返す。
    """
    n = int(num.shape[0])
    if n == 0:
        return 0.0
    num = num.astype(np.float64)
    cat = cat.astype(np.int64)
    total_mean = float(num.mean())
    ss_total = float(((num - total_mean) ** 2).sum())
    if ss_total == 0.0:
        return 0.0
    ss_between = 0.0
    for c in np.unique(cat):
        group = num[cat == c]
        if group.shape[0] == 0:
            continue
        gm = float(group.mean())
        ss_between += float(group.shape[0]) * (gm - total_mean) ** 2
    eta_squared = ss_between / ss_total
    if eta_squared < 0.0:
        eta_squared = 0.0
    if eta_squared > 1.0:
        eta_squared = 1.0
    return float(np.sqrt(eta_squared))


def _pair_correlation(a: str, b: str, columns: dict[str, np.ndarray]) -> float:
    """属性ペア (a, b) の相関値を返す（対称）."""
    a_num = a in _NUMERIC_ATTRIBUTES
    b_num = b in _NUMERIC_ATTRIBUTES
    if a_num and b_num:
        return 1.0
    if a_num:
        return _correlation_ratio(columns[a], columns[b])
    if b_num:
        return _correlation_ratio(columns[b], columns[a])
    return _cramers_v(columns[a], columns[b])


def _build_correlation_matrix(
    columns: dict[str, np.ndarray],
    attrs: tuple[str, ...],
) -> np.ndarray:
    """属性ペアの相関を要素とする対称行列（n × n）を組み立てる.

    対角は 1.0、非対角は (連続,カテゴリ) → eta、(カテゴリ,カテゴリ) → V。
    対称行列なので上三角のみ計算してミラーする（重複計算を避ける）。
    """
    n = len(attrs)
    mat = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            v = _pair_correlation(attrs[i], attrs[j], columns)
            mat[i, j] = v
            mat[j, i] = v
    return mat


def _all_pairs(attrs: Iterable[str]) -> list[tuple[str, str]]:
    """属性のすべてのユニークなペア（順序固定）を返す."""
    items = list(attrs)
    pairs: list[tuple[str, str]] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            pairs.append((items[i], items[j]))
    return pairs


class BroadUtilityEvaluator:
    """Broad utility 評価器（``synthetic`` と ``holdout`` の 2 入力）.

    Attributes
    ----------
    name : str
        ``"broad_utility"`` 固定。``metrics.json`` のキー prefix。
    attributes : tuple[str, ...]
        評価対象の属性名タプル。デフォルトは
        ``("age", "sex", "role", "family_type")``。``household_id`` は
        unique 値が多いため対象外（Issue #96 計画 §6 参照）。
    """

    name: str = "broad_utility"

    def __init__(self, attributes: tuple[str, ...] = _DEFAULT_ATTRIBUTES) -> None:
        self.attributes = attributes

    def evaluate(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> dict[str, float]:
        """``synthetic`` と ``holdout`` の broad utility 指標を計算する.

        Parameters
        ----------
        synthetic : PopulationArrays
            合成人口（評価対象）。
        holdout : PopulationArrays
            real 個票（参照）。

        Returns
        -------
        dict[str, float]
            ``broad_utility.*`` キーを含む dict。
            空人口でも 0 除算しない（中立値 0.0 を返す）。
        """
        synth_cols = {a: _column(synthetic, a) for a in self.attributes}
        real_cols = {a: _column(holdout, a) for a in self.attributes}

        result: dict[str, float] = {}

        # 単変量 TV / L1
        for attr in self.attributes:
            tv = _univariate_tv(synth_cols[attr], real_cols[attr])
            result[f"{self.name}.tv.{attr}"] = tv
            result[f"{self.name}.l1.{attr}"] = 2.0 * tv

        # ペア joint TV
        sum_pair_tv = 0.0
        for a, b in _all_pairs(self.attributes):
            tv = _pair_joint_tv(synth_cols[a], synth_cols[b], real_cols[a], real_cols[b])
            result[f"{self.name}.pair_tv.{a}__{b}"] = tv
            sum_pair_tv += tv
        result[f"{self.name}.sum_pair_tv"] = sum_pair_tv

        # 混合型相関 Frobenius / max-abs
        if synthetic.n_persons == 0 or holdout.n_persons == 0:
            result[f"{self.name}.correlation_frobenius_diff"] = 0.0
            result[f"{self.name}.correlation_max_abs_diff"] = 0.0
        else:
            mat_s = _build_correlation_matrix(synth_cols, self.attributes)
            mat_r = _build_correlation_matrix(real_cols, self.attributes)
            diff = mat_s - mat_r
            result[f"{self.name}.correlation_frobenius_diff"] = float(np.linalg.norm(diff))
            result[f"{self.name}.correlation_max_abs_diff"] = float(np.abs(diff).max())

        return result
