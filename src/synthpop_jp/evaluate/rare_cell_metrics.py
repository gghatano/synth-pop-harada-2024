"""Rare cell monitoring metrics (Phase 3.5, Issue #61).

合成人口における ``(family_type, age)`` の組合せを cell とみなし、
cell サイズ < 5 の割合と unique（== 1）の割合を計算する Evaluator を提供する。

`docs/spec/metrics.md` §6 に基づく実装。`docs/spec/spec.md` §11.5 の
soft constraint（improve ループでの reject）の前提値となる。

提供するもの
------------
- ``RareCellEvaluator``: ``domain/protocols.py::Evaluator`` Protocol を実装

出力キー命名規則
----------------
- ``rare_cell.total_cells``: 非空 cell の総数
- ``rare_cell.fraction_below_5``: cell size < 5 の割合（0.0–1.0）
- ``rare_cell.fraction_unique``: cell size == 1 の割合
- ``rare_cell.per_family_type.fraction_below_5.<family_type>``: 属性別
- ``rare_cell.per_family_type.fraction_unique.<family_type>``: 属性別

空人口（n_persons == 0）では全 fraction = 0、total_cells = 0 を返す（0 除算回避）。
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthpop_jp.optimize.state import PopulationArrays


# rare cell 判定の閾値（spec §11.5）
_RARE_THRESHOLD: int = 5
_UNIQUE_THRESHOLD: int = 1


class RareCellEvaluator:
    """``(family_type, age)`` cell の脅威度メトリクス（``Evaluator`` Protocol 実装）.

    合成人口の各 person を ``(family_type, age)`` で分類し、cell サイズの分布から
    rare（size < 5）/ unique（size == 1）の割合を計算する。

    Attributes
    ----------
    name : str
        ``"rare_cell"`` 固定。``metrics.json`` のキー prefix として使われる。
    """

    name: str = "rare_cell"

    def evaluate(self, pop: PopulationArrays) -> dict[str, float]:
        """合成人口の rare cell メトリクスを計算する.

        Parameters
        ----------
        pop : PopulationArrays
            評価対象の合成人口配列。

        Returns
        -------
        dict[str, float]
            ``rare_cell.*`` キーを含む dict。空人口でも 0 除算しない。
        """
        result: dict[str, float] = {}

        n = pop.n_persons
        if n == 0:
            result["rare_cell.total_cells"] = 0.0
            result["rare_cell.fraction_below_5"] = 0.0
            result["rare_cell.fraction_unique"] = 0.0
            return result

        # cell = (family_type_id, age). 全体集計
        family_types = pop.family_type
        ages = pop.age
        cells = Counter(zip(family_types.tolist(), ages.tolist(), strict=True))
        total_cells = len(cells)
        cells_below_5 = sum(1 for c in cells.values() if c < _RARE_THRESHOLD)
        cells_unique = sum(1 for c in cells.values() if c == _UNIQUE_THRESHOLD)
        result["rare_cell.total_cells"] = float(total_cells)
        result["rare_cell.fraction_below_5"] = (
            cells_below_5 / total_cells if total_cells > 0 else 0.0
        )
        result["rare_cell.fraction_unique"] = cells_unique / total_cells if total_cells > 0 else 0.0

        # per family_type 分解
        for ft_name in pop.family_reg.all_names():
            ft_id = pop.family_reg.id_of(ft_name)
            ft_cells = {(fid, age): cnt for (fid, age), cnt in cells.items() if fid == ft_id}
            ft_total = len(ft_cells)
            if ft_total == 0:
                ft_below_5 = 0.0
                ft_unique = 0.0
            else:
                ft_below_5 = sum(1 for c in ft_cells.values() if c < _RARE_THRESHOLD) / ft_total
                ft_unique = sum(1 for c in ft_cells.values() if c == _UNIQUE_THRESHOLD) / ft_total
            result[f"rare_cell.per_family_type.fraction_below_5.{ft_name}"] = ft_below_5
            result[f"rare_cell.per_family_type.fraction_unique.{ft_name}"] = ft_unique

        return result
