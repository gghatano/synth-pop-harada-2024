"""Attribute inference baselines: Generalized CAP / TCAP (Phase 3.5, Issue #65).

合成人口に対する **属性推論リスク** の baseline 評価器を提供する。
quasi-identifier ``Q`` から sensitive attribute ``S`` を推定したときの一致確率を
``synthetic`` と ``holdout``（real 個票）の比較で測る。

`docs/spec/metrics.md` §5.2 / `docs/spec/spec.md` §13.3 に基づく。
出典: Taub et al. (2018) "Differential Correct Attribution Probability"。

提供するもの
------------
- :class:`CAPEvaluator`: ``domain/protocols.py::PrivacyMetric`` Protocol の実装

出力キー命名規則
----------------
- ``cap.generalized``: Generalized CAP（0.0–1.0）
- ``cap.targeted``: TCAP（0.0–1.0）
- ``cap.coverage``: holdout のうち synthetic でカバーされた person の割合
- ``cap.per_family_type.generalized.<family_type>``: 属性別 GCAP
- ``cap.per_family_type.targeted.<family_type>``: 属性別 TCAP

カバレッジに含まれない person（synthetic に同じ Q を持たない person）は
GCAP / TCAP の分母から除外し、coverage 値で見えるようにする。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Literal

import numpy as np

from synthpop_jp.optimize.state import PopulationArrays

if TYPE_CHECKING:
    from synthpop_jp.domain.protocols import PrivacyLayer


_AttrName = Literal["age", "sex", "role", "family_type", "household_id"]


def _column(pop: PopulationArrays, name: str) -> np.ndarray:
    """``PopulationArrays`` から属性配列を名前で引く."""
    if name == "age":
        return pop.age
    if name == "sex":
        return pop.sex
    if name == "role":
        return pop.role
    if name == "family_type":
        return pop.family_type
    if name == "household_id":
        return pop.household_id
    raise ValueError(f"Unknown attribute: {name!r}")


def _q_keys(pop: PopulationArrays, attrs: tuple[str, ...]) -> list[tuple[int, ...]]:
    """各 person の Q-キー（属性値タプル）の列を返す."""
    cols = [_column(pop, a) for a in attrs]
    n = pop.n_persons
    return [tuple(int(c[i]) for c in cols) for i in range(n)]


class CAPEvaluator:
    """Generalized CAP / TCAP の Evaluator（``PrivacyMetric`` Protocol 実装）.

    ``synthetic`` から得られる ``P(S | Q=q)`` と ``holdout`` の真値 ``S`` の
    一致確率を計算する。属性推論攻撃の成功率を 1 数値で要約した指標。

    Attributes
    ----------
    name : str
        ``"cap"`` 固定。``metrics.json`` のキー prefix。
    layer : PrivacyLayer
        ``"attribute_inference"`` 固定。spec §13.3 の中段に対応。
    quasi_identifiers : tuple[str, ...]
        Q として使う属性名のタプル。デフォルトは ``("family_type", "sex")``。
    sensitive : str
        S として使う属性名。デフォルトは ``"age"``。

    Notes
    -----
    Generalized CAP は holdout の各 person について
    ``synthetic`` 内で同じ Q を持つ部分集合の S 分布から該当 S 値の出現確率を取り、
    それを holdout 全体で平均する。
    TCAP は synthetic の同 Q 部分集合の最頻 S が holdout の S と一致する割合
    （0/1 の平均）。

    holdout に存在するが synthetic には存在しない Q の person は
    分母から除外し、``cap.coverage`` で見える化する。
    """

    name: str = "cap"
    layer: PrivacyLayer = "attribute_inference"

    def __init__(
        self,
        quasi_identifiers: tuple[str, ...] = ("family_type", "sex"),
        sensitive: str = "age",
    ) -> None:
        self.quasi_identifiers = quasi_identifiers
        self.sensitive = sensitive

    def evaluate(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> dict[str, float]:
        """Generalized CAP / TCAP / coverage を計算する.

        Parameters
        ----------
        synthetic : PopulationArrays
            合成人口（攻撃者が観測する公開データ）.
        holdout : PopulationArrays
            real 個票（攻撃の正解データ）.

        Returns
        -------
        dict[str, float]
            ``cap.*`` キーを含む dict。空人口でも 0 除算しない。
        """
        result: dict[str, float] = {}

        # 全体スコア
        gcap, tcap, coverage = self._scores(synthetic, holdout)
        result["cap.generalized"] = gcap
        result["cap.targeted"] = tcap
        result["cap.coverage"] = coverage

        # per family_type 分解（holdout に存在する family_type 全てを出す）
        for ft_name in holdout.family_reg.all_names():
            ft_id = holdout.family_reg.id_of(ft_name)
            mask = holdout.family_type == ft_id
            ft_holdout = self._slice(holdout, mask)
            ft_gcap, ft_tcap, _coverage = self._scores(synthetic, ft_holdout)
            result[f"cap.per_family_type.generalized.{ft_name}"] = ft_gcap
            result[f"cap.per_family_type.targeted.{ft_name}"] = ft_tcap

        return result

    def _scores(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> tuple[float, float, float]:
        """``(gcap, tcap, coverage)`` を返す内部実装."""
        n_holdout = holdout.n_persons
        if n_holdout == 0 or synthetic.n_persons == 0:
            return 0.0, 0.0, 0.0

        # synthetic 内で Q ごとの S 分布を集計
        q_synth = _q_keys(synthetic, self.quasi_identifiers)
        s_synth_arr = _column(synthetic, self.sensitive)
        s_dist: dict[tuple[int, ...], Counter[int]] = defaultdict(Counter)
        for i, q in enumerate(q_synth):
            s_dist[q][int(s_synth_arr[i])] += 1

        # synthetic 内 mode のキャッシュ（TCAP 用）
        s_mode: dict[tuple[int, ...], int] = {
            q: counter.most_common(1)[0][0] for q, counter in s_dist.items()
        }

        # holdout 各 person について GCAP / TCAP を集計
        q_hold = _q_keys(holdout, self.quasi_identifiers)
        s_hold_arr = _column(holdout, self.sensitive)
        gcap_sum = 0.0
        tcap_sum = 0
        covered = 0
        for i, q in enumerate(q_hold):
            counter = s_dist.get(q)
            if counter is None:
                continue
            covered += 1
            total = sum(counter.values())
            s_true = int(s_hold_arr[i])
            gcap_sum += counter.get(s_true, 0) / total
            if s_mode[q] == s_true:
                tcap_sum += 1

        coverage = covered / n_holdout
        if covered == 0:
            return 0.0, 0.0, coverage
        return gcap_sum / covered, tcap_sum / covered, coverage

    @staticmethod
    def _slice(pop: PopulationArrays, mask: np.ndarray) -> PopulationArrays:
        """``mask`` で絞った部分人口を返す（registry は共有）."""
        return PopulationArrays(
            age=pop.age[mask],
            sex=pop.sex[mask],
            role=pop.role[mask],
            household_id=pop.household_id[mask],
            family_type=pop.family_type[mask],
            _family_reg=pop.family_reg,
            _role_reg=pop.role_reg,
            _sex_reg=pop.sex_reg,
        )
