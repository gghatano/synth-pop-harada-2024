"""Transition operators (age-change Phase 2, age-swap Phase 3a, hybrid Phase 3a).

このモジュールは SA（シミュレーテッドアニーリング）の候補解生成を担う。

提供するもの:
- ``AgeChangeTransition``: §12.2A. 1 人の age を変更する遷移。
  ``propose() -> (person_idx, new_age)``
- ``AgeSwapTransition``: §12.2B. 同 family_type 同 sex の 2 人の age を交換する遷移
  （Phase 3a, Issue #57）。``propose() -> ((idx_a, new_age_a), (idx_b, new_age_b))``
- ``HybridTransition``: §12.2C. ``AgeChangeTransition`` と ``AgeSwapTransition`` を
  確率 ``p_change`` / ``1 - p_change`` で混合する遷移（Phase 3a, Issue #67）。
  SA loop 側は ``hybrid.choose()`` で内部 transition を取り出し既存ロジックを再利用する。

ハード制約一覧（両遷移で共通）
------------------------------
- 年齢は 0 以上 100 以下
- husband / wife / father / mother は 18 歳以上
- father / mother / parent（義親）は同世帯の child の最高齢 + 14 歳以上
- child は同世帯の father / mother / parent の最若年 - 14 歳以下

制約違反時は内部で retry（最大 MAX_RETRY 回）し、超過したら TransitionError を raise する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from synthpop_jp.io.schemas import DemographicByAgeSexRow, DemographicByFamilyTypeRoleRow
    from synthpop_jp.optimize.state import PopulationArrays

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

#: age の有効範囲 [AGE_MIN, AGE_MAX]
AGE_MIN: int = 0
AGE_MAX: int = 100

#: 成人年齢（husband / wife / father / mother / single が満たすべき最低年齢）
ADULT_AGE_MIN: int = 18

#: parent（義親役割）が child の最高齢より何歳以上年上でなければならないか
PARENT_CHILD_AGE_GAP: int = 14

#: parent 系役割の最低年齢（分布フィルタに使用）
PARENT_ROLE_AGE_MIN: int = 40

#: child 系役割の最高年齢（分布フィルタに使用）
CHILD_ROLE_AGE_MAX: int = 25

#: propose() の 1 回あたりの最大 retry 数
MAX_RETRY: int = 10

#: 役割別の sex フィルタ（None なら両方）
_ROLE_SEX_FILTER: dict[str, str | None] = {
    "husband": "M",
    "wife": "F",
    "father": "M",
    "mother": "F",
    "child": None,
    "parent": None,
    "single": None,
}

#: 役割別の最低年齢フィルタ
_ROLE_AGE_MIN: dict[str, int] = {
    "husband": ADULT_AGE_MIN,
    "wife": ADULT_AGE_MIN,
    "father": ADULT_AGE_MIN,
    "mother": ADULT_AGE_MIN,
    "child": AGE_MIN,
    "parent": PARENT_ROLE_AGE_MIN,
    "single": ADULT_AGE_MIN,
}

#: 役割別の最高年齢フィルタ
_ROLE_AGE_MAX: dict[str, int] = {
    "husband": AGE_MAX,
    "wife": AGE_MAX,
    "father": AGE_MAX,
    "mother": AGE_MAX,
    "child": CHILD_ROLE_AGE_MAX,
    "parent": AGE_MAX,
    "single": AGE_MAX,
}

# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class TransitionError(Exception):
    """ハード制約を満たす新年齢が retry 上限内に見つからなかった.

    ``AgeChangeTransition.propose()`` が ``MAX_RETRY`` 回試行しても
    有効な new_age を見つけられないときに raise される。
    """


# ---------------------------------------------------------------------------
# 役割別年齢分布の構築
# ---------------------------------------------------------------------------


def build_role_age_dist(
    demo_by_age_sex: list[DemographicByAgeSexRow],
    demo_ft_role: list[DemographicByFamilyTypeRoleRow] | None,
) -> dict[str, np.ndarray]:
    """役割別の年齢確率分布（shape=(101,)）を構築して返す.

    Parameters
    ----------
    demo_by_age_sex : list[DemographicByAgeSexRow]
        ``demographic_by_age_sex.csv`` の行リスト。フォールバック用。
    demo_ft_role : list[DemographicByFamilyTypeRoleRow] | None
        ``demographic_by_family_type_role.csv`` の行リスト。
        None または空リストのときはフォールバックを使う。

    Returns
    -------
    dict[str, np.ndarray]
        key: role 名、value: shape=(101,) の正規化確率配列（index = age）。

    Notes
    -----
    ``demo_ft_role`` が提供されている場合、対象 role に対するデータが 1 行以上
    存在すれば、``demo_ft_role`` を優先して分布を構築する。
    データが存在しない role は ``demo_by_age_sex`` にフォールバックする。
    """
    roles = list(_ROLE_SEX_FILTER.keys())

    # demo_ft_role を role ごとに集計（age → count）
    ft_role_by_role: dict[str, dict[int, int]] = {}
    if demo_ft_role:
        for row in demo_ft_role:
            if row.role in roles:
                age_counts = ft_role_by_role.setdefault(row.role, {})
                age_counts[row.age] = age_counts.get(row.age, 0) + row.count

    # demo_by_age_sex を age → {sex → count} に整理
    # shape=(101, 2): axis0=age, axis1=sex (M=0, F=1)
    demo_arr = np.zeros((AGE_MAX + 1, 2), dtype=np.float64)
    for row in demo_by_age_sex:
        if AGE_MIN <= row.age <= AGE_MAX:
            sex_idx = 0 if row.sex == "M" else 1
            demo_arr[row.age, sex_idx] += row.count

    result: dict[str, np.ndarray] = {}

    for role in roles:
        prob = np.zeros(AGE_MAX + 1, dtype=np.float64)

        if role in ft_role_by_role:
            # ft_role データで構築
            for age, count in ft_role_by_role[role].items():
                if AGE_MIN <= age <= AGE_MAX:
                    prob[age] = float(count)
        else:
            # demo_by_age_sex でフォールバック
            sex_filter = _ROLE_SEX_FILTER[role]
            if sex_filter == "M":
                prob_raw = demo_arr[:, 0].copy()
            elif sex_filter == "F":
                prob_raw = demo_arr[:, 1].copy()
            else:
                # 両方合計
                prob_raw = demo_arr[:, 0] + demo_arr[:, 1]
            prob = prob_raw.copy()

        # role 固有の age フィルタを適用（ハード制約の static 部分）
        age_min = _ROLE_AGE_MIN[role]
        age_max = _ROLE_AGE_MAX[role]
        if age_min > 0:
            prob[:age_min] = 0.0
        if age_max < AGE_MAX:
            prob[age_max + 1 :] = 0.0

        # 正規化
        total = prob.sum()
        if total > 0:
            prob /= total
        else:
            # フォールバック: 有効範囲内の一様分布
            valid_range = age_max - age_min + 1
            if valid_range > 0:
                prob[age_min : age_max + 1] = 1.0 / valid_range

        result[role] = prob

    return result


# ---------------------------------------------------------------------------
# AgeChangeTransition
# ---------------------------------------------------------------------------


class AgeChangeTransition:
    """役割別年齢分布から新年齢を抽選する age-change 遷移.

    SA runner が ``propose()`` を繰り返し呼ぶことで候補解を生成する。
    ``propose()`` はハード制約を満たす ``(person_idx, new_age)`` を返す。

    Parameters
    ----------
    arrays : PopulationArrays
        SA の状態配列。propose() は副作用なし（配列を変更しない）。
    demo_by_age_sex : list[DemographicByAgeSexRow]
        人口ピラミッド（sex / age 別 count）。役割別分布のフォールバック用。
    rng : np.random.Generator
        ``SeedRegistry.rng("sa_transition")`` で注入する乱数源。
    demo_ft_role : list[DemographicByFamilyTypeRoleRow] | None
        役割別詳細分布（任意）。あれば demo_by_age_sex より優先する。
    """

    def __init__(
        self,
        arrays: PopulationArrays,
        demo_by_age_sex: list[DemographicByAgeSexRow],
        rng: np.random.Generator,
        demo_ft_role: list[DemographicByFamilyTypeRoleRow] | None = None,
    ) -> None:
        self._arrays = arrays
        self._rng = rng

        # 役割別年齢確率配列を事前構築
        self._role_dist: dict[str, np.ndarray] = build_role_age_dist(demo_by_age_sex, demo_ft_role)

        # role id → role name のマッピングを用意
        role_reg = arrays.role_reg
        self._role_id_to_name: dict[int, str] = {}
        for role_name in _ROLE_SEX_FILTER:
            try:
                rid = role_reg.id_of(role_name)
                self._role_id_to_name[rid] = role_name
            except KeyError:
                pass

        # age 配列の候補リスト（age 0-100）
        self._age_choices = np.arange(AGE_MAX + 1, dtype=np.int64)

        # ハード制約の動的部分をプリコンピュート
        # household_id ごとに:
        #   - child の max_age（parent/father/mother 用: new_age >= child_max + 14）
        #   - parent 系の min_age（child 用: new_age <= parent_min - 14）
        self._precompute_household_constraints()

    def _precompute_household_constraints(self) -> None:
        """世帯内の親子制約を事前に計算する.

        各 person のハード制約（親子関係由来の dynamic 部分）を
        person_idx → (age_min, age_max) の形で
        self._dynamic_age_min / self._dynamic_age_max に格納する。

        静的制約（role 固有の最低/最高年齢）は role_dist の構築時点で処理済みのため、
        ここでは親子関係の dynamic な制約のみを扱う。
        """
        arrays = self._arrays
        n = arrays.n_persons
        role_reg = arrays.role_reg

        # person ごとの dynamic 制約（-1 は制約なしを意味する）
        # dynamic_age_min[i]: new_age の下限（ハード制約由来）
        # dynamic_age_max[i]: new_age の上限（ハード制約由来）
        self._dynamic_age_min = np.full(n, -1, dtype=np.int64)
        self._dynamic_age_max = np.full(n, -1, dtype=np.int64)

        if n == 0:
            return

        # 役割 ID を取得（KeyError は無視）
        def get_role_id(name: str) -> int | None:
            try:
                return role_reg.id_of(name)
            except KeyError:
                return None

        father_id = get_role_id("father")
        mother_id = get_role_id("mother")
        parent_id = get_role_id("parent")
        child_id = get_role_id("child")

        parent_role_ids = {rid for rid in [father_id, mother_id, parent_id] if rid is not None}
        child_role_id = child_id

        if not parent_role_ids and child_role_id is None:
            return

        # 世帯ごとに child max_age と parent系 min_age を計算
        hh_ids = arrays.household_id
        roles = arrays.role
        ages = arrays.age

        # ユニークな世帯 ID
        unique_hh_ids = np.unique(hh_ids)

        for hh_id in unique_hh_ids:
            mask = hh_ids == hh_id
            hh_roles = roles[mask]
            hh_ages = ages[mask].astype(np.int64)
            hh_indices = np.where(mask)[0]

            # child の max_age を計算
            child_max_age = -1
            if child_role_id is not None:
                child_mask = hh_roles == child_role_id
                if child_mask.any():
                    child_max_age = int(hh_ages[child_mask].max())

            # parent 系の min_age を計算
            parent_min_age = -1
            if parent_role_ids:
                parent_mask = np.zeros(len(hh_roles), dtype=bool)
                for pid in parent_role_ids:
                    parent_mask |= hh_roles == pid
                if parent_mask.any():
                    parent_min_age = int(hh_ages[parent_mask].min())

            # 各 person に動的制約を設定
            for local_i, global_i in enumerate(hh_indices):
                role_id = int(hh_roles[local_i])
                if role_id in parent_role_ids and child_max_age >= 0:
                    # father/mother/parent は child の max_age + 14 以上
                    self._dynamic_age_min[global_i] = child_max_age + PARENT_CHILD_AGE_GAP
                elif child_role_id is not None and role_id == child_role_id and parent_min_age >= 0:
                    # child は parent 系の min_age - 14 以下
                    self._dynamic_age_max[global_i] = parent_min_age - PARENT_CHILD_AGE_GAP

    def _sample_age_for_role(self, role_name: str) -> int:
        """役割別確率分布から age を 1 つサンプリングして返す.

        Parameters
        ----------
        role_name : str
            サンプリング対象の役割名。

        Returns
        -------
        int
            サンプリングされた age（0-100）。
        """
        dist = self._role_dist.get(role_name)
        if dist is None:
            # 未知の役割: 全範囲一様
            return int(self._rng.integers(AGE_MIN, AGE_MAX + 1))
        return int(self._rng.choice(self._age_choices, p=dist))

    def _check_hard_constraints(self, person_idx: int, new_age: int, role_name: str) -> bool:
        """new_age がハード制約を満たすか検証する.

        Parameters
        ----------
        person_idx : int
            対象 person のインデックス。
        new_age : int
            検証する新年齢。
        role_name : str
            対象 person の役割名。

        Returns
        -------
        bool
            True ならハード制約を満たす（有効な new_age）。
        """
        # 静的制約: role 固有の最低/最高年齢
        static_min = _ROLE_AGE_MIN.get(role_name, AGE_MIN)
        static_max = _ROLE_AGE_MAX.get(role_name, AGE_MAX)
        if new_age < static_min or new_age > static_max:
            return False

        # グローバル制約: 0-100
        if new_age < AGE_MIN or new_age > AGE_MAX:
            return False

        # 動的制約: 親子関係
        dyn_min = int(self._dynamic_age_min[person_idx])
        dyn_max = int(self._dynamic_age_max[person_idx])

        if dyn_min >= 0 and new_age < dyn_min:
            return False
        return not (dyn_max >= 0 and new_age > dyn_max)

    def propose(self) -> tuple[int, int]:
        """1 人を選んで新年齢を提案する（副作用なし）.

        1/N の一様分布でランダムに person を選び、その役割に対応する
        年齢確率分布から new_age を抽選する。ハード制約を満たさない場合は
        最大 MAX_RETRY 回 retry する。

        Returns
        -------
        tuple[int, int]
            ``(person_idx, new_age)`` のタプル。
            ``person_idx`` は PopulationArrays のインデックス（0-based）。
            ``new_age`` は ハード制約を満たす新年齢（0-100）。

        Raises
        ------
        TransitionError
            MAX_RETRY 回 retry してもハード制約を満たす new_age が見つからない場合。
        """
        arrays = self._arrays
        n = arrays.n_persons

        # 1/N 一様分布で person を選択
        person_idx = int(self._rng.integers(0, n))

        # 役割名を取得
        role_id = int(arrays.role[person_idx])
        role_name = self._role_id_to_name.get(role_id, "")

        # ハード制約を満たすまで retry
        for _ in range(MAX_RETRY):
            new_age = self._sample_age_for_role(role_name)
            if self._check_hard_constraints(person_idx, new_age, role_name):
                return (person_idx, new_age)

        msg = (
            f"propose() が {MAX_RETRY} 回の retry 後もハード制約を満たす"
            f" new_age を見つけられませんでした"
            f"（person_idx={person_idx}, role={role_name!r}）"
        )
        raise TransitionError(msg)


# ---------------------------------------------------------------------------
# AgeSwapTransition (§12.2B, Phase 3a Issue #57)
# ---------------------------------------------------------------------------


class AgeSwapTransition:
    """同一 family_type・同一 sex の 2 人の年齢を交換する遷移（§12.2B）.

    Murata 2017 の age-swap. age-change と異なり family_type 別の人口構成を保つ。
    ``propose()`` は ``((idx_a, new_age_a), (idx_b, new_age_b))`` を返し、
    ``new_age_a == old_age_b`` および ``new_age_b == old_age_a``（年齢の交換）が成り立つ。

    ハード制約は AgeChangeTransition と共通（§11.5）。swap 後の両 person について
    role 静的制約（age >= 18 等）と動的制約（親子年齢差 >= 14）を検証する。
    動的制約は **swap 前の状態**に基づき precompute された値を使う（保守的判定）。

    Parameters
    ----------
    arrays : PopulationArrays
        SA の状態配列。propose() は副作用なし。
    demo_by_age_sex : list[DemographicByAgeSexRow]
        現在は使用しない（API 互換のため）。
    rng : np.random.Generator
        乱数源。
    demo_ft_role : list[DemographicByFamilyTypeRoleRow] | None
        現在は使用しない（API 互換のため）。
    """

    def __init__(
        self,
        arrays: PopulationArrays,
        demo_by_age_sex: list[DemographicByAgeSexRow],
        rng: np.random.Generator,
        demo_ft_role: list[DemographicByFamilyTypeRoleRow] | None = None,
    ) -> None:
        # demo_by_age_sex / demo_ft_role は AgeChangeTransition と signature を揃えるため
        # 受け取るが、age-swap では年齢分布からの抽選を行わないので使用しない。
        del demo_by_age_sex, demo_ft_role
        self._arrays = arrays
        self._rng = rng

        # role id → name のマッピング
        role_reg = arrays.role_reg
        self._role_id_to_name: dict[int, str] = {}
        for role_name in _ROLE_SEX_FILTER:
            try:
                rid = role_reg.id_of(role_name)
                self._role_id_to_name[rid] = role_name
            except KeyError:
                pass

        # ハード制約の動的部分: AgeChange と同じ pre-compute ロジックを再利用
        self._dynamic_age_min, self._dynamic_age_max = _compute_dynamic_constraints(arrays)

        # (family_type_id, sex_id) → list[person_idx] のプール（size >= 2 のみ）
        self._pools: list[tuple[tuple[int, int], np.ndarray]] = self._build_swap_pools()

    def _build_swap_pools(self) -> list[tuple[tuple[int, int], np.ndarray]]:
        """同 family_type・同 sex で 2 人以上いるグループを列挙する.

        Returns
        -------
        list[tuple[tuple[int, int], np.ndarray]]
            ``[((family_type_id, sex_id), person_indices), ...]`` のリスト。
            ``person_indices`` のサイズは 2 以上。
        """
        arrays = self._arrays
        n = arrays.n_persons
        pools: list[tuple[tuple[int, int], np.ndarray]] = []
        if n == 0:
            return pools

        # family_type と sex の組合せごとに person index を集約
        fts = arrays.family_type
        sexes = arrays.sex
        unique_fts = np.unique(fts)
        unique_sexes = np.unique(sexes)
        for ft_id in unique_fts:
            for sex_id in unique_sexes:
                mask = (fts == ft_id) & (sexes == sex_id)
                indices = np.where(mask)[0]
                if indices.size >= 2:
                    pools.append(((int(ft_id), int(sex_id)), indices))
        return pools

    def _check_swap_constraint(self, person_idx: int, new_age: int) -> bool:
        """person_idx を new_age にした場合のハード制約を検証する."""
        if new_age < AGE_MIN or new_age > AGE_MAX:
            return False
        role_id = int(self._arrays.role[person_idx])
        role_name = self._role_id_to_name.get(role_id, "")
        static_min = _ROLE_AGE_MIN.get(role_name, AGE_MIN)
        static_max = _ROLE_AGE_MAX.get(role_name, AGE_MAX)
        if new_age < static_min or new_age > static_max:
            return False
        dyn_min = int(self._dynamic_age_min[person_idx])
        dyn_max = int(self._dynamic_age_max[person_idx])
        if dyn_min >= 0 and new_age < dyn_min:
            return False
        return not (dyn_max >= 0 and new_age > dyn_max)

    def propose(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """同 family_type 同 sex の 2 人を選んで年齢を交換する提案を返す（副作用なし）.

        Returns
        -------
        tuple[tuple[int, int], tuple[int, int]]
            ``((idx_a, new_age_a), (idx_b, new_age_b))``。
            ``new_age_a == arrays.age[idx_b]``、``new_age_b == arrays.age[idx_a]``。

        Raises
        ------
        TransitionError
            プールが空（同 family_type 同 sex で 2 人組が存在しない）、または
            MAX_RETRY 回 retry してもハード制約を満たすペアが見つからない場合。
        """
        if not self._pools:
            msg = "AgeSwapTransition: 同 family_type 同 sex の 2 人組プールが空です"
            raise TransitionError(msg)

        for _ in range(MAX_RETRY):
            # プールを 1 つ選び、その中から 2 人を抽選
            pool_idx = int(self._rng.integers(0, len(self._pools)))
            _, indices = self._pools[pool_idx]
            chosen = self._rng.choice(indices, size=2, replace=False)
            idx_a, idx_b = int(chosen[0]), int(chosen[1])

            old_age_a = int(self._arrays.age[idx_a])
            old_age_b = int(self._arrays.age[idx_b])
            # swap が無意味（同年齢）ならスキップして retry
            if old_age_a == old_age_b:
                continue

            new_age_a = old_age_b
            new_age_b = old_age_a
            if self._check_swap_constraint(idx_a, new_age_a) and self._check_swap_constraint(
                idx_b, new_age_b
            ):
                return ((idx_a, new_age_a), (idx_b, new_age_b))

        msg = (
            f"AgeSwapTransition: {MAX_RETRY} 回の retry 後もハード制約を満たす"
            f" swap ペアが見つかりませんでした"
        )
        raise TransitionError(msg)


# ---------------------------------------------------------------------------
# 内部ヘルパー: 動的制約の precompute（AgeSwapTransition から再利用）
# ---------------------------------------------------------------------------


def _compute_dynamic_constraints(arrays: PopulationArrays) -> tuple[np.ndarray, np.ndarray]:
    """世帯内の親子制約から ``(dyn_min, dyn_max)`` 配列を計算する.

    AgeChangeTransition._precompute_household_constraints と同じロジックの
    module-level 抽出。AgeSwapTransition との共有のため。

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ``(dynamic_age_min, dynamic_age_max)``。``-1`` は制約なしを意味する。
    """
    n = arrays.n_persons
    dyn_min = np.full(n, -1, dtype=np.int64)
    dyn_max = np.full(n, -1, dtype=np.int64)
    if n == 0:
        return dyn_min, dyn_max

    role_reg = arrays.role_reg

    def get_role_id(name: str) -> int | None:
        try:
            return role_reg.id_of(name)
        except KeyError:
            return None

    father_id = get_role_id("father")
    mother_id = get_role_id("mother")
    parent_id = get_role_id("parent")
    child_id = get_role_id("child")

    parent_role_ids = {rid for rid in [father_id, mother_id, parent_id] if rid is not None}

    if not parent_role_ids and child_id is None:
        return dyn_min, dyn_max

    hh_ids = arrays.household_id
    roles = arrays.role
    ages = arrays.age

    for hh_id in np.unique(hh_ids):
        mask = hh_ids == hh_id
        hh_roles = roles[mask]
        hh_ages = ages[mask].astype(np.int64)
        hh_indices = np.where(mask)[0]

        child_max_age = -1
        if child_id is not None:
            child_mask = hh_roles == child_id
            if child_mask.any():
                child_max_age = int(hh_ages[child_mask].max())

        parent_min_age = -1
        if parent_role_ids:
            parent_mask = np.zeros(len(hh_roles), dtype=bool)
            for pid in parent_role_ids:
                parent_mask |= hh_roles == pid
            if parent_mask.any():
                parent_min_age = int(hh_ages[parent_mask].min())

        for local_i, global_i in enumerate(hh_indices):
            role_id = int(hh_roles[local_i])
            if role_id in parent_role_ids and child_max_age >= 0:
                dyn_min[global_i] = child_max_age + PARENT_CHILD_AGE_GAP
            elif child_id is not None and role_id == child_id and parent_min_age >= 0:
                dyn_max[global_i] = parent_min_age - PARENT_CHILD_AGE_GAP

    return dyn_min, dyn_max


# ---------------------------------------------------------------------------
# HybridTransition (§12.2C, Phase 3a Issue #67)
# ---------------------------------------------------------------------------


class HybridTransition:
    """``AgeChangeTransition`` と ``AgeSwapTransition`` の確率混合遷移.

    spec §12.2C: 各 SA 反復で確率 ``p_change`` で AgeChange、
    ``1 - p_change`` で AgeSwap を選択する。
    どちらが選ばれたかで propose() の戻り値型が異なるため、本クラス自身は
    propose() を持たず、SA loop 側に ``choose()`` で内部 transition を返す。

    Parameters
    ----------
    change : AgeChangeTransition
        age-change 遷移インスタンス。
    swap : AgeSwapTransition
        age-swap 遷移インスタンス。
    p_change : float
        AgeChange を選ぶ確率 (0.0–1.0)。残りが AgeSwap の確率。
    rng : np.random.Generator
        どちらを選ぶかの乱数源（SeedRegistry の独立 stream を渡す）。

    Raises
    ------
    ValueError
        ``p_change`` が ``[0.0, 1.0]`` の範囲外のとき。

    Notes
    -----
    動的スケジュール（反復に応じた p_change 変化）は spec §12.2C で示唆されているが
    本実装では固定確率のみ。スケジュール対応は後続 Issue で。
    """

    def __init__(
        self,
        change: AgeChangeTransition,
        swap: AgeSwapTransition,
        p_change: float,
        rng: np.random.Generator,
    ) -> None:
        if not (0.0 <= p_change <= 1.0):
            msg = f"p_change は [0.0, 1.0] の範囲でなければなりません (got {p_change})"
            raise ValueError(msg)
        self._change = change
        self._swap = swap
        self._p_change = float(p_change)
        self._rng = rng

    def choose(self) -> AgeChangeTransition | AgeSwapTransition:
        """乱数で AgeChange / AgeSwap のどちらか 1 つを返す.

        Returns
        -------
        AgeChangeTransition | AgeSwapTransition
            各呼び出し時点で確率的に選ばれる内部 transition。
        """
        if self._rng.uniform() < self._p_change:
            return self._change
        return self._swap
