"""Narrow utility evaluator (Phase 4a, Issue #97).

合成データで学習したモデルが実データのタスクで使えるかを **TSTR / TRTS** で測る。
spec §13.2 / metrics.md §4 で凍結された 3 タスクを実行する。

3 タスク
--------
- **Task A**: family_type 分類（features=[age, sex, household_size], target=family_type, macro-F1）
- **Task B**: 世帯人数回帰（features=[family_type, n_children], target=household_size, RMSE）
- **Task C**: 役割予測（features=[age, sex, family_type], target=role, macro-F1）

Task A と C は person 単位、Task B は household 単位の評価。

評価方式
--------
- TSTR: synthetic 全件で train、real 全件で test
- TRTS: real 全件で train、synthetic 全件で test
- hold-out split は **しない**（synth と real は別サンプルとみなす）

提供するもの
------------
- :class:`NarrowUtilityEvaluator`: synth と real の 2 入力で TSTR/TRTS を計算する評価器

出力キー命名規則
----------------
- ``narrow_utility.task_a.tstr_macro_f1`` / ``trts_macro_f1``
- ``narrow_utility.task_b.tstr_rmse``    / ``trts_rmse``
- ``narrow_utility.task_c.tstr_macro_f1`` / ``trts_macro_f1``

備考
----
- spec §13.2 の Task A 元定義「世帯内 role 分布」は household 単位特徴量で
  per-person タスクと整合しないため、本実装では household_size に簡素化した
  （Issue #97 計画 §2.1 で記録、別 Issue で再定義可能）。
- baseline モデル: scikit-learn の LogisticRegression / LinearRegression（既定）。
  seed 固定で再現性を担保（``random_state=self.seed``）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from sklearn.linear_model import (  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
    LinearRegression,
    LogisticRegression,
)
from sklearn.metrics import (  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
    f1_score,  # pyright: ignore[reportUnknownVariableType]
    mean_squared_error,  # pyright: ignore[reportUnknownVariableType]
)

if TYPE_CHECKING:
    from synthpop_jp.optimize.state import PopulationArrays


class _HouseholdAggregates:
    """``_household_features_full`` の戻り値を保持する小さい構造体."""

    __slots__ = (
        "child_count",
        "ft_per_household",
        "household_size_per_person",
        "member_count",
        "n_children_per_person",
    )

    def __init__(
        self,
        household_size_per_person: np.ndarray,
        n_children_per_person: np.ndarray,
        member_count: np.ndarray,
        child_count: np.ndarray,
        ft_per_household: np.ndarray,
    ) -> None:
        self.household_size_per_person = household_size_per_person
        self.n_children_per_person = n_children_per_person
        self.member_count = member_count
        self.child_count = child_count
        self.ft_per_household = ft_per_household


def _household_aggregates(pop: PopulationArrays) -> _HouseholdAggregates:
    """``pop`` から household 集計（メンバー数・child 数・family_type）を 1 度だけ計算.

    Task A は household_size_per_person、Task B は member_count / child_count /
    ft_per_household を使う。同じ集計を Task ごとに繰り返さないようまとめる。
    """
    n = pop.n_persons
    if n == 0:
        empty_i64 = np.empty(0, dtype=np.int64)
        return _HouseholdAggregates(empty_i64, empty_i64, empty_i64, empty_i64, empty_i64)

    hids = np.asarray(pop.household_id, dtype=np.int64)
    fts = np.asarray(pop.family_type, dtype=np.int64)
    roles = np.asarray(pop.role, dtype=np.int64)

    try:
        child_role_id = pop.role_reg.id_of("child")
    except KeyError:
        child_role_id = -1

    # household_id ごとに集計（unique は出現順を保つ）
    unique_hids, first_idx, inverse = np.unique(hids, return_index=True, return_inverse=True)
    member_count = np.bincount(inverse, minlength=unique_hids.shape[0]).astype(np.int64)
    child_count = np.bincount(
        inverse,
        weights=(roles == child_role_id).astype(np.int64),
        minlength=unique_hids.shape[0],
    ).astype(np.int64)

    # household 単位の family_type は「各世帯で最初に現れた person」の family_type。
    # np.unique(return_index=True) は unique_hids[k] が最初に現れた位置を返すので
    # それを使って Python ループを排除する。
    ft_per_household = fts[first_idx]

    return _HouseholdAggregates(
        household_size_per_person=member_count[inverse],
        n_children_per_person=child_count[inverse],
        member_count=member_count,
        child_count=child_count,
        ft_per_household=ft_per_household,
    )


def _household_features(pop: PopulationArrays) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """後方互換ラッパー: ``(household_size_per_person, n_children_per_person, ft_per_household)``.

    既存テストや外部コードのために残す。新規呼び出しは ``_household_aggregates`` を使うこと。
    """
    agg = _household_aggregates(pop)
    return agg.household_size_per_person, agg.n_children_per_person, agg.ft_per_household


def _features_task_a(pop: PopulationArrays) -> tuple[np.ndarray, np.ndarray]:
    """Task A: features=[age, sex, household_size], target=family_type."""
    n = pop.n_persons
    if n == 0:
        return np.empty((0, 3), dtype=np.float64), np.empty(0, dtype=np.int64)
    household_size, _, _ = _household_features(pop)
    x = np.column_stack(
        [
            np.asarray(pop.age, dtype=np.float64),
            np.asarray(pop.sex, dtype=np.float64),
            household_size.astype(np.float64),
        ]
    )
    y = np.asarray(pop.family_type, dtype=np.int64)
    return x, y


def _features_task_b(pop: PopulationArrays) -> tuple[np.ndarray, np.ndarray]:
    """Task B: features=[family_type, n_children], target=household_size（household 単位）."""
    if pop.n_persons == 0:
        return np.empty((0, 2), dtype=np.float64), np.empty(0, dtype=np.float64)
    agg = _household_aggregates(pop)
    x = np.column_stack(
        [agg.ft_per_household.astype(np.float64), agg.child_count.astype(np.float64)]
    )
    y = agg.member_count.astype(np.float64)
    return x, y


def _features_task_c(pop: PopulationArrays) -> tuple[np.ndarray, np.ndarray]:
    """Task C: features=[age, sex, family_type], target=role."""
    n = pop.n_persons
    if n == 0:
        return np.empty((0, 3), dtype=np.float64), np.empty(0, dtype=np.int64)
    x = np.column_stack(
        [
            np.asarray(pop.age, dtype=np.float64),
            np.asarray(pop.sex, dtype=np.float64),
            np.asarray(pop.family_type, dtype=np.float64),
        ]
    )
    y = np.asarray(pop.role, dtype=np.int64)
    return x, y


def _macro_f1_classification(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    seed: int,
) -> float:
    """LogisticRegression で train→test を評価し macro-F1 を返す.

    train セットに 1 クラスしかない、または train/test が空 ⇒ 0.0 を返す
    （中立値）。
    """
    if x_train.shape[0] == 0 or x_test.shape[0] == 0:
        return 0.0
    if np.unique(y_train).shape[0] < 2:
        return 0.0
    model = LogisticRegression(max_iter=200, random_state=seed)
    model.fit(x_train, y_train)  # pyright: ignore[reportUnknownMemberType]
    pred = model.predict(x_test)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    # zero_division=0: if a class has no positive samples, F1 is set to 0
    # (sklearn stub declares zero_division: str only, but runtime accepts int)
    score = f1_score(
        y_test,
        pred,
        average="macro",
        zero_division=0,  # pyright: ignore[reportArgumentType]
    )
    return float(score)  # pyright: ignore[reportArgumentType]


def _rmse_regression(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> float:
    """LinearRegression で train→test を評価し RMSE を返す.

    train または test が空のときは 0.0 を返す（中立値）。
    """
    if x_train.shape[0] == 0 or x_test.shape[0] == 0:
        return 0.0
    model = LinearRegression()
    model.fit(x_train, y_train)  # pyright: ignore[reportUnknownMemberType]
    pred = model.predict(x_test)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    mse = float(mean_squared_error(y_test, pred))  # pyright: ignore[reportUnknownArgumentType]
    return float(np.sqrt(mse))


class NarrowUtilityEvaluator:
    """Narrow utility 評価器（``synthetic`` と ``holdout`` の 2 入力）.

    Attributes
    ----------
    name : str
        ``"narrow_utility"`` 固定。``metrics.json`` のキー prefix。
    seed : int
        baseline モデルの ``random_state``。デフォルト 42。
    """

    name: str = "narrow_utility"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def evaluate(
        self,
        synthetic: PopulationArrays,
        holdout: PopulationArrays,
    ) -> dict[str, float]:
        """3 タスクの TSTR / TRTS を計算する.

        Parameters
        ----------
        synthetic : PopulationArrays
            合成人口。
        holdout : PopulationArrays
            real 個票。

        Returns
        -------
        dict[str, float]
            ``narrow_utility.*`` キーを含む dict（6 個）。
            空人口でも 0.0 で埋める（NaN を返さない）。
        """
        result: dict[str, float] = {}

        # Task A: family_type classification
        xa_s, ya_s = _features_task_a(synthetic)
        xa_r, ya_r = _features_task_a(holdout)
        result["narrow_utility.task_a.tstr_macro_f1"] = _macro_f1_classification(
            xa_s, ya_s, xa_r, ya_r, seed=self.seed
        )
        result["narrow_utility.task_a.trts_macro_f1"] = _macro_f1_classification(
            xa_r, ya_r, xa_s, ya_s, seed=self.seed
        )

        # Task B: household_size regression
        xb_s, yb_s = _features_task_b(synthetic)
        xb_r, yb_r = _features_task_b(holdout)
        result["narrow_utility.task_b.tstr_rmse"] = _rmse_regression(xb_s, yb_s, xb_r, yb_r)
        result["narrow_utility.task_b.trts_rmse"] = _rmse_regression(xb_r, yb_r, xb_s, yb_s)

        # Task C: role prediction
        xc_s, yc_s = _features_task_c(synthetic)
        xc_r, yc_r = _features_task_c(holdout)
        result["narrow_utility.task_c.tstr_macro_f1"] = _macro_f1_classification(
            xc_s, yc_s, xc_r, yc_r, seed=self.seed
        )
        result["narrow_utility.task_c.trts_macro_f1"] = _macro_f1_classification(
            xc_r, yc_r, xc_s, yc_s, seed=self.seed
        )

        return result
