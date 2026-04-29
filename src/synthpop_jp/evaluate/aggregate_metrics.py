"""Aggregate 21-statistic L1 error reporter (Phase 3.5, Issue #59).

Phase 2 実装済みの 5 統計（``ObjectiveState.stats`` と同型）に対し、observed と
target の L1 誤差を統計別 + 合計で返す Evaluator を提供する。21 統計拡張は
Phase 3a の別 Issue で対応する。

提供するもの
------------
- ``AggregateStatL1Evaluator``: ``domain/protocols.py::Evaluator`` Protocol を実装

出力キー命名規則
----------------
- ``aggregate.l1.father_child_age_diff``
- ``aggregate.l1.mother_child_age_diff``
- ``aggregate.l1.couple_age_diff``
- ``aggregate.l1.pyramid_male``
- ``aggregate.l1.pyramid_female``
- ``aggregate.l1.total``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synthpop_jp.optimize.objective import build_objective_stats

if TYPE_CHECKING:
    from synthpop_jp.io.schemas import (
        AgeDiffCoupleRow,
        AgeDiffParentChildRow,
        DemographicByAgeSexRow,
    )
    from synthpop_jp.optimize.state import PopulationArrays


# 5 統計の出力キー名（``build_objective_stats`` のインデックス順）
_STAT_NAMES: tuple[str, ...] = (
    "father_child_age_diff",
    "mother_child_age_diff",
    "couple_age_diff",
    "pyramid_male",
    "pyramid_female",
)


class AggregateStatL1Evaluator:
    """統計別 L1 誤差レポータ（``Evaluator`` Protocol 実装）.

    入力 CSV から target 統計を保持し、``evaluate(pop)`` で合成人口に対する
    observed を都度計算して L1 誤差を返す。

    Parameters
    ----------
    age_diff_parent_child : list[AgeDiffParentChildRow]
        ``age_diff_parent_child.csv`` から読んだ全行。
    age_diff_couple : list[AgeDiffCoupleRow]
        ``age_diff_couple.csv`` から読んだ全行。
    demographic_by_age_sex : list[DemographicByAgeSexRow]
        ``demographic_by_age_sex.csv`` から読んだ全行。

    Attributes
    ----------
    name : str
        ``"aggregate"`` 固定。``metrics.json`` のキー prefix として使われる。
    """

    name: str = "aggregate"

    def __init__(
        self,
        age_diff_parent_child: list[AgeDiffParentChildRow],
        age_diff_couple: list[AgeDiffCoupleRow],
        demographic_by_age_sex: list[DemographicByAgeSexRow],
    ) -> None:
        self._age_diff_parent_child = age_diff_parent_child
        self._age_diff_couple = age_diff_couple
        self._demographic_by_age_sex = demographic_by_age_sex

    def evaluate(self, pop: PopulationArrays) -> dict[str, float]:
        """合成人口の 5 統計 L1 誤差を計算して dict で返す.

        Parameters
        ----------
        pop : PopulationArrays
            評価対象の合成人口配列。``observed`` ヒストグラムの算出元。

        Returns
        -------
        dict[str, float]
            ``aggregate.l1.<stat_name>`` × 5 + ``aggregate.l1.total`` を含む
            6 キーの dict。
        """
        stats = build_objective_stats(
            arrays=pop,
            age_diff_parent_child=self._age_diff_parent_child,
            age_diff_couple=self._age_diff_couple,
            demographic_by_age_sex=self._demographic_by_age_sex,
        )
        result: dict[str, float] = {}
        total = 0.0
        for i, stat in enumerate(stats):
            l1 = stat.l1_score()
            result[f"{self.name}.l1.{_STAT_NAMES[i]}"] = l1
            total += l1
        result[f"{self.name}.l1.total"] = total
        return result
