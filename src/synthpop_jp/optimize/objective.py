"""差分更新版目的関数 — ObjectiveState (Issue #27).

SA（シミュレーテッドアニーリング）の 1 ステップで 1 人の age が変わるとき、
5 統計のヒストグラムを O(1) で差分更新し、目的スコアを維持するクラスを提供する。

5 統計（spec §11.2）
----------------------
- stats[0]: father-child 年齢差 (parent_age - child_age, role=father)
- stats[1]: mother-child 年齢差 (parent_age - child_age, role=mother)
- stats[2]: couple 年齢差 (husband_age - wife_age)
- stats[3]: male demographic pyramid (sex=M)
- stats[4]: female demographic pyramid (sex=F)

目的関数（原論文式(1) primary）
---------------------------------
    f(A) = Σ_s Σ_j |observed[s,j] - target[s,j]|

weight は全部 1.0（研究拡張モード / ペナルティは非スコープ）。

差分更新
---------
- ``propose_change(person_idx, new_age) -> float``: 副作用なし、スコア差分のみ返す
- ``apply_change(person_idx, new_age) -> None``: 内部状態を実更新
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from synthpop_jp.io.schemas import (
    AgeDiffCoupleRow,
    AgeDiffParentChildRow,
    DemographicByAgeSexRow,
    DemographicByFamilyTypeRoleRow,
)

if TYPE_CHECKING:
    from synthpop_jp.optimize.state import PopulationArrays


# ---------------------------------------------------------------------------
# StatTable: 1 統計分の observed / target ヒストグラム
# ---------------------------------------------------------------------------


@dataclass
class StatTable:
    """1 統計分の observed/target ヒストグラム.

    Attributes
    ----------
    observed : np.ndarray
        観測値ヒストグラム（int64, shape=(n_bins,)）。
        合成人口から計算した各 bin のカウント。
    target : np.ndarray
        目標値ヒストグラム（int64, shape=(n_bins,)）。
        入力 CSV から得た各 bin のカウント。
    bin_edges : np.ndarray
        ビン境界（float64, shape=(n_bins+1,)）。
        半開区間 [bin_edges[i], bin_edges[i+1]) で各 bin を定義する。
    """

    observed: np.ndarray
    target: np.ndarray
    bin_edges: np.ndarray

    def l1_score(self) -> float:
        """この統計の L1 スコア（Σ|observed - target|）を返す."""
        return float(np.abs(self.observed.astype(np.int64) - self.target.astype(np.int64)).sum())

    def bin_index(self, value: float) -> int:
        """Value が属する bin の index を返す.

        範囲外の場合は -1（bin_edges より小さい）または n_bins（大きい）を返す。
        numpy.searchsorted の挙動に準じる。

        Parameters
        ----------
        value : float
            ビンに割り当てる値。

        Returns
        -------
        int
            0-indexed の bin index。範囲外なら -1 または len(observed)。
        """
        idx = int(np.searchsorted(self.bin_edges[1:], value, side="right"))
        return idx


# ---------------------------------------------------------------------------
# ビン index 計算ユーティリティ
# ---------------------------------------------------------------------------


def _bin_index(bin_edges: np.ndarray, value: float) -> int:
    """Value が属する bin の index を numpy.histogram と一致する方法で返す.

    np.histogram は最後のビンだけ右端を閉じた区間 [left, right] として扱う。
    これを再現するために、value == bin_edges[-1] の場合は最後のビンに含める。

    Parameters
    ----------
    bin_edges : np.ndarray
        ビン境界配列（長さ n_bins+1）。
    value : float
        ビンに割り当てる値。

    Returns
    -------
    int
        0-indexed の bin index。
        範囲外（value < bin_edges[0] または value > bin_edges[-1]）なら
        ``-1`` または ``n_bins`` を返す。
    """
    n_bins = len(bin_edges) - 1
    idx = int(np.searchsorted(bin_edges[1:], value, side="right"))
    # np.histogram の最後ビンは右端閉: [bin_edges[-2], bin_edges[-1]] を含む
    if idx == n_bins and value == bin_edges[-1]:
        idx = n_bins - 1
    return idx


# ---------------------------------------------------------------------------
# ヒストグラム構築ヘルパー
# ---------------------------------------------------------------------------


def _build_diff_bins(rows: list[AgeDiffParentChildRow] | list[AgeDiffCoupleRow]) -> np.ndarray:
    """Diff rows から bin_edges 配列を構築する.

    Parameters
    ----------
    rows : list[AgeDiffParentChildRow] | list[AgeDiffCoupleRow]
        ソート済みの bin 定義行。

    Returns
    -------
    np.ndarray
        shape=(n_bins+1,) の bin 境界配列。
    """
    if not rows:
        return np.array([0.0, 1.0], dtype=np.float64)
    edges = [float(rows[0].diff_min)]
    for row in rows:
        edges.append(float(row.diff_max))
    return np.array(edges, dtype=np.float64)


def _build_age_bins(rows: list[DemographicByAgeSexRow]) -> np.ndarray:
    """demographic_by_age_sex rows から age bin_edges を構築する.

    各行の age 値が bin の下端。次の値までが 1 bin。
    最後の bin の上端は最大 age + 1 step とする。

    Parameters
    ----------
    rows : list[DemographicByAgeSexRow]
        同じ sex でフィルタした行（ソート済みを想定）。

    Returns
    -------
    np.ndarray
        shape=(n_bins+1,) の bin 境界配列。
    """
    ages = sorted({row.age for row in rows})
    if not ages:
        return np.array([0.0, 1.0], dtype=np.float64)
    if len(ages) == 1:
        return np.array([float(ages[0]), float(ages[0] + 5)], dtype=np.float64)
    # bin 幅を最初の差分から推定（通常 5 歳刻み）
    step = ages[1] - ages[0]
    edges = [float(a) for a in ages] + [float(ages[-1] + step)]
    return np.array(edges, dtype=np.float64)


def _build_parent_child_stat(
    rows: list[AgeDiffParentChildRow],
    role_name: str,
    arrays: PopulationArrays,
) -> StatTable:
    """親子年齢差統計を構築する.

    Parameters
    ----------
    rows : list[AgeDiffParentChildRow]
        age_diff_parent_child.csv から読んだ全行。
    role_name : str
        ``"father"`` または ``"mother"``。
    arrays : PopulationArrays
        初期人口配列。

    Returns
    -------
    StatTable
        observed と target が初期化された統計テーブル。
    """
    role_rows = sorted(
        [r for r in rows if r.role == role_name],
        key=lambda r: r.diff_min,
    )
    bin_edges = _build_diff_bins(role_rows)
    n_bins = len(bin_edges) - 1

    # target: CSV の count
    target = np.zeros(n_bins, dtype=np.int64)
    for i, row in enumerate(role_rows):
        target[i] = row.count

    # observed: 合成人口から計算
    observed = _compute_parent_child_observed(arrays, role_name, bin_edges, n_bins)

    return StatTable(observed=observed, target=target, bin_edges=bin_edges)


def _compute_parent_child_observed(
    arrays: PopulationArrays,
    role_name: str,
    bin_edges: np.ndarray,
    n_bins: int,
) -> np.ndarray:
    """親子年齢差の observed ヒストグラムを計算する.

    Parameters
    ----------
    arrays : PopulationArrays
        人口配列。
    role_name : str
        ``"father"`` または ``"mother"``。
    bin_edges : np.ndarray
        ビン境界。
    n_bins : int
        ビン数。

    Returns
    -------
    np.ndarray
        shape=(n_bins,) の observed カウント配列（int64）。
    """
    observed = np.zeros(n_bins, dtype=np.int64)

    try:
        parent_role_id = arrays.role_reg.id_of(role_name)
    except KeyError:
        return observed

    try:
        child_role_id = arrays.role_reg.id_of("child")
    except KeyError:
        return observed

    parent_mask = arrays.role == parent_role_id
    if not np.any(parent_mask):
        return observed

    parent_indices = np.where(parent_mask)[0]

    # 世帯ごとに親と子の組み合わせを計算
    # child_role_id を持つ世帯員を household_id でグループ化
    child_mask = arrays.role == child_role_id
    if not np.any(child_mask):
        return observed

    child_indices = np.where(child_mask)[0]

    # household_id → child_ages のマッピング
    hid_to_child_ages: dict[int, list[int]] = {}
    for ci in child_indices:
        hid = int(arrays.household_id[ci])
        if hid not in hid_to_child_ages:
            hid_to_child_ages[hid] = []
        hid_to_child_ages[hid].append(int(arrays.age[ci]))

    # 親ごとに差分を計算してビンに追加
    for pi in parent_indices:
        hid = int(arrays.household_id[pi])
        parent_age = int(arrays.age[pi])
        child_ages = hid_to_child_ages.get(hid, [])
        for child_age in child_ages:
            diff = float(parent_age - child_age)
            bin_idx = _bin_index(bin_edges, diff)
            if 0 <= bin_idx < n_bins:
                observed[bin_idx] += 1

    return observed


def _build_couple_stat(
    rows: list[AgeDiffCoupleRow],
    arrays: PopulationArrays,
) -> StatTable:
    """夫婦年齢差統計を構築する.

    couple_diff = husband_age - wife_age

    Parameters
    ----------
    rows : list[AgeDiffCoupleRow]
        age_diff_couple.csv から読んだ全行。
    arrays : PopulationArrays
        初期人口配列。

    Returns
    -------
    StatTable
        observed と target が初期化された統計テーブル。
    """
    sorted_rows = sorted(rows, key=lambda r: r.diff_min)
    bin_edges = _build_diff_bins(sorted_rows)
    n_bins = len(bin_edges) - 1

    # target: CSV の count
    target = np.zeros(n_bins, dtype=np.int64)
    for i, row in enumerate(sorted_rows):
        target[i] = row.count

    observed = _compute_couple_observed(arrays, bin_edges, n_bins)

    return StatTable(observed=observed, target=target, bin_edges=bin_edges)


def _compute_couple_observed(
    arrays: PopulationArrays,
    bin_edges: np.ndarray,
    n_bins: int,
) -> np.ndarray:
    """夫婦年齢差の observed ヒストグラムを計算する.

    Parameters
    ----------
    arrays : PopulationArrays
        人口配列。
    bin_edges : np.ndarray
        ビン境界。
    n_bins : int
        ビン数。

    Returns
    -------
    np.ndarray
        shape=(n_bins,) の observed カウント配列（int64）。
    """
    observed = np.zeros(n_bins, dtype=np.int64)

    try:
        husband_role_id = arrays.role_reg.id_of("husband")
        wife_role_id = arrays.role_reg.id_of("wife")
    except KeyError:
        return observed

    husband_mask = arrays.role == husband_role_id
    if not np.any(husband_mask):
        return observed

    husband_indices = np.where(husband_mask)[0]

    # household_id → wife_age のマッピング
    wife_mask = arrays.role == wife_role_id
    wife_indices = np.where(wife_mask)[0]
    hid_to_wife_age: dict[int, int] = {}
    for wi in wife_indices:
        hid = int(arrays.household_id[wi])
        hid_to_wife_age[hid] = int(arrays.age[wi])

    # 夫ごとに差分を計算してビンに追加
    for hi in husband_indices:
        hid = int(arrays.household_id[hi])
        if hid not in hid_to_wife_age:
            continue
        husband_age = int(arrays.age[hi])
        wife_age = hid_to_wife_age[hid]
        diff = float(husband_age - wife_age)
        bin_idx = _bin_index(bin_edges, diff)
        if 0 <= bin_idx < n_bins:
            observed[bin_idx] += 1

    return observed


def _build_pyramid_stat(
    rows: list[DemographicByAgeSexRow],
    sex_label: str,
    arrays: PopulationArrays,
) -> StatTable:
    """性別別人口ピラミッド統計を構築する.

    Parameters
    ----------
    rows : list[DemographicByAgeSexRow]
        demographic_by_age_sex.csv から読んだ全行。
    sex_label : str
        ``"M"`` または ``"F"``。
    arrays : PopulationArrays
        初期人口配列。

    Returns
    -------
    StatTable
        observed と target が初期化された統計テーブル。
    """
    sex_rows = sorted([r for r in rows if r.sex == sex_label], key=lambda r: r.age)
    bin_edges = _build_age_bins(sex_rows)
    n_bins = len(bin_edges) - 1

    # target: CSV の count（bin_edges に対応する順序で）
    target = np.zeros(n_bins, dtype=np.int64)
    age_to_idx = {int(bin_edges[i]): i for i in range(n_bins)}
    for row in sex_rows:
        idx = age_to_idx.get(row.age)
        if idx is not None and 0 <= idx < n_bins:
            target[idx] = row.count

    # observed: 合成人口の sex 別年齢ヒストグラム
    sex_id = arrays.sex_reg.id_of(sex_label)
    observed = _compute_pyramid_observed(arrays, sex_id, bin_edges, n_bins)

    return StatTable(observed=observed, target=target, bin_edges=bin_edges)


def _compute_pyramid_observed(
    arrays: PopulationArrays,
    sex_id: int,
    bin_edges: np.ndarray,
    n_bins: int,
) -> np.ndarray:
    """性別別人口ピラミッドの observed ヒストグラムを計算する.

    Parameters
    ----------
    arrays : PopulationArrays
        人口配列。
    sex_id : int
        性別 ID（0=M, 1=F）。
    bin_edges : np.ndarray
        ビン境界（年齢）。
    n_bins : int
        ビン数。

    Returns
    -------
    np.ndarray
        shape=(n_bins,) の observed カウント配列（int64）。
    """
    sex_mask = arrays.sex == sex_id
    ages = arrays.age[sex_mask].astype(np.int64)
    observed, _ = np.histogram(ages, bins=bin_edges)
    return observed.astype(np.int64)


# ---------------------------------------------------------------------------
# family_type 別 demographic pyramid (Issue #71)
# ---------------------------------------------------------------------------


def _build_family_type_pyramid_stat(
    rows: list[DemographicByFamilyTypeRoleRow],
    family_type: str,
    sex_label: str,
    arrays: PopulationArrays,
) -> StatTable:
    """family_type × sex 別の demographic pyramid 統計を構築する.

    target は ``demographic_by_family_type_role.csv`` を ``(family_type, sex, age)``
    で集計（role を集約）した値。observed は合成集団の (family_type, sex) 別 age 分布。

    Parameters
    ----------
    rows : list[DemographicByFamilyTypeRoleRow]
        ``demographic_by_family_type_role.csv`` から読んだ全行。
    family_type : str
        対象の family_type 名。
    sex_label : str
        ``"M"`` または ``"F"``。
    arrays : PopulationArrays
        合成集団の人口配列。

    Returns
    -------
    StatTable
        observed と target が初期化された統計テーブル。target に該当 age が無い
        family_type/sex でも空の StatTable（target 全 0、bin_edges は age 0..100）を返す。
    """
    # 該当 family_type × sex の rows を age 別に集約（role を sum）
    matched = [r for r in rows if r.family_type == family_type and r.sex == sex_label]
    age_to_count: dict[int, int] = {}
    for r in matched:
        age_to_count[r.age] = age_to_count.get(r.age, 0) + r.count

    # bin_edges は age 0..100 の固定 (101 bins)。target に無い age は 0 として扱う。
    # observed が target 範囲外で捨てられないように 0..100 を網羅する。
    bin_edges = np.arange(0, 102, dtype=np.float64)
    target = np.zeros(101, dtype=np.int64)
    for age, count in age_to_count.items():
        if 0 <= age <= 100:
            target[age] = count

    family_type_id = arrays.family_reg.id_of(family_type)
    sex_id = arrays.sex_reg.id_of(sex_label)
    n_bins = len(bin_edges) - 1
    observed = _compute_family_type_pyramid_observed(
        arrays, family_type_id, sex_id, bin_edges, n_bins
    )
    return StatTable(observed=observed, target=target, bin_edges=bin_edges)


def _compute_family_type_pyramid_observed(
    arrays: PopulationArrays,
    family_type_id: int,
    sex_id: int,
    bin_edges: np.ndarray,
    n_bins: int,
) -> np.ndarray:
    """family_type × sex の observed pyramid を計算する."""
    mask = (arrays.family_type == family_type_id) & (arrays.sex == sex_id)
    ages = arrays.age[mask].astype(np.int64)
    observed, _ = np.histogram(ages, bins=bin_edges)
    return observed.astype(np.int64)


def family_type_pyramid_index(offset: int, family_type_id: int, sex_id: int, n_sex: int = 2) -> int:
    """family_type × sex から ``stats`` リストのインデックスを計算する."""
    return offset + family_type_id * n_sex + sex_id


# ---------------------------------------------------------------------------
# build_objective_stats: 5 統計 (+ optional family_type pyramid) の構築
# ---------------------------------------------------------------------------


def build_objective_stats(
    arrays: PopulationArrays,
    age_diff_parent_child: list[AgeDiffParentChildRow],
    age_diff_couple: list[AgeDiffCoupleRow],
    demographic_by_age_sex: list[DemographicByAgeSexRow],
    *,
    demo_ft_role: list[DemographicByFamilyTypeRoleRow] | None = None,
    use_family_type_pyramid: bool = False,
) -> list[StatTable]:
    """5 統計（+ optional family_type × sex pyramid）を構築する.

    返り値のインデックス:
    - 0: father-child 年齢差
    - 1: mother-child 年齢差
    - 2: couple 年齢差（husband - wife）
    - 3: male demographic pyramid
    - 4: female demographic pyramid
    - 5..5 + 2N - 1: ``use_family_type_pyramid=True`` のとき
      ``family_type_id * 2 + sex_id`` 順で family_type × sex pyramid

    Parameters
    ----------
    arrays : PopulationArrays
        初期人口配列。
    age_diff_parent_child : list[AgeDiffParentChildRow]
        age_diff_parent_child.csv から読んだ全行。
    age_diff_couple : list[AgeDiffCoupleRow]
        age_diff_couple.csv から読んだ全行。
    demographic_by_age_sex : list[DemographicByAgeSexRow]
        demographic_by_age_sex.csv から読んだ全行。
    demo_ft_role : list[DemographicByFamilyTypeRoleRow] | None
        ``demographic_by_family_type_role.csv`` の全行。
        ``use_family_type_pyramid=True`` のとき必須。
    use_family_type_pyramid : bool
        True で family_type × sex pyramid 統計を末尾に追加する（Issue #71）。

    Returns
    -------
    list[StatTable]
        長さ 5（拡張オフ時）または 5 + 2N（拡張オン時）。
    """
    base = [
        _build_parent_child_stat(age_diff_parent_child, "father", arrays),
        _build_parent_child_stat(age_diff_parent_child, "mother", arrays),
        _build_couple_stat(age_diff_couple, arrays),
        _build_pyramid_stat(demographic_by_age_sex, "M", arrays),
        _build_pyramid_stat(demographic_by_age_sex, "F", arrays),
    ]
    if not use_family_type_pyramid:
        return base

    if demo_ft_role is None:
        msg = "use_family_type_pyramid=True のとき demo_ft_role を渡す必要があります"
        raise ValueError(msg)

    # family_type は登録 ID 順で列挙する。stats[offset + ft_id*2 + sex_id] で
    # 正しいインデックスを引けるよう、set ベースの順序非決定性を避ける（Issue #71）。
    n_ft = len(arrays.family_reg)
    extended: list[StatTable] = []
    for ft_id in range(n_ft):
        ft = arrays.family_reg.name_of(ft_id)
        for sex in ("M", "F"):
            extended.append(_build_family_type_pyramid_stat(demo_ft_role, ft, sex, arrays))
    return base + extended


# ---------------------------------------------------------------------------
# ObjectiveState
# ---------------------------------------------------------------------------


@dataclass
class ObjectiveState:
    """差分更新版目的関数の状態コンテナ.

    SA の内部ループで 1 人の age が変わるとき、
    5 統計（+ optional family_type × sex pyramid）のヒストグラムを O(1) で
    差分更新しながら total_score を維持する。

    Attributes
    ----------
    arrays : PopulationArrays
        人口配列への参照（コピーしない）。
    stats : list[StatTable]
        StatTable リスト。インデックスの意味は ``build_objective_stats`` 参照。
        family_type pyramid 拡張オンのとき長さは 5 + 2N。
    total_score : float
        現在の目的スコア = Σ_s L1(stats[s])。
    family_type_pyramid_offset : int | None
        ``stats`` における family_type × sex pyramid の開始インデックス。
        拡張オフ時は ``None``（Issue #71）。
    n_family_types : int
        family_type pyramid の対象 family_type 数（拡張オフ時は 0）。
    """

    arrays: PopulationArrays
    stats: list[StatTable]
    total_score: float
    family_type_pyramid_offset: int | None = None
    n_family_types: int = 0

    @classmethod
    def from_arrays(
        cls,
        arrays: PopulationArrays,
        age_diff_parent_child: list[AgeDiffParentChildRow],
        age_diff_couple: list[AgeDiffCoupleRow],
        demographic_by_age_sex: list[DemographicByAgeSexRow],
        *,
        demo_ft_role: list[DemographicByFamilyTypeRoleRow] | None = None,
        use_family_type_pyramid: bool = False,
    ) -> ObjectiveState:
        """PopulationArrays と統計テーブルから ObjectiveState を構築する.

        Parameters
        ----------
        arrays : PopulationArrays
            初期人口配列（参照として保持。コピーしない）。
        age_diff_parent_child : list[AgeDiffParentChildRow]
            age_diff_parent_child.csv から読んだ全行。
        age_diff_couple : list[AgeDiffCoupleRow]
            age_diff_couple.csv から読んだ全行。
        demographic_by_age_sex : list[DemographicByAgeSexRow]
            demographic_by_age_sex.csv から読んだ全行。
        demo_ft_role : list[DemographicByFamilyTypeRoleRow] | None
            ``demographic_by_family_type_role.csv`` の全行。
            ``use_family_type_pyramid=True`` のとき必須。
        use_family_type_pyramid : bool
            True で family_type × sex pyramid を追加する（Issue #71）。

        Returns
        -------
        ObjectiveState
            初期化済みの ObjectiveState。total_score は全統計の L1 合計。
        """
        stats = build_objective_stats(
            arrays=arrays,
            age_diff_parent_child=age_diff_parent_child,
            age_diff_couple=age_diff_couple,
            demographic_by_age_sex=demographic_by_age_sex,
            demo_ft_role=demo_ft_role,
            use_family_type_pyramid=use_family_type_pyramid,
        )
        total_score = sum(s.l1_score() for s in stats)
        if use_family_type_pyramid:
            offset: int | None = 5
            n_ft = len(arrays.family_reg)
        else:
            offset = None
            n_ft = 0
        return cls(
            arrays=arrays,
            stats=stats,
            total_score=total_score,
            family_type_pyramid_offset=offset,
            n_family_types=n_ft,
        )

    # -----------------------------------------------------------------------
    # 差分更新
    # -----------------------------------------------------------------------

    def _compute_delta_for_change(self, person_idx: int, new_age: int) -> float:
        """person_idx の age を new_age に変えたときのスコア差分を計算する（副作用なし）.

        各統計に対して「old_age の寄与を除き、new_age の寄与を加えた」後の
        L1 変化量を計算する。

        Parameters
        ----------
        person_idx : int
            変更対象の person の index。
        new_age : int
            変更後の age。

        Returns
        -------
        float
            スコア差分 (new_score - old_score)。負なら改善、正なら悪化。
        """
        old_age = int(self.arrays.age[person_idx])
        if old_age == new_age:
            return 0.0

        delta = 0.0

        # --- stats[3]: male pyramid, stats[4]: female pyramid ---
        sex_id = int(self.arrays.sex[person_idx])
        # sex_id=0 → stats[3], sex_id=1 → stats[4]
        pyramid_idx = 3 + sex_id
        pyramid_stat = self.stats[pyramid_idx]
        delta += _delta_pyramid(pyramid_stat, old_age, new_age)

        # --- family_type × sex pyramid (Issue #71、拡張オン時のみ) ---
        if self.family_type_pyramid_offset is not None:
            ft_id = int(self.arrays.family_type[person_idx])
            ft_pyramid_idx = family_type_pyramid_index(
                self.family_type_pyramid_offset, ft_id, sex_id
            )
            ft_pyramid_stat = self.stats[ft_pyramid_idx]
            delta += _delta_pyramid(ft_pyramid_stat, old_age, new_age)

        # --- stats[0]: father-child, stats[1]: mother-child ---
        role_id = int(self.arrays.role[person_idx])
        role_name = self.arrays.role_reg.name_of(role_id)
        hid = int(self.arrays.household_id[person_idx])

        if role_name in ("father", "mother"):
            stat_idx = 0 if role_name == "father" else 1
            stat = self.stats[stat_idx]
            try:
                child_role_id = self.arrays.role_reg.id_of("child")
                child_mask = (self.arrays.household_id == hid) & (self.arrays.role == child_role_id)
                child_ages = self.arrays.age[child_mask].astype(np.int64)
                delta += _delta_parent_child_diffs(stat, old_age, new_age, child_ages)
            except KeyError:
                pass

        elif role_name == "child":
            # child の age 変化 → 同世帯の father/mother の差分が変化
            try:
                father_role_id = self.arrays.role_reg.id_of("father")
                father_mask = (self.arrays.household_id == hid) & (
                    self.arrays.role == father_role_id
                )
                father_ages = self.arrays.age[father_mask].astype(np.int64)
                if np.any(father_mask):
                    delta += _delta_child_changes_parent_diff(
                        self.stats[0], old_age, new_age, father_ages
                    )
            except KeyError:
                pass

            try:
                mother_role_id = self.arrays.role_reg.id_of("mother")
                mother_mask = (self.arrays.household_id == hid) & (
                    self.arrays.role == mother_role_id
                )
                mother_ages = self.arrays.age[mother_mask].astype(np.int64)
                if np.any(mother_mask):
                    delta += _delta_child_changes_parent_diff(
                        self.stats[1], old_age, new_age, mother_ages
                    )
            except KeyError:
                pass

        elif role_name == "husband":
            # husband の age 変化 → couple 差分が変化
            try:
                wife_role_id = self.arrays.role_reg.id_of("wife")
                wife_mask = (self.arrays.household_id == hid) & (self.arrays.role == wife_role_id)
                wife_ages = self.arrays.age[wife_mask].astype(np.int64)
                if np.any(wife_mask):
                    delta += _delta_husband_age_changes_couple(
                        self.stats[2], old_age, new_age, wife_ages
                    )
            except KeyError:
                pass

        elif role_name == "wife":
            # wife の age 変化 → couple 差分が変化（diff = husband - wife なので符号逆）
            try:
                husband_role_id = self.arrays.role_reg.id_of("husband")
                husband_mask = (self.arrays.household_id == hid) & (
                    self.arrays.role == husband_role_id
                )
                husband_ages = self.arrays.age[husband_mask].astype(np.int64)
                if np.any(husband_mask):
                    delta += _delta_wife_age_changes_couple(
                        self.stats[2], old_age, new_age, husband_ages
                    )
            except KeyError:
                pass

        return delta

    def propose_change(self, person_idx: int, new_age: int) -> float:
        """Age 変更の差分スコアを副作用なしで計算する.

        Parameters
        ----------
        person_idx : int
            変更対象の person の index（0-indexed）。
        new_age : int
            変更後の age（0 以上）。

        Returns
        -------
        float
            スコア差分 (new_score - old_score)。
            負なら改善、正なら悪化、0 なら変化なし。
        """
        return self._compute_delta_for_change(person_idx, new_age)

    def apply_change(self, person_idx: int, new_age: int) -> None:
        """Age 変更を内部状態に適用する.

        observed ヒストグラムと total_score を更新し、
        arrays.age[person_idx] を new_age に書き換える。

        Parameters
        ----------
        person_idx : int
            変更対象の person の index（0-indexed）。
        new_age : int
            変更後の age（0 以上）。
        """
        old_age = int(self.arrays.age[person_idx])
        if old_age == new_age:
            return

        # スコア差分を計算してから状態を更新
        delta = self._compute_delta_for_change(person_idx, new_age)

        # ヒストグラムを実更新
        self._update_histograms(person_idx, old_age, new_age)

        # arrays.age を更新
        self.arrays.age[person_idx] = np.int16(new_age)

        # total_score を更新
        self.total_score += delta

    def propose_swap(self, idx_a: int, new_age_a: int, idx_b: int, new_age_b: int) -> float:
        """Age swap の合算 delta スコアを副作用なしで計算する.

        Issue #57 / §12.2B age-swap 用。実装は ``apply_change(idx_a)`` →
        ``propose_change(idx_b)`` → ``apply_change(idx_a, old)`` で revert することで
        side-effect-free を保ちつつ atomic な合算 delta を得る。

        Parameters
        ----------
        idx_a, idx_b : int
            交換対象の 2 人の person index（0-indexed）。同じ index を渡した場合は 0.0 を返す。
        new_age_a, new_age_b : int
            交換後の age（age-swap では ``new_age_a == old_age_b``、``new_age_b == old_age_a``）。

        Returns
        -------
        float
            合算スコア差分（``apply_swap`` 後の total_score 変化と一致）。
        """
        if idx_a == idx_b:
            return 0.0

        score_initial = self.total_score
        old_age_a = int(self.arrays.age[idx_a])

        # A を適用して中間状態を作る
        self.apply_change(idx_a, new_age_a)
        delta_a = self.total_score - score_initial

        # B の delta を中間状態（A 適用後）に対して計算
        delta_b = self._compute_delta_for_change(idx_b, new_age_b)

        # A を revert（apply_change で元の age に戻す）
        self.apply_change(idx_a, old_age_a)

        return delta_a + delta_b

    def apply_swap(self, idx_a: int, new_age_a: int, idx_b: int, new_age_b: int) -> None:
        """Age swap を atomic に内部状態へ適用する.

        Issue #57 / §12.2B age-swap 用。``apply_change(idx_a)`` → ``apply_change(idx_b)``
        の順で適用し、最終的な ``total_score`` と histograms を整合状態に保つ。

        Parameters
        ----------
        idx_a, idx_b : int
            交換対象の 2 人の person index。同じ index を渡した場合は何もしない。
        new_age_a, new_age_b : int
            交換後の age。
        """
        if idx_a == idx_b:
            return
        self.apply_change(idx_a, new_age_a)
        self.apply_change(idx_b, new_age_b)

    def _update_histograms(self, person_idx: int, old_age: int, new_age: int) -> None:
        """Observed ヒストグラムを差分更新する（arrays.age は更新前）.

        Parameters
        ----------
        person_idx : int
            変更対象の person の index。
        old_age : int
            変更前の age。
        new_age : int
            変更後の age。
        """
        sex_id = int(self.arrays.sex[person_idx])
        pyramid_idx = 3 + sex_id
        pyramid_stat = self.stats[pyramid_idx]
        _apply_pyramid_update(pyramid_stat, old_age, new_age)

        # family_type × sex pyramid (Issue #71)
        if self.family_type_pyramid_offset is not None:
            ft_id = int(self.arrays.family_type[person_idx])
            ft_pyramid_idx = family_type_pyramid_index(
                self.family_type_pyramid_offset, ft_id, sex_id
            )
            _apply_pyramid_update(self.stats[ft_pyramid_idx], old_age, new_age)

        role_id = int(self.arrays.role[person_idx])
        role_name = self.arrays.role_reg.name_of(role_id)
        hid = int(self.arrays.household_id[person_idx])

        if role_name in ("father", "mother"):
            stat_idx = 0 if role_name == "father" else 1
            stat = self.stats[stat_idx]
            try:
                child_role_id = self.arrays.role_reg.id_of("child")
                child_mask = (self.arrays.household_id == hid) & (self.arrays.role == child_role_id)
                child_ages = self.arrays.age[child_mask].astype(np.int64)
                _apply_parent_child_update(stat, old_age, new_age, child_ages)
            except KeyError:
                pass

        elif role_name == "child":
            try:
                father_role_id = self.arrays.role_reg.id_of("father")
                father_mask = (self.arrays.household_id == hid) & (
                    self.arrays.role == father_role_id
                )
                father_ages = self.arrays.age[father_mask].astype(np.int64)
                if np.any(father_mask):
                    _apply_child_parent_diff_update(self.stats[0], old_age, new_age, father_ages)
            except KeyError:
                pass

            try:
                mother_role_id = self.arrays.role_reg.id_of("mother")
                mother_mask = (self.arrays.household_id == hid) & (
                    self.arrays.role == mother_role_id
                )
                mother_ages = self.arrays.age[mother_mask].astype(np.int64)
                if np.any(mother_mask):
                    _apply_child_parent_diff_update(self.stats[1], old_age, new_age, mother_ages)
            except KeyError:
                pass

        elif role_name == "husband":
            try:
                wife_role_id = self.arrays.role_reg.id_of("wife")
                wife_mask = (self.arrays.household_id == hid) & (self.arrays.role == wife_role_id)
                wife_ages = self.arrays.age[wife_mask].astype(np.int64)
                if np.any(wife_mask):
                    _apply_husband_couple_update(self.stats[2], old_age, new_age, wife_ages)
            except KeyError:
                pass

        elif role_name == "wife":
            try:
                husband_role_id = self.arrays.role_reg.id_of("husband")
                husband_mask = (self.arrays.household_id == hid) & (
                    self.arrays.role == husband_role_id
                )
                husband_ages = self.arrays.age[husband_mask].astype(np.int64)
                if np.any(husband_mask):
                    _apply_wife_couple_update(self.stats[2], old_age, new_age, husband_ages)
            except KeyError:
                pass


# ---------------------------------------------------------------------------
# 差分計算ヘルパー（副作用なし）
# ---------------------------------------------------------------------------


def _delta_pyramid(stat: StatTable, old_age: int, new_age: int) -> float:
    """Pyramid 統計の L1 変化量を計算する（副作用なし）.

    old_age → new_age の変化で observed[old_bin] -= 1, observed[new_bin] += 1 が起きる。

    Parameters
    ----------
    stat : StatTable
        pyramid 統計テーブル。
    old_age : int
        変更前の age。
    new_age : int
        変更後の age。

    Returns
    -------
    float
        スコア変化量 Δ（新スコア - 旧スコア）。
    """
    n_bins = len(stat.observed)
    old_bin = _bin_index(stat.bin_edges, float(old_age))
    new_bin = _bin_index(stat.bin_edges, float(new_age))

    if old_bin == new_bin:
        return 0.0

    delta = 0.0

    # old_bin: observed が 1 減る
    if 0 <= old_bin < n_bins:
        obs = int(stat.observed[old_bin])
        tgt = int(stat.target[old_bin])
        old_contrib = abs(obs - tgt)
        new_contrib = abs((obs - 1) - tgt)
        delta += new_contrib - old_contrib

    # new_bin: observed が 1 増える
    if 0 <= new_bin < n_bins:
        obs = int(stat.observed[new_bin])
        tgt = int(stat.target[new_bin])
        old_contrib = abs(obs - tgt)
        new_contrib = abs((obs + 1) - tgt)
        delta += new_contrib - old_contrib

    return delta


def _delta_parent_child_diffs(
    stat: StatTable,
    parent_old_age: int,
    parent_new_age: int,
    child_ages: np.ndarray,
) -> float:
    """親の age 変化による親子差分統計の L1 変化量を計算する（副作用なし）.

    Parameters
    ----------
    stat : StatTable
        親子差分統計テーブル。
    parent_old_age : int
        親の変更前 age。
    parent_new_age : int
        親の変更後 age。
    child_ages : np.ndarray
        同世帯の child の age 配列。

    Returns
    -------
    float
        スコア変化量 Δ。
    """
    if len(child_ages) == 0:
        return 0.0

    n_bins = len(stat.observed)
    delta = 0.0

    # 一時 observed を作成してデルタを計算
    temp_observed = stat.observed.copy()

    for child_age in child_ages:
        old_diff = float(parent_old_age - int(child_age))
        new_diff = float(parent_new_age - int(child_age))

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            obs = int(temp_observed[old_bin])
            tgt = int(stat.target[old_bin])
            delta += abs((obs - 1) - tgt) - abs(obs - tgt)
            temp_observed[old_bin] -= 1

        if 0 <= new_bin < n_bins:
            obs = int(temp_observed[new_bin])
            tgt = int(stat.target[new_bin])
            delta += abs((obs + 1) - tgt) - abs(obs - tgt)
            temp_observed[new_bin] += 1

    return delta


def _delta_child_changes_parent_diff(
    stat: StatTable,
    child_old_age: int,
    child_new_age: int,
    parent_ages: np.ndarray,
) -> float:
    """Child の age 変化による親子差分統計の L1 変化量を計算する（副作用なし）.

    diff = parent_age - child_age なので、child_age が上がると diff が下がる。

    Parameters
    ----------
    stat : StatTable
        親子差分統計テーブル。
    child_old_age : int
        child の変更前 age。
    child_new_age : int
        child の変更後 age。
    parent_ages : np.ndarray
        同世帯の親（father または mother）の age 配列。

    Returns
    -------
    float
        スコア変化量 Δ。
    """
    if len(parent_ages) == 0:
        return 0.0

    n_bins = len(stat.observed)
    delta = 0.0
    temp_observed = stat.observed.copy()

    for parent_age in parent_ages:
        old_diff = float(int(parent_age) - child_old_age)
        new_diff = float(int(parent_age) - child_new_age)

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            obs = int(temp_observed[old_bin])
            tgt = int(stat.target[old_bin])
            delta += abs((obs - 1) - tgt) - abs(obs - tgt)
            temp_observed[old_bin] -= 1

        if 0 <= new_bin < n_bins:
            obs = int(temp_observed[new_bin])
            tgt = int(stat.target[new_bin])
            delta += abs((obs + 1) - tgt) - abs(obs - tgt)
            temp_observed[new_bin] += 1

    return delta


def _delta_husband_age_changes_couple(
    stat: StatTable,
    husband_old_age: int,
    husband_new_age: int,
    wife_ages: np.ndarray,
) -> float:
    """Husband の age 変化による couple 差分統計の L1 変化量を計算する（副作用なし）.

    diff = husband_age - wife_age

    Parameters
    ----------
    stat : StatTable
        couple 差分統計テーブル。
    husband_old_age : int
        夫の変更前 age。
    husband_new_age : int
        夫の変更後 age。
    wife_ages : np.ndarray
        同世帯の妻の age 配列。

    Returns
    -------
    float
        スコア変化量 Δ。
    """
    if len(wife_ages) == 0:
        return 0.0

    n_bins = len(stat.observed)
    delta = 0.0
    temp_observed = stat.observed.copy()

    for wife_age in wife_ages:
        old_diff = float(husband_old_age - int(wife_age))
        new_diff = float(husband_new_age - int(wife_age))

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            obs = int(temp_observed[old_bin])
            tgt = int(stat.target[old_bin])
            delta += abs((obs - 1) - tgt) - abs(obs - tgt)
            temp_observed[old_bin] -= 1

        if 0 <= new_bin < n_bins:
            obs = int(temp_observed[new_bin])
            tgt = int(stat.target[new_bin])
            delta += abs((obs + 1) - tgt) - abs(obs - tgt)
            temp_observed[new_bin] += 1

    return delta


def _delta_wife_age_changes_couple(
    stat: StatTable,
    wife_old_age: int,
    wife_new_age: int,
    husband_ages: np.ndarray,
) -> float:
    """Wife の age 変化による couple 差分統計の L1 変化量を計算する（副作用なし）.

    diff = husband_age - wife_age なので wife_age が上がると diff が下がる。

    Parameters
    ----------
    stat : StatTable
        couple 差分統計テーブル。
    wife_old_age : int
        妻の変更前 age。
    wife_new_age : int
        妻の変更後 age。
    husband_ages : np.ndarray
        同世帯の夫の age 配列。

    Returns
    -------
    float
        スコア変化量 Δ。
    """
    if len(husband_ages) == 0:
        return 0.0

    n_bins = len(stat.observed)
    delta = 0.0
    temp_observed = stat.observed.copy()

    for husband_age in husband_ages:
        old_diff = float(int(husband_age) - wife_old_age)
        new_diff = float(int(husband_age) - wife_new_age)

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            obs = int(temp_observed[old_bin])
            tgt = int(stat.target[old_bin])
            delta += abs((obs - 1) - tgt) - abs(obs - tgt)
            temp_observed[old_bin] -= 1

        if 0 <= new_bin < n_bins:
            obs = int(temp_observed[new_bin])
            tgt = int(stat.target[new_bin])
            delta += abs((obs + 1) - tgt) - abs(obs - tgt)
            temp_observed[new_bin] += 1

    return delta


# ---------------------------------------------------------------------------
# ヒストグラム実更新ヘルパー（apply_change 用）
# ---------------------------------------------------------------------------


def _apply_pyramid_update(stat: StatTable, old_age: int, new_age: int) -> None:
    """Pyramid 統計の observed ヒストグラムを実更新する.

    Parameters
    ----------
    stat : StatTable
        pyramid 統計テーブル（インプレース更新）。
    old_age : int
        変更前の age。
    new_age : int
        変更後の age。
    """
    n_bins = len(stat.observed)
    old_bin = _bin_index(stat.bin_edges, float(old_age))
    new_bin = _bin_index(stat.bin_edges, float(new_age))

    if old_bin == new_bin:
        return

    if 0 <= old_bin < n_bins:
        stat.observed[old_bin] -= 1
    if 0 <= new_bin < n_bins:
        stat.observed[new_bin] += 1


def _apply_parent_child_update(
    stat: StatTable,
    parent_old_age: int,
    parent_new_age: int,
    child_ages: np.ndarray,
) -> None:
    """親子差分統計の observed を実更新する（親の age 変化）.

    Parameters
    ----------
    stat : StatTable
        親子差分統計テーブル（インプレース更新）。
    parent_old_age : int
        親の変更前 age。
    parent_new_age : int
        親の変更後 age。
    child_ages : np.ndarray
        同世帯の child age 配列。
    """
    n_bins = len(stat.observed)
    for child_age in child_ages:
        old_diff = float(parent_old_age - int(child_age))
        new_diff = float(parent_new_age - int(child_age))

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            stat.observed[old_bin] -= 1
        if 0 <= new_bin < n_bins:
            stat.observed[new_bin] += 1


def _apply_child_parent_diff_update(
    stat: StatTable,
    child_old_age: int,
    child_new_age: int,
    parent_ages: np.ndarray,
) -> None:
    """親子差分統計の observed を実更新する（child の age 変化）.

    Parameters
    ----------
    stat : StatTable
        親子差分統計テーブル（インプレース更新）。
    child_old_age : int
        child の変更前 age。
    child_new_age : int
        child の変更後 age。
    parent_ages : np.ndarray
        同世帯の親（father または mother）の age 配列。
    """
    n_bins = len(stat.observed)
    for parent_age in parent_ages:
        old_diff = float(int(parent_age) - child_old_age)
        new_diff = float(int(parent_age) - child_new_age)

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            stat.observed[old_bin] -= 1
        if 0 <= new_bin < n_bins:
            stat.observed[new_bin] += 1


def _apply_husband_couple_update(
    stat: StatTable,
    husband_old_age: int,
    husband_new_age: int,
    wife_ages: np.ndarray,
) -> None:
    """Couple 差分統計の observed を実更新する（husband の age 変化）.

    Parameters
    ----------
    stat : StatTable
        couple 差分統計テーブル（インプレース更新）。
    husband_old_age : int
        夫の変更前 age。
    husband_new_age : int
        夫の変更後 age。
    wife_ages : np.ndarray
        同世帯の妻の age 配列。
    """
    n_bins = len(stat.observed)
    for wife_age in wife_ages:
        old_diff = float(husband_old_age - int(wife_age))
        new_diff = float(husband_new_age - int(wife_age))

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            stat.observed[old_bin] -= 1
        if 0 <= new_bin < n_bins:
            stat.observed[new_bin] += 1


def _apply_wife_couple_update(
    stat: StatTable,
    wife_old_age: int,
    wife_new_age: int,
    husband_ages: np.ndarray,
) -> None:
    """Couple 差分統計の observed を実更新する（wife の age 変化）.

    Parameters
    ----------
    stat : StatTable
        couple 差分統計テーブル（インプレース更新）。
    wife_old_age : int
        妻の変更前 age。
    wife_new_age : int
        妻の変更後 age。
    husband_ages : np.ndarray
        同世帯の夫の age 配列。
    """
    n_bins = len(stat.observed)
    for husband_age in husband_ages:
        old_diff = float(int(husband_age) - wife_old_age)
        new_diff = float(int(husband_age) - wife_new_age)

        old_bin = _bin_index(stat.bin_edges, old_diff)
        new_bin = _bin_index(stat.bin_edges, new_diff)

        if old_bin == new_bin:
            continue

        if 0 <= old_bin < n_bins:
            stat.observed[old_bin] -= 1
        if 0 <= new_bin < n_bins:
            stat.observed[new_bin] += 1
