"""Distance-based privacy metrics: DCR / NNDR / ARD (Phase 4b, Issue #99).

合成人口の **類似度 proxy** 層（Harada 2024 §5.2）に位置する 3 指標を提供する。
3 つすべて Gower 距離（``synthpop_jp.domain.distance``、Issue #98）を土台にする。

提供するもの
------------
- :class:`DCREvaluator`: Distance to Closest Record (synth → real の最近傍距離)
- :class:`NNDREvaluator`: Nearest Neighbor Distance Ratio
- :class:`ARDEvaluator`: Average Record Distance (Harada 2024 §5.2)

出典
----
- DCR: Lampe & Knauer (2018) "Synthetic Data Vault" 等
- NNDR: Platzer & Reutterer (2021) "Holdout-Based Empirical Assessment"
- ARD: Harada 2024 §5.2

スコープ外
----------
- shadow training に基づく MIA (Phase 5、Issue #100 protocol 準拠)
- DP guarantee による上界（別 Issue）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np

from synthpop_jp.domain.distance import gower_distance_matrix

if TYPE_CHECKING:
    from synthpop_jp.optimize.state import PopulationArrays


PrivacyLayer = Literal["proxy", "attribute_inference", "mia"]


# DCR / NNDR / ARD 共通の属性集合（PopulationArrays の主要 4 列）
_ATTRIBUTES: tuple[str, ...] = ("age", "sex", "role", "family_type")
_IS_NUMERIC: tuple[bool, ...] = (True, False, False, False)


def _build_matrix(pop: PopulationArrays) -> np.ndarray:
    """``PopulationArrays`` から (N, 4) の数値行列を作る."""
    if pop.n_persons == 0:
        return np.empty((0, len(_ATTRIBUTES)), dtype=np.float64)
    return np.column_stack(
        [
            np.asarray(pop.age, dtype=np.float64),
            np.asarray(pop.sex, dtype=np.float64),
            np.asarray(pop.role, dtype=np.float64),
            np.asarray(pop.family_type, dtype=np.float64),
        ]
    )


def _common_distance_matrix(synthetic: PopulationArrays, holdout: PopulationArrays) -> np.ndarray:
    """``gower_distance_matrix`` の共通呼び出しを抽象化."""
    if synthetic.n_persons == 0 or holdout.n_persons == 0:
        return np.empty((synthetic.n_persons, holdout.n_persons), dtype=np.float64)
    x = _build_matrix(synthetic)
    y = _build_matrix(holdout)
    return gower_distance_matrix(x, y, is_numeric=list(_IS_NUMERIC))


def _dcr_metrics(d: np.ndarray) -> dict[str, float]:
    if d.size == 0:
        return {"dcr.p05": 0.0, "dcr.p50": 0.0, "dcr.mean": 0.0}
    nearest = d.min(axis=1)
    return {
        "dcr.p05": float(np.percentile(nearest, 5)),
        "dcr.p50": float(np.percentile(nearest, 50)),
        "dcr.mean": float(nearest.mean()),
    }


def _nndr_metrics(d: np.ndarray) -> dict[str, float]:
    if d.size == 0 or d.shape[1] < 2:
        return {"nndr.p05": 0.0, "nndr.p50": 0.0, "nndr.mean": 0.0}
    sorted_d = np.sort(d, axis=1)
    nearest = sorted_d[:, 0]
    second_nearest = sorted_d[:, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(second_nearest > 0, nearest / second_nearest, 0.0)
    return {
        "nndr.p05": float(np.percentile(ratio, 5)),
        "nndr.p50": float(np.percentile(ratio, 50)),
        "nndr.mean": float(ratio.mean()),
    }


def _ard_metrics(d: np.ndarray) -> dict[str, float]:
    if d.size == 0:
        return {"ard.mean": 0.0}
    return {"ard.mean": float(d.mean())}


def evaluate_distance_proxy_metrics(
    synthetic: PopulationArrays,
    holdout: PopulationArrays,
) -> dict[str, float]:
    """DCR / NNDR / ARD を共有 Gower 距離行列で **一度だけ** 計算する.

    各評価器を独立に呼ぶと N×M Gower 距離行列を 3 回計算するが、本関数は
    一度計算した行列を 3 つの集約関数で再利用する。CLI から呼ばれる
    主入口（CLI で 1 回の計算で 3 指標が揃う）。
    """
    d = _common_distance_matrix(synthetic, holdout)
    return {**_dcr_metrics(d), **_nndr_metrics(d), **_ard_metrics(d)}


# ---------------------------------------------------------------------------
# DCREvaluator
# ---------------------------------------------------------------------------


class DCREvaluator:
    """DCR (Distance to Closest Record) — synth → real 最近傍距離の集約.

    Attributes
    ----------
    name : str
        ``"dcr"`` 固定。``metrics.json`` のキー prefix。
    layer : PrivacyLayer
        ``"proxy"`` 固定（Harada 2024 §5.2 (a) 類似度 proxy）。
    """

    name: str = "dcr"
    layer: PrivacyLayer = "proxy"

    def evaluate(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> dict[str, float]:
        """各 synth レコードに対する real 集合での最近傍距離を集約する."""
        return _dcr_metrics(_common_distance_matrix(synthetic, holdout))


# ---------------------------------------------------------------------------
# NNDREvaluator
# ---------------------------------------------------------------------------


class NNDREvaluator:
    """NNDR (Nearest Neighbor Distance Ratio) — 最近傍 / 2 番目近傍 の比率.

    値が低いほど「synth レコードが特定の real レコードに近すぎる」ことを示す。
    """

    name: str = "nndr"
    layer: PrivacyLayer = "proxy"

    def evaluate(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> dict[str, float]:
        """各 synth について NNDR を集約する.

        分母（2 番目近傍距離）が 0 のときは 0 を返す（中立値）。
        """
        return _nndr_metrics(_common_distance_matrix(synthetic, holdout))


# ---------------------------------------------------------------------------
# ARDEvaluator
# ---------------------------------------------------------------------------


class ARDEvaluator:
    """ARD (Average Record Distance, Harada 2024 §5.2) — synth × real の Gower 距離平均.

    全 N×M ペアの平均 Gower 距離を返す。
    DCR が「最近傍だけ」を見るのに対し、ARD は「全体としての近さ」を見る。
    """

    name: str = "ard"
    layer: PrivacyLayer = "proxy"

    def evaluate(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> dict[str, float]:
        """Synth × real ペアの平均 Gower 距離を返す."""
        return _ard_metrics(_common_distance_matrix(synthetic, holdout))
