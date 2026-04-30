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


def _household_features(pop: PopulationArrays) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """各 person に household-level 特徴量（household_size, n_children）を broadcast する.

    Returns
    -------
    household_size : np.ndarray
        各 person の所属世帯のメンバー数。shape=(n_persons,)。
    n_children : np.ndarray
        各 person の所属世帯の child 数。shape=(n_persons,)。
    family_type_per_household : np.ndarray
        household_id 出現順での family_type 配列（Task B で使用）。
    """
    n = pop.n_persons
    if n == 0:
        return (
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.int64),
        )
    hids = np.asarray(pop.household_id, dtype=np.int64)
    fts = np.asarray(pop.family_type, dtype=np.int64)
    roles = np.asarray(pop.role, dtype=np.int64)

    try:
        child_role_id = pop.role_reg.id_of("child")
    except KeyError:
        child_role_id = -1  # role に "child" 未登録なら 0 件扱い

    # household_id ごとにメンバー数と child 数を集計
    unique_hids, inverse = np.unique(hids, return_inverse=True)
    member_count = np.bincount(inverse, minlength=unique_hids.shape[0]).astype(np.int64)
    child_count = np.bincount(
        inverse,
        weights=(roles == child_role_id).astype(np.int64),
        minlength=unique_hids.shape[0],
    ).astype(np.int64)

    # 各 person に broadcast
    household_size_per_person = member_count[inverse]
    n_children_per_person = child_count[inverse]

    # household 単位の family_type（household_id ごとに最初に現れた値）
    ft_per_household = np.empty(unique_hids.shape[0], dtype=np.int64)
    seen = np.zeros(unique_hids.shape[0], dtype=bool)
    for i in range(n):
        h = int(inverse[i])
        if not seen[h]:
            ft_per_household[h] = int(fts[i])
            seen[h] = True

    return household_size_per_person, n_children_per_person, ft_per_household


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
    n = pop.n_persons
    if n == 0:
        return np.empty((0, 2), dtype=np.float64), np.empty(0, dtype=np.float64)
    hids = np.asarray(pop.household_id, dtype=np.int64)
    fts = np.asarray(pop.family_type, dtype=np.int64)
    try:
        child_role_id = pop.role_reg.id_of("child")
    except KeyError:
        child_role_id = -1
    roles = np.asarray(pop.role, dtype=np.int64)

    unique_hids, inverse = np.unique(hids, return_inverse=True)
    member_count = np.bincount(inverse, minlength=unique_hids.shape[0]).astype(np.int64)
    child_count = np.bincount(
        inverse,
        weights=(roles == child_role_id).astype(np.int64),
        minlength=unique_hids.shape[0],
    ).astype(np.int64)

    # household 単位の family_type
    ft_per_household = np.empty(unique_hids.shape[0], dtype=np.int64)
    seen = np.zeros(unique_hids.shape[0], dtype=bool)
    for i in range(n):
        h = int(inverse[i])
        if not seen[h]:
            ft_per_household[h] = int(fts[i])
            seen[h] = True

    x = np.column_stack([ft_per_household.astype(np.float64), child_count.astype(np.float64)])
    y = member_count.astype(np.float64)
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
