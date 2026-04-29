"""Aggregate L1 error reporter (Phase 3.5, Issue #59 / #71).

minimal 5 統計（Issue #59）と、optional の family_type × sex pyramid 統計
（Issue #71、5 + 2N 統計）に対し、observed と target の L1 誤差を統計別 + 合計で
返す Evaluator を提供する。

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
- ``aggregate.l1.pyramid_per_family_type.<family_type>.<sex>``
  （``use_family_type_pyramid=True`` のときのみ）
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
        DemographicByFamilyTypeRoleRow,
    )
    from synthpop_jp.optimize.state import PopulationArrays


# minimal 5 統計の出力キー名（``build_objective_stats`` のインデックス順）
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
    demo_ft_role : list[DemographicByFamilyTypeRoleRow] | None
        ``demographic_by_family_type_role.csv`` の全行。
        ``use_family_type_pyramid=True`` のとき必須（Issue #71）。
    use_family_type_pyramid : bool
        True で family_type × sex pyramid 統計の L1 を追加する（Issue #71）。

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
        *,
        demo_ft_role: list[DemographicByFamilyTypeRoleRow] | None = None,
        use_family_type_pyramid: bool = False,
        exclude_male_female_pyramid: bool = False,
    ) -> None:
        self._age_diff_parent_child = age_diff_parent_child
        self._age_diff_couple = age_diff_couple
        self._demographic_by_age_sex = demographic_by_age_sex
        self._demo_ft_role = demo_ft_role
        self._use_family_type_pyramid = use_family_type_pyramid
        self._exclude_male_female_pyramid = exclude_male_female_pyramid

    def evaluate(self, pop: PopulationArrays) -> dict[str, float]:
        """合成人口の統計別 L1 誤差を計算して dict で返す.

        Parameters
        ----------
        pop : PopulationArrays
            評価対象の合成人口配列。``observed`` ヒストグラムの算出元。

        Returns
        -------
        dict[str, float]
            minimal 5 統計の ``aggregate.l1.<stat_name>`` + ``aggregate.l1.total``。
            ``use_family_type_pyramid=True`` のときは
            ``aggregate.l1.pyramid_per_family_type.<ft>.<sex>`` も追加。
            ``exclude_male_female_pyramid=True`` のときは ``pyramid_male`` /
            ``pyramid_female`` キーを出力しない（Murata 式(3) 準拠、Issue #76）。
        """
        stats = build_objective_stats(
            arrays=pop,
            age_diff_parent_child=self._age_diff_parent_child,
            age_diff_couple=self._age_diff_couple,
            demographic_by_age_sex=self._demographic_by_age_sex,
            demo_ft_role=self._demo_ft_role,
            use_family_type_pyramid=self._use_family_type_pyramid,
        )
        result: dict[str, float] = {}
        total = 0.0
        # 0: father_child_age_diff, 1: mother_child_age_diff, 2: couple_age_diff
        # 3: pyramid_male (D), 4: pyramid_female (E)
        excluded_indices: tuple[int, ...] = (3, 4) if self._exclude_male_female_pyramid else ()
        for i in range(5):
            if i in excluded_indices:
                continue
            l1 = stats[i].l1_score()
            result[f"{self.name}.l1.{_STAT_NAMES[i]}"] = l1
            total += l1

        if self._use_family_type_pyramid:
            n_ft = len(pop.family_reg)
            for ft_id in range(n_ft):
                ft_name = pop.family_reg.name_of(ft_id)
                for s_idx, sex in enumerate(("M", "F")):
                    stat_idx = 5 + ft_id * 2 + s_idx
                    l1 = stats[stat_idx].l1_score()
                    key = f"{self.name}.l1.pyramid_per_family_type.{ft_name}.{sex}"
                    result[key] = l1
                    total += l1

        result[f"{self.name}.l1.total"] = total
        return result
